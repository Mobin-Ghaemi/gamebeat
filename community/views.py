from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q, Count
from django.views.decorators.http import require_POST
from .models import GamerProfile, Post, PostLike, Comment, Follow, FollowRequest, LFGPost, LFGJoinRequest, Achievement, GamingAccount, Hashtag
from .models import Notification, Conversation, Message, Block, PinnedConversation, MutedConversation
from .models import GameBacklog, PostReaction
from .models import ActivityLog, Challenge, Club, ClubMember, ClubPost
from .models import GroupChat, GroupMember, GroupMessage, PinnedGroupChat, MutedGroupChat
from .models import Channel, ChannelMember, ChannelPost, ChannelReaction, PinnedChannel, MutedChannel
from .models import PLATFORM_CHOICES, CITY_CHOICES, ScoreSettings, UserSession
from .models import SpinWheel, SpinWheelItem, SpinRecord
from .models import ZarbanWallet, ZarbanTransaction
from .models import ProfileView, PremiumPlan
from django.utils import timezone
import re
import json
import urllib.request
import urllib.parse
import jdatetime


def _to_jalali(dt, fmt='%Y/%m/%d'):
    """تبدیل datetime میلادی به شمسی با اعداد فارسی"""
    _pd = str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹')
    if timezone.is_aware(dt):
        dt = timezone.localtime(dt)
    jdt = jdatetime.datetime.fromgregorian(datetime=dt)
    return jdt.strftime(fmt).translate(_pd)


def get_or_create_gamer_profile(user):
    profile, _ = GamerProfile.objects.get_or_create(user=user)
    return profile


def extract_and_save_hashtags(post):
    """Extract #hashtags from post content, save to DB, update counts"""
    tags = set(re.findall(r'#([a-zA-Z؀-ۿ\w]{2,50})', post.content))
    post.hashtags.clear()
    for tag_name in tags:
        tag_name_lower = tag_name.lower()
        hashtag, created = Hashtag.objects.get_or_create(
            name=tag_name_lower,
            defaults={'is_approved': False},
        )
        hashtag.post_count = hashtag.posts.count()
        hashtag.save()
        post.hashtags.add(hashtag)


def _record_profile_view(viewer, profile_user):
    """ثبت بازدید + نوتیف آنی
    - پریمیوم: نوتیف فوری با اسم واقعی
    - غیرپریمیوم: نوتیف روزانه تجمیعی (فقط تعداد، بدون اسم)
    """
    from django.core.cache import cache
    from datetime import date
    cache_key = f'pv_{profile_user.id}_{viewer.id}'
    if cache.get(cache_key):
        return  # throttle ۶ ساعته
    ProfileView.objects.create(viewer=viewer, viewed_user=profile_user)
    cache.set(cache_key, True, 60 * 60 * 6)

    profile = get_or_create_gamer_profile(profile_user)

    # همه کاربران (پریمیوم و غیرپریمیوم) همین نوتیف را می‌گیرند
    # پریمیوم: اسم بازدیدکننده نشان داده می‌شود
    # غیرپریمیوم: فقط متن عمومی (اسم مخفی)
    if profile.is_premium:
        Notification.objects.create(
            recipient=profile_user,
            sender=viewer,
            notif_type='profile_view',
            custom_text='👁️ یک نفر پروفایل تو رو دید',
        )
    else:
        # نوتیف تجمیعی روزانه — فقط یک نوتیف در روز، آپدیت می‌شود
        today = date.today()
        existing = Notification.objects.filter(
            recipient=profile_user,
            notif_type='view_digest',
            created_at__date=today,
        ).first()
        if existing:
            existing.sender = viewer
            existing.custom_text = '👁️ یک نفر پروفایل تو رو دید'
            existing.is_read = False
            existing.save(update_fields=['custom_text', 'sender', 'is_read'])
        else:
            Notification.objects.create(
                recipient=profile_user,
                sender=viewer,
                notif_type='view_digest',
                custom_text='👁️ یک نفر پروفایل تو رو دید',
            )


# نگه‌دار alias قدیمی برای سازگاری
def _send_profile_view_notif(viewer, profile_user):
    _record_profile_view(viewer, profile_user)


def _annotate_reactions(posts, user):
    """Attach my_reaction and reactions_summary to each post"""
    post_ids = [p.id for p in posts]
    # all reactions for these posts
    all_rxns = PostReaction.objects.filter(post_id__in=post_ids)
    my_rxns  = {r.post_id: r.reaction_type for r in all_rxns.filter(user=user)} if (user and user.is_authenticated) else {}
    # counts per post per type
    from collections import defaultdict
    counts = defaultdict(lambda: defaultdict(int))
    emoji_map = dict(PostReaction.REACTION_CHOICES)
    emoji_chars = {r[0]: PostReaction.REACTION_EMOJI[r[0]] for r in PostReaction.REACTION_CHOICES}
    for r in all_rxns:
        counts[r.post_id][r.reaction_type] += 1
    for p in posts:
        p.my_reaction = my_rxns.get(p.id, '')
        summary = {}
        for rtype, cnt in counts[p.id].items():
            summary[rtype] = {'emoji': emoji_chars[rtype], 'count': cnt, 'label': emoji_map[rtype]}
        p.reactions_summary = summary
    return posts


def _build_combined_feed(posts, lfg_list):
    combined, lfg_idx = [], 0
    insert_at = {2, 7}
    for i, p in enumerate(posts):
        if i in insert_at and lfg_idx < len(lfg_list):
            combined.append({'kind': 'lfg', 'obj': lfg_list[lfg_idx]})
            lfg_idx += 1
        combined.append({'kind': 'post', 'obj': p})
    while lfg_idx < len(lfg_list):
        combined.append({'kind': 'lfg', 'obj': lfg_list[lfg_idx]})
        lfg_idx += 1
    return combined


def feed(request):
    # Unauthenticated users see the same community feed with public posts
    if not request.user.is_authenticated:
        posts = list(Post.objects.filter(is_public=True)
                    .select_related('author', 'author__gamer_profile')
                    .prefetch_related('reactions', 'comments')
                    .order_by('-created_at')[:30])
        for p in posts:
            p.my_reaction = ''
            p.reactions_summary = {}

        # یوزر رسمی گیم‌بیت (admin) همیشه آخرین نفر — ۴ تای اول پرفالوورترین گیمرها
        GAMEBEAT_OFFICIAL = 'admin'
        gamebeat_user = User.objects.filter(username=GAMEBEAT_OFFICIAL, gamer_profile__isnull=False).first()
        exclude_ids = [gamebeat_user.id] if gamebeat_user else []

        top_gamers = list(User.objects.filter(
            gamer_profile__isnull=False
        ).exclude(
            id__in=exclude_ids
        ).annotate(
            followers_count=Count('followers_set')
        ).order_by('-followers_count')[:4])

        suggested_gamers = top_gamers
        if gamebeat_user:
            gamebeat_user.followers_count = Follow.objects.filter(following=gamebeat_user).count()
            suggested_gamers = top_gamers + [gamebeat_user]

        stats = {
            'users': User.objects.count(),
            'posts': Post.objects.filter(is_public=True).count(),
        }

        return render(request, 'community/feed.html', {
            'posts': posts,
            'combined_feed': [{'kind': 'post', 'obj': p} for p in posts],
            'liked_post_ids': set(),
            'my_profile': None,
            'suggested_gamers': suggested_gamers,
            'stats': stats,
        })

    my_profile = get_or_create_gamer_profile(request.user)
    following_ids = list(Follow.objects.filter(follower=request.user).values_list('following_id', flat=True))

    posts = list(Post.objects.filter(
        Q(author__in=following_ids) | Q(author=request.user),
        is_public=True
    ).select_related('author', 'author__gamer_profile').prefetch_related('likes', 'comments', 'reactions').order_by('-created_at')[:50])

    # ── Discover mode: no follows yet → show popular posts ──────────────────
    is_discover = len(posts) == 0 and len(following_ids) == 0
    if is_discover:
        # Top users by follower count (excluding self)
        popular_users = User.objects.exclude(
            id=request.user.id
        ).filter(
            gamer_profile__isnull=False
        ).annotate(
            fc=Count('followers_set')
        ).order_by('-fc')[:10]

        popular_ids = [u.id for u in popular_users]
        posts = list(Post.objects.filter(
            author__in=popular_ids, is_public=True
        ).select_related('author', 'author__gamer_profile')
         .prefetch_related('likes', 'comments', 'reactions')
         .order_by('-created_at')[:30])

    # ── بوست‌شده‌های فعال رو بالای فید بیار ──
    now = timezone.now()
    boosted = [p for p in posts if p.is_boosted and p.boost_expires_at and p.boost_expires_at > now]
    normal  = [p for p in posts if not (p.is_boosted and p.boost_expires_at and p.boost_expires_at > now)]
    posts   = boosted + normal

    _annotate_reactions(posts, request.user)
    liked_post_ids = set(PostLike.objects.filter(user=request.user).values_list('post_id', flat=True))

    # یوزر رسمی گیم‌بیت (admin) همیشه آخرین نفر — ۴ تای اول پرفالوورترین گیمرها
    GAMEBEAT_OFFICIAL = 'admin'
    gamebeat_user = User.objects.filter(username=GAMEBEAT_OFFICIAL, gamer_profile__isnull=False).first()
    exclude_ids = [request.user.id]
    if gamebeat_user:
        exclude_ids.append(gamebeat_user.id)

    top_gamers = list(User.objects.exclude(
        id__in=exclude_ids
    ).exclude(
        id__in=following_ids
    ).filter(
        gamer_profile__isnull=False
    ).annotate(
        followers_count=Count('followers_set')
    ).order_by('-followers_count')[:4])

    suggested_gamers = top_gamers
    if gamebeat_user and gamebeat_user.id != request.user.id:
        gamebeat_user.followers_count = Follow.objects.filter(following=gamebeat_user).count()
        suggested_gamers = top_gamers + [gamebeat_user]

    context = {
        'posts': posts,
        'combined_feed': [{'kind': 'post', 'obj': p} for p in posts],
        'liked_post_ids': liked_post_ids,
        'my_profile': my_profile,
        'suggested_gamers': suggested_gamers,
        'is_discover': is_discover,
    }
    return render(request, 'community/feed.html', context)


def gamer_profile(request, username):
    profile_user = get_object_or_404(User, username=username)
    profile = get_or_create_gamer_profile(profile_user)
    my_profile = get_or_create_gamer_profile(request.user) if request.user.is_authenticated else None

    is_own_profile = request.user == profile_user
    is_following = Follow.objects.filter(follower=request.user, following=profile_user).exists() if request.user.is_authenticated else False

    follow_request = None
    if not is_own_profile and request.user.is_authenticated:
        follow_request = FollowRequest.objects.filter(from_user=request.user, to_user=profile_user).first()

    # آپدیت آخرین بازدید کاربر لاگین‌شده
    from django.utils import timezone
    if request.user.is_authenticated:
        request.user.gamer_profile.last_seen = timezone.now()
        request.user.gamer_profile.save(update_fields=['last_seen'])

    # ثبت بازدید پروفایل — برای همه (پریمیوم نوتیف آنی، غیرپریمیوم digest شبانه)
    if request.user.is_authenticated and not is_own_profile:
        _record_profile_view(viewer=request.user, profile_user=profile_user)

    # پروفایل خصوصی — فقط صاحب پروفایل یا فالوورها می‌بینن
    if profile.is_private and not is_own_profile:
        if not is_following:
            return render(request, 'community/private_profile.html', {
                'profile_user': profile_user,
                'profile': profile,
                'is_following': is_following,
                'followers_count': profile.followers_count,
                'following_count': profile.following_count,
                'posts_count': profile.posts_count,
                'follow_request': follow_request,
            })

    posts = list(Post.objects.filter(author=profile_user, is_public=True)
                 .select_related('author', 'author__gamer_profile')
                 .prefetch_related('reactions')
                 .order_by('-created_at')[:30])
    _annotate_reactions(posts, request.user)
    liked_post_ids = set(PostLike.objects.filter(user=request.user).values_list('post_id', flat=True)) if request.user.is_authenticated else set()
    achievements = Achievement.objects.filter(user=profile_user)
    followers = Follow.objects.filter(following=profile_user).select_related('follower', 'follower__gamer_profile')[:12]
    following = Follow.objects.filter(follower=profile_user).select_related('following', 'following__gamer_profile')[:12]
    gaming_accounts = GamingAccount.objects.filter(user=profile_user)

    bl_cols = [
        ('want',      'می‌خوام بازی کنم', '#60a5fa', '🎯'),
        ('playing',   'دارم بازی می‌کنم',  '#4ade80', '🎮'),
        ('completed', 'تموم کردم',         '#fbbf24', '🏆'),
        ('dropped',   'رها کردم',           '#f87171', '💔'),
    ]

    # Gaming showcase: 1 query → split in Python (instead of 3 separate DB queries)
    all_backlog = list(GameBacklog.objects.filter(user=profile_user).order_by('game_name'))
    showcase_favorites = [b for b in all_backlog if b.is_favorite]
    showcase_playing   = sorted([b for b in all_backlog if b.status == 'playing'],
                                 key=lambda b: b.updated_at, reverse=True)
    showcase_completed = sorted([b for b in all_backlog if b.status == 'completed'],
                                 key=lambda b: (-(b.rating or 0), b.updated_at), reverse=False)[:20]

    completed_count = profile.completed_games_count
    fav_genre = profile.favorite_genre
    completed_games = [b for b in all_backlog if b.status == 'completed']

    # ── آنالیتیکس پریمیوم (فقط روی پروفایل خودت) ──
    analytics = None
    if is_own_profile and profile.is_premium:
        from datetime import timedelta
        from django.db.models.functions import TruncDate
        from django.db.models import Count
        import json as _json

        today = timezone.now().date()
        since_14 = today - timedelta(days=13)
        since_30 = today - timedelta(days=29)

        # ── بازدید ۱۴ روز — یک کوئری با GROUP BY ──
        view_qs = (
            ProfileView.objects
            .filter(viewed_user=profile_user, viewed_at__date__gte=since_14)
            .annotate(day=TruncDate('viewed_at'))
            .values('day')
            .annotate(cnt=Count('id'))
        )
        view_map = {row['day']: row['cnt'] for row in view_qs}

        # ── فالوور جدید روزانه ۱۴ روز — یک کوئری با GROUP BY ──
        follow_qs = (
            Follow.objects
            .filter(following=profile_user, created_at__date__gte=since_14)
            .annotate(day=TruncDate('created_at'))
            .values('day')
            .annotate(cnt=Count('id'))
        )
        follow_map = {row['day']: row['cnt'] for row in follow_qs}

        # ساخت آرایه ۱۴ روز با مقادیر صفر برای روزهای بدون داده
        labels, view_data, follow_data = [], [], []
        for i in range(13, -1, -1):
            d = today - timedelta(days=i)
            labels.append(jdatetime.date.fromgregorian(date=d).strftime('%m/%d').translate(str.maketrans('0123456789','۰۱۲۳۴۵۶۷۸۹')))
            view_data.append(view_map.get(d, 0))
            follow_data.append(follow_map.get(d, 0))

        analytics = {
            'view_labels':        _json.dumps(labels),
            'view_data':          _json.dumps(view_data),
            'follow_labels':      _json.dumps(labels),
            'follow_data':        _json.dumps(follow_data),
            'total_views_30d':    ProfileView.objects.filter(
                                      viewed_user=profile_user,
                                      viewed_at__date__gte=since_30,
                                  ).count(),
            'total_reactions_14d': PostReaction.objects.filter(
                                       post__author=profile_user,
                                       created_at__date__gte=since_14,
                                   ).count(),
            'followers_now':      Follow.objects.filter(following=profile_user).count(),
        }

    context = {
        'profile_user': profile_user,
        'profile': profile,
        'my_profile': my_profile,
        'is_following': is_following,
        'is_own_profile': is_own_profile,
        'posts': posts,
        'liked_post_ids': liked_post_ids,
        'achievements': achievements,
        'followers': followers,
        'following': following,
        'gaming_accounts': gaming_accounts,
        'bl_cols': bl_cols,
        'showcase_favorites': showcase_favorites,
        'showcase_playing': showcase_playing,
        'showcase_completed': showcase_completed,
        'user_platforms': profile.get_platforms_list(),
        'user_platform_labels': dict(PLATFORM_CHOICES),
        'follow_request': follow_request,
        'completed_count': completed_count,
        'fav_genre': fav_genre,
        'completed_games': completed_games,
        'analytics': analytics,
    }
    return render(request, 'community/profile.html', context)


@login_required
def user_settings(request):
    profile = request.user.gamer_profile
    if request.method == 'POST':
        profile.is_private     = 'is_private'     in request.POST
        profile.show_online    = 'show_online'     in request.POST
        profile.show_last_seen = 'show_last_seen'  in request.POST
        profile.show_email     = 'show_email'      in request.POST
        profile.allow_dm          = 'allow_dm'          in request.POST
        profile.dm_followers_only = 'dm_followers_only' in request.POST
        profile.show_backlog      = 'show_backlog'      in request.POST
        profile.show_stats     = 'show_stats'      in request.POST
        profile.show_location  = 'show_location'   in request.POST
        profile.show_on_map    = 'show_on_map'     in request.POST
        profile.save()
        return JsonResponse({'ok': True})
    return render(request, 'community/settings.html', {'profile': profile})


