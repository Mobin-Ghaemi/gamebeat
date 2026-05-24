from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q, Count
from django.views.decorators.http import require_POST
from .models import GamerProfile, Post, PostLike, Comment, Follow, LFGPost, Achievement, GamingAccount, Hashtag
from .models import Notification, Conversation, Message
from .models import GameBacklog, PostReaction
from .models import PLATFORM_CHOICES, CITY_CHOICES
import re
import json
import urllib.request
import urllib.parse


def get_or_create_gamer_profile(user):
    profile, _ = GamerProfile.objects.get_or_create(user=user)
    return profile


def extract_and_save_hashtags(post):
    """Extract #hashtags from post content, save to DB, update counts"""
    tags = set(re.findall(r'#([a-zA-Z؀-ۿ\w]{2,50})', post.content))
    post.hashtags.clear()
    for tag_name in tags:
        tag_name_lower = tag_name.lower()
        hashtag, created = Hashtag.objects.get_or_create(name=tag_name_lower)
        hashtag.post_count = hashtag.posts.count()
        hashtag.save()
        post.hashtags.add(hashtag)


def _annotate_reactions(posts, user):
    """Attach my_reaction and reactions_summary to each post"""
    post_ids = [p.id for p in posts]
    # all reactions for these posts
    all_rxns = PostReaction.objects.filter(post_id__in=post_ids)
    my_rxns  = {r.post_id: r.reaction_type for r in all_rxns.filter(user=user)}
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

        suggested_gamers = User.objects.filter(
            gamer_profile__isnull=False
        ).annotate(
            followers_count=Count('followers_set')
        ).order_by('-followers_count')[:5]

        active_lfg = LFGPost.objects.filter(is_active=True).select_related(
            'author', 'author__gamer_profile'
        ).order_by('-created_at')[:5]

        stats = {
            'users': User.objects.count(),
            'posts': Post.objects.filter(is_public=True).count(),
        }

        return render(request, 'community/feed.html', {
            'posts': posts,
            'liked_post_ids': set(),
            'my_profile': None,
            'suggested_gamers': suggested_gamers,
            'active_lfg': active_lfg,
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

    _annotate_reactions(posts, request.user)
    liked_post_ids = set(PostLike.objects.filter(user=request.user).values_list('post_id', flat=True))

    suggested_gamers = User.objects.exclude(
        id=request.user.id
    ).exclude(
        id__in=following_ids
    ).filter(
        gamer_profile__isnull=False
    ).annotate(
        followers_count=Count('followers_set')
    ).order_by('-followers_count')[:5]

    active_lfg = LFGPost.objects.filter(is_active=True).select_related('author', 'author__gamer_profile').order_by('-created_at')[:5]

    context = {
        'posts': posts,
        'liked_post_ids': liked_post_ids,
        'my_profile': my_profile,
        'suggested_gamers': suggested_gamers,
        'active_lfg': active_lfg,
        'is_discover': is_discover,
    }
    return render(request, 'community/feed.html', context)


@login_required
def gamer_profile(request, username):
    profile_user = get_object_or_404(User, username=username)
    profile = get_or_create_gamer_profile(profile_user)
    my_profile = get_or_create_gamer_profile(request.user)

    is_following = Follow.objects.filter(follower=request.user, following=profile_user).exists()
    is_own_profile = request.user == profile_user

    posts = list(Post.objects.filter(author=profile_user, is_public=True)
                 .select_related('author', 'author__gamer_profile')
                 .prefetch_related('reactions')
                 .order_by('-created_at')[:30])
    _annotate_reactions(posts, request.user)
    liked_post_ids = set(PostLike.objects.filter(user=request.user).values_list('post_id', flat=True))
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
    }
    return render(request, 'community/profile.html', context)


@login_required
def edit_profile(request):
    profile = get_or_create_gamer_profile(request.user)

    if request.method == 'POST':
        request.user.first_name = request.POST.get('first_name', '')
        request.user.last_name = request.POST.get('last_name', '')
        request.user.save()

        profile.bio = request.POST.get('bio', '')
        profile.city = request.POST.get('city', '')
        selected_platforms = request.POST.getlist('platforms')
        profile.platforms = selected_platforms
        profile.platform = selected_platforms[0] if selected_platforms else 'pc'
        profile.gaming_style = request.POST.get('gaming_style', '')
        profile.rank = request.POST.get('rank', '')
        profile.favorite_games = request.POST.get('favorite_games', '')
        profile.steam_id = request.POST.get('steam_id', '')
        profile.psn_id = request.POST.get('psn_id', '')
        profile.xbox_gamertag = request.POST.get('xbox_gamertag', '')

        if 'avatar' in request.FILES:
            profile.avatar = request.FILES['avatar']
        if 'banner' in request.FILES:
            profile.banner = request.FILES['banner']

        profile.save()
        messages.success(request, 'پروفایل آپدیت شد!')
        return redirect('community:profile', username=request.user.username)

    context = {
        'profile': profile,
        'platform_choices': PLATFORM_CHOICES,
        'city_choices': CITY_CHOICES,
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
        )
        if 'image' in request.FILES:
            post.image = request.FILES['image']
            post.save()

        extract_and_save_hashtags(post)

        profile = get_or_create_gamer_profile(request.user)
        profile.xp += 10
        if profile.xp >= profile.level * 100:
            profile.level += 1
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


@login_required
@require_POST
def add_comment(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    content = request.POST.get('content', '').strip()
    if content:
        Comment.objects.create(post=post, author=request.user, content=content)
        # Notification: comment
        if post.author != request.user:
            Notification.objects.create(
                recipient=post.author, sender=request.user,
                notif_type='comment', post=post
            )
    return redirect(request.META.get('HTTP_REFERER', 'community:feed'))


@login_required
@require_POST
def toggle_follow(request, username):
    target_user = get_object_or_404(User, username=username)
    if target_user == request.user:
        return JsonResponse({'error': 'نمی‌توانید خودتان را دنبال کنید'}, status=400)

    follow, created = Follow.objects.get_or_create(follower=request.user, following=target_user)
    if not created:
        follow.delete()
        following = False
    else:
        following = True
        profile = get_or_create_gamer_profile(request.user)
        profile.xp += 5
        profile.save()
        # Notification: follow
        Notification.objects.get_or_create(
            recipient=target_user, sender=request.user,
            notif_type='follow', post=None
        )

    target_profile = get_or_create_gamer_profile(target_user)
    return JsonResponse({'following': following, 'followers_count': target_profile.followers_count})


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

    gamers = gamers.order_by('-level', '-xp')[:30]

    following_ids = set(Follow.objects.filter(follower=request.user).values_list('following_id', flat=True))

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
    }
    return render(request, 'community/search.html', context)


@login_required
def lfg_board(request):
    my_profile = get_or_create_gamer_profile(request.user)
    platform_filter = request.GET.get('platform', '')
    game_filter = request.GET.get('game', '')

    lfg_posts = LFGPost.objects.filter(is_active=True).select_related('author', 'author__gamer_profile')

    if platform_filter:
        lfg_posts = lfg_posts.filter(platform=platform_filter)
    if game_filter:
        lfg_posts = lfg_posts.filter(game_name__icontains=game_filter)

    lfg_posts = lfg_posts.order_by('-created_at')[:50]

    context = {
        'lfg_posts': lfg_posts,
        'platform_filter': platform_filter,
        'game_filter': game_filter,
        'my_profile': my_profile,
        'platform_choices': PLATFORM_CHOICES,
        'popular_games': ['Valorant', 'FIFA 25', 'Call of Duty', 'GTA Online', 'PUBG', 'Dota 2', 'CS2', 'Fortnite'],
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
    )
    messages.success(request, 'پست LFG منتشر شد! منتظر بازیکن باش 🎮')
    return redirect('community:lfg')


@login_required
def leaderboard(request):
    my_profile = get_or_create_gamer_profile(request.user)
    top_gamers = GamerProfile.objects.select_related('user').order_by('-xp', '-level')[:20]
    context = {
        'top_gamers': top_gamers,
        'my_profile': my_profile,
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
        )
        if 'image' in request.FILES:
            post.image = request.FILES['image']
            post.save()
        if 'video' in request.FILES:
            post.video = request.FILES['video']
            post.save()
        extract_and_save_hashtags(post)
        profile = get_or_create_gamer_profile(request.user)
        profile.xp += 10
        if profile.xp >= profile.level * 100:
            profile.level += 1
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
    notifs = Notification.objects.filter(
        recipient=request.user
    ).select_related('sender', 'sender__gamer_profile', 'post').order_by('-created_at')[:60]
    # mark all as read
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    return render(request, 'community/notifications.html', {'notifs': notifs})


@login_required
def notifications_count(request):
    count = Notification.objects.filter(recipient=request.user, is_read=False).count()
    return JsonResponse({'count': count})


# ═══════════════════════════════════════
#  DIRECT MESSAGES
# ═══════════════════════════════════════

@login_required
def inbox(request):
    convs = request.user.conversations.prefetch_related(
        'participants', 'participants__gamer_profile', 'messages'
    ).order_by('-updated_at')
    # annotate unread count per conversation
    conv_data = []
    for c in convs:
        other = c.other_participant(request.user)
        unread = c.messages.filter(is_read=False).exclude(sender=request.user).count()
        conv_data.append({'conv': c, 'other': other, 'unread': unread, 'last': c.last_message})
    return render(request, 'community/inbox.html', {'conv_data': conv_data})


@login_required
def conversation(request, username):
    other_user = get_object_or_404(User, username=username)
    if other_user == request.user:
        return redirect('community:inbox')

    # get or create conversation
    conv = Conversation.objects.filter(
        participants=request.user
    ).filter(participants=other_user).first()

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
        return redirect('community:conversation', username=username)

    # mark messages as read
    conv.messages.filter(is_read=False).exclude(sender=request.user).update(is_read=True)

    msgs = conv.messages.select_related('sender', 'sender__gamer_profile').order_by('created_at')
    other_profile = getattr(other_user, 'gamer_profile', None)
    return render(request, 'community/conversation.html', {
        'conv': conv,
        'msgs': msgs,
        'other_user': other_user,
        'other_profile': other_profile,
    })


@login_required
def send_message_ajax(request, username):
    """AJAX send message — returns JSON"""
    if request.method != 'POST':
        return JsonResponse({'error': 'method'}, status=405)
    other_user = get_object_or_404(User, username=username)
    content = request.POST.get('content', '').strip()
    if not content:
        return JsonResponse({'error': 'empty'}, status=400)

    conv = Conversation.objects.filter(
        participants=request.user
    ).filter(participants=other_user).first()
    if not conv:
        conv = Conversation.objects.create()
        conv.participants.add(request.user, other_user)

    msg = Message.objects.create(conversation=conv, sender=request.user, content=content)
    conv.save()
    return JsonResponse({
        'ok': True,
        'id': msg.id,
        'content': msg.content,
        'created_at': msg.created_at.strftime('%H:%M'),
    })


@login_required
def inbox_unread_count(request):
    count = Message.objects.filter(
        conversation__participants=request.user,
        is_read=False
    ).exclude(sender=request.user).count()
    return JsonResponse({'count': count})


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
    return JsonResponse({'ok': True, 'id': obj.id, 'status': obj.status, 'created': created})


@login_required
@require_POST
def backlog_update(request, item_id):
    obj = get_object_or_404(GameBacklog, id=item_id, user=request.user)
    if 'status' in request.POST:
        obj.status = request.POST['status']
    if 'rating' in request.POST:
        r = request.POST.get('rating')
        obj.rating = int(r) if r and r.isdigit() else None
    if 'notes' in request.POST:
        obj.notes = request.POST['notes'][:300]
    if 'is_favorite' in request.POST:
        obj.is_favorite = request.POST['is_favorite'] == '1'
    obj.save()
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


@login_required
def games_ranking(request):
    """Community game ratings — top games by avg rating"""
    from django.db.models import Avg, Count as DCount
    top = (
        GameBacklog.objects
        .filter(status='completed', rating__isnull=False)
        .values('game_name')
        .annotate(avg=Avg('rating'), cnt=DCount('id'))
        .filter(cnt__gte=1)
        .order_by('-avg', '-cnt')[:50]
    )
    my_backlog = {b.game_name: b for b in GameBacklog.objects.filter(user=request.user)}
    return render(request, 'community/games_ranking.html', {
        'top': top,
        'my_backlog': my_backlog,
        'platforms': PLATFORM_CHOICES,
    })