@login_required
@require_POST
def update_banner(request):
    """آپلود/حذف بنر پروفایل — AJAX"""
    try:
        profile = get_or_create_gamer_profile(request.user)

        if request.POST.get('remove') == '1':
            if profile.banner:
                profile.banner.delete(save=False)
                profile.banner = None
                profile.save(update_fields=['banner'])
            return JsonResponse({'ok': True, 'url': ''})

        if 'banner' not in request.FILES:
            return JsonResponse({'ok': False, 'error': 'فایلی ارسال نشد'}, status=400)

        f = request.FILES['banner']
        allowed = ('image/jpeg', 'image/png', 'image/webp', 'image/gif')
        if f.content_type not in allowed:
            return JsonResponse({'ok': False, 'error': 'فرمت فایل پشتیبانی نمیشه'}, status=400)
        if f.size > 5 * 1024 * 1024:
            return JsonResponse({'ok': False, 'error': 'حداکثر حجم ۵ مگابایت'}, status=400)

        import os
        ext = os.path.splitext(f.name)[1].lower() or '.jpg'
        fname = f'banner_{request.user.id}{ext}'
        profile.banner.save(fname, f, save=True)
        return JsonResponse({'ok': True, 'url': profile.banner.url})

    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@login_required
def edit_profile(request):
    profile = get_or_create_gamer_profile(request.user)

    if request.method == 'POST':
        request.user.first_name = request.POST.get('first_name', '')
        request.user.last_name  = request.POST.get('last_name', '')
        new_email = request.POST.get('email', '').strip()
        if new_email:
            request.user.email = new_email
        request.user.save()

        profile.bio = request.POST.get('bio', '')
        profile.city = request.POST.get('city', '')

        # location_label from province + city selects in edit profile
        loc_province = request.POST.get('location_province', '').strip()
        loc_city     = request.POST.get('location_city', '').strip()
        if loc_province or loc_city:
            profile.location_label = ' — '.join(filter(None, [loc_province, loc_city]))
            # وقتی آدرس ست میشه، به صورت خودکار در گیمر یابی نمایش داده می‌شه
            profile.show_location = True
            # set approximate coords from known city coords
            _CITY_COORDS = {
                'تهران':(35.694,51.421),'کرج':(35.835,50.999),'مشهد':(36.297,59.606),
                'اصفهان':(32.661,51.680),'شیراز':(29.591,52.584),'تبریز':(38.080,46.299),
                'اهواز':(31.319,48.671),'قم':(34.640,50.876),'کرمانشاه':(34.314,47.065),
                'رشت':(37.281,49.583),'ارومیه':(37.552,45.076),'زاهدان':(29.496,60.862),
                'همدان':(34.799,48.515),'اراک':(34.094,49.689),'یزد':(31.898,54.367),
                'اردبیل':(38.249,48.293),'بندر عباس':(27.189,56.276),'کرمان':(30.285,57.079),
                'زنجان':(36.679,48.496),'سنندج':(35.321,46.999),'خرم آباد':(33.488,48.355),
                'گرگان':(36.846,54.435),'ساری':(36.563,53.060),'بجنورد':(37.476,57.330),
                'بیرجند':(32.865,59.221),'ایلام':(33.636,46.422),'بوشهر':(28.968,50.838),
                'شهرکرد':(32.325,50.864),'سمنان':(35.576,53.395),'قزوین':(36.270,50.004),
                'یاسوج':(30.668,51.588),'آمل':(36.471,52.351),'بابل':(36.551,52.678),
            }
                # use map-picked coords if provided, else fall back to city coords
            raw_lat = request.POST.get('location_lat', '').strip()
            raw_lng = request.POST.get('location_lng', '').strip()
            if raw_lat and raw_lng:
                try:
                    profile.location_lat  = round(float(raw_lat), 3)
                    profile.location_lng  = round(float(raw_lng), 3)
                except ValueError:
                    pass
            elif not profile.location_lat:
                coords = _CITY_COORDS.get(loc_city) or _CITY_COORDS.get(loc_province)
                if coords:
                    profile.location_lat, profile.location_lng = coords
        elif 'location_province' in request.POST:
            # both empty → clear label and coords
            profile.location_label = ''
            profile.location_lat = None
            profile.location_lng = None

        selected_platforms = request.POST.getlist('platforms')
        profile.platforms = selected_platforms
        profile.platform = selected_platforms[0] if selected_platforms else 'pc'
        profile.gaming_style = request.POST.get('gaming_style', '')
        profile.rank = request.POST.get('rank', '')
        profile.favorite_games = request.POST.get('favorite_games', '')
        profile.phone = request.POST.get('phone', '').strip()
        raw_nid = request.POST.get('national_id', '').strip()
        raw_nid = raw_nid.translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789'))
        profile.national_id = raw_nid
        profile.steam_id = request.POST.get('steam_id', '')
        profile.psn_id = request.POST.get('psn_id', '')
        profile.xbox_gamertag = request.POST.get('xbox_gamertag', '')

        if 'avatar' in request.FILES:
            f = request.FILES['avatar']
            profile.avatar.save(f.name, f, save=False)
        if 'banner' in request.FILES:
            f = request.FILES['banner']
            profile.banner.save(f.name, f, save=False)

        profile.save()
        messages.success(request, 'پروفایل آپدیت شد!')
        return redirect('community:profile', username=request.user.username)

    # parse location_label into province + city for the edit form
    loc_parts = profile.location_label.split(' — ', 1) if profile.location_label else []
    loc_province_val = loc_parts[0].strip() if len(loc_parts) >= 1 else ''
    loc_city_val     = loc_parts[1].strip() if len(loc_parts) >= 2 else ''

    context = {
        'profile': profile,
        'platform_choices': PLATFORM_CHOICES,
        'city_choices': CITY_CHOICES,
        'loc_province_val': loc_province_val,
        'loc_city_val': loc_city_val,
        'popular_games': [
            'Valorant', 'FIFA 25', 'Call of Duty', 'GTA V', 'PUBG',
            'Dota 2', 'CS2', 'Fortnite', 'Minecraft', 'League of Legends',
            'Apex Legends', 'Elden Ring', 'Dark Souls', 'Cyberpunk 2077',
            'Red Dead Redemption 2', 'God of War', 'Spider-Man',
            'Witcher 3', 'Zelda: Tears of the Kingdom', 'Overwatch 2',
        ],
    }
    return render(request, 'community/edit_profile.html', context)


@login_required
def create_post(request):
    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        if not content:
            messages.error(request, 'محتوای پست نمی‌تواند خالی باشد!')
            return redirect('community:feed')

        post = Post.objects.create(
            author=request.user,
            content=content,
            post_type=request.POST.get('post_type', 'text'),
            game_tag=request.POST.get('game_tag', ''),
            is_approved=False,
        )
        if 'image' in request.FILES:
            post.image = request.FILES['image']
            post.save()

        extract_and_save_hashtags(post)

        profile = get_or_create_gamer_profile(request.user)
        profile.save()

        messages.success(request, 'پست منتشر شد!')
    return redirect('community:feed')


@login_required
@require_POST
def toggle_like(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    like, created = PostLike.objects.get_or_create(post=post, user=request.user)
    if not created:
        like.delete()
        liked = False
    else:
        liked = True
        # Notification: like
        if post.author != request.user:
            Notification.objects.get_or_create(
                recipient=post.author, sender=request.user,
                notif_type='like', post=post
            )

    return JsonResponse({'liked': liked, 'count': post.likes_count})


def post_interactions(request, post_id):
    """Tabbed interactions modal: likes + reactions with search & pagination."""
    post    = get_object_or_404(Post, id=post_id)
    tab     = request.GET.get('tab', 'all')   # all | likes | fire | dead | ...
    q       = request.GET.get('q', '').strip()
    page    = max(1, int(request.GET.get('page', 1)))
    per     = 15

    EMOJI  = PostReaction.REACTION_EMOJI
    LABELS = {r[0]: r[1] for r in PostReaction.REACTION_CHOICES}

    # ── Tab counts (always computed from DB) ──────────────────────────────
    like_count = PostLike.objects.filter(post=post).count()
    rxn_counts = {}
    for rtype in EMOJI:
        c = PostReaction.objects.filter(post=post, reaction_type=rtype).count()
        if c:
            rxn_counts[rtype] = c
    total_all = like_count + sum(rxn_counts.values())

    # ── Build tabs list for frontend ──────────────────────────────────────
    # "همه" + "❤️" always present; reaction tabs only when > 0
    tabs_info = [
        {'key': 'all',   'emoji': '👥', 'label': 'همه',  'count': total_all},
        {'key': 'likes', 'emoji': '❤️', 'label': 'لایک', 'count': like_count},
    ]
    for rtype in ['fire', 'dead', 'tryhard', 'legend', 'ggez', 'cry']:
        if rtype in rxn_counts:
            tabs_info.append({
                'key':   rtype,
                'emoji': EMOJI[rtype],
                'label': LABELS.get(rtype, rtype),
                'count': rxn_counts[rtype],
            })

    # ── Fetch users for current tab ───────────────────────────────────────
    def _user_row(u, badge):
        try:
            pr  = u.gamer_profile
            av  = pr.avatar.url if pr.avatar else None
        except Exception:
            av = None
        return {'username': u.username, 'full_name': u.get_full_name() or u.username,
                'avatar': av, 'badge': badge}

    def _search_filter(qs, field_prefix):
        if not q:
            return qs
        return qs.filter(
            Q(**{f'{field_prefix}__username__icontains': q}) |
            Q(**{f'{field_prefix}__first_name__icontains': q}) |
            Q(**{f'{field_prefix}__last_name__icontains': q})
        )

    if tab == 'all':
        likes = list(_search_filter(
            PostLike.objects.filter(post=post).select_related('user', 'user__gamer_profile')
            .order_by('-created_at'), 'user'
        )[:300])
        rxns  = list(_search_filter(
            PostReaction.objects.filter(post=post).select_related('user', 'user__gamer_profile')
            .order_by('-created_at'), 'user'
        )[:300])
        seen, combined = set(), []
        for obj in likes:
            if obj.user_id not in seen:
                seen.add(obj.user_id); combined.append((obj.user, '❤️'))
        for obj in rxns:
            if obj.user_id not in seen:
                seen.add(obj.user_id); combined.append((obj.user, EMOJI.get(obj.reaction_type, '👍')))
        total_filtered = len(combined)
        total_pages    = max(1, (total_filtered + per - 1) // per)
        page           = min(page, total_pages)
        rows  = [_user_row(u, b) for u, b in combined[(page-1)*per: page*per]]

    elif tab == 'likes':
        qs     = _search_filter(
            PostLike.objects.filter(post=post).select_related('user', 'user__gamer_profile')
            .order_by('-created_at'), 'user'
        )
        total_filtered = qs.count()
        total_pages    = max(1, (total_filtered + per - 1) // per)
        page           = min(page, total_pages)
        rows  = [_user_row(obj.user, '❤️') for obj in qs[(page-1)*per: page*per]]

    else:  # specific reaction
        qs     = _search_filter(
            PostReaction.objects.filter(post=post, reaction_type=tab)
            .select_related('user', 'user__gamer_profile').order_by('-created_at'), 'user'
        )
        badge  = EMOJI.get(tab, '👍')
        total_filtered = qs.count()
        total_pages    = max(1, (total_filtered + per - 1) // per)
        page           = min(page, total_pages)
        rows  = [_user_row(obj.user, badge) for obj in qs[(page-1)*per: page*per]]

    return JsonResponse({
        'users':    rows,
        'tabs':     tabs_info,
        'tab':      tab,
        'filtered': total_filtered,
        'page':     page,
        'pages':    total_pages,
        'has_prev': page > 1,
        'has_next': page < total_pages,
    })


def post_likes_list(request, post_id):
    """Return paginated + searchable list of users who liked a post (JSON)."""
    post    = get_object_or_404(Post, id=post_id)
    q       = request.GET.get('q', '').strip()
    page    = max(1, int(request.GET.get('page', 1)))
    per     = 15

    qs = PostLike.objects.filter(post=post).select_related('user', 'user__gamer_profile')
    if q:
        qs = qs.filter(
            Q(user__username__icontains=q) |
            Q(user__first_name__icontains=q) |
            Q(user__last_name__icontains=q)
        )
    qs = qs.order_by('-created_at')

    total_filtered = qs.count()
    total_pages    = max(1, (total_filtered + per - 1) // per)
    page           = min(page, total_pages)
    offset         = (page - 1) * per
    likes          = qs[offset: offset + per]

    data = []
    for like in likes:
        u = like.user
        try:
            profile   = u.gamer_profile
            avatar_url = profile.avatar.url if profile.avatar else None
        except Exception:
            avatar_url = None
        data.append({
            'username':  u.username,
            'full_name': u.get_full_name() or u.username,
            'avatar':    avatar_url,
        })
    return JsonResponse({
        'likes':    data,
        'total':    post.likes_count,      # همیشه کل لایک‌ها
        'filtered': total_filtered,        # با فیلتر سرچ
        'page':     page,
        'pages':    total_pages,
        'has_prev': page > 1,
        'has_next': page < total_pages,
    })


def post_comments_list(request, post_id):
    """Return list of comments for a post (JSON)."""
    post = get_object_or_404(Post, id=post_id)
    comments = (post.comments.all()
                .select_related('author', 'author__gamer_profile')
                .order_by('created_at')[:200])
    data = []
    for c in comments:
        u = c.author
        try:
            profile = u.gamer_profile
            avatar_url = profile.avatar.url if profile.avatar else None
        except Exception:
            avatar_url = None
        data.append({
            'id': c.id,
            'username': u.username,
            'full_name': u.get_full_name() or u.username,
            'avatar': avatar_url,
            'content': c.content,
            'created_at': _to_jalali(c.created_at, '%Y/%m/%d %H:%M'),
        })
    return JsonResponse({'comments': data, 'total': post.comments_count})


@login_required
@require_POST
def add_comment(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    content = request.POST.get('content', '').strip()
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if content:
        comment = Comment.objects.create(
            post=post, author=request.user,
            content=content, is_approved=False,
        )
        if post.author != request.user:
            Notification.objects.create(
                recipient=post.author, sender=request.user,
                notif_type='comment', post=post,
                custom_text=content[:120],
            )
        if is_ajax:
            profile = get_or_create_gamer_profile(request.user)
            return JsonResponse({
                'ok': True,
                'comment': {
                    'id': comment.id,
                    'username': request.user.username,
                    'full_name': request.user.get_full_name() or request.user.username,
                    'avatar': profile.avatar.url if profile.avatar else None,
                    'content': comment.content,
                    'created_at': comment.created_at.strftime('%H:%M'),
                },
                'total': post.comments_count,
            })
    elif is_ajax:
        return JsonResponse({'ok': False, 'error': 'کامنت خالی است'}, status=400)

    return redirect(request.META.get('HTTP_REFERER', 'community:feed'))


@login_required
def toggle_follow(request, username):
    if request.method != 'POST':
        return JsonResponse({'error': 'method'}, status=405)
    target_user = get_object_or_404(User, username=username)
    if target_user == request.user:
        return JsonResponse({'error': 'self'}, status=400)

    target_profile = get_or_create_gamer_profile(target_user)

    # اگه پروفایل خصوصیه، درخواست بفرست نه فالو مستقیم
    if target_profile.is_private:
        existing = FollowRequest.objects.filter(from_user=request.user, to_user=target_user).first()
        if existing:
            if existing.status == 'pending':
                existing.delete()
                return JsonResponse({'status': 'cancelled', 'followers_count': target_profile.followers_count})
            elif existing.status == 'accepted':
                # قبلاً accept شده = فالو شده، آنفالو کن
                Follow.objects.filter(follower=request.user, following=target_user).delete()
                existing.delete()
                return JsonResponse({'status': 'unfollowed', 'followers_count': target_profile.followers_count})
        else:
            FollowRequest.objects.create(from_user=request.user, to_user=target_user)
            Notification.objects.create(
                recipient=target_user,
                sender=request.user,
                notif_type='follow_request',
                custom_text=f'{request.user.get_full_name() or request.user.username} درخواست دنبال کردن فرستاد'
            )
            return JsonResponse({'status': 'requested', 'followers_count': target_profile.followers_count})

    # پروفایل عمومی — فالو/آنفالو مستقیم
    follow, created = Follow.objects.get_or_create(follower=request.user, following=target_user)
    if not created:
        follow.delete()
        following = False
    else:
        following = True
        Notification.objects.create(
            recipient=target_user,
            sender=request.user,
            notif_type='follow',
            post=None
        )
    return JsonResponse({'following': following, 'followers_count': target_profile.followers_count})


@login_required
def manage_follow_requests(request):
    """لیست درخواست‌های دنبال کردن دریافتی"""
    requests_list = FollowRequest.objects.filter(
        to_user=request.user, status='pending'
    ).select_related('from_user', 'from_user__gamer_profile').order_by('-created_at')
    return render(request, 'community/follow_requests.html', {'requests_list': requests_list})


@login_required
def respond_follow_request(request, request_id):
    """قبول یا رد درخواست دنبال کردن"""
    if request.method != 'POST':
        return JsonResponse({'error': 'method'}, status=405)

    fr = get_object_or_404(FollowRequest, id=request_id, to_user=request.user)
    action = request.POST.get('action')  # 'accept' or 'reject'

    sender_name = request.user.get_full_name() or request.user.username

    if action == 'accept':
        fr.status = 'accepted'
        fr.save()
        Follow.objects.get_or_create(follower=fr.from_user, following=request.user)
        Notification.objects.create(
            recipient=fr.from_user,
            sender=request.user,
            notif_type='follow_accepted',
            post=None,
            custom_text=f'{sender_name} درخواست دنبال کردن شما را پذیرفت'
        )
        return JsonResponse({'ok': True, 'action': 'accepted'})
    elif action == 'reject':
        fr.status = 'rejected'
        fr.save()
        Notification.objects.create(
            recipient=fr.from_user,
            sender=request.user,
            notif_type='follow_rejected',
            post=None,
            custom_text=f'{sender_name} درخواست دنبال کردن شما را رد کرد'
        )
        return JsonResponse({'ok': True, 'action': 'rejected'})

    return JsonResponse({'error': 'invalid action'}, status=400)


@login_required
def search_gamers(request):
    query = request.GET.get('q', '').strip()
    platform_filter = request.GET.get('platform', '')
    city_filter = request.GET.get('city', '')
    game_filter = request.GET.get('game', '')
    my_profile = get_or_create_gamer_profile(request.user)

    gamers = GamerProfile.objects.select_related('user').exclude(user=request.user)

    if query:
        gamers = gamers.filter(
            Q(user__username__icontains=query) |
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(favorite_games__icontains=query) |
            Q(bio__icontains=query)
        )
    if platform_filter:
        gamers = gamers.filter(platform=platform_filter)
    if city_filter:
        gamers = gamers.filter(city=city_filter)
    if game_filter:
        gamers = gamers.filter(favorite_games__icontains=game_filter)

    gamers = gamers.order_by('-total_hours_played')[:30]

    following_ids = set(Follow.objects.filter(follower=request.user).values_list('following_id', flat=True))

    # درخواست‌های دنبال کردن دریافتی
    pending_requests = FollowRequest.objects.filter(
        to_user=request.user, status='pending'
    ).select_related('from_user', 'from_user__gamer_profile').order_by('-created_at')

    context = {
        'gamers': gamers,
        'query': query,
        'platform_filter': platform_filter,
        'city_filter': city_filter,
        'game_filter': game_filter,
        'following_ids': following_ids,
        'my_profile': my_profile,
        'platform_choices': PLATFORM_CHOICES,
        'city_choices': CITY_CHOICES,
        'pending_requests': pending_requests,
        'pending_count': pending_requests.count(),
    }
    return render(request, 'community/search.html', context)


def lfg_board(request):
    my_profile = get_or_create_gamer_profile(request.user) if request.user.is_authenticated else None
    platform_filter = request.GET.get('platform', '')
    game_filter = request.GET.get('game', '')

    lfg_posts = LFGPost.objects.filter(is_active=True).select_related('author', 'author__gamer_profile')

    if platform_filter:
        lfg_posts = lfg_posts.filter(platform=platform_filter)
    if game_filter:
        lfg_posts = lfg_posts.filter(game_name__icontains=game_filter)

    lfg_posts = list(lfg_posts.order_by('-created_at')[:50])
    # پریمیوم‌ها بالای بورد
    premium_lfg = [p for p in lfg_posts if p.author.gamer_profile.is_premium]
    normal_lfg  = [p for p in lfg_posts if not p.author.gamer_profile.is_premium]
    lfg_posts   = premium_lfg + normal_lfg

    from dashboard.models import Game as DashboardGame
    _fallback = ['Valorant', 'FIFA 25', 'Call of Duty', 'GTA Online', 'PUBG', 'Dota 2', 'CS2', 'Fortnite']
    try:
        _db_games = list(DashboardGame.objects.filter(is_active=True, is_online=True).values_list('name', flat=True).order_by('name'))
        game_choices = _db_games if _db_games else _fallback
    except Exception:
        game_choices = _fallback

    # user join status sets (for simple "in" checks in template)
    joined_ids = set()
    pending_ids = set()
    rejected_ids = set()
    # pending requests on own posts {post_id: [req, ...]}
    _pending_map = {}

    if request.user.is_authenticated:
        for r in LFGJoinRequest.objects.filter(user=request.user, post__in=lfg_posts):
            if r.status == 'accepted':
                joined_ids.add(r.post_id)
            elif r.status == 'pending':
                pending_ids.add(r.post_id)
            elif r.status == 'rejected':
                rejected_ids.add(r.post_id)

        for r in LFGJoinRequest.objects.filter(
            post__author=request.user, post__in=lfg_posts, status='pending'
        ).select_related('user', 'user__gamer_profile'):
            _pending_map.setdefault(r.post_id, []).append(r)

    # annotate each post object so the template can iterate without a variable key lookup
    for post in lfg_posts:
        post.pending_reqs = _pending_map.get(post.pk, [])

    _party_groups = {g.lfg_post_id: g for g in GroupChat.objects.filter(lfg_post__in=lfg_posts)}
    for post in lfg_posts:
        post.party_group_obj = _party_groups.get(post.pk)

    context = {
        'lfg_posts': lfg_posts,
        'platform_filter': platform_filter,
        'game_filter': game_filter,
        'my_profile': my_profile,
        'platform_choices': PLATFORM_CHOICES,
        'popular_games': _fallback,
        'game_choices': game_choices,
        'joined_ids': joined_ids,
        'pending_ids': pending_ids,
        'rejected_ids': rejected_ids,
    }
    return render(request, 'community/lfg.html', context)


@login_required
@require_POST
def create_lfg(request):
    LFGPost.objects.create(
        author=request.user,
        game_name=request.POST.get('game_name', ''),
        game_mode=request.POST.get('game_mode', 'normal'),
        platform=request.POST.get('platform', 'pc'),
        skill_level=request.POST.get('skill_level', 'any'),
        description=request.POST.get('description', ''),
        max_players=int(request.POST.get('max_players', 4)),
        join_type=request.POST.get('join_type', 'open'),
    )
    messages.success(request, 'پست LFG منتشر شد! منتظر بازیکن باش 🎮')
    return redirect('community:lfg')


def _maybe_create_party_group(post):
    """Create a GroupChat when an LFG party fills up."""
    if post.current_players < post.max_players:
        return None

    # Return existing group if already created
    try:
        existing = GroupChat.objects.get(lfg_post=post)
        return existing
    except GroupChat.DoesNotExist:
        pass

    try:
        from django.db import IntegrityError as _IE
        group = GroupChat.objects.create(
            name=f'🎮 پارتی {post.game_name}',
            description=f'گروه پارتی {post.game_name}. هر وقت خواستی می‌تونی بری.',
            created_by=post.author,
            lfg_post=post,
            is_temp=False,
        )
    except Exception:
        # Race condition: another request created the group first
        try:
            return GroupChat.objects.get(lfg_post=post)
        except GroupChat.DoesNotExist:
            return None

    # Add author as owner
    GroupMember.objects.get_or_create(group=group, user=post.author, defaults={'role': 'owner'})

    # Add all accepted members
    accepted_users = LFGJoinRequest.objects.filter(post=post, status='accepted').select_related('user')
    for req in accepted_users:
        member, _ = GroupMember.objects.get_or_create(group=group, user=req.user, defaults={'role': 'member'})

    # Notify party creator (author) that their party is full
    Notification.objects.create(
        recipient=post.author,
        sender=post.author,
        notif_type='lfg_party',
        custom_text=f'🎉 پارتی «{post.game_name}» کامل شد! گروه چت آماده‌ست.',
    )

    # Notify all members (except the author)
    for req in accepted_users:
        if req.user != post.author:
            Notification.objects.create(
                recipient=req.user,
                sender=post.author,
                notif_type='lfg_party',
                custom_text=f'پارتی «{post.game_name}» کامل شد! گروه چت آماده‌ست 🎮',
            )

    # Send an automatic welcome message in the group
    # (so all members see an unread message and know they've been added)
    GroupMessage.objects.create(
        group=group,
        sender=post.author,
        content=(
            f'🎮 پارتی «{post.game_name}» کامل شد!\n'
            f'به گروه خوش اومدید 👋\n'
            f'ایدی و اطلاعات تماس رو اینجا به اشتراک بذارید 🕹️'
        ),
    )

    return group


@login_required
@require_POST
def join_lfg(request, post_id):
    post = get_object_or_404(LFGPost, pk=post_id, is_active=True)

    if post.author == request.user:
        return JsonResponse({'error': 'نمی‌توانید به پست خودتان بپیوندید'}, status=400)
    if post.spots_left <= 0:
        return JsonResponse({'error': 'ظرفیت تکمیل شده'}, status=400)

    if post.join_type == 'open':
        # direct join — prevent duplicate
        already = LFGJoinRequest.objects.filter(post=post, user=request.user, status='accepted').exists()
        if already:
            return JsonResponse({'error': 'قبلاً پیوسته‌اید'}, status=400)
        LFGJoinRequest.objects.update_or_create(
            post=post, user=request.user,
            defaults={'status': 'accepted'}
        )
        post.current_players = min(post.current_players + 1, post.max_players)
        post.save(update_fields=['current_players'])
        Notification.objects.create(
            recipient=post.author, sender=request.user,
            notif_type='lfg_join',
            custom_text=f'{request.user.username} به پست «{post.game_name}» پیوست',
        )
        party = _maybe_create_party_group(post)
        return JsonResponse({'ok': True, 'type': 'joined',
                             'current': post.current_players, 'max': post.max_players,
                             'party_group_id': party.pk if party else None})

    else:  # request type
        req, created = LFGJoinRequest.objects.get_or_create(post=post, user=request.user)
        if not created:
            if req.status == 'pending':
                return JsonResponse({'error': 'درخواست شما در انتظار تأیید است'}, status=400)
            if req.status == 'accepted':
                return JsonResponse({'error': 'قبلاً پذیرفته شده‌اید'}, status=400)
            req.status = 'pending'
            req.save(update_fields=['status'])
        Notification.objects.create(
            recipient=post.author, sender=request.user,
            notif_type='lfg_req',
            custom_text=f'{request.user.username} درخواست پیوستن به «{post.game_name}» داد',
        )
        return JsonResponse({'ok': True, 'type': 'requested'})


@login_required
@require_POST
def respond_lfg_join(request, req_id):
    join_req = get_object_or_404(LFGJoinRequest, pk=req_id, post__author=request.user, status='pending')
    action = request.POST.get('action')  # 'accept' or 'reject'

    if action == 'accept':
        if join_req.post.spots_left <= 0:
            return JsonResponse({'error': 'ظرفیت تکمیل شده'}, status=400)
        join_req.status = 'accepted'
        join_req.save(update_fields=['status'])
        join_req.post.current_players = min(join_req.post.current_players + 1, join_req.post.max_players)
        join_req.post.save(update_fields=['current_players'])
        Notification.objects.create(
            recipient=join_req.user, sender=request.user,
            notif_type='lfg_ok',
            custom_text=f'درخواست پیوستن به «{join_req.post.game_name}» تأیید شد 🎮',
        )
        party = _maybe_create_party_group(join_req.post)
        return JsonResponse({'ok': True, 'status': 'accepted',
                             'current': join_req.post.current_players, 'max': join_req.post.max_players,
                             'party_group_id': party.pk if party else None})

    elif action == 'reject':
        join_req.status = 'rejected'
        join_req.save(update_fields=['status'])
        Notification.objects.create(
            recipient=join_req.user, sender=request.user,
            notif_type='lfg_no',
            custom_text=f'درخواست پیوستن به «{join_req.post.game_name}» رد شد',
        )
        return JsonResponse({'ok': True, 'status': 'rejected'})

    return JsonResponse({'error': 'عملیات نامعتبر'}, status=400)


@login_required
@require_POST
def delete_party_group(request, post_id):
    """سازنده پست LFG می‌تواند گروه موقت را حذف کند."""
    post = get_object_or_404(LFGPost, pk=post_id, author=request.user)
    try:
        group = GroupChat.objects.get(lfg_post=post)
        group.delete()
    except GroupChat.DoesNotExist:
        pass
    return JsonResponse({'ok': True})


def leaderboard(request):
    from django.db.models import Count, Q
    from django.db.models.functions import TruncDate
    from django.utils import timezone
    from datetime import timedelta
    from collections import defaultdict

    # ── بازه زمانی — مرز تقویمی شمسی ──
    period = request.GET.get('period', 'monthly')
    now = timezone.now()
    local_now = timezone.localtime(now)
    day_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)

    import jdatetime as _jdt
    from datetime import datetime as _dt, time as _time
    from django.utils.timezone import make_aware as _mka

    jnow = _jdt.datetime.fromgregorian(datetime=local_now)
    j_wd = jnow.weekday()          # 0=شنبه … 6=جمعه

    # شروع هفته جاری (شنبه امروز یا گذشته)
    week_start  = day_start - timedelta(days=j_wd)

    # شروع ماه جاری شمسی (روز ۱)
    j_m1        = _jdt.date(jnow.year, jnow.month, 1).togregorian()
    month_start = _mka(_dt.combine(j_m1, _time.min))

    # شروع سال جاری شمسی (فروردین ۱)
    j_y1        = _jdt.date(jnow.year, 1, 1).togregorian()
    year_start  = _mka(_dt.combine(j_y1, _time.min))

    PERIOD_SINCE = {
        'daily':   day_start,
        'weekly':  week_start,
        'monthly': month_start,
        'yearly':  year_start,
    }
    since = PERIOD_SINCE.get(period)   # None = alltime

    # ── زمان ریست بعدی هر بازه (Unix timestamp برای JS) ──
    daily_reset   = day_start + timedelta(days=1)
    # هفتگی: شنبه بعدی — اگه امروز شنبه است ۷ روز دیگر
    days_to_sat   = 7 if j_wd == 0 else (7 - j_wd)
    week_reset    = day_start + timedelta(days=days_to_sat)
    # ماهانه: اول ماه بعدی شمسی
    jnext_m_args  = (jnow.year + 1, 1, 1) if jnow.month == 12 else (jnow.year, jnow.month + 1, 1)
    monthly_reset = _mka(_dt.combine(_jdt.date(*jnext_m_args).togregorian(), _time.min))
    # سالانه: اول فروردین سال بعدی
    yearly_reset  = _mka(_dt.combine(_jdt.date(jnow.year + 1, 1, 1).togregorian(), _time.min))

    PERIOD_RESET  = {
        'daily':   daily_reset,
        'weekly':  week_reset,
        'monthly': monthly_reset,
        'yearly':  yearly_reset,
        'alltime': None,
    }
    next_reset_dt  = PERIOD_RESET.get(period)
    current_reset_ts = int(next_reset_dt.timestamp()) if next_reset_dt else 0

    my_profile = get_or_create_gamer_profile(request.user) if request.user.is_authenticated else None

    # ── step 1: پست و کامنت برای هر کاربر (از DB) ──
    def _db_counts(qs, since):
        if since:
            return qs.annotate(
                db_post_count=Count('user__posts', filter=Q(user__posts__created_at__gte=since), distinct=True),
                db_comment_count=Count('user__comment', filter=Q(user__comment__created_at__gte=since), distinct=True),
            )
        return qs.annotate(
            db_post_count=Count('user__posts', distinct=True),
            db_comment_count=Count('user__comment', distinct=True),
        )

    # ── step 2: روزهای فعال ──
    def _active_days_map(user_ids, since):
        if not user_ids:
            return {}
        days = defaultdict(set)
        pf = Q(author_id__in=user_ids)
        cf = Q(author_id__in=user_ids)
        if since:
            pf &= Q(created_at__gte=since)
            cf &= Q(created_at__gte=since)
        for row in Post.objects.filter(pf).annotate(d=TruncDate('created_at')).values('author_id', 'd').distinct():
            days[row['author_id']].add(row['d'])
        for row in Comment.objects.filter(cf).annotate(d=TruncDate('created_at')).values('author_id', 'd').distinct():
            days[row['author_id']].add(row['d'])
        return {uid: len(s) for uid, s in days.items()}

    # ── step 3: خواندن ضرایب از تنظیمات ادمین ──
    cfg = ScoreSettings.get()

    def _final_score(g):
        online_hours = getattr(g, 'online_secs', 0) / 3600
        return (
            g.db_post_count                * cfg.post_score +
            g.db_comment_count             * cfg.comment_score +
            getattr(g, 'active_days', 0)   * cfg.active_day_score +
            online_hours                   * cfg.online_hour_score
        )

    # واکشی همه کاربران فعال از DB
    all_profiles = list(
        _db_counts(GamerProfile.objects.select_related('user'), since)
        .filter(Q(db_post_count__gt=0) | Q(db_comment_count__gt=0))
    )

    all_user_ids = [g.user_id for g in all_profiles]

    # محاسبه روزهای فعال + ساعات آنلاین برای همه
    admap      = _active_days_map(all_user_ids, since)
    online_map = UserSession.total_seconds_in_period(all_user_ids, since)

    for g in all_profiles:
        g.active_days  = admap.get(g.user_id, 0)
        g.online_secs  = online_map.get(g.user_id, 0)
        g.activity_score = int(_final_score(g))

    # مرتب‌سازی و تاپ ۱۰
    all_sorted  = sorted(all_profiles, key=lambda g: -g.activity_score)
    top_gamers  = all_sorted[:10]

    # ── رتبه کاربر جاری اگر توی تاپ ۱۰ نبود ──
    my_rank  = None
    my_entry = None
    if request.user.is_authenticated:
        in_top = any(g.user_id == request.user.id for g in top_gamers)
        if not in_top:
            # پیدا کردن رتبه در لیست کامل
            for idx, g in enumerate(all_sorted):
                if g.user_id == request.user.id:
                    my_rank  = idx + 1
                    my_entry = g
                    break
            # اگر اصلاً فعالیتی نداشت
            if not my_entry:
                me = GamerProfile.objects.select_related('user').filter(user=request.user).first()
                if me:
                    me.db_post_count    = 0
                    me.db_comment_count = 0
                    me.active_days      = 0
                    me.online_secs      = 0
                    me.activity_score   = 0
                    my_rank  = len(all_sorted) + 1
                    my_entry = me

    context = {
        'top_gamers':        top_gamers,
        'my_profile':        my_profile,
        'period':            period,
        'my_rank':           my_rank,
        'my_entry':          my_entry,
        'score_cfg':         cfg,
        'current_reset_ts':  current_reset_ts,   # Unix timestamp برای countdown
    }
    return render(request, 'community/leaderboard.html', context)


@login_required
def my_profile_dashboard(request):
    """پروفایل شخصی - نمای عمومی + دکمه ویرایش"""
    # نمایش همان صفحه پروفایل عمومی، با is_own_profile=True
    return gamer_profile(request, username=request.user.username)


@login_required
@require_POST
def delete_post(request, post_id):
    Post.objects.filter(id=post_id, author=request.user).delete()
    return JsonResponse({'ok': True})


@login_required
@require_POST
def boost_post(request, post_id):
    """بوست پست — فقط برای کاربران پریمیوم، ۲۴ ساعته"""
    from datetime import timedelta
    post = get_object_or_404(Post, pk=post_id, author=request.user)
    my_profile = get_or_create_gamer_profile(request.user)

    if not my_profile.is_premium:
        return JsonResponse({'ok': False, 'error': 'premium_required'}, status=403)

    if post.boost_active:
        # لغو بوست
        post.is_boosted = False
        post.boost_expires_at = None
        post.save(update_fields=['is_boosted', 'boost_expires_at'])
        return JsonResponse({'ok': True, 'boosted': False})

    # بررسی محدودیت: حداکثر ۱ بوست فعال همزمان
    active_boosts = Post.objects.filter(
        author=request.user,
        is_boosted=True,
        boost_expires_at__gt=timezone.now(),
    ).exclude(pk=post_id).count()
    if active_boosts >= 1:
        return JsonResponse({'ok': False, 'error': 'max_boost_reached'}, status=400)

    # فعال‌سازی بوست ۲۴ ساعته
    post.is_boosted = True
    post.boost_expires_at = timezone.now() + timedelta(hours=24)
    post.save(update_fields=['is_boosted', 'boost_expires_at'])
    return JsonResponse({'ok': True, 'boosted': True, 'expires': post.boost_expires_at.isoformat()})


@login_required
@require_POST
def connect_gaming_account(request):
    from .gaming_apis import lookup_account
    from django.utils import timezone

    platform = request.POST.get('platform', '').strip()
    username = request.POST.get('username', '').strip()

    if not platform or not username:
        return JsonResponse({'ok': False, 'error': 'اطلاعات ناقص است'})

    result = lookup_account(platform, username)

    if result['ok']:
        account, created = GamingAccount.objects.update_or_create(
            user=request.user,
            platform=platform,
            defaults={
                'username': username,
                'display_name': result.get('display_name', username),
                'avatar_url': result.get('avatar_url', ''),
                'profile_url': result.get('profile_url', ''),
                'extra_data': result.get('extra', {}),
                'verified': True,
                'last_synced': timezone.now(),
            }
        )
        return JsonResponse({
            'ok': True,
            'display_name': account.display_name,
            'avatar_url': account.avatar_url,
            'profile_url': account.profile_url,
            'platform': platform,
        })
    else:
        return JsonResponse({'ok': False, 'error': result.get('error', 'خطا')})


@login_required
@require_POST
def disconnect_gaming_account(request):
    platform = request.POST.get('platform', '')
    GamingAccount.objects.filter(user=request.user, platform=platform).delete()
    return JsonResponse({'ok': True})


def hashtag_feed(request, tag_name):
    """Posts tagged with #hashtag"""
    hashtag = get_object_or_404(Hashtag, name=tag_name.lower())
    posts = Post.objects.filter(hashtags=hashtag, is_public=True).select_related(
        'author', 'author__gamer_profile'
    ).prefetch_related('likes', 'comments').order_by('-created_at')[:50]
    liked_post_ids = set()
    my_profile = None
    if request.user.is_authenticated:
        liked_post_ids = set(PostLike.objects.filter(user=request.user).values_list('post_id', flat=True))
        my_profile = get_or_create_gamer_profile(request.user)
    trending = Hashtag.objects.filter(post_count__gt=0).order_by('-post_count')[:15]
    context = {
        'hashtag': hashtag,
        'posts': posts,
        'liked_post_ids': liked_post_ids,
        'my_profile': my_profile,
        'trending': trending,
    }
    return render(request, 'community/hashtag_feed.html', context)


def hashtag_suggest(request):
    """AJAX: suggest hashtags by prefix"""
    q = request.GET.get('q', '').strip().lower().lstrip('#')
    if len(q) < 1:
        tags = Hashtag.objects.filter(post_count__gt=0).order_by('-post_count')[:10]
    else:
        tags = Hashtag.objects.filter(name__startswith=q).order_by('-post_count')[:10]
    return JsonResponse({'tags': [{'name': t.name, 'count': t.post_count} for t in tags]})


@login_required
def create_post_page(request):
    """Full-page post creation"""
    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        if not content:
            messages.error(request, 'محتوای پست نمی‌تواند خالی باشد!')
            return redirect('community:create_post_page')
        post = Post.objects.create(
            author=request.user,
            content=content,
            post_type=request.POST.get('post_type', 'text'),
            game_tag=request.POST.get('game_tag', ''),
            link_url=request.POST.get('link_url', ''),
            link_title=request.POST.get('link_title', ''),
            link_description=request.POST.get('link_description', ''),
            link_image_url=request.POST.get('link_image_url', ''),
            is_approved=False,
        )
        if 'image' in request.FILES:
            post.image = request.FILES['image']
            post.save()
        if 'video' in request.FILES:
            post.video = request.FILES['video']
            post.save()
        extract_and_save_hashtags(post)
        profile = get_or_create_gamer_profile(request.user)
        profile.save()
        messages.success(request, 'پست منتشر شد! 🎮')
        return redirect('community:profile', username=request.user.username)
    trending = Hashtag.objects.filter(post_count__gt=0).order_by('-post_count')[:12]
    popular_games = ['Valorant', 'FIFA 25', 'CS2', 'GTA Online', 'PUBG', 'Dota 2', 'Fortnite', 'Elden Ring']
    my_profile = get_or_create_gamer_profile(request.user)
    context = {
        'trending': trending,
        'popular_games': popular_games,
        'my_profile': my_profile,
    }
    return render(request, 'community/create_post.html', context)


def link_preview(request):
    """Fetch OG/meta data from a URL for link preview"""
    url = request.GET.get('url', '').strip()
    if not url:
        return JsonResponse({'ok': False})
    try:
        import requests as req
        from html.parser import HTMLParser

        r = req.get(url, timeout=5, headers={'User-Agent': 'GameBeat Bot/1.0'}, allow_redirects=True)

        class OGParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.og = {}
                self.title = ''
                self._in_title = False

            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if tag == 'meta':
                    prop = attrs.get('property', attrs.get('name', ''))
                    content = attrs.get('content', '')
                    if prop in ('og:title', 'og:description', 'og:image', 'og:url',
                                'twitter:title', 'twitter:description', 'twitter:image'):
                        key = prop.replace('og:', '').replace('twitter:', '')
                        if key not in self.og:
                            self.og[key] = content
                if tag == 'title':
                    self._in_title = True

            def handle_data(self, data):
                if self._in_title:
                    self.title = data.strip()
                    self._in_title = False

        parser = OGParser()
        parser.feed(r.text[:20000])

        return JsonResponse({
            'ok': True,
            'title': parser.og.get('title', parser.title)[:200],
            'description': parser.og.get('description', '')[:300],
            'image': parser.og.get('image', ''),
            'url': url,
        })
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)})


# ═══════════════════════════════════════
#  NOTIFICATIONS
# ═══════════════════════════════════════

@login_required
def notifications_list(request):
    has_unread = Notification.objects.filter(
        recipient=request.user, is_read=False
    ).exclude(notif_type='dm').exists()

    notifs = Notification.objects.filter(
        recipient=request.user
    ).exclude(notif_type='dm').select_related('sender', 'sender__gamer_profile', 'post').order_by('-created_at')[:60]
    # فقط نوتیف‌های غیر-DM رو بخوانده بزن
    Notification.objects.filter(
        recipient=request.user, is_read=False
    ).exclude(notif_type='dm').update(is_read=True)
    return render(request, 'community/notifications.html', {'notifs': notifs, 'has_unread': has_unread})


@login_required
@require_POST
def notifications_mark_all_read(request):
    """AJAX: همه نوتیف‌های خوانده‌نشده را خوانده می‌کند"""
    Notification.objects.filter(
        recipient=request.user, is_read=False
    ).exclude(notif_type='dm').update(is_read=True)
    return JsonResponse({'ok': True})


@login_required
def notifications_count(request):
    # DM ها توی chat badge نشون داده می‌شن، نه notification bell
    count = Notification.objects.filter(
        recipient=request.user,
        is_read=False,
    ).exclude(notif_type='dm').count()
    return JsonResponse({'count': count})


# ═══════════════════════════════════════
#  DIRECT MESSAGES
# ═══════════════════════════════════════

@login_required
def inbox(request):
    # self-DM notification ها (از پنل ادمین به خود) رو پاک کن
    Notification.objects.filter(
        recipient=request.user,
        sender=request.user,
        notif_type='dm',
        is_read=False,
    ).update(is_read=True)

    convs = request.user.conversations.prefetch_related(
        'participants', 'participants__gamer_profile', 'messages'
    ).order_by('-updated_at')

    blocked_ids = set(Block.objects.filter(blocker=request.user).values_list('blocked_id', flat=True))
    pinned_conv_ids = set(PinnedConversation.objects.filter(user=request.user).values_list('conversation_id', flat=True))
    muted_conv_ids = set(MutedConversation.objects.filter(user=request.user).values_list('conversation_id', flat=True))

    conv_data = []
    for c in convs:
        other = c.other_participant(request.user)
        if not other:
            continue
        if other.id in blocked_ids:
            continue
        unread = c.messages.filter(is_read=False).exclude(sender=request.user).count()
        is_muted = c.id in muted_conv_ids
        is_pinned = c.id in pinned_conv_ids
        if is_muted:
            unread = 0
        conv_data.append({
            'conv': c, 'other': other, 'unread': unread, 'last': c.last_message,
            'is_pinned': is_pinned, 'is_muted': is_muted,
        })

    # پین‌شده → نخونده → بقیه (هر گروه بر اساس آخرین پیام)
    conv_data.sort(key=lambda x: (
        0 if x['is_pinned'] else (1 if x['unread'] > 0 else 2),
        -x['conv'].updated_at.timestamp()
    ))

    dm_unread_count = sum(1 for x in conv_data if x['unread'] > 0)

    group_data   = _get_group_sidebar(request.user)
    channel_data = _get_channel_sidebar(request.user)
    return render(request, 'community/inbox.html', {
        'conv_data':            conv_data,
        'dm_unread_count':      dm_unread_count,
        'group_data':           group_data,
        'channel_data':         channel_data,
        'group_unread_count':   sum(1 for g in group_data if g['unread'] > 0 and not g['is_muted']),
        'channel_unread_count': sum(1 for c in channel_data if c['unread'] > 0 and not c['is_muted']),
    })


@login_required
def conversation(request, username):
    other_user = get_object_or_404(User, username=username)
    if other_user == request.user:
        return redirect('community:inbox')

    # ── DM بدون فالو فقط برای پریمیوم ──
    my_profile = get_or_create_gamer_profile(request.user)
    if not my_profile.is_premium:
        is_mutual = (
            Follow.objects.filter(follower=request.user, following=other_user).exists() or
            Follow.objects.filter(follower=other_user, following=request.user).exists()
        )
        if not is_mutual and other_user.username != 'admin':
            messages.error(request, '✉️ برای ارسال پیام به افرادی که دنبالشان نیستید، اشتراک پریمیوم تهیه کنید.')
            return redirect('community:premium_info')

    # get or create conversation
    conv = Conversation.objects.filter(
        participants=request.user
    ).filter(participants=other_user).first()

    # هیچ‌کس نمی‌تونه به admin پیام بده
    if other_user.username == 'admin':
        messages.error(request, 'ارسال پیام به مدیریت گیم‌بیت امکان‌پذیر نیست.')
        return redirect('community:inbox')

    if not conv:
        conv = Conversation.objects.create()
        conv.participants.add(request.user, other_user)

    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        if content:
            Message.objects.create(
                conversation=conv, sender=request.user, content=content
            )
            conv.save()  # bump updated_at
            Notification.objects.create(
                recipient=other_user,
                sender=request.user,
                notif_type='dm',
                custom_text=content[:100],
            )
        return redirect('community:conversation', username=username)

    msgs = conv.messages.select_related('sender', 'sender__gamer_profile').order_by('created_at')
    other_profile = getattr(other_user, 'gamer_profile', None)

    blocked_ids = set(Block.objects.filter(blocker=request.user).values_list('blocked_id', flat=True))
    pinned_conv_ids = set(PinnedConversation.objects.filter(user=request.user).values_list('conversation_id', flat=True))
    muted_conv_ids = set(MutedConversation.objects.filter(user=request.user).values_list('conversation_id', flat=True))

    is_blocked = other_user.id in blocked_ids
    is_pinned = conv.id in pinned_conv_ids
    is_muted = conv.id in muted_conv_ids

    # sidebar conversation list (same as inbox)
    all_convs = request.user.conversations.prefetch_related(
        'participants', 'participants__gamer_profile', 'messages'
    ).order_by('-updated_at')
    conv_data = []
    for c in all_convs:
        other = c.other_participant(request.user)
        if not other:
            continue
        if other.id in blocked_ids:
            continue
        unread = c.messages.filter(is_read=False).exclude(sender=request.user).count()
        c_is_muted = c.id in muted_conv_ids
        c_is_pinned = c.id in pinned_conv_ids
        if c_is_muted:
            unread = 0
        conv_data.append({
            'conv': c, 'other': other, 'unread': unread, 'last': c.last_message,
            'is_pinned': c_is_pinned, 'is_muted': c_is_muted,
        })
    conv_data.sort(key=lambda x: (
        0 if x['is_pinned'] else (1 if x['unread'] > 0 else 2),
        -x['conv'].updated_at.timestamp()
    ))

    # هیچ‌کس نمی‌تونه به چت مدیریت گیم بیت پاسخ بده (یک‌طرفه برای همه)
    is_locked = is_admin_other
    other_gp = getattr(other_user, 'gamer_profile', None)
    if request.user != other_user and other_gp:
        if not other_gp.allow_dm:
            is_locked = True
        elif other_gp.dm_followers_only:
            # چک کن آیا other_user، request.user رو فالو می‌کنه
            follows_me = Follow.objects.filter(follower=other_user, following=request.user).exists()
            if not follows_me:
                is_locked = True

    return render(request, 'community/conversation.html', {
        'conv': conv,
        'msgs': msgs,
        'other_user': other_user,
        'other_profile': other_profile,
        'conv_data': conv_data,
        'is_admin_other': is_admin_other,
        'is_locked': is_locked,
        'is_blocked': is_blocked,
        'is_pinned': is_pinned,
        'is_muted': is_muted,
    })


@login_required
def send_message_ajax(request, username):
    """AJAX send message — returns JSON"""
    if request.method != 'POST':
        return JsonResponse({'error': 'method'}, status=405)
    other_user = get_object_or_404(User, username=username)
    # کاربر عادی نمی‌تونه به یوزر admin (مدیریت گیم‌بیت) پیام بده
    if other_user.username == 'admin':
        return JsonResponse({'error': 'ارسال پیام به مدیریت گیم‌بیت امکان‌پذیر نیست.'}, status=403)
    # بررسی بلاک
    if Block.objects.filter(blocker=other_user, blocked=request.user).exists():
        return JsonResponse({'error': 'blocked'}, status=403)
    # بررسی تنظیمات پیام
    other_gp = getattr(other_user, 'gamer_profile', None)
    if other_gp:
        if not other_gp.allow_dm:
            return JsonResponse({'ok': False, 'error': 'این کاربر دریافت پیام را غیرفعال کرده'}, status=403)
        if other_gp.dm_followers_only:
            follows_me = Follow.objects.filter(follower=other_user, following=request.user).exists()
            if not follows_me:
                return JsonResponse({'ok': False, 'error': 'این کاربر فقط از دنبال‌کننده‌هایش پیام می‌گیره'}, status=403)

    content = request.POST.get('content', '').strip()
    image_file = request.FILES.get('image')
    attach_file = request.FILES.get('file')

    if not content and not image_file and not attach_file:
        return JsonResponse({'error': 'empty'}, status=400)

    # اعتبارسنجی فایل‌ها
    ALLOWED_IMAGE_EXTS = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
    ALLOWED_FILE_EXTS = {'pdf', 'zip', 'rar', 'mp4', 'mp3', 'doc', 'docx', 'txt'}
    MAX_IMAGE_SIZE = 5 * 1024 * 1024   # 5MB
    MAX_FILE_SIZE  = 20 * 1024 * 1024  # 20MB

    if image_file:
        ext = image_file.name.rsplit('.', 1)[-1].lower()
        if ext not in ALLOWED_IMAGE_EXTS:
            return JsonResponse({'error': 'فرمت عکس مجاز نیست'}, status=400)
        if image_file.size > MAX_IMAGE_SIZE:
            return JsonResponse({'error': 'حجم عکس نباید بیشتر از ۵ مگابایت باشد'}, status=400)

    if attach_file:
        ext = attach_file.name.rsplit('.', 1)[-1].lower()
        if ext not in ALLOWED_FILE_EXTS:
            return JsonResponse({'error': 'فرمت فایل مجاز نیست'}, status=400)
        if attach_file.size > MAX_FILE_SIZE:
            return JsonResponse({'error': 'حجم فایل نباید بیشتر از ۲۰ مگابایت باشد'}, status=400)

    conv = Conversation.objects.filter(
        participants=request.user
    ).filter(participants=other_user).first()
    if not conv:
        conv = Conversation.objects.create()
        conv.participants.add(request.user, other_user)

    msg = Message(conversation=conv, sender=request.user, content=content)
    if image_file:
        msg.image = image_file
    if attach_file:
        msg.file = attach_file
        msg.file_name = attach_file.name
    msg.save()
    conv.save()

    # نوتیف برای گیرنده بساز
    notif_text = content[:100] if content else ('📎 فایل' if attach_file else '🖼 عکس')
    Notification.objects.create(
        recipient=other_user,
        sender=request.user,
        notif_type='dm',
        custom_text=notif_text,
    )

    resp = {
        'ok': True,
        'id': msg.id,
        'content': msg.content,
        'created_at': msg.created_at.strftime('%H:%M'),
        'image_url': msg.image.url if msg.image else None,
        'file_url': msg.file.url if msg.file else None,
        'file_name': msg.file_name,
    }
    return JsonResponse(resp)


@login_required
def toggle_block(request, username):
    """بلاک/آنبلاک کردن کاربر"""
    if request.method != 'POST':
        return JsonResponse({'error': 'method'}, status=405)
    other_user = get_object_or_404(User, username=username)
    block, created = Block.objects.get_or_create(blocker=request.user, blocked=other_user)
    if not created:
        block.delete()
        is_blocked = False
    else:
        is_blocked = True

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'ok': True, 'is_blocked': is_blocked})
    return redirect('community:inbox')


@login_required
def toggle_pin_conversation(request, conv_id):
    """پین/آنپین کردن مکالمه"""
    if request.method != 'POST':
        return JsonResponse({'error': 'method'}, status=405)
    conv = get_object_or_404(Conversation, id=conv_id, participants=request.user)
    pin, created = PinnedConversation.objects.get_or_create(user=request.user, conversation=conv)
    if not created:
        pin.delete()
        is_pinned = False
    else:
        is_pinned = True
    return JsonResponse({'ok': True, 'is_pinned': is_pinned})


@login_required
def toggle_mute_conversation(request, conv_id):
    """میوت/آنمیوت کردن مکالمه"""
    if request.method != 'POST':
        return JsonResponse({'error': 'method'}, status=405)
    conv = get_object_or_404(Conversation, id=conv_id, participants=request.user)
    mute, created = MutedConversation.objects.get_or_create(user=request.user, conversation=conv)
    if not created:
        mute.delete()
        is_muted = False
    else:
        is_muted = True
    return JsonResponse({'ok': True, 'is_muted': is_muted})


@login_required
def inbox_unread_count(request):
    """
    تعداد کل پیام‌های نخونده:
      - پیام خصوصی (DM)
      - پیام گروه (بدون میوت)
      - پست کانال (بدون میوت)
    """
    user = request.user

    # ── ۱. DM نخونده ──
    dm_unread = Notification.objects.filter(
        recipient=user, is_read=False, notif_type='dm',
    ).count()

    # ── ۲. گروه نخونده (بدون گروه‌های میوت) ──
    muted_group_ids = set(MutedGroupChat.objects.filter(user=user).values_list('group_id', flat=True))
    group_memberships = GroupMember.objects.filter(user=user).exclude(group_id__in=muted_group_ids)
    group_unread = 0
    for m in group_memberships:
        cutoff = m.last_read_at or m.joined_at
        group_unread += GroupMessage.objects.filter(
            group_id=m.group_id,
            created_at__gt=cutoff,
        ).exclude(sender=user).count()

    # ── ۳. کانال نخونده (بدون کانال‌های میوت) ──
    muted_channel_ids = set(MutedChannel.objects.filter(user=user).values_list('channel_id', flat=True))
    channel_memberships = ChannelMember.objects.filter(user=user).exclude(channel_id__in=muted_channel_ids)
    channel_unread = 0
    for m in channel_memberships:
        cutoff = m.last_read_at or m.joined_at
        channel_unread += ChannelPost.objects.filter(
            channel_id=m.channel_id,
            created_at__gt=cutoff,
        ).count()

    total = dm_unread + group_unread + channel_unread
    return JsonResponse({'count': total})


@login_required
def mark_conversation_read(request, username):
    """AJAX: mark messages and notifications as read for a conversation."""
    if request.method != 'POST':
        return JsonResponse({'error': 'method'}, status=405)
    other_user = get_object_or_404(User, username=username)
    conv = Conversation.objects.filter(
        participants=request.user
    ).filter(participants=other_user).first()
    if conv:
        conv.messages.filter(is_read=False).exclude(sender=request.user).update(is_read=True)
        Notification.objects.filter(
            recipient=request.user,
            sender=other_user,
            notif_type='dm',
            is_read=False,
        ).update(is_read=True)
    return JsonResponse({'ok': True})


@login_required
def conversation_poll(request, username):
    """
    Polling endpoint برای real-time chat:
    - is_blocked_by_other: آیا طرف مقابل ما رو بلاک کرده؟
    - new_messages: پیام‌های جدید بعد از after_id
    """
    other_user = get_object_or_404(User, username=username)
    is_blocked = Block.objects.filter(blocker=other_user, blocked=request.user).exists()

    after_id = request.GET.get('after', 0)
    try:
        after_id = int(after_id)
    except (ValueError, TypeError):
        after_id = 0

    conv = Conversation.objects.filter(
        participants=request.user
    ).filter(participants=other_user).first()

    new_msgs = []
    if conv and after_id:
        qs = conv.messages.filter(id__gt=after_id).select_related('sender', 'sender__gamer_profile').order_by('id')
        for msg in qs:
            is_mine = msg.sender == request.user
            sender_profile = getattr(msg.sender, 'gamer_profile', None)
            avatar_url = None
            if sender_profile and sender_profile.avatar:
                avatar_url = sender_profile.avatar.url
            new_msgs.append({
                'id': msg.id,
                'content': msg.content,
                'created_at': msg.created_at.strftime('%H:%M'),
                'is_mine': is_mine,
                'sender': msg.sender.username,
                'sender_initial': msg.sender.username[0].upper(),
                'avatar_url': avatar_url,
                'image_url': msg.image.url if msg.image else None,
                'file_url': msg.file.url if msg.file else None,
                'file_name': msg.file_name or '',
                'is_admin': msg.sender.username == 'admin',
            })
        # پیام‌های جدید رو read کن
        if new_msgs:
            qs.exclude(sender=request.user).update(is_read=True)

    return JsonResponse({
        'is_blocked_by_other': is_blocked,
        'new_messages': new_msgs,
    })


# ═══════════════════════════════════════
#  POST REACTIONS
# ═══════════════════════════════════════

@login_required
@require_POST
def react_post(request, post_id):
    post     = get_object_or_404(Post, id=post_id)
    rtype    = request.POST.get('reaction', '')
    valid    = [r[0] for r in PostReaction.REACTION_CHOICES]
    if rtype not in valid:
        return JsonResponse({'error': 'invalid'}, status=400)

    existing = PostReaction.objects.filter(user=request.user, post=post).first()

    if existing and existing.reaction_type == rtype:
        existing.delete()
        active = None
    elif existing:
        existing.reaction_type = rtype
        existing.save()
        active = rtype
    else:
        PostReaction.objects.create(user=request.user, post=post, reaction_type=rtype)
        active = rtype
        # notification
        if post.author != request.user:
            Notification.objects.get_or_create(
                recipient=post.author, sender=request.user,
                notif_type='like', post=post
            )

    counts = {}
    for r in PostReaction.REACTION_CHOICES:
        c = post.reactions.filter(reaction_type=r[0]).count()
        if c: counts[r[0]] = c

    return JsonResponse({'active': active, 'counts': counts})


@login_required
def get_post_reactions(request, post_id):
    post   = get_object_or_404(Post, id=post_id)
    counts = {}
    for r in PostReaction.REACTION_CHOICES:
        c = post.reactions.filter(reaction_type=r[0]).count()
        if c: counts[r[0]] = c
    my = PostReaction.objects.filter(user=request.user, post=post).first()
    return JsonResponse({'counts': counts, 'active': my.reaction_type if my else None})


# ═══════════════════════════════════════
#  GAME BACKLOG
# ═══════════════════════════════════════

@login_required
@require_POST
def backlog_add(request):
    name      = request.POST.get('game_name', '').strip()
    status    = request.POST.get('status', 'want')
    plat      = request.POST.get('platform', '')
    cover_url = request.POST.get('cover_url', '').strip()
    if not name:
        return JsonResponse({'error': 'no name'}, status=400)
    obj, created = GameBacklog.objects.get_or_create(
        user=request.user, game_name=name,
        defaults={'status': status, 'platform': plat, 'cover_url': cover_url}
    )
    if not created:
        obj.status   = status
        obj.platform = plat
        if cover_url:
            obj.cover_url = cover_url
        obj.save()
    # Log activity
    ActivityLog.objects.create(user=request.user, activity_type='added_to_list', game_name=name)
    return JsonResponse({'ok': True, 'id': obj.id, 'status': obj.status, 'created': created})


@login_required
@require_POST
def backlog_update(request, item_id):
    obj = get_object_or_404(GameBacklog, id=item_id, user=request.user)
    new_status = None
    if 'status' in request.POST:
        new_status = request.POST['status']
        obj.status = new_status
    if 'rating' in request.POST:
        r = request.POST.get('rating')
        obj.rating = int(r) if r and r.isdigit() else None
    if 'notes' in request.POST:
        obj.notes = request.POST['notes'][:300]
    if 'is_favorite' in request.POST:
        obj.is_favorite = request.POST['is_favorite'] == '1'
    obj.save()
    # Log status activity
    if new_status:
        from django.utils import timezone as tz
        act_map = {'playing': 'started_playing', 'completed': 'completed', 'dropped': 'dropped'}
        if new_status in act_map:
            ActivityLog.objects.update_or_create(
                user=request.user, activity_type=act_map[new_status], game_name=obj.game_name,
                defaults={'extra': {}}
            )
    return JsonResponse({'ok': True, 'status': obj.status, 'rating': obj.rating, 'is_favorite': obj.is_favorite})


@login_required
@require_POST
def backlog_toggle_favorite(request, item_id):
    obj = get_object_or_404(GameBacklog, id=item_id, user=request.user)
    obj.is_favorite = not obj.is_favorite
    obj.save()
    return JsonResponse({'ok': True, 'is_favorite': obj.is_favorite})


@login_required
@require_POST
def backlog_remove(request, item_id):
    obj = get_object_or_404(GameBacklog, id=item_id, user=request.user)
    obj.delete()
    return JsonResponse({'ok': True})


@login_required
def backlog_list(request, username):
    profile_user = get_object_or_404(User, username=username)
    items = GameBacklog.objects.filter(user=profile_user).order_by('-updated_at')
    data = [
        {'id': i.id, 'game_name': i.game_name, 'status': i.status,
         'platform': i.platform, 'rating': i.rating, 'notes': i.notes,
         'cover_url': i.cover_url, 'is_favorite': i.is_favorite,
         'added_at': i.added_at.isoformat()}
        for i in items
    ]
    return JsonResponse({'items': data})


@login_required
def steam_fetch(request):
    """Fetch game info from Steam API by URL or AppID"""
    q = request.GET.get('q', '').strip()
    if not q:
        return JsonResponse({'error': 'no query'}, status=400)

    # Extract AppID from URL or use as-is
    match = re.search(r'/app/(\d+)', q)
    appid = match.group(1) if match else (q if q.isdigit() else None)
    if not appid:
        return JsonResponse({'error': 'invalid Steam URL or AppID'}, status=400)

    try:
        api_url = f'https://store.steampowered.com/api/appdetails?appids={appid}&cc=ir&l=english'
        req = urllib.request.Request(api_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read())

        app_data = data.get(str(appid), {})
        if not app_data.get('success'):
            return JsonResponse({'error': 'بازی پیدا نشد'}, status=404)

        game = app_data['data']
        return JsonResponse({
            'name': game.get('name', ''),
            'cover_url': game.get('header_image', ''),
            'description': game.get('short_description', '')[:200],
            'appid': appid,
            'release_date': game.get('release_date', {}).get('date', ''),
            'genres': [g['description'] for g in game.get('genres', [])[:3]],
        })
    except urllib.error.URLError:
        return JsonResponse({'error': 'اتصال به Steam برقرار نشد'}, status=503)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def steam_search(request):
    """Search games by name using Steam store search"""
    q = request.GET.get('q', '').strip()
    if len(q) < 2:
        return JsonResponse({'results': []})

    try:
        encoded = urllib.parse.quote(q)
        api_url = f'https://store.steampowered.com/api/storesearch/?term={encoded}&l=english&cc=us'
        req = urllib.request.Request(api_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read())

        results = []
        for item in data.get('items', [])[:8]:
            results.append({
                'appid': str(item['id']),
                'name': item['name'],
                'cover_url': item.get('tiny_image', f"https://cdn.akamai.steamstatic.com/steam/apps/{item['id']}/header.jpg"),
            })
        return JsonResponse({'results': results})
    except Exception:
        return JsonResponse({'results': []})


def games_ranking(request):
    """لیست بازی‌های فعال با فیلتر ژانر و جستجو"""
    from dashboard.models import Game, GENRE_CHOICES as GAME_GENRE_CHOICES

    q     = request.GET.get('q', '').strip()
    genre = request.GET.get('genre', '')

    games = Game.objects.filter(is_active=True)

    if q:
        games = games.filter(name__icontains=q)
    if genre and genre != 'all':
        # genres یه JSONField است (list)
        games = games.filter(genres__contains=[genre])

    games = games.order_by('-is_featured', 'name')

    my_backlog = {}
    if request.user.is_authenticated:
        my_backlog = {b.game_name: b for b in GameBacklog.objects.filter(user=request.user)}

    return render(request, 'community/games_ranking.html', {
        'games':        games,
        'q':            q,
        'genre':        genre,
        'genre_choices': GAME_GENRE_CHOICES,
        'my_backlog':   my_backlog,
    })


def game_detail(request, game_id):
    """صفحه جزئیات بازی — گیمری و خفن"""
    from dashboard.models import Game
    from django.db.models import Avg

    game = get_object_or_404(Game, pk=game_id, is_active=True)

    # آمار بک‌لاگ
    backlog_count = GameBacklog.objects.filter(game_name=game.name).count()
    playing_count = GameBacklog.objects.filter(game_name=game.name, status='playing').count()
    completed_count = GameBacklog.objects.filter(game_name=game.name, status='completed').count()

    # میانگین امتیاز جامعه
    avg_rating = GameBacklog.objects.filter(game_name=game.name, rating__isnull=False).aggregate(Avg('rating'))['rating__avg']
    rating_count = GameBacklog.objects.filter(game_name=game.name, rating__isnull=False).count()

    # وضعیت بک‌لاگ کاربر
    my_backlog_item = None
    if request.user.is_authenticated:
        my_backlog_item = GameBacklog.objects.filter(user=request.user, game_name=game.name).first()

    # نظرات بازی
    from .models import GameReview
    reviews = GameReview.objects.filter(game_id=game_id).select_related('user', 'user__gamer_profile').order_by('-created_at')
    my_review = None
    if request.user.is_authenticated:
        my_review = reviews.filter(user=request.user).first()

    # میانگین از نظرات
    review_ratings = [r.rating for r in reviews if r.rating is not None]
    review_avg = round(sum(review_ratings) / len(review_ratings), 1) if review_ratings else None
    review_rating_count = len(review_ratings)

    return render(request, 'community/game_detail.html', {
        'game':            game,
        'backlog_count':   backlog_count,
        'playing_count':   playing_count,
        'completed_count': completed_count,
        'my_backlog_item': my_backlog_item,
        'avg_rating':      avg_rating,
        'rating_count':    rating_count,
        'reviews':            reviews,
        'my_review':          my_review,
        'review_avg':         review_avg,
        'review_rating_count': review_rating_count,
    })


@login_required
def rate_game(request, game_id):
    """AJAX: امتیازدهی به بازی"""
    from dashboard.models import Game
    from django.db.models import Avg
    if request.method != 'POST':
        return JsonResponse({'error': 'method'}, status=405)
    game = get_object_or_404(Game, pk=game_id, is_active=True)
    try:
        score = int(request.POST.get('score', 0))
    except (ValueError, TypeError):
        return JsonResponse({'error': 'invalid score'}, status=400)
    if not (1 <= score <= 5):
        return JsonResponse({'error': 'score must be 1-5'}, status=400)

    item = GameBacklog.objects.filter(user=request.user, game_name=game.name).first()
    if not item:
        return JsonResponse({'error': 'not in backlog'}, status=400)
    item.rating = score
    item.save()

    # Log activity
    ActivityLog.objects.create(
        user=request.user, activity_type='rated',
        game_name=game.name, extra={'rating': score}, game_id=game_id
    )

    avg_rating = GameBacklog.objects.filter(game_name=game.name, rating__isnull=False).aggregate(Avg('rating'))['rating__avg']
    rating_count = GameBacklog.objects.filter(game_name=game.name, rating__isnull=False).count()
    return JsonResponse({'ok': True, 'avg_rating': round(avg_rating, 1) if avg_rating else None, 'rating_count': rating_count})


@login_required
def add_game_review(request, game_id):
    """AJAX: ثبت یا ویرایش نظر برای بازی"""
    from dashboard.models import Game
    from .models import GameReview
    from django.db.models import Avg

    if request.method != 'POST':
        return JsonResponse({'error': 'method'}, status=405)

    game = get_object_or_404(Game, pk=game_id, is_active=True)
    body = request.POST.get('body', '').strip()
    rating_raw = request.POST.get('rating', '').strip()

    if not body:
        return JsonResponse({'error': 'متن نظر نمی‌تواند خالی باشد'}, status=400)
    if len(body) > 1000:
        return JsonResponse({'error': 'نظر خیلی طولانی است (حداکثر ۱۰۰۰ کاراکتر)'}, status=400)

    rating = None
    if rating_raw:
        try:
            rating = int(rating_raw)
            if not (1 <= rating <= 5):
                rating = None
        except ValueError:
            rating = None

    review, created = GameReview.objects.update_or_create(
        user=request.user,
        game_id=game_id,
        defaults={'body': body, 'rating': rating, 'game_name': game.name}
    )

    # آمار به‌روز
    reviews = GameReview.objects.filter(game_id=game_id)
    review_ratings = [r.rating for r in reviews if r.rating is not None]
    review_avg = round(sum(review_ratings) / len(review_ratings), 1) if review_ratings else None

    gp = getattr(request.user, 'gamer_profile', None)
    avatar_url = gp.avatar.url if gp and gp.avatar else None

    return JsonResponse({
        'ok': True,
        'created': created,
        'review': {
            'id': review.id,
            'body': review.body,
            'rating': review.rating,
            'user': request.user.get_full_name() or request.user.username,
            'username': request.user.username,
            'avatar': avatar_url,
            'created_at': _to_jalali(review.created_at, '%Y/%m/%d'),
        },
        'review_avg': review_avg,
        'review_count': reviews.count(),
        'review_rating_count': len(review_ratings),
    })


@login_required
def delete_game_review(request, game_id, review_id):
    """AJAX: حذف نظر"""
    from .models import GameReview
    if request.method != 'POST':
        return JsonResponse({'error': 'method'}, status=405)
    review = get_object_or_404(GameReview, pk=review_id, user=request.user, game_id=game_id)
    review.delete()

    reviews = GameReview.objects.filter(game_id=game_id)
    review_ratings = [r.rating for r in reviews if r.rating is not None]
    review_avg = round(sum(review_ratings) / len(review_ratings), 1) if review_ratings else None

    return JsonResponse({
        'ok': True,
        'review_avg': review_avg,
        'review_count': reviews.count(),
        'review_rating_count': len(review_ratings),
    })


# ═══════════════════════════════════════
#  ACTIVITY FEED
# ═══════════════════════════════════════

@login_required
def activity_feed(request):
    following_ids = Follow.objects.filter(follower=request.user).values_list('following_id', flat=True)
    user_ids = list(following_ids) + [request.user.id]
    activities = ActivityLog.objects.filter(user_id__in=user_ids).select_related('user', 'user__gamer_profile')[:50]
    return render(request, 'community/activity_feed.html', {'activities': activities})


# ═══════════════════════════════════════
#  PROFILE EXTRAS
# ═══════════════════════════════════════

@login_required
def set_pinned_game(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'method'}, status=405)
    game_name = request.POST.get('game_name', '').strip()
    profile = request.user.gamer_profile
    profile.pinned_game_name = game_name
    profile.save()
    return JsonResponse({'ok': True})


# ═══════════════════════════════════════
#  CHALLENGES
# ═══════════════════════════════════════

def challenges_page(request):
    from django.utils import timezone
    now = timezone.now()
    active_challenges = Challenge.objects.filter(is_active=True, end_date__gte=now)
    past_challenges = Challenge.objects.filter(is_active=True, end_date__lt=now)[:5]

    challenges_data = []
    for ch in active_challenges:
        lb = ch.get_leaderboard()
        challenges_data.append({'challenge': ch, 'leaderboard': lb})

    return render(request, 'community/challenges.html', {
        'challenges_data': challenges_data,
        'past_challenges': past_challenges,
    })


# ═══════════════════════════════════════
#  CLUBS
# ═══════════════════════════════════════

def clubs_list(request):
    clubs = Club.objects.filter(is_public=True).annotate(mc=Count('memberships')).order_by('-mc')
    my_clubs = []
    if request.user.is_authenticated:
        my_clubs = Club.objects.filter(memberships__user=request.user)
    return render(request, 'community/clubs_list.html', {'clubs': clubs, 'my_clubs': my_clubs})


@login_required
def create_club(request):
    if request.method == 'POST':
        from django.utils.text import slugify
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        genre_tag = request.POST.get('genre_tag', '').strip()
        if not name:
            from dashboard.models import GENRE_CHOICES as GAME_GENRE_CHOICES
            return render(request, 'community/create_club.html', {'genre_choices': GAME_GENRE_CHOICES, 'error': 'نام گروه الزامی است'})
        slug_val = slugify(name, allow_unicode=True)
        # Ensure unique slug
        base_slug = slug_val
        counter = 1
        while Club.objects.filter(slug=slug_val).exists():
            slug_val = f'{base_slug}-{counter}'
            counter += 1
        club = Club.objects.create(name=name, slug=slug_val, description=description, genre_tag=genre_tag, owner=request.user)
        ClubMember.objects.create(club=club, user=request.user, role='owner')
        return redirect('community:club_detail', slug=slug_val)
    from dashboard.models import GENRE_CHOICES as GAME_GENRE_CHOICES
    return render(request, 'community/create_club.html', {'genre_choices': GAME_GENRE_CHOICES})


def club_detail(request, slug):
    club = get_object_or_404(Club, slug=slug)
    posts = club.posts.select_related('author', 'author__gamer_profile')[:30]
    members = club.memberships.select_related('user', 'user__gamer_profile')[:20]
    is_member = request.user.is_authenticated and club.memberships.filter(user=request.user).exists()
    user_role = None
    if is_member:
        user_role = club.memberships.get(user=request.user).role
    return render(request, 'community/club_detail.html', {
        'club': club, 'posts': posts, 'members': members,
        'is_member': is_member, 'user_role': user_role,
    })


@login_required
def join_club(request, slug):
    if request.method != 'POST':
        return JsonResponse({'error': 'method'}, status=405)
    club = get_object_or_404(Club, slug=slug)
    ClubMember.objects.get_or_create(club=club, user=request.user, defaults={'role': 'member'})
    return JsonResponse({'ok': True, 'member_count': club.member_count})


@login_required
def leave_club(request, slug):
    if request.method != 'POST':
        return JsonResponse({'error': 'method'}, status=405)
    ClubMember.objects.filter(club__slug=slug, user=request.user).exclude(role='owner').delete()
    return JsonResponse({'ok': True})


@login_required
def club_post(request, slug):
    if request.method != 'POST':
        return JsonResponse({'error': 'method'}, status=405)
    club = get_object_or_404(Club, slug=slug)
    if not club.memberships.filter(user=request.user).exists():
        return JsonResponse({'error': 'not a member'}, status=403)
    content = request.POST.get('content', '').strip()
    if content:
        ClubPost.objects.create(club=club, author=request.user, content=content)
    return JsonResponse({'ok': True})


# ═══════════════════════════════════════════════════════════
#  GROUP CHAT VIEWS
# ═══════════════════════════════════════════════════════════

def _get_group_sidebar(user):
    """لیست گروه‌های کاربر برای sidebar"""
    pinned_ids = set(PinnedGroupChat.objects.filter(user=user).values_list('group_id', flat=True))
    muted_ids  = set(MutedGroupChat.objects.filter(user=user).values_list('group_id', flat=True))
    memberships = GroupMember.objects.filter(user=user).select_related(
        'group').order_by('-group__updated_at')
    data = []
    for m in memberships:
        g = m.group
        last = g.last_message
        is_muted  = g.id in muted_ids
        is_pinned = g.id in pinned_ids
        # پیام‌های نخونده: بعد از last_read_at (یا joined_at اگه هنوز باز نشده)
        cutoff = m.last_read_at or m.joined_at
        unread = g.group_messages.filter(
            created_at__gt=cutoff
        ).exclude(sender=user).count()
        data.append({
            'group': g, 'role': m.role,
            'last': last, 'unread': unread,
            'is_pinned': is_pinned, 'is_muted': is_muted,
        })
    data.sort(key=lambda x: (0 if x['is_pinned'] else (1 if x['unread'] > 0 else 2), -x['group'].updated_at.timestamp()))
    return data


def _get_channel_sidebar(user):
    """لیست کانال‌های کاربر برای sidebar"""
    pinned_ids = set(PinnedChannel.objects.filter(user=user).values_list('channel_id', flat=True))
    muted_ids  = set(MutedChannel.objects.filter(user=user).values_list('channel_id', flat=True))
    memberships = ChannelMember.objects.filter(user=user).select_related(
        'channel').order_by('-channel__updated_at')
    data = []
    for m in memberships:
        c = m.channel
        last = c.last_post
        is_muted  = c.id in muted_ids
        is_pinned = c.id in pinned_ids
        # پست‌های نخونده: بعد از last_read_at (یا joined_at اگه هنوز باز نشده)
        cutoff = m.last_read_at or m.joined_at
        unread = c.channel_posts.filter(created_at__gt=cutoff).count()
        data.append({
            'channel': c, 'role': m.role,
            'last': last, 'unread': unread,
            'is_pinned': is_pinned, 'is_muted': is_muted,
        })
    data.sort(key=lambda x: (0 if x['is_pinned'] else (1 if x['unread'] > 0 else 2), -x['channel'].updated_at.timestamp()))
    return data


@login_required
def create_group(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        icon = request.FILES.get('icon')
        member_ids = request.POST.getlist('members')
        if not name:
            return JsonResponse({'error': 'نام گروه الزامی است'}, status=400)
        group = GroupChat.objects.create(
            name=name, description=description,
            icon=icon, created_by=request.user
        )
        GroupMember.objects.create(group=group, user=request.user, role='owner')
        added_members = []
        for uid in member_ids:
            try:
                u = User.objects.get(id=int(uid))
                if u != request.user:
                    GroupMember.objects.get_or_create(group=group, user=u, defaults={'role': 'member'})
                    added_members.append(u)
            except (User.DoesNotExist, ValueError):
                pass

        # پیام خوش‌آمدگویی خودکار در گروه
        GroupMessage.objects.create(
            group=group,
            sender=request.user,
            content=(
                f'👋 گروه «{name}» ایجاد شد!\n'
                f'به گروه خوش اومدید 🎮'
            ),
        )

        # اطلاع‌رسانی به اعضای اضافه‌شده
        for member in added_members:
            Notification.objects.create(
                recipient=member,
                sender=request.user,
                notif_type='group_add',
                custom_text=f'به گروه «{name}» اضافه شدید 👥',
            )

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'ok': True, 'group_id': group.id})
        return redirect('community:group_chat', group_id=group.id)
    # GET — فرم
    following = Follow.objects.filter(follower=request.user).select_related('following', 'following__gamer_profile')
    friends = [f.following for f in following]
    return render(request, 'community/create_group.html', {'friends': friends})


@login_required
def group_chat(request, group_id):
    group = get_object_or_404(GroupChat, id=group_id)
    membership = get_object_or_404(GroupMember, group=group, user=request.user)

    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        image = request.FILES.get('image')
        file  = request.FILES.get('file')
        if content or image or file:
            msg = GroupMessage(group=group, sender=request.user, content=content)
            if image:
                msg.image = image
            if file:
                msg.file = file
                msg.file_name = file.name
            msg.save()
            group.save()  # bump updated_at
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'ok': True, 'msg_id': msg.id if (content or image or file) else None})
        return redirect('community:group_chat', group_id=group_id)

    # وقتی گروه باز میشه، last_read_at رو آپدیت کن
    from django.utils import timezone as tz
    GroupMember.objects.filter(group=group, user=request.user).update(last_read_at=tz.now())

    msgs = group.group_messages.select_related('sender', 'sender__gamer_profile').order_by('created_at')
    members = group.group_members.select_related('user', 'user__gamer_profile').order_by('role', 'joined_at')
    pinned_ids = set(PinnedGroupChat.objects.filter(user=request.user).values_list('group_id', flat=True))
    muted_ids  = set(MutedGroupChat.objects.filter(user=request.user).values_list('group_id', flat=True))

    # sidebar — همه مکالمه‌ها نشون داده میشه
    conv_data   = _get_inbox_sidebar(request.user, show_all=True)
    group_data  = _get_group_sidebar(request.user)
    channel_data = _get_channel_sidebar(request.user)

    return render(request, 'community/group_chat.html', {
        'group': group,
        'msgs': msgs,
        'members': members,
        'membership': membership,
        'is_admin': membership.is_admin,
        'is_pinned': group_id in pinned_ids,
        'is_muted': group_id in muted_ids,
        'conv_data': conv_data,
        'group_data': group_data,
        'channel_data': channel_data,
        'group_unread_count':   sum(g['unread'] for g in group_data if not g['is_muted']),
        'channel_unread_count': sum(c['unread'] for c in channel_data if not c['is_muted']),
    })


@login_required
def group_send_message(request, group_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'method'}, status=405)
    group = get_object_or_404(GroupChat, id=group_id)
    get_object_or_404(GroupMember, group=group, user=request.user)
    content = request.POST.get('content', '').strip()
    image = request.FILES.get('image')
    file  = request.FILES.get('file')
    if not content and not image and not file:
        return JsonResponse({'error': 'empty'}, status=400)
    msg = GroupMessage(group=group, sender=request.user, content=content)
    if image:
        msg.image = image
    if file:
        msg.file = file
        msg.file_name = file.name
    msg.save()
    group.save()
    sender_profile = getattr(request.user, 'gamer_profile', None)
    return JsonResponse({
        'ok': True,
        'msg': {
            'id': msg.id,
            'content': msg.content,
            'sender': request.user.username,
            'sender_name': request.user.get_full_name() or request.user.username,
            'avatar': sender_profile.avatar.url if sender_profile and sender_profile.avatar else None,
            'time': msg.created_at.strftime('%H:%M'),
            'image': msg.image.url if msg.image else None,
            'file': msg.file.url if msg.file else None,
            'file_name': msg.file_name,
        }
    })


@login_required
def group_poll_messages(request, group_id):
    group = get_object_or_404(GroupChat, id=group_id)
    get_object_or_404(GroupMember, group=group, user=request.user)
    after_id = int(request.GET.get('after', 0))
    msgs = group.group_messages.filter(id__gt=after_id).select_related('sender', 'sender__gamer_profile')
    result = []
    for m in msgs:
        sp = getattr(m.sender, 'gamer_profile', None)
        result.append({
            'id': m.id,
            'content': m.content,
            'sender': m.sender.username,
            'sender_name': m.sender.get_full_name() or m.sender.username,
            'avatar': sp.avatar.url if sp and sp.avatar else None,
            'time': m.created_at.strftime('%H:%M'),
            'is_me': m.sender == request.user,
            'image': m.image.url if m.image else None,
            'file': m.file.url if m.file else None,
            'file_name': m.file_name,
        })
    return JsonResponse({'msgs': result})


@login_required
def group_pin(request, group_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'method'}, status=405)
    group = get_object_or_404(GroupChat, id=group_id)
    get_object_or_404(GroupMember, group=group, user=request.user)
    obj, created = PinnedGroupChat.objects.get_or_create(user=request.user, group=group)
    if not created:
        obj.delete()
    return JsonResponse({'ok': True, 'is_pinned': created})


@login_required
def group_mute(request, group_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'method'}, status=405)
    group = get_object_or_404(GroupChat, id=group_id)
    get_object_or_404(GroupMember, group=group, user=request.user)
    obj, created = MutedGroupChat.objects.get_or_create(user=request.user, group=group)
    if not created:
        obj.delete()
    return JsonResponse({'ok': True, 'is_muted': created})


@login_required
def group_leave(request, group_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'method'}, status=405)
    group = get_object_or_404(GroupChat, id=group_id)
    GroupMember.objects.filter(group=group, user=request.user).exclude(role='owner').delete()
    return JsonResponse({'ok': True})


@login_required
def group_add_admin(request, group_id, username):
    if request.method != 'POST':
        return JsonResponse({'error': 'method'}, status=405)
    group = get_object_or_404(GroupChat, id=group_id)
    membership = get_object_or_404(GroupMember, group=group, user=request.user)
    if not membership.is_admin:
        return JsonResponse({'error': 'forbidden'}, status=403)
    target = get_object_or_404(User, username=username)
    GroupMember.objects.filter(group=group, user=target).update(role='admin')
    return JsonResponse({'ok': True})


@login_required
def group_remove_admin(request, group_id, username):
    if request.method != 'POST':
        return JsonResponse({'error': 'method'}, status=405)
    group = get_object_or_404(GroupChat, id=group_id)
    membership = get_object_or_404(GroupMember, group=group, user=request.user)
    if membership.role != 'owner':
        return JsonResponse({'error': 'forbidden'}, status=403)
    target = get_object_or_404(User, username=username)
    GroupMember.objects.filter(group=group, user=target, role='admin').update(role='member')
    return JsonResponse({'ok': True})


@login_required
def group_remove_member(request, group_id, username):
    if request.method != 'POST':
        return JsonResponse({'error': 'method'}, status=405)
    group = get_object_or_404(GroupChat, id=group_id)
    membership = get_object_or_404(GroupMember, group=group, user=request.user)
    if not membership.is_admin:
        return JsonResponse({'error': 'forbidden'}, status=403)
    target = get_object_or_404(User, username=username)
    GroupMember.objects.filter(group=group, user=target).exclude(role='owner').delete()
    return JsonResponse({'ok': True})


@login_required
def group_add_member(request, group_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'method'}, status=405)
    group = get_object_or_404(GroupChat, id=group_id)
    membership = get_object_or_404(GroupMember, group=group, user=request.user)
    if not membership.is_admin:
        return JsonResponse({'error': 'forbidden'}, status=403)
    username = request.POST.get('username', '').strip()
    target = get_object_or_404(User, username=username)
    _, created = GroupMember.objects.get_or_create(group=group, user=target, defaults={'role': 'member'})
    if created:
        # پیام اطلاع‌رسانی در خود گروه
        GroupMessage.objects.create(
            group=group,
            sender=request.user,
            content=f'👥 {target.username} به گروه اضافه شد.',
        )
        # نوتیف برای کاربر اضافه‌شده
        Notification.objects.create(
            recipient=target,
            sender=request.user,
            notif_type='group_add',
            custom_text=f'به گروه «{group.name}» اضافه شدید 👥',
        )
    return JsonResponse({'ok': True})


def _get_inbox_sidebar(user, show_all=False):
    """نسخه helper برای sidebar DM — فقط نخونده + پین‌شده نشون میده"""
    blocked_ids = set(Block.objects.filter(blocker=user).values_list('blocked_id', flat=True))
    pinned_ids  = set(PinnedConversation.objects.filter(user=user).values_list('conversation_id', flat=True))
    muted_ids   = set(MutedConversation.objects.filter(user=user).values_list('conversation_id', flat=True))
    convs = user.conversations.prefetch_related(
        'participants', 'participants__gamer_profile', 'messages'
    ).order_by('-updated_at')
    data = []
    for c in convs:
        other = c.other_participant(user)
        if not other or other.id in blocked_ids:
            continue
        unread = c.messages.filter(is_read=False).exclude(sender=user).count()
        is_muted = c.id in muted_ids
        if is_muted:
            unread = 0
        is_pinned = c.id in pinned_ids
        # فقط نخونده یا پین‌شده — مگر show_all باشه
        if not show_all and unread == 0 and not is_pinned:
            continue
        data.append({
            'conv': c, 'other': other, 'unread': unread, 'last': c.last_message,
            'is_pinned': is_pinned, 'is_muted': is_muted,
        })
    data.sort(key=lambda x: (
        0 if x['is_pinned'] else (1 if x['unread'] > 0 else 2),
        -x['conv'].updated_at.timestamp()
    ))
    return data


# ═══════════════════════════════════════════════════════════
#  CHANNEL VIEWS
# ═══════════════════════════════════════════════════════════

@login_required
def create_channel(request):
    if request.method == 'POST':
        name        = request.POST.get('name', '').strip()
        username    = request.POST.get('username', '').strip().lower()
        description = request.POST.get('description', '').strip()
        icon        = request.FILES.get('icon')
        is_public   = request.POST.get('is_public') == 'on'
        if not name or not username:
            return render(request, 'community/create_channel.html', {'error': 'نام و نام‌کاربری الزامی است'})
        if Channel.objects.filter(username=username).exists():
            return render(request, 'community/create_channel.html', {'error': 'این نام‌کاربری قبلاً گرفته شده'})
        channel = Channel.objects.create(
            name=name, username=username, description=description,
            icon=icon, owner=request.user, is_public=is_public
        )
        ChannelMember.objects.create(channel=channel, user=request.user, role='owner')
        return redirect('community:channel_view', channel_username=username)
    return render(request, 'community/create_channel.html')


@login_required
def channel_view(request, channel_username):
    channel = get_object_or_404(Channel, username=channel_username)
    membership = ChannelMember.objects.filter(channel=channel, user=request.user).first()
    is_subscribed = membership is not None
    can_post = membership and membership.can_post

    pinned_ids = set(PinnedChannel.objects.filter(user=request.user).values_list('channel_id', flat=True))
    muted_ids  = set(MutedChannel.objects.filter(user=request.user).values_list('channel_id', flat=True))

    posts = channel.channel_posts.select_related('author', 'author__gamer_profile').prefetch_related('channel_reactions')

    # ری‌اکشن‌های کاربر
    # set از "post_id:emoji" — قابل چک در template
    my_reactions = set()
    if is_subscribed:
        for r in ChannelReaction.objects.filter(post__channel=channel, user=request.user):
            my_reactions.add(f"{r.post_id}:{r.emoji}")

    # وقتی کانال باز میشه، last_read_at رو آپدیت کن
    if membership:
        from django.utils import timezone as tz
        ChannelMember.objects.filter(channel=channel, user=request.user).update(last_read_at=tz.now())

    conv_data    = _get_inbox_sidebar(request.user, show_all=True)
    group_data   = _get_group_sidebar(request.user)
    channel_data = _get_channel_sidebar(request.user)

    return render(request, 'community/channel_view.html', {
        'channel': channel,
        'membership': membership,
        'is_subscribed': is_subscribed,
        'can_post': can_post,
        'posts': posts,
        'my_reactions': my_reactions,
        'is_pinned': channel.id in pinned_ids,
        'is_muted': channel.id in muted_ids,
        'conv_data': conv_data,
        'group_data': group_data,
        'channel_data': channel_data,
        'group_unread_count':   sum(g['unread'] for g in group_data if not g['is_muted']),
        'channel_unread_count': sum(c['unread'] for c in channel_data if not c['is_muted']),
    })


@login_required
def channel_post(request, channel_username):
    if request.method != 'POST':
        return JsonResponse({'error': 'method'}, status=405)
    channel = get_object_or_404(Channel, username=channel_username)
    membership = get_object_or_404(ChannelMember, channel=channel, user=request.user)
    if not membership.can_post:
        return JsonResponse({'error': 'forbidden'}, status=403)
    content = request.POST.get('content', '').strip()
    image   = request.FILES.get('image')
    if not content and not image:
        return JsonResponse({'error': 'empty'}, status=400)
    post = ChannelPost.objects.create(channel=channel, author=request.user, content=content)
    if image:
        post.image = image
        post.save()
    channel.save()
    return JsonResponse({'ok': True, 'post_id': post.id})


@login_required
def channel_react(request, post_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'method'}, status=405)
    post = get_object_or_404(ChannelPost, id=post_id)
    get_object_or_404(ChannelMember, channel=post.channel, user=request.user)
    emoji = request.POST.get('emoji', '🔥')
    obj = ChannelReaction.objects.filter(post=post, user=request.user).first()
    if obj:
        if obj.emoji == emoji:
            obj.delete()
            reacted = False
        else:
            obj.emoji = emoji
            obj.save()
            reacted = True
    else:
        ChannelReaction.objects.create(post=post, user=request.user, emoji=emoji)
        reacted = True
    counts = {}
    for r in ChannelReaction.objects.filter(post=post):
        counts[r.emoji] = counts.get(r.emoji, 0) + 1
    return JsonResponse({'ok': True, 'reacted': reacted, 'counts': counts})


@login_required
def channel_pin(request, channel_username):
    if request.method != 'POST':
        return JsonResponse({'error': 'method'}, status=405)
    channel = get_object_or_404(Channel, username=channel_username)
    obj, created = PinnedChannel.objects.get_or_create(user=request.user, channel=channel)
    if not created:
        obj.delete()
    return JsonResponse({'ok': True, 'is_pinned': created})


@login_required
def channel_mute(request, channel_username):
    if request.method != 'POST':
        return JsonResponse({'error': 'method'}, status=405)
    channel = get_object_or_404(Channel, username=channel_username)
    obj, created = MutedChannel.objects.get_or_create(user=request.user, channel=channel)
    if not created:
        obj.delete()
    return JsonResponse({'ok': True, 'is_muted': created})


@login_required
def channel_add_admin(request, channel_username, username):
    if request.method != 'POST':
        return JsonResponse({'error': 'method'}, status=405)
    channel = get_object_or_404(Channel, username=channel_username)
    membership = get_object_or_404(ChannelMember, channel=channel, user=request.user)
    if membership.role != 'owner':
        return JsonResponse({'error': 'forbidden'}, status=403)
    target = get_object_or_404(User, username=username)
    ChannelMember.objects.filter(channel=channel, user=target).update(role='admin')
    return JsonResponse({'ok': True})


@login_required
def channel_remove_admin(request, channel_username, username):
    if request.method != 'POST':
        return JsonResponse({'error': 'method'}, status=405)
    channel = get_object_or_404(Channel, username=channel_username)
    membership = get_object_or_404(ChannelMember, channel=channel, user=request.user)
    if membership.role != 'owner':
        return JsonResponse({'error': 'forbidden'}, status=403)
    target = get_object_or_404(User, username=username)
    ChannelMember.objects.filter(channel=channel, user=target, role='admin').update(role='subscriber')
    return JsonResponse({'ok': True})


@login_required
def channel_settings(request, channel_username):
    from .models import ChannelJoinRequest, GroupChat
    channel = get_object_or_404(Channel, username=channel_username)
    membership = get_object_or_404(ChannelMember, channel=channel, user=request.user)
    if membership.role != 'owner':
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden()

    if request.method == 'POST':
        action = request.POST.get('action', 'save')

        if action == 'save':
            channel.name             = request.POST.get('name', channel.name).strip()
            channel.description      = request.POST.get('description', channel.description).strip()
            channel.is_public        = request.POST.get('is_public') == 'on'
            channel.show_author      = request.POST.get('show_author') == 'on'
            channel.require_approval = request.POST.get('require_approval') == 'on'
            channel.reactions_enabled = request.POST.get('reactions_enabled') == 'on'
            channel.comments_enabled  = request.POST.get('comments_enabled') == 'on'
            # لینک گروه
            group_id = request.POST.get('linked_group', '')
            if group_id:
                try:
                    channel.linked_group_id = int(group_id)
                except (ValueError, TypeError):
                    channel.linked_group = None
            else:
                channel.linked_group = None
            if request.FILES.get('icon'):
                channel.icon = request.FILES['icon']
            channel.save()
            return JsonResponse({'ok': True, 'msg': 'تنظیمات ذخیره شد ✓'})

        elif action == 'respond_join':
            req_id = request.POST.get('request_id')
            resp   = request.POST.get('response')  # accept / reject
            jr = get_object_or_404(ChannelJoinRequest, id=req_id, channel=channel)
            if resp == 'accept':
                jr.status = 'accepted'
                jr.save()
                ChannelMember.objects.get_or_create(channel=channel, user=jr.user, defaults={'role': 'subscriber'})
            else:
                jr.status = 'rejected'
                jr.save()
            return JsonResponse({'ok': True})

        elif action == 'remove_member':
            target_user = get_object_or_404(User, username=request.POST.get('username'))
            ChannelMember.objects.filter(channel=channel, user=target_user).exclude(role='owner').delete()
            return JsonResponse({'ok': True})

        elif action == 'promote':
            target_user = get_object_or_404(User, username=request.POST.get('username'))
            ChannelMember.objects.filter(channel=channel, user=target_user, role='subscriber').update(role='admin')
            return JsonResponse({'ok': True})

        elif action == 'demote':
            target_user = get_object_or_404(User, username=request.POST.get('username'))
            ChannelMember.objects.filter(channel=channel, user=target_user, role='admin').update(role='subscriber')
            return JsonResponse({'ok': True})

        elif action == 'delete_post':
            post_id = request.POST.get('post_id')
            ChannelPost.objects.filter(id=post_id, channel=channel).delete()
            return JsonResponse({'ok': True})

    # GET
    members = channel.channel_members.select_related('user', 'user__gamer_profile').order_by('role', 'joined_at')
    join_requests = ChannelJoinRequest.objects.filter(channel=channel, status='pending').select_related('user', 'user__gamer_profile')
    my_groups = GroupChat.objects.filter(group_members__user=request.user)

    return render(request, 'community/channel_settings.html', {
        'channel':       channel,
        'members':       members,
        'join_requests': join_requests,
        'my_groups':     my_groups,
    })


@login_required
def channel_subscribe(request, channel_username):
    """Override: handle require_approval"""
    if request.method != 'POST':
        return JsonResponse({'error': 'method'}, status=405)
    from .models import ChannelJoinRequest
    channel = get_object_or_404(Channel, username=channel_username)
    obj = ChannelMember.objects.filter(channel=channel, user=request.user).first()
    if obj:
        if obj.role != 'owner':
            obj.delete()
        return JsonResponse({'ok': True, 'subscribed': False, 'count': channel.subscriber_count, 'pending': False})

    if channel.require_approval and not channel.is_public:
        jr, created = ChannelJoinRequest.objects.get_or_create(channel=channel, user=request.user)
        return JsonResponse({'ok': True, 'subscribed': False, 'count': channel.subscriber_count, 'pending': True})

    ChannelMember.objects.create(channel=channel, user=request.user, role='subscriber')
    return JsonResponse({'ok': True, 'subscribed': True, 'count': channel.subscriber_count, 'pending': False})


# ══════════════════════════════════════════════
#  گیمر یابی — Gamer Finder
# ══════════════════════════════════════════════
import math
import random
from decimal import Decimal, ROUND_HALF_UP
from django.core.cache import cache


def _haversine_km(lat1, lng1, lat2, lng2):
    """Returns distance in km between two lat/lng pairs."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


@login_required
def gamer_finder_page(request):
    profile = get_or_create_gamer_profile(request.user)

    # بازی‌های کاربر جاری — از backlog (همه بازی‌ها) + favorite_games دستی
    my_backlog_games = list(
        GameBacklog.objects.filter(user=request.user)
        .exclude(status='dropped')
        .values_list('game_name', flat=True)
        .order_by('-updated_at')[:50]
    )
    my_fav_games = profile.get_favorite_games_list()
    # ترکیب + حذف تکراری با حفظ ترتیب
    seen = set()
    my_games = []
    for g in my_backlog_games + my_fav_games:
        if g and g not in seen:
            seen.add(g)
            my_games.append(g)

    # Parse city/province from label
    user_label = (profile.location_label or '').strip()
    user_city = ''
    if user_label:
        parts = [p.strip() for p in user_label.split('—') if p.strip()]
        user_city = parts[-1] if parts else user_label

    has_location = bool(user_label)

    city_gamers_list = []   # has lat/lng → map markers
    all_citymates    = []   # all matching → همشهری‌ها tab
    all_games_set    = set(my_games)

    def _label_parts(label):
        """استخراج استان و شهر از label"""
        parts = [p.strip() for p in label.replace('—', '—').split('—') if p.strip()]
        province = parts[0] if len(parts) >= 2 else ''
        city     = parts[-1] if parts else label.strip()
        return province, city

    user_province, user_city_key = _label_parts(user_label)

    if has_location:
        qs = GamerProfile.objects.filter(
            show_location=True,
            location_label__gt='',
        ).exclude(user=request.user).select_related('user')

        citymate_users = [p.user_id for p in qs[:500]]

        # بازی‌های همشهری‌ها — bulk از backlog
        backlog_qs = (
            GameBacklog.objects
            .filter(user_id__in=citymate_users)
            .exclude(status='dropped')
            .values('user_id', 'game_name')
            .order_by('user_id', '-updated_at')
        )
        user_games_map = {}
        for row in backlog_qs:
            uid = row['user_id']
            if uid not in user_games_map:
                user_games_map[uid] = []
            if len(user_games_map[uid]) < 8:
                user_games_map[uid].append(row['game_name'])

        # کاربرایی که از قبل فالو شدن
        following_ids = set(
            Follow.objects.filter(follower=request.user, following_id__in=citymate_users)
            .values_list('following_id', flat=True)
        )
        # درخواست‌های فالو در انتظار
        pending_ids = set(
            FollowRequest.objects.filter(
                from_user=request.user, to_user_id__in=citymate_users, status='pending'
            ).values_list('to_user_id', flat=True)
        )

        for p in qs[:500]:
            if not p.location_label:
                continue
            other_province, other_city_key = _label_parts(p.location_label)
            match = (user_city_key and user_city_key == other_city_key) or \
                    (user_province and user_province == other_province)
            if not match:
                continue

            platforms = p.get_platforms_list() or ['pc']
            primary   = platforms[0] if platforms else 'pc'
            games = user_games_map.get(p.user_id) or p.get_favorite_games_list()[:8]
            all_games_set.update(games)

            is_following      = p.user_id in following_ids
            has_follow_request = p.user_id in pending_ids

            base = {
                'username':           p.user.username,
                'display_name':       p.user.get_full_name() or p.user.username,
                'avatar':             p.avatar.url if p.avatar else None,
                'location_label':     p.location_label,
                'games':              games,
                'platforms':          platforms,
                'platform':           primary,
                'profile_url':        f'/profile/{p.user.username}/',
                'dm_url':             f'/dm/{p.user.username}/',
                'is_private':         p.is_private,
                'allow_dm':           p.allow_dm,
                'dm_followers_only':  p.dm_followers_only,
                'is_following':       is_following,
                'has_follow_request': has_follow_request,
            }
            all_citymates.append(base)

            if p.location_lat and p.location_lng and p.show_on_map:
                offset_lat = float(p.location_lat) + random.uniform(-0.003, 0.003)
                offset_lng = float(p.location_lng) + random.uniform(-0.003, 0.003)
                city_gamers_list.append({
                    **base,
                    'lat': round(offset_lat, 5),
                    'lng': round(offset_lng, 5),
                })

    # ALL_GAMES = بازی‌های خودم + بازی‌های همشهری‌ها (مرتب شده)
    all_games = sorted(all_games_set, key=lambda x: x.lower())

    return render(request, 'community/gamer_finder.html', {
        'user_lat':          float(profile.location_lat) if profile.location_lat else None,
        'user_lng':          float(profile.location_lng) if profile.location_lng else None,
        'user_label':        user_label,
        'has_location':      has_location,
        'my_games':          my_games,
        'all_games_json':    json.dumps(all_games, ensure_ascii=False),
        'city_gamers_json':  json.dumps(city_gamers_list, ensure_ascii=False),
        'citymates_json':    json.dumps(all_citymates, ensure_ascii=False),
        'city_gamers_count': len(city_gamers_list),
        'citymates_count':   len(all_citymates),
        'user_city':         user_city,
    })


@login_required
def gamer_finder_search(request):
    """API endpoint — جستجو"""
    # Rate limiting: 10 req/min per user
    cache_key = f'gf_ratelimit_{request.user.id}'
    hit_count = cache.get(cache_key, 0)
    if hit_count >= 10:
        return JsonResponse({'error': 'rate_limited', 'message': 'حداکثر ۱۰ درخواست در دقیقه'}, status=429)
    cache.set(cache_key, hit_count + 1, 60)

    try:
        lat = float(request.GET.get('lat', ''))
        lng = float(request.GET.get('lng', ''))
        radius_km = float(request.GET.get('radius_km', '5'))
    except (ValueError, TypeError):
        return JsonResponse({'error': 'invalid_params'}, status=400)

    game_filter = request.GET.get('game', '').strip()

    # Rough bounding box first (avoid full table scan)
    deg_margin = radius_km / 111.0 + 0.05
    profiles = GamerProfile.objects.filter(
        show_location=True,
        location_lat__isnull=False,
        location_lng__isnull=False,
        location_lat__gte=lat - deg_margin,
        location_lat__lte=lat + deg_margin,
        location_lng__gte=lng - deg_margin,
        location_lng__lte=lng + deg_margin,
    ).exclude(user=request.user).select_related('user')

    if game_filter:
        profiles = profiles.filter(favorite_games__icontains=game_filter)

    results = []
    for p in profiles:
        dist = _haversine_km(lat, lng, float(p.location_lat), float(p.location_lng))
        if dist <= radius_km:
            results.append((dist, p))
        if len(results) >= 100:  # hard cap before sort
            break

    results.sort(key=lambda x: x[0])
    results = results[:50]

    gamers = []
    for dist, p in results:
        # Privacy: add ±0.003° random offset (~300m)
        offset_lat = float(p.location_lat) + random.uniform(-0.003, 0.003)
        offset_lng = float(p.location_lng) + random.uniform(-0.003, 0.003)
        avatar_url = p.avatar.url if p.avatar else None
        gamers.append({
            'username': p.user.username,
            'display_name': p.user.get_full_name() or p.user.username,
            'avatar': avatar_url,
            'location_label': p.location_label,
            'games': p.get_favorite_games_list()[:5],
            'lat': round(offset_lat, 5),
            'lng': round(offset_lng, 5),
            'dist_km': round(dist, 1),
            'profile_url': f'/profile/{p.user.username}/',
            'dm_url': f'/dm/{p.user.username}/',
        })

    return JsonResponse({'gamers': gamers})


@login_required
def save_location(request):
    """ذخیره موقعیت کاربر — AJAX POST"""
    if request.method != 'POST':
        return JsonResponse({'error': 'method'}, status=405)

    import json as _json
    try:
        body = _json.loads(request.body)
    except Exception:
        body = request.POST

    profile = get_or_create_gamer_profile(request.user)

    action = body.get('action', '')
    if action == 'clear':
        profile.location_lat = None
        profile.location_lng = None
        profile.location_label = ''
        profile.show_location = False
        profile.save(update_fields=['location_lat', 'location_lng', 'location_label', 'show_location'])
        return JsonResponse({'ok': True, 'cleared': True})

    try:
        lat = float(body.get('lat', ''))
        lng = float(body.get('lng', ''))
    except (ValueError, TypeError):
        return JsonResponse({'error': 'invalid_coords'}, status=400)

    # Round to 3 decimal places (~111m accuracy)
    lat = round(lat, 3)
    lng = round(lng, 3)

    label = str(body.get('location_label', '')).strip()[:100]
    show = bool(body.get('show_location', False))

    profile.location_lat = Decimal(str(lat))
    profile.location_lng = Decimal(str(lng))
    profile.location_label = label
    profile.show_location = show
    profile.save(update_fields=['location_lat', 'location_lng', 'location_label', 'show_location'])
    return JsonResponse({'ok': True})


# ══════════════════════════════════════════════════════════
#  🎰  گردونه شانس
# ══════════════════════════════════════════════════════════

def _spin_eligible(user, wheel):
    """True اگر کاربر می‌تواند رایگان بچرخاند (cooldown گذشته یا محدودیت ندارد)."""
    from datetime import timedelta
    if wheel.cooldown_hours == 0:
        return True
    last = SpinRecord.objects.filter(user=user, wheel=wheel).order_by('-spun_at').first()
    if last is None:
        return True
    return (timezone.now() - last.spun_at).total_seconds() >= wheel.cooldown_hours * 3600


def _spin_remaining_secs(user, wheel):
    """ثانیه‌های باقی‌مانده (فقط برای backward compat — از _next_spin_ts استفاده کن)."""
    from datetime import timedelta
    if wheel.cooldown_hours == 0:
        return 0
    last = SpinRecord.objects.filter(user=user, wheel=wheel).order_by('-spun_at').first()
    if last is None:
        return 0
    remaining = (last.spun_at + timedelta(hours=wheel.cooldown_hours) - timezone.now()).total_seconds()
    return max(0, int(remaining))


def _next_spin_ts(user, wheel):
    """Unix timestamp (int) لحظه‌ای که کاربر می‌تواند رایگان بچرخاند.
    اگر الان می‌تواند → 0 برمی‌گرداند.
    این عدد ثابت است — با هر refresh یکسان است → تایمر هیچ‌وقت ریست نمی‌شود.
    """
    from datetime import timedelta
    if wheel.cooldown_hours == 0:
        return 0
    last = SpinRecord.objects.filter(user=user, wheel=wheel).order_by('-spun_at').first()
    if last is None:
        return 0
    next_dt = last.spun_at + timedelta(hours=wheel.cooldown_hours)
    if next_dt <= timezone.now():
        return 0
    return int(next_dt.timestamp())


def spin_list(request):
    """لیست همه گردونه‌های فعال — بدون لاگین هم قابل مشاهده"""
    wheels = SpinWheel.objects.filter(is_active=True).prefetch_related('items').order_by('order', '-created_at')

    logged_in = request.user.is_authenticated
    my_profile = get_or_create_gamer_profile(request.user) if logged_in else None

    wheel_data = []
    for wheel in wheels:
        if logged_in:
            can_spin_free = _spin_eligible(user=request.user, wheel=wheel)
            next_spin_ts  = _next_spin_ts(user=request.user, wheel=wheel)
        else:
            can_spin_free = False
            next_spin_ts  = 0
        active_items = list(wheel.items.filter(is_active=True).order_by('order', 'id'))
        items_json   = json.dumps([{
            'name': i.name, 'emoji': i.emoji,
            'color': i.color, 'probability': i.probability,
        } for i in active_items])
        wheel_data.append({
            'wheel':         wheel,
            'can_spin_free': can_spin_free,
            'next_spin_ts':  next_spin_ts,
            'item_count':    len(active_items),
            'items':         active_items,
            'items_json':    items_json,
        })

    return render(request, 'community/spin_list.html', {
        'wheel_data': wheel_data,
        'my_profile': my_profile,
    })


def spin_detail(request, wheel_id):
    """صفحه یک گردونه + اطلاعات برای Canvas — بدون لاگین هم قابل مشاهده"""
    wheel = get_object_or_404(SpinWheel, pk=wheel_id, is_active=True)
    items = list(wheel.items.filter(is_active=True).order_by('order', 'id'))

    logged_in = request.user.is_authenticated
    my_profile = get_or_create_gamer_profile(request.user) if logged_in else None

    if logged_in:
        can_spin_free  = _spin_eligible(user=request.user, wheel=wheel)
        next_spin_ts   = _next_spin_ts(user=request.user, wheel=wheel)
        remaining_secs = _spin_remaining_secs(user=request.user, wheel=wheel)
        try:
            zarban_balance = ZarbanWallet.get_or_create_for(request.user).balance
        except Exception:
            zarban_balance = 0
        can_spin     = can_spin_free or (wheel.cost_zarban > 0 and zarban_balance >= wheel.cost_zarban)
        recent_spins = SpinRecord.objects.filter(
            user=request.user, wheel=wheel
        ).select_related('item').order_by('-spun_at')[:5]
    else:
        can_spin_free  = False
        next_spin_ts   = 0
        remaining_secs = 0
        zarban_balance = 0
        can_spin       = False
        recent_spins   = []

    items_json = json.dumps([{
        'id': item.pk, 'name': item.name,
        'emoji': item.emoji, 'color': item.color,
        'probability': item.probability,
    } for item in items])

    return render(request, 'community/spin_wheel.html', {
        'wheel':          wheel,
        'items':          items,
        'items_json':     items_json,
        'can_spin_free':  can_spin_free,
        'next_spin_ts':   next_spin_ts,
        'remaining_secs': remaining_secs,
        'zarban_balance': zarban_balance,
        'my_profile':     my_profile,
        'recent_spins':   recent_spins,
        'can_spin':       can_spin,
    })


@login_required
@require_POST
def spin_go(request, wheel_id):
    """انجام چرخش — AJAX POST (سیستم cooldown-based)"""
    wheel = get_object_or_404(SpinWheel, pk=wheel_id, is_active=True)
    # ⚠️ ترتیب باید دقیقاً با spin_detail یکی باشه تا won_index درست باشه
    items = list(wheel.items.filter(is_active=True).order_by('order', 'id'))

    if not items:
        return JsonResponse({'ok': False, 'error': 'این گردونه آیتمی ندارد'})

    can_spin_free = _spin_eligible(user=request.user, wheel=wheel)
    cost = 0

    if not can_spin_free:
        # cooldown تموم نشده — آیا با ضربان می‌تونه؟
        if wheel.cost_zarban == 0:
            remaining = _spin_remaining_secs(request.user, wheel)
            h, m = divmod(remaining // 60, 60)
            wait_str = f'{h} ساعت و {m} دقیقه' if h > 0 else f'{m} دقیقه'
            return JsonResponse({'ok': False, 'error': f'هنوز {wait_str} تا چرخش بعدی مونده'})
        wallet = ZarbanWallet.get_or_create_for(request.user)
        if wallet.balance < wheel.cost_zarban:
            return JsonResponse({'ok': False, 'error': f'ضربان کافی نیست (نیاز: {wheel.cost_zarban} 💜)'})
        wallet.balance -= wheel.cost_zarban
        wallet.save()
        ZarbanTransaction.objects.create(
            wallet=wallet, amount=wheel.cost_zarban,
            tx_type='debit', reason=f'چرخش گردونه: {wheel.name}'
        )
        cost = wheel.cost_zarban

    # انتخاب تصادفی وزن‌دار
    weights = [max(0.01, item.probability) for item in items]
    won_item = random.choices(items, weights=weights, k=1)[0]

    # اعمال جایزه
    reward_text = ''
    profile = get_or_create_gamer_profile(request.user)

    if won_item.reward_type == SpinWheelItem.REWARD_ZARBAN and won_item.reward_amount > 0:
        wallet = ZarbanWallet.get_or_create_for(request.user)
        wallet.balance += won_item.reward_amount
        wallet.save()
        ZarbanTransaction.objects.create(
            wallet=wallet, amount=won_item.reward_amount,
            tx_type='credit', reason=f'جایزه گردونه: {won_item.name}'
        )
        reward_text = f'{won_item.reward_amount} ضربان 💜 به کیف‌پولت اضافه شد!'

    elif won_item.reward_type == SpinWheelItem.REWARD_XP and won_item.reward_amount > 0:
        # XP system removed — ignore this reward type
        reward_text = f'{won_item.reward_amount} XP ⚡ دریافت کردی!'

    elif won_item.reward_type == SpinWheelItem.REWARD_SPIN:
        # چرخش مجدد — SpinRecord ثبت نمی‌کنیم تا cooldown شروع نشه
        # کاربر بلافاصله می‌تونه دوباره بچرخونه
        reward_text = 'یک چرخش رایگان بردی! 🎰 دوباره بچرخون!'
        Notification.objects.create(
            recipient=request.user, sender=request.user,
            notif_type='spin',
            custom_text=f'🎰 از گردونه {wheel.name} یه چرخش رایگان بردی! دوباره بچرخون!'
        )
        return JsonResponse({
            'ok': True,
            'won_index': items.index(won_item),
            'item': {
                'id': won_item.pk, 'name': won_item.name,
                'emoji': won_item.emoji, 'color': won_item.color,
                'reward_type': won_item.reward_type,
                'reward_amount': won_item.reward_amount,
            },
            'reward_text': reward_text,
            'is_free': can_spin_free,
            'can_spin_free': True,
            'next_spin_ts': 0,   # هنوز می‌تونه → تایمر پنهان
        })

    elif won_item.reward_type == SpinWheelItem.REWARD_NOTHING:
        reward_text = 'بدشانس آوردی 💀 دفعه بعد بهتره!'

    # ذخیره رکورد (cooldown از این لحظه شروع می‌شه)
    SpinRecord.objects.create(
        user=request.user, wheel=wheel, item=won_item,
        is_free=can_spin_free, cost=cost
    )

    # نوتیف
    if won_item.reward_type == SpinWheelItem.REWARD_ZARBAN and won_item.reward_amount > 0:
        notif_text = f'🎉 توی گردونه {wheel.name} {won_item.reward_amount} ضربان بردی، مبارکت باشه!'
    elif won_item.reward_type == SpinWheelItem.REWARD_XP and won_item.reward_amount > 0:
        notif_text = f'⚡ گردونه {wheel.name} بهت {won_item.reward_amount} XP داد، مبارکت باشه!'
    else:
        notif_text = f'🎰 گردونه {wheel.name} رو زدی ولی اینبار چیزی نبود!'
    Notification.objects.create(
        recipient=request.user, sender=request.user,
        notif_type='spin',
        custom_text=notif_text,
    )

    # timestamp مطلق لحظه چرخش بعدی (از SpinRecord که همین الان ساخته شد)
    new_next_ts = _next_spin_ts(request.user, wheel)

    return JsonResponse({
        'ok': True,
        'won_index': items.index(won_item),
        'item': {
            'id': won_item.pk, 'name': won_item.name,
            'emoji': won_item.emoji, 'color': won_item.color,
            'reward_type': won_item.reward_type,
            'reward_amount': won_item.reward_amount,
        },
        'reward_text': reward_text,
        'is_free': can_spin_free,
        'can_spin_free': False,
        'next_spin_ts': new_next_ts,  # ← timestamp مطلق — هیچ‌وقت ریست نمی‌شه
    })


# ═══════════════════════════════════════════════════════════════
#  WHO VIEWED ME
# ═══════════════════════════════════════════════════════════════

@login_required
def who_viewed_me(request):
    from django.utils import timezone
    from datetime import timedelta
    my_profile = get_or_create_gamer_profile(request.user)
    is_premium = my_profile.is_premium

    # غیرپریمیوم → ارور + ریدایرکت به صفحه پریمیوم
    if not is_premium:
        messages.error(request, 'ابتدا اشتراک پریمیوم تهیه کنید تا بازدیدکنندگان پروفایلتان را ببینید.')
        return redirect('community:premium_info')

    # ۳۰ روز اخیر
    since = timezone.now() - timedelta(days=30)
    views_qs = (
        ProfileView.objects
        .filter(viewed_user=request.user, viewed_at__gte=since)
        .select_related('viewer', 'viewer__gamer_profile')
        .order_by('-viewed_at')
    )

    unique_count = views_qs.values('viewer').distinct().count()
    today_count  = views_qs.filter(viewed_at__date=timezone.now().date()).count()

    seen = set()
    viewers = []
    for v in views_qs:
        if v.viewer_id not in seen:
            seen.add(v.viewer_id)
            viewers.append(v)
        if len(viewers) >= 50:
            break

    plans = PremiumPlan.objects.filter(is_active=True)

    return render(request, 'community/who_viewed_me.html', {
        'is_premium':    is_premium,
        'viewers':       viewers,
        'unique_count':  unique_count,
        'today_count':   today_count,
        'plans':         plans,
        'blur_count':    min(unique_count, 12),  # تعداد آواتار تار برای غیرپریمیوم
    })


@login_required
def premium_info(request):
    """صفحه پریمیوم پابلیک — نمایش پلن‌ها به کاربر عادی"""
    plans = PremiumPlan.objects.filter(is_active=True)
    return render(request, 'community/premium_info.html', {'plans': plans})


@login_required
def dm_list_api(request):
    """لیست DM‌ها برای شیر کردن پست — JSON"""
    blocked_ids = set(Block.objects.filter(blocker=request.user).values_list('blocked_id', flat=True))
    convs = request.user.conversations.prefetch_related(
        'participants', 'participants__gamer_profile'
    ).order_by('-updated_at')
    result = []
    for c in convs:
        other = c.other_participant(request.user)
        if not other or other.id in blocked_ids or other.username == 'admin':
            continue
        avatar_url = ''
        profile = getattr(other, 'gamer_profile', None)
        if profile and profile.avatar:
            avatar_url = profile.avatar.url
        result.append({
            'username': other.username,
            'display': other.get_full_name() or other.username,
            'avatar': avatar_url,
            'initial': other.username[0].upper() if other.username else '?',
        })
    # کاربرانی که هنوز DM نداریم ولی می‌فالویم
    following_ids = set(Follow.objects.filter(follower=request.user).values_list('following_id', flat=True))
    existing_usernames = {r['username'] for r in result}
    extra = User.objects.filter(id__in=following_ids).exclude(username__in=existing_usernames).exclude(username='admin').select_related('gamer_profile')[:20]
    for u in extra:
        profile = getattr(u, 'gamer_profile', None)
        avatar_url = profile.avatar.url if profile and profile.avatar else ''
        result.append({
            'username': u.username,
            'display': u.get_full_name() or u.username,
            'avatar': avatar_url,
            'initial': u.username[0].upper(),
        })
    return JsonResponse({'ok': True, 'contacts': result})
