from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.contrib import messages
from django.core.paginator import Paginator
from django.core.files.base import ContentFile
from datetime import timedelta, date
import urllib.request
import urllib.parse
import os
import jdatetime
from django.conf import settings
from .models import Game, GENRE_CHOICES, PLATFORM_CHOICES
from community.models import Post, Comment, Hashtag, GamerProfile, PostLike, PostReaction, GameBacklog
from community.models import Notification, Conversation, Message, ScoreSettings, UserSession
from community.models import ZarbanWallet, ZarbanTransaction
from community.models import SpinWheel, SpinWheelItem, SpinRecord
from community.models import PremiumPlan, PremiumSubscription
from community.models import MissionDay, DailyMission
from community.models import AchievementDefinition


def _to_jalali(dt, fmt='%Y/%m/%d'):
    _pd = str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹')
    if timezone.is_aware(dt):
        dt = timezone.localtime(dt)
    return jdatetime.datetime.fromgregorian(datetime=dt).strftime(fmt).translate(_pd)


def _int(val, default=0):
    """تبدیل امن رشته به int — رشته خالی یا None را به default تبدیل می‌کند."""
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _float(val, default=0.0):
    """تبدیل امن رشته به float."""
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _download_steam_cover(url, game_name):
    """Download a Steam cover image and return a ContentFile with filename."""
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = resp.read()
        ext = os.path.splitext(url.split('?')[0])[1] or '.jpg'
        safe_name = ''.join(c for c in game_name if c.isalnum() or c in ' _-')[:40].strip().replace(' ', '_')
        filename = f"steam_{safe_name}{ext}"
        return ContentFile(data, name=filename)
    except Exception:
        return None


def is_admin(user):
    return user.is_staff or user.is_superuser


@login_required
@user_passes_test(is_admin)
def dashboard_index(request):
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    total_users = User.objects.count()
    active_users = User.objects.filter(last_login__gte=week_ago).count()
    total_posts = Post.objects.count()
    posts_today = Post.objects.filter(created_at__gte=today_start).count()
    total_comments = Comment.objects.count()
    total_hashtags = Hashtag.objects.count()
    total_games = Game.objects.count()
    new_users_today = User.objects.filter(date_joined__gte=today_start).count()
    new_users_week = User.objects.filter(date_joined__gte=week_ago).count()
    new_users_month = User.objects.filter(date_joined__gte=month_ago).count()
    total_backlog = GameBacklog.objects.count()

    # Chart data: last 30 days — 2 queries total instead of 60
    thirty_ago = now - timedelta(days=30)

    user_by_day = {
        row['day']: row['count']
        for row in User.objects.filter(date_joined__gte=thirty_ago)
        .annotate(day=TruncDate('date_joined'))
        .values('day')
        .annotate(count=Count('id'))
    }
    post_by_day = {
        row['day']: row['count']
        for row in Post.objects.filter(created_at__gte=thirty_ago)
        .annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(count=Count('id'))
    }

    chart_labels = []
    chart_users = []
    chart_posts = []
    for i in range(29, -1, -1):
        day = (now - timedelta(days=i)).date()
        _jday = jdatetime.date.fromgregorian(date=day)
        _pd = str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹')
        chart_labels.append(f'{_jday.month}/{_jday.day}'.translate(_pd))
        chart_users.append(user_by_day.get(day, 0))
        chart_posts.append(post_by_day.get(day, 0))

    max_chart = max(max(chart_users, default=0), max(chart_posts, default=0), 1)

    top_hashtags = Hashtag.objects.order_by('-post_count')[:5]
    recent_posts = Post.objects.select_related('author').order_by('-created_at')[:6]
    recent_users = User.objects.order_by('-date_joined')[:6]

    stats = {
        'total_users': total_users,
        'active_users': active_users,
        'total_posts': total_posts,
        'posts_today': posts_today,
        'total_comments': total_comments,
        'total_hashtags': total_hashtags,
        'total_games': total_games,
        'new_users_today': new_users_today,
        'new_users_week': new_users_week,
        'new_users_month': new_users_month,
        'total_backlog': total_backlog,
    }

    return render(request, 'dashboard/index.html', {
        'stats': stats,
        'chart_labels': chart_labels,
        'chart_users': chart_users,
        'chart_posts': chart_posts,
        'chart_data': chart_users,  # backward-compat alias
        'max_chart': max_chart,
        'top_hashtags': top_hashtags,
        'recent_posts': recent_posts,
        'recent_users': recent_users,
    })


@login_required
@user_passes_test(is_admin)
def monitoring(request):
    now = timezone.now()
    online_cutoff = now - timedelta(seconds=UserSession.SESSION_TIMEOUT)
    last_hour = now - timedelta(hours=1)
    last_24h = now - timedelta(hours=24)

    online_sessions = list(
        UserSession.objects.filter(ended_at__isnull=True, last_activity__gte=online_cutoff)
        .select_related('user', 'user__gamer_profile')
        .order_by('-last_activity')
    )
    seen_user_ids = set()
    online_users = []
    for s in online_sessions:
        if s.user_id in seen_user_ids:
            continue
        seen_user_ids.add(s.user_id)
        online_users.append(s)

    active_last_hour = UserSession.objects.filter(started_at__gte=last_hour).values('user_id').distinct().count()
    active_last_24h = UserSession.objects.filter(started_at__gte=last_24h).values('user_id').distinct().count()

    db_path = settings.DATABASES['default']['NAME']
    try:
        db_size_mb = round(os.path.getsize(db_path) / (1024 * 1024), 2)
    except OSError:
        db_size_mb = None

    counts = {
        'users': User.objects.count(),
        'posts': Post.objects.count(),
        'comments': Comment.objects.count(),
        'messages': Message.objects.count(),
        'notifications': Notification.objects.count(),
        'sessions_total': UserSession.objects.count(),
    }

    debug_mode = settings.DEBUG
    sentry_active = bool(getattr(settings, 'SENTRY_DSN', ''))

    # ── خلاصه‌ی سلامت سیستم: یک حکم کلی بالای صفحه ──
    issues = []
    if debug_mode:
        issues.append({
            'level': 'critical',
            'text': 'DEBUG فعاله — روی سرور واقعی این یعنی اطلاعات داخلی سیستم لو می‌ره.',
        })
    if not sentry_active:
        issues.append({
            'level': 'warning',
            'text': 'رصد خطا (Sentry) تنظیم نشده — اگه چیزی بترکه، خودت نمی‌فهمی.',
        })

    context = {
        'online_users': online_users,
        'online_count': len(online_users),
        'active_last_hour': active_last_hour,
        'active_last_24h': active_last_24h,
        'sentry_active': sentry_active,
        'debug_mode': debug_mode,
        'db_size_mb': db_size_mb,
        'db_engine': settings.DATABASES['default']['ENGINE'].split('.')[-1],
        'counts': counts,
        'issues': issues,
        'has_critical': any(i['level'] == 'critical' for i in issues),
    }
    return render(request, 'dashboard/monitoring.html', context)


@login_required
@user_passes_test(is_admin)
def user_list(request):
    from community.models import CITY_CHOICES, CITY_BY_PROVINCE
    from urllib.parse import urlencode
    q           = request.GET.get('q', '').strip()
    filter_type = request.GET.get('filter', 'all')
    cities      = [c.strip() for c in request.GET.getlist('city') if c.strip()]

    city_label_map = dict(CITY_CHOICES)

    users = User.objects.select_related('gamer_profile').annotate(post_count=Count('posts')).order_by('-date_joined')

    if q:
        users = users.filter(Q(username__icontains=q) | Q(email__icontains=q))
    if filter_type == 'active':
        users = users.filter(is_active=True, is_staff=False)
    elif filter_type == 'banned':
        users = users.filter(is_active=False)
    elif filter_type == 'staff':
        users = users.filter(is_staff=True)
    if cities:
        users = users.filter(gamer_profile__city__in=cities)

    paginator = Paginator(users, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    # Annotate each user with their city's Persian label
    for u in page_obj.object_list:
        profile = getattr(u, 'gamer_profile', None)
        raw_city = getattr(profile, 'city', '') or ''
        u.city_label = city_label_map.get(raw_city, '')

    # Base query string for pagination (preserves q, filter, and all city params)
    qd = request.GET.copy()
    qd.pop('page', None)
    pagination_qs = qd.urlencode()

    # Base query string for filter-type links (preserves q and all city params, no filter/page)
    qd2 = request.GET.copy()
    qd2.pop('page', None)
    qd2.pop('filter', None)
    filter_links_base = qd2.urlencode()

    return render(request, 'dashboard/users.html', {
        'page_obj':          page_obj,
        'users':             page_obj,
        'q':                 q,
        'status':            filter_type,
        'filter_type':       filter_type,
        'cities':            cities,
        'city_choices':      CITY_CHOICES,
        'city_by_province':  CITY_BY_PROVINCE,
        'pagination_qs':     pagination_qs,
        'filter_links_base': filter_links_base,
    })


@login_required
@user_passes_test(is_admin)
def user_toggle_ban(request, user_id):
    if request.method == 'POST':
        u = get_object_or_404(User, pk=user_id)
        if u != request.user:
            u.is_active = not u.is_active
            u.save()
            messages.success(request, f'کاربر {u.username} {"فعال" if u.is_active else "مسدود"} شد.')
    return redirect('dashboard:users')


@login_required
@user_passes_test(is_admin)
def user_toggle_verified(request, user_id):
    if request.method == 'POST':
        u = get_object_or_404(User, pk=user_id)
        profile, _ = GamerProfile.objects.get_or_create(user=u)
        profile.is_verified = not profile.is_verified
        profile.save(update_fields=['is_verified'])
        messages.success(request, f'کاربر {u.username} {"تأیید شد ✓" if profile.is_verified else "از تأیید خارج شد"}.')
    next_url = request.POST.get('next') or 'dashboard:users'
    if next_url == 'dashboard:user_detail':
        return redirect('dashboard:user_detail', user_id=user_id)
    return redirect('dashboard:users')


@login_required
@user_passes_test(is_admin)
def post_list(request):
    q = request.GET.get('q', '').strip()
    filter_type = request.GET.get('filter', 'all')
    tab = request.GET.get('tab', 'pending')

    posts = Post.objects.select_related('author').annotate(
        likes_count_ann=Count('likes', distinct=True),
        comments_count_ann=Count('comments', distinct=True),
    ).order_by('-created_at')

    if q:
        posts = posts.filter(Q(content__icontains=q) | Q(author__username__icontains=q))

    if filter_type != 'all':
        posts = posts.filter(post_type=filter_type)

    pending_count = posts.filter(is_approved=False).count()
    approved_count = posts.filter(is_approved=True).count()

    if tab == 'approved':
        posts = posts.filter(is_approved=True)
    else:
        posts = posts.filter(is_approved=False)

    paginator = Paginator(posts, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'dashboard/posts.html', {
        'page_obj': page_obj,
        'q': q,
        'filter_type': filter_type,
        'post_type_choices': Post.POST_TYPES,
        'tab': tab,
        'pending_count': pending_count,
        'approved_count': approved_count,
    })


@login_required
@user_passes_test(is_admin)
def post_approve(request, pk):
    post = get_object_or_404(Post, pk=pk)
    post.is_approved = True
    post.save(update_fields=['is_approved'])
    return redirect(request.META.get('HTTP_REFERER', 'dashboard:posts'))


@login_required
@user_passes_test(is_admin)
def post_delete(request, post_id):
    if request.method == 'POST':
        post = get_object_or_404(Post, id=post_id)
        post.delete()
        messages.success(request, 'پست حذف شد.')
    return redirect('dashboard:posts')


@login_required
@user_passes_test(is_admin)
def comment_list(request):
    q = request.GET.get('q', '').strip()
    tab = request.GET.get('tab', 'pending')

    comments = Comment.objects.select_related('post', 'author').order_by('-created_at')

    if q:
        comments = comments.filter(Q(content__icontains=q) | Q(author__username__icontains=q))

    pending_count = comments.filter(is_approved=False).count()
    approved_count = comments.filter(is_approved=True).count()

    if tab == 'approved':
        comments = comments.filter(is_approved=True)
    else:
        comments = comments.filter(is_approved=False)

    paginator = Paginator(comments, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'dashboard/comments.html', {
        'page_obj': page_obj,
        'q': q,
        'tab': tab,
        'pending_count': pending_count,
        'approved_count': approved_count,
    })


@login_required
@user_passes_test(is_admin)
def comment_approve(request, pk):
    comment = get_object_or_404(Comment, pk=pk)
    comment.is_approved = True
    comment.save(update_fields=['is_approved'])
    return redirect(request.META.get('HTTP_REFERER', 'dashboard:comments'))


@login_required
@user_passes_test(is_admin)
def comment_delete(request, comment_id):
    if request.method == 'POST':
        comment = get_object_or_404(Comment, id=comment_id)
        comment.delete()
        messages.success(request, 'کامنت حذف شد.')
    return redirect('dashboard:comments')


@login_required
@user_passes_test(is_admin)
def hashtag_list(request):
    # Handle inline hashtag creation (POST on the same page)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip().lstrip('#')
        if name:
            hashtag, created = Hashtag.objects.get_or_create(
                name=name.lower(),
                defaults={'is_approved': True}
            )
            if not created:
                hashtag.is_approved = True
                hashtag.save(update_fields=['is_approved'])
        return redirect('dashboard:hashtags')

    q = request.GET.get('q', '').strip()
    tab = request.GET.get('tab', 'pending')
    hashtags = Hashtag.objects.order_by('-post_count')

    if q:
        hashtags = hashtags.filter(name__icontains=q)

    pending_count = hashtags.filter(is_approved=False).count()
    approved_count = hashtags.filter(is_approved=True).count()

    if tab == 'approved':
        hashtags = hashtags.filter(is_approved=True)
    else:
        hashtags = hashtags.filter(is_approved=False)

    return render(request, 'dashboard/hashtags.html', {
        'hashtags': hashtags,
        'q': q,
        'tab': tab,
        'pending_count': pending_count,
        'approved_count': approved_count,
    })


@login_required
@user_passes_test(is_admin)
def hashtag_approve(request, pk):
    hashtag = get_object_or_404(Hashtag, pk=pk)
    hashtag.is_approved = True
    hashtag.save(update_fields=['is_approved'])
    return redirect(request.META.get('HTTP_REFERER', 'dashboard:hashtags'))


@login_required
@user_passes_test(is_admin)
def hashtag_delete(request, hashtag_id):
    if request.method == 'POST':
        hashtag = get_object_or_404(Hashtag, id=hashtag_id)
        hashtag.delete()
        messages.success(request, 'هشتگ حذف شد.')
    return redirect('dashboard:hashtags')


@login_required
@user_passes_test(is_admin)
def game_list(request):
    from django.core.paginator import Paginator
    q = request.GET.get('q', '')
    genre = request.GET.get('genre', '')
    filter_genre = request.GET.get('filter_genre', genre)
    games = Game.objects.all().order_by('name')
    if q:
        games = games.filter(Q(name__icontains=q) | Q(name_fa__icontains=q))
    if filter_genre and filter_genre != 'all':
        # SQLite از contains روی JSONField پشتیبانی نمی‌کند؛ با icontains و کوتیشن مچ دقیق
        games = games.filter(genres__icontains='"%s"' % filter_genre)

    total_count = games.count()

    per_page_options = [20, 50, 100]
    try:
        per_page = int(request.GET.get('per_page', 20))
    except (TypeError, ValueError):
        per_page = 20
    if per_page not in per_page_options:
        per_page = 20

    paginator = Paginator(games, per_page)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'dashboard/games.html', {
        'games': page_obj,
        'page_obj': page_obj,
        'total_count': total_count,
        'per_page': per_page,
        'per_page_options': per_page_options,
        'q': q,
        'genre': genre,
        'filter_genre': filter_genre,
        'genre_choices': GENRE_CHOICES,
    })


@login_required
@user_passes_test(is_admin)
def game_bulk_delete(request):
    if request.method == 'POST':
        ids = request.POST.getlist('ids')
        if ids:
            n = Game.objects.filter(id__in=ids).count()
            Game.objects.filter(id__in=ids).delete()
            messages.success(request, f'{n} بازی حذف شد.')
        else:
            messages.error(request, 'هیچ بازی‌ای انتخاب نشده بود.')
    return redirect('dashboard:games')


@login_required
@user_passes_test(is_admin)
def game_add(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        steam_url = request.POST.get('steam_url', '').strip()

        if Game.objects.filter(name__iexact=name).exists():
            messages.error(request, f'بازی با نام «{name}» قبلاً ثبت شده.')
            return render(request, 'dashboard/game_form.html', {
                'action': 'add', 'genre_choices': GENRE_CHOICES, 'platform_choices': PLATFORM_CHOICES,
            })
        if steam_url and Game.objects.filter(steam_url=steam_url).exists():
            messages.error(request, 'این لینک استیم قبلاً برای یک بازی دیگر ثبت شده.')
            return render(request, 'dashboard/game_form.html', {
                'action': 'add', 'genre_choices': GENRE_CHOICES, 'platform_choices': PLATFORM_CHOICES,
            })

        g = Game()
        g.name = name
        g.steam_url = steam_url
        g.genre = request.POST.get('genre', '')
        g.developer = request.POST.get('developer', '')
        g.publisher = request.POST.get('publisher', '')
        g.release_year = request.POST.get('release_year') or None
        g.description = request.POST.get('description', '')
        g.is_featured = 'is_featured' in request.POST
        g.is_popular  = 'is_popular'  in request.POST
        g.is_online       = 'is_online'       in request.POST
        g.is_crack_online = 'is_crack_online' in request.POST
        g.platforms = request.POST.getlist('platforms')
        if request.FILES.get('cover'):
            g.cover = request.FILES['cover']
        elif request.POST.get('steam_cover_url'):
            cf = _download_steam_cover(request.POST['steam_cover_url'], g.name)
            if cf:
                g.cover = cf
        g.save()
        messages.success(request, f'بازی «{g.name}» اضافه شد.')
        return redirect('dashboard:games')
    return render(request, 'dashboard/game_form.html', {
        'action': 'add', 'genre_choices': GENRE_CHOICES, 'platform_choices': PLATFORM_CHOICES,
    })


@login_required
@user_passes_test(is_admin)
def game_edit(request, game_id):
    game = get_object_or_404(Game, pk=game_id)
    if request.method == 'POST':
        new_name = request.POST.get('name', '').strip()
        new_steam_url = request.POST.get('steam_url', '').strip()

        if Game.objects.filter(name__iexact=new_name).exclude(pk=game.pk).exists():
            messages.error(request, f'بازی دیگری با نام «{new_name}» وجود دارد.')
            return render(request, 'dashboard/game_form.html', {
                'action': 'edit', 'game': game,
                'genre_choices': GENRE_CHOICES, 'platform_choices': PLATFORM_CHOICES,
            })
        if new_steam_url and Game.objects.filter(steam_url=new_steam_url).exclude(pk=game.pk).exists():
            messages.error(request, 'این لینک استیم قبلاً برای یک بازی دیگر ثبت شده.')
            return render(request, 'dashboard/game_form.html', {
                'action': 'edit', 'game': game,
                'genre_choices': GENRE_CHOICES, 'platform_choices': PLATFORM_CHOICES,
            })

        game.name = new_name
        game.steam_url = new_steam_url
        game.genre = request.POST.get('genre', '')
        game.developer = request.POST.get('developer', '')
        game.publisher = request.POST.get('publisher', '')
        game.release_year = request.POST.get('release_year') or None
        game.description = request.POST.get('description', '')
        game.is_featured = 'is_featured' in request.POST
        game.is_popular  = 'is_popular'  in request.POST
        game.is_online   = 'is_online'   in request.POST
        game.platforms = request.POST.getlist('platforms')
        if request.FILES.get('cover'):
            game.cover = request.FILES['cover']
        elif request.POST.get('steam_cover_url'):
            cf = _download_steam_cover(request.POST['steam_cover_url'], game.name)
            if cf:
                game.cover = cf
        game.save()
        messages.success(request, f'بازی «{game.name}» ویرایش شد.')
        return redirect('dashboard:games')
    return render(request, 'dashboard/game_form.html', {
        'action': 'edit', 'game': game,
        'genre_choices': GENRE_CHOICES, 'platform_choices': PLATFORM_CHOICES,
    })


@login_required
@user_passes_test(is_admin)
def game_delete(request, game_id):
    if request.method == 'POST':
        game = get_object_or_404(Game, pk=game_id)
        name = game.name
        game.delete()
        messages.success(request, f'بازی «{name}» حذف شد.')
    return redirect('dashboard:games')


@login_required
@user_passes_test(is_admin)
def game_toggle_active(request, game_id):
    if request.method != 'POST':
        from django.http import HttpResponseNotAllowed
        return HttpResponseNotAllowed(['POST'])
    game = get_object_or_404(Game, pk=game_id)
    game.is_active = not game.is_active
    game.save(update_fields=['is_active'])
    return JsonResponse({'is_active': game.is_active})


@login_required
@user_passes_test(is_admin)
def game_toggle_online(request, game_id):
    if request.method != 'POST':
        from django.http import HttpResponseNotAllowed
        return HttpResponseNotAllowed(['POST'])
    game = get_object_or_404(Game, pk=game_id)
    game.is_online = not game.is_online
    game.save(update_fields=['is_online'])
    return JsonResponse({'is_online': game.is_online})


# ─── User Detail ───────────────────────────────────────────────────────────────

@login_required
@user_passes_test(is_admin)
def user_detail(request, user_id):
    u = get_object_or_404(User, pk=user_id)
    profile = getattr(u, 'gamer_profile', None)
    user_posts = Post.objects.filter(author=u).order_by('-created_at')[:10]
    user_backlog = GameBacklog.objects.filter(user=u).order_by('-updated_at')[:10]
    post_count = Post.objects.filter(author=u).count()
    comment_count = Comment.objects.filter(author=u).count()
    backlog_count = GameBacklog.objects.filter(user=u).count()
    return render(request, 'dashboard/user_detail.html', {
        'u': u,
        'profile': profile,
        'user_posts': user_posts,
        'user_backlog': user_backlog,
        'post_count': post_count,
        'comment_count': comment_count,
        'backlog_count': backlog_count,
    })


# ─── Post Detail ───────────────────────────────────────────────────────────────

@login_required
@user_passes_test(is_admin)
def post_detail(request, post_id):
    post = get_object_or_404(
        Post.objects.select_related('author').prefetch_related('comments__author', 'hashtags'),
        pk=post_id
    )
    comments = post.comments.select_related('author').order_by('created_at')
    return render(request, 'dashboard/post_detail.html', {
        'post': post,
        'comments': comments,
    })


# ─── Bulk Delete ───────────────────────────────────────────────────────────────

@login_required
@user_passes_test(is_admin)
def post_bulk_delete(request):
    if request.method == 'POST':
        ids = request.POST.getlist('ids')
        if ids:
            deleted, _ = Post.objects.filter(pk__in=ids).delete()
            messages.success(request, f'{deleted} پست حذف شد.')
        else:
            messages.error(request, 'هیچ پستی انتخاب نشده.')
    return redirect('dashboard:posts')


@login_required
@user_passes_test(is_admin)
def user_search_api(request):
    """AJAX: search users by username / email / phone — for notify autocomplete."""
    q = request.GET.get('q', '').strip()
    if len(q) < 1:
        return JsonResponse({'results': []})

    # phone را جدا subquery می‌کنیم تا JOIN روی gamer_profile
    # کاربرانی که profile ندارند (مثل superuserها) را drop نکند
    phone_ids = GamerProfile.objects.filter(
        phone__istartswith=q
    ).values_list('user_id', flat=True)

    users = (
        User.objects
        .filter(is_active=True)
        .filter(
            Q(username__istartswith=q) |
            Q(email__icontains=q) |
            Q(pk__in=phone_ids)
        )
        .select_related('gamer_profile')
        .distinct()[:12]
    )

    results = []
    for u in users:
        phone = ''
        try:
            phone = u.gamer_profile.phone or ''
        except Exception:
            pass
        results.append({
            'id':           u.pk,
            'username':     u.username,
            'email':        u.email or '',
            'phone':        phone,
            'initial':      u.username[0].upper() if u.username else '?',
            'is_staff':     u.is_staff,
            'is_superuser': u.is_superuser,
        })

    return JsonResponse({'results': results})


@login_required
@user_passes_test(is_admin)
def notify_center(request):
    """Send notification or DM to one or all users from admin panel."""
    if request.method == 'POST':
        target    = request.POST.get('target', '').strip()   # user id or 'all'
        text      = request.POST.get('text', '').strip()
        send_type = request.POST.get('send_type', 'notif')   # notif | dm | both

        if not text:
            messages.error(request, 'متن پیام خالی است.')
            return redirect('dashboard:notify')

        # Build recipient list
        if target == 'all':
            recipients = list(User.objects.filter(is_active=True).exclude(pk=request.user.pk))
        else:
            try:
                recipients = [User.objects.get(pk=int(target))]
            except (User.DoesNotExist, ValueError):
                messages.error(request, 'کاربر یافت نشد.')
                return redirect('dashboard:notify')

        # پیام‌ها از طرف یوزر admin (مدیریت گیم‌بیت) ارسال میشه
        try:
            admin_sender = User.objects.get(username='admin')
        except User.DoesNotExist:
            admin_sender = request.user

        sent = 0
        for user in recipients:
            if user == admin_sender:
                continue
            if send_type in ('notif', 'both'):
                Notification.objects.create(
                    recipient=user,
                    sender=admin_sender,
                    notif_type='admin',
                    custom_text=text,
                )
            if send_type in ('dm', 'both'):
                conv = (
                    Conversation.objects
                    .filter(participants=admin_sender)
                    .filter(participants=user)
                    .first()
                )
                if not conv:
                    conv = Conversation.objects.create()
                    conv.participants.add(admin_sender, user)
                Message.objects.create(conversation=conv, sender=admin_sender, content=text)
                conv.save()
                Notification.objects.create(
                    recipient=user,
                    sender=admin_sender,
                    notif_type='dm',
                    custom_text=text[:100],
                )
            sent += 1

        messages.success(request, f'پیام با موفقیت به {sent} کاربر ارسال شد.')
        return redirect('dashboard:notify')

    # GET
    try:
        admin_sender = User.objects.get(username='admin')
    except User.DoesNotExist:
        admin_sender = request.user
    active_qs = User.objects.filter(is_active=True).exclude(pk=admin_sender.pk)
    recent = (
        Notification.objects
        .filter(notif_type__in=('admin', 'dm'), sender=admin_sender)
        .select_related('recipient', 'recipient__gamer_profile')
        .order_by('-created_at')[:30]
    )
    return render(request, 'dashboard/notify.html', {
        'total_active': active_qs.count(),
        'total_staff':  active_qs.filter(Q(is_staff=True) | Q(is_superuser=True)).count(),
        'recent': recent,
        'send_types': [
            ('notif', '🔔', 'اعلان'),
            ('dm',    '💬', 'پیام خصوصی'),
            ('both',  '📣', 'هر دو'),
        ],
    })


@login_required
@user_passes_test(is_admin)
def comment_reject(request, pk):
    """Reject (delete) a comment and optionally send a message to its author."""
    if request.method == 'POST':
        comment   = get_object_or_404(Comment, pk=pk)
        author    = comment.author
        text      = request.POST.get('message', '').strip()
        send_type = request.POST.get('send_type', '')   # notif | dm | both | ''

        if text and send_type:
            if send_type in ('notif', 'both'):
                Notification.objects.create(
                    recipient=author,
                    sender=request.user,
                    notif_type='admin',
                    custom_text=text,
                )
            if send_type in ('dm', 'both'):
                conv = (
                    Conversation.objects
                    .filter(participants=request.user)
                    .filter(participants=author)
                    .first()
                )
                if not conv:
                    conv = Conversation.objects.create()
                    conv.participants.add(request.user, author)
                Message.objects.create(conversation=conv, sender=request.user, content=text)
                conv.save()
                Notification.objects.create(
                    recipient=author,
                    sender=request.user,
                    notif_type='dm',
                    custom_text=text[:100],
                )

        comment.delete()
        msg = 'کامنت رد شد'
        if text and send_type:
            msg += ' و پیام ارسال شد'
        msg += '.'
        messages.success(request, msg)

    return redirect(request.META.get('HTTP_REFERER', 'dashboard:comments'))


@login_required
@user_passes_test(is_admin)
def comment_bulk_delete(request):
    if request.method == 'POST':
        ids = request.POST.getlist('ids')
        if ids:
            deleted, _ = Comment.objects.filter(pk__in=ids).delete()
            messages.success(request, f'{deleted} کامنت حذف شد.')
        else:
            messages.error(request, 'هیچ کامنتی انتخاب نشده.')
    return redirect('dashboard:comments')


@login_required
@user_passes_test(is_admin)
def score_settings_view(request):
    cfg, _ = ScoreSettings.objects.get_or_create(pk=1)
    if request.method == 'POST':
        try:
            cfg.post_score        = max(0, int(request.POST.get('post_score',        cfg.post_score)))
            cfg.comment_score     = max(0, int(request.POST.get('comment_score',     cfg.comment_score)))
            cfg.active_day_score  = max(0, int(request.POST.get('active_day_score',  cfg.active_day_score)))
            cfg.online_hour_score = max(0, int(request.POST.get('online_hour_score', cfg.online_hour_score)))
            cfg.save()
            messages.success(request, 'تنظیمات امتیاز ذخیره شد ✓')
        except (ValueError, TypeError):
            messages.error(request, 'مقادیر وارد شده معتبر نیستند.')
        return redirect('dashboard:score_settings')
    return render(request, 'dashboard/score_settings.html', {'cfg': cfg})


# ═══════════════════════════════════════════════════════
#  💜 مدیریت ضربان
# ═══════════════════════════════════════════════════════

@login_required
@user_passes_test(is_admin)
def zarban_list(request):
    """لیست کاربران + موجودی ضربان + فرم اعطا/کسر"""
    search = request.GET.get('q', '').strip()
    sort   = request.GET.get('sort', 'balance')   # balance | username | date

    users_qs = User.objects.select_related('zarban_wallet', 'gamer_profile').all()
    if search:
        users_qs = users_qs.filter(
            Q(username__icontains=search) |
            Q(email__icontains=search)    |
            Q(gamer_profile__phone__icontains=search)
        )

    # Attach wallet eagerly (get_or_create for users with no wallet)
    user_list = list(users_qs)
    for u in user_list:
        if not hasattr(u, 'zarban_balance'):
            try:
                u.zarban_balance = u.zarban_wallet.balance
            except ZarbanWallet.DoesNotExist:
                u.zarban_balance = 0

    if sort == 'balance':
        user_list.sort(key=lambda u: u.zarban_balance, reverse=True)
    elif sort == 'username':
        user_list.sort(key=lambda u: u.username.lower())
    else:
        user_list.sort(key=lambda u: u.date_joined, reverse=True)

    paginator   = Paginator(user_list, 20)
    page_number = request.GET.get('page', 1)
    page_obj    = paginator.get_page(page_number)

    # Stats
    from django.db.models import Sum
    total_zarban = ZarbanWallet.objects.aggregate(s=Sum('balance'))['s'] or 0
    total_tx     = ZarbanTransaction.objects.count()
    total_wallets = ZarbanWallet.objects.count()

    # Recent transactions (last 30)
    recent_tx = ZarbanTransaction.objects.select_related(
        'wallet__user', 'admin'
    ).order_by('-created_at')[:30]

    return render(request, 'dashboard/zarban.html', {
        'page_obj':      page_obj,
        'search':        search,
        'sort':          sort,
        'total_zarban':  total_zarban,
        'total_tx':      total_tx,
        'total_wallets': total_wallets,
        'recent_tx':     recent_tx,
    })


@login_required
@user_passes_test(is_admin)
def zarban_manage(request, user_id):
    """اعطا یا کسر ضربان از یک کاربر مشخص"""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'method not allowed'}, status=405)

    target_user = get_object_or_404(User, pk=user_id)
    wallet      = ZarbanWallet.get_or_create_for(target_user)

    try:
        action = request.POST.get('action')   # 'add' یا 'deduct'
        amount = int(request.POST.get('amount', 0))
        reason = request.POST.get('reason', '').strip()
        notify = request.POST.get('notify') == '1'

        if amount <= 0:
            return JsonResponse({'ok': False, 'error': 'مقدار باید مثبت باشد'})

        if action == 'add':
            wallet.balance += amount
            tx_type = ZarbanTransaction.TX_CREDIT
        elif action == 'deduct':
            wallet.balance = max(0, wallet.balance - amount)
            tx_type = ZarbanTransaction.TX_DEBIT
        else:
            return JsonResponse({'ok': False, 'error': 'action نامعتبر'})

        wallet.save()

        ZarbanTransaction.objects.create(
            wallet=wallet, amount=amount, tx_type=tx_type,
            reason=reason, admin=request.user
        )

        # اعلان به کاربر
        if notify:
            if action == 'add':
                text = f'ادمین {amount} ضربان 💜 به کیف پول شما اضافه کرد'
                if reason:
                    text += f' — {reason}'
            else:
                text = f'ادمین {amount} ضربان 💜 از کیف پول شما کسر کرد'
                if reason:
                    text += f' — {reason}'

            Notification.objects.create(
                recipient=target_user,
                sender=request.user,
                notif_type='zarban',
                custom_text=text,
            )

        return JsonResponse({
            'ok': True,
            'new_balance': wallet.balance,
            'action': action,
            'amount': amount,
        })

    except (ValueError, TypeError) as e:
        return JsonResponse({'ok': False, 'error': str(e)})


# ══════════════════════════════════════════════════════════
#  🎰  مدیریت گردونه شانس
# ══════════════════════════════════════════════════════════

@login_required
@user_passes_test(is_admin)
def spin_wheel_list(request):
    wheels = SpinWheel.objects.annotate(item_count=Count('items')).order_by('order', '-created_at')
    return render(request, 'dashboard/spin_wheels.html', {'wheels': wheels})


@login_required
@user_passes_test(is_admin)
def spin_wheel_add(request):
    if request.method == 'POST':
        wheel = SpinWheel()
        wheel.name             = request.POST.get('name', '').strip()
        wheel.description      = request.POST.get('description', '').strip()
        wheel.cooldown_hours   = max(0, _int(request.POST.get('cooldown_hours'), 24))
        wheel.cost_zarban      = max(0, _int(request.POST.get('cost_zarban'), 50))
        wheel.order            = _int(request.POST.get('order'), 0)
        wheel.is_active        = request.POST.get('is_active') == 'on'
        wheel.save()
        messages.success(request, f'گردونه «{wheel.name}» ساخته شد ✓')
        return redirect('dashboard:spin_wheel_edit', wheel_id=wheel.pk)
    return render(request, 'dashboard/spin_wheel_form.html', {'action': 'add', 'wheel': None})


@login_required
@user_passes_test(is_admin)
def spin_wheel_edit(request, wheel_id):
    wheel = get_object_or_404(SpinWheel, pk=wheel_id)
    if request.method == 'POST':
        wheel.name             = request.POST.get('name', wheel.name).strip()
        wheel.description      = request.POST.get('description', '').strip()
        wheel.cooldown_hours   = max(0, _int(request.POST.get('cooldown_hours'), 24))
        wheel.cost_zarban      = max(0, _int(request.POST.get('cost_zarban'), 0))
        wheel.order            = _int(request.POST.get('order'), 0)
        wheel.is_active        = request.POST.get('is_active') == 'on'
        wheel.save()
        messages.success(request, 'تغییرات ذخیره شد ✓')
        return redirect('dashboard:spin_wheel_edit', wheel_id=wheel.pk)
    items = wheel.items.order_by('order', 'id')
    total_prob = sum(i.probability for i in items if i.is_active)
    return render(request, 'dashboard/spin_wheel_form.html', {
        'action': 'edit', 'wheel': wheel, 'items': items,
        'total_prob': total_prob,
        'reward_types': SpinWheelItem.REWARD_TYPES,
    })


@login_required
@user_passes_test(is_admin)
def spin_wheel_delete(request, wheel_id):
    wheel = get_object_or_404(SpinWheel, pk=wheel_id)
    if request.method == 'POST':
        name = wheel.name
        wheel.delete()
        messages.success(request, f'گردونه «{name}» حذف شد.')
        return redirect('dashboard:spin_wheels')
    return render(request, 'dashboard/spin_wheel_form.html', {'action': 'delete', 'wheel': wheel})


@login_required
@user_passes_test(is_admin)
def spin_wheel_toggle(request, wheel_id):
    wheel = get_object_or_404(SpinWheel, pk=wheel_id)
    wheel.is_active = not wheel.is_active
    wheel.save()
    return JsonResponse({'ok': True, 'is_active': wheel.is_active})


@login_required
@user_passes_test(is_admin)
def spin_wheel_items(request, wheel_id):
    """AJAX: مدیریت آیتم‌های یک گردونه (add / edit / delete)"""
    wheel = get_object_or_404(SpinWheel, pk=wheel_id)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'add':
            item = SpinWheelItem(wheel=wheel)
            item.name          = request.POST.get('name', '').strip()
            item.probability   = _float(request.POST.get('probability'), 10)
            item.reward_type   = request.POST.get('reward_type', SpinWheelItem.REWARD_NOTHING)
            item.reward_amount = _int(request.POST.get('reward_amount'), 0)
            item.color         = request.POST.get('color', '#6d28d9')
            item.emoji         = request.POST.get('emoji', '🎁')
            item.order         = _int(request.POST.get('order'), 0)
            item.is_active     = True
            item.save()
            total = sum(i.probability for i in wheel.items.filter(is_active=True))
            return JsonResponse({'ok': True, 'item_id': item.pk, 'total_prob': round(total, 2)})

        elif action == 'edit':
            item = get_object_or_404(SpinWheelItem, pk=request.POST.get('item_id'), wheel=wheel)
            item.name          = request.POST.get('name', item.name).strip()
            item.probability   = _float(request.POST.get('probability'), item.probability)
            item.reward_type   = request.POST.get('reward_type', item.reward_type)
            item.reward_amount = _int(request.POST.get('reward_amount'), item.reward_amount)
            item.color         = request.POST.get('color', item.color)
            item.emoji         = request.POST.get('emoji', item.emoji)
            item.order         = _int(request.POST.get('order'), item.order)
            item.is_active     = request.POST.get('is_active', 'true') == 'true'
            item.save()
            total = sum(i.probability for i in wheel.items.filter(is_active=True))
            return JsonResponse({'ok': True, 'total_prob': round(total, 2)})

        elif action == 'delete':
            item = get_object_or_404(SpinWheelItem, pk=request.POST.get('item_id'), wheel=wheel)
            item.delete()
            total = sum(i.probability for i in wheel.items.filter(is_active=True))
            return JsonResponse({'ok': True, 'total_prob': round(total, 2)})

    return JsonResponse({'ok': False, 'error': 'invalid'}, status=400)


@login_required
@user_passes_test(is_admin)
def upload_spin_icon(request):
    if request.method != 'POST' or 'svg' not in request.FILES:
        return JsonResponse({'ok': False, 'error': 'فایل ارسال نشد'})
    f = request.FILES['svg']
    if not f.name.lower().endswith('.svg') and f.content_type not in ('image/svg+xml', 'text/plain'):
        return JsonResponse({'ok': False, 'error': 'فقط فایل SVG قبول میشه'})
    if f.size > 200 * 1024:
        return JsonResponse({'ok': False, 'error': 'حداکثر ۲۰۰ کیلوبایت'})
    import uuid
    from django.conf import settings
    icon_dir = os.path.join(settings.MEDIA_ROOT, 'spin_icons')
    os.makedirs(icon_dir, exist_ok=True)
    fname = f'custom_{uuid.uuid4().hex[:8]}.svg'
    fpath = os.path.join(icon_dir, fname)
    with open(fpath, 'wb') as out:
        for chunk in f.chunks():
            out.write(chunk)
    url = settings.MEDIA_URL + 'spin_icons/' + fname
    return JsonResponse({'ok': True, 'url': url})


# ═══════════════════════════════════════════════════════════════
#  PREMIUM
# ═══════════════════════════════════════════════════════════════

@login_required
@user_passes_test(is_admin)
def premium_index(request):
    plans = PremiumPlan.objects.all()
    active_subs = PremiumSubscription.objects.filter(
        is_active=True, end_date__gt=timezone.now()
    ).select_related('user', 'plan').order_by('-created_at')
    expired_subs = PremiumSubscription.objects.filter(
        is_active=True, end_date__lte=timezone.now()
    ).select_related('user', 'plan').order_by('-end_date')[:20]
    return render(request, 'dashboard/premium.html', {
        'plans': plans,
        'active_subs': active_subs,
        'expired_subs': expired_subs,
        'active_count': active_subs.count(),
    })


@login_required
@user_passes_test(is_admin)
def premium_plan_save(request):
    if request.method != 'POST':
        return redirect('dashboard:premium')
    plan_id  = request.POST.get('plan_id')
    plan     = get_object_or_404(PremiumPlan, pk=plan_id) if plan_id else PremiumPlan()
    plan.name        = request.POST.get('name', '').strip()
    plan.duration    = request.POST.get('duration', '1_month')
    plan.price       = int(request.POST.get('price', 0) or 0)
    plan.description = request.POST.get('description', '').strip()
    plan.features    = request.POST.get('features', '').strip()
    plan.is_active   = request.POST.get('is_active') == 'on'
    plan.save()
    messages.success(request, 'پلن ذخیره شد.')
    return redirect('dashboard:premium')


@login_required
@user_passes_test(is_admin)
def premium_plan_delete(request, plan_id):
    plan = get_object_or_404(PremiumPlan, pk=plan_id)
    plan.delete()
    messages.success(request, 'پلن حذف شد.')
    return redirect('dashboard:premium')


def _find_user_by_query(q):
    """پیدا کردن کاربر با یوزرنیم، ایمیل یا شماره موبایل"""
    user = User.objects.filter(username=q).first()
    if user:
        return user
    user = User.objects.filter(email__iexact=q).first()
    if user:
        return user
    gp = GamerProfile.objects.filter(phone=q).select_related('user').first()
    if gp:
        return gp.user
    return None


@login_required
@user_passes_test(is_admin)
def premium_assign(request):
    if request.method != 'POST':
        return redirect('dashboard:premium')
    query   = request.POST.get('user_query', '').strip()
    plan_id = request.POST.get('plan_id')
    note    = request.POST.get('note', '').strip()
    user = _find_user_by_query(query)
    if not user:
        messages.error(request, f'کاربری با «{query}» پیدا نشد.')
        return redirect('dashboard:premium')
    plan  = get_object_or_404(PremiumPlan, pk=plan_id)
    start = timezone.now()
    end   = start + timedelta(days=plan.duration_days)
    PremiumSubscription.objects.create(
        user=user, plan=plan, start_date=start, end_date=end,
        is_active=True, assigned_by=request.user, note=note
    )
    superuser = User.objects.filter(is_superuser=True).first()
    if superuser:
        Notification.objects.create(
            recipient=user, sender=superuser,
            notif_type='admin',
            custom_text=f'🌟 اشتراک پریمیوم «{plan.name}» برای شما فعال شد! تا {_to_jalali(end)} معتبر است.'
        )
    messages.success(request, f'اشتراک پریمیوم برای «{user.username}» فعال شد.')
    return redirect('dashboard:premium')


@login_required
@user_passes_test(is_admin)
def premium_revoke(request, sub_id):
    sub = get_object_or_404(PremiumSubscription, pk=sub_id)
    sub.is_active = False
    sub.save(update_fields=['is_active'])
    messages.success(request, f'اشتراک «{sub.user.username}» لغو شد.')
    return redirect('dashboard:premium')


@login_required
@user_passes_test(is_admin)
def premium_adjust_days(request):
    """هدیه دادن یا کم کردن روز پریمیوم از کاربر"""
    if request.method != 'POST':
        return redirect('dashboard:premium')

    query = request.POST.get('user_query', '').strip()
    try:
        days = int(request.POST.get('days', 0))
    except ValueError:
        messages.error(request, 'تعداد روز نامعتبر است.')
        return redirect('dashboard:premium')
    note = request.POST.get('note', '').strip()

    if days == 0:
        messages.error(request, 'تعداد روز نمی‌تواند صفر باشد.')
        return redirect('dashboard:premium')

    user = _find_user_by_query(query)
    if not user:
        messages.error(request, f'کاربری با «{query}» پیدا نشد.')
        return redirect('dashboard:premium')

    now = timezone.now()
    sub = PremiumSubscription.objects.filter(user=user, is_active=True, end_date__gt=now).order_by('-end_date').first()

    if sub:
        new_end = sub.end_date + timedelta(days=days)
        if new_end <= now:
            # اشتراک منفی شد — لغو کن
            sub.is_active = False
            sub.end_date = now
            sub.save(update_fields=['is_active', 'end_date'])
            action_text = f'اشتراک «{user.username}» به دلیل کسر روز لغو شد.'
        else:
            sub.end_date = new_end
            if note:
                sub.note = (sub.note + ' | ' + note).strip(' | ')
            sub.save(update_fields=['end_date', 'note'])
            action_text = f'{"+" if days > 0 else ""}{days} روز برای «{user.username}» اعمال شد. پایان جدید: {_to_jalali(new_end)}'
    else:
        if days <= 0:
            messages.error(request, f'کاربر «{user.username}» اشتراک فعالی ندارد؛ نمی‌توان روز کم کرد.')
            return redirect('dashboard:premium')
        # اشتراک جدید هدیه‌ای بدون پلن
        end = now + timedelta(days=days)
        sub = PremiumSubscription.objects.create(
            user=user, plan=None, start_date=now, end_date=end,
            is_active=True, assigned_by=request.user,
            note=note or f'هدیه {days} روزه از ادمین'
        )
        action_text = f'{days} روز پریمیوم هدیه به «{user.username}» داده شد. تا {_to_jalali(end)}'

    # اطلاع‌رسانی به کاربر
    admin_user = User.objects.filter(username='admin').first() or request.user
    if days > 0:
        Notification.objects.create(
            recipient=user, sender=admin_user,
            notif_type='admin',
            custom_text=f'🎁 {days} روز اشتراک پریمیوم به شما داده شد.'
        )
    else:
        Notification.objects.create(
            recipient=user, sender=admin_user,
            notif_type='admin',
            custom_text=f'⚠️ {abs(days)} روز اشتراک پریمیوم از شما کسر شد.'
        )

    messages.success(request, action_text)
    return redirect('dashboard:premium')


# ══════════════════════════════════════════════════════════
#  🎯  ماموریت‌های روزانه (چرخه‌ی روزها + ماموریت‌ها)
# ══════════════════════════════════════════════════════════

@login_required
@user_passes_test(is_admin)
def daily_mission_list(request):
    from django.db.models import Prefetch
    days = MissionDay.objects.prefetch_related(
        Prefetch('missions', queryset=DailyMission.objects.order_by('order', 'id'))
    ).annotate(mission_count=Count('missions')).order_by('day_number', 'id')
    cycle = MissionDay.active_cycle()
    today_day = MissionDay.current()
    always_missions = DailyMission.objects.filter(day__isnull=True).order_by('order', 'id')
    return render(request, 'dashboard/daily_missions.html', {
        'days': days,
        'cycle_len': len(cycle),
        'today_day': today_day,
        'always_missions': always_missions,
        'event_choices': DailyMission.EVENT_CHOICES,
    })


@login_required
@user_passes_test(is_admin)
def mission_day_add(request):
    if request.method == 'POST':
        d = MissionDay()
        d.day_number = max(1, _int(request.POST.get('day_number'), 1))
        d.label      = request.POST.get('label', '').strip()
        d.is_active  = request.POST.get('is_active') == 'on'
        d.save()
        messages.success(request, f'«{d}» اضافه شد ✓')
        return redirect('dashboard:mission_day_edit', day_id=d.pk)
    # شماره‌ی پیشنهادی روز بعدی
    last = MissionDay.objects.order_by('-day_number').first()
    next_num = (last.day_number + 1) if last else 1
    return render(request, 'dashboard/mission_day_form.html', {
        'action': 'add', 'day': None, 'next_num': next_num,
        'event_choices': DailyMission.EVENT_CHOICES,
    })


@login_required
@user_passes_test(is_admin)
def mission_day_edit(request, day_id):
    day = get_object_or_404(MissionDay, pk=day_id)
    if request.method == 'POST':
        day.day_number = max(1, _int(request.POST.get('day_number'), day.day_number))
        day.label      = request.POST.get('label', '').strip()
        day.is_active  = request.POST.get('is_active') == 'on'
        day.save()
        # اگه AJAX بود JSON برگردون، وگرنه redirect معمولی
        if request.headers.get('X-CSRFToken') and request.POST.get('ajax') == '1':
            return JsonResponse({'ok': True})
        messages.success(request, 'تغییرات روز ذخیره شد ✓')
        return redirect('dashboard:mission_day_edit', day_id=day.pk)
    missions = day.missions.order_by('order', 'id')
    return render(request, 'dashboard/mission_day_form.html', {
        'action': 'edit', 'day': day, 'missions': missions,
        'event_choices': DailyMission.EVENT_CHOICES,
    })


@login_required
@user_passes_test(is_admin)
def mission_day_delete(request, day_id):
    day = get_object_or_404(MissionDay, pk=day_id)
    if request.method == 'POST':
        label = str(day)
        day.delete()  # ماموریت‌های این روز هم cascade حذف می‌شوند
        messages.success(request, f'«{label}» و ماموریت‌هایش حذف شد.')
        return redirect('dashboard:daily_missions')
    return redirect('dashboard:mission_day_edit', day_id=day.pk)


@login_required
@user_passes_test(is_admin)
def mission_day_toggle(request, day_id):
    day = get_object_or_404(MissionDay, pk=day_id)
    day.is_active = not day.is_active
    day.save(update_fields=['is_active'])
    return JsonResponse({'ok': True, 'is_active': day.is_active})


@login_required
@user_passes_test(is_admin)
def mission_save(request):
    """AJAX: افزودن/ویرایش/حذف یک ماموریت (هم برای روزهای چرخه، هم ماموریت‌های همیشگی).
    day_id خالی = ماموریت همیشگی."""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'invalid'}, status=400)

    action = request.POST.get('action')
    valid_events = [e[0] for e in DailyMission.EVENT_CHOICES]

    if action == 'delete':
        m = get_object_or_404(DailyMission, pk=request.POST.get('mission_id'))
        m.delete()
        return JsonResponse({'ok': True})

    if action == 'add':
        m = DailyMission()
        day_id = request.POST.get('day_id')
        m.day = get_object_or_404(MissionDay, pk=day_id) if day_id else None
    elif action == 'edit':
        m = get_object_or_404(DailyMission, pk=request.POST.get('mission_id'))
    else:
        return JsonResponse({'ok': False, 'error': 'invalid action'}, status=400)

    event = request.POST.get('event', '')
    if event not in valid_events:
        return JsonResponse({'ok': False, 'error': 'رویداد نامعتبر'}, status=400)
    m.title         = request.POST.get('title', '').strip() or 'ماموریت'
    m.description   = request.POST.get('description', '').strip()
    m.event         = event
    m.target_count  = max(1, _int(request.POST.get('target_count'), 1))
    m.reward_zarban = max(0, _int(request.POST.get('reward_zarban'), 0))
    m.icon          = request.POST.get('icon', '').strip() or 'bi-check-circle-fill'
    m.order         = _int(request.POST.get('order'), 0)
    if action == 'add':
        m.is_active = True
    else:
        m.is_active = request.POST.get('is_active', 'true') == 'true'
    m.save()
    return JsonResponse({'ok': True, 'mission_id': m.pk})


# ══════════════════════════════════════════════════════════
# دستاوردها
# ══════════════════════════════════════════════════════════

@login_required
@user_passes_test(is_admin)
def achievements_list(request):
    definitions = AchievementDefinition.objects.all().order_by('order', 'title')
    return render(request, 'dashboard/achievements.html', {
        'definitions': definitions,
    })


@login_required
@user_passes_test(is_admin)
def achievement_definition_save(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)
    action = request.POST.get('action')
    if action == 'delete':
        defn = get_object_or_404(AchievementDefinition, pk=request.POST.get('id'))
        defn.delete()
        return JsonResponse({'ok': True})
    if action == 'add':
        defn = AchievementDefinition()
    else:
        defn = get_object_or_404(AchievementDefinition, pk=request.POST.get('id'))
    ach_type = request.POST.get('ach_type', '').strip()
    title    = request.POST.get('title', '').strip()
    if not ach_type or not title:
        return JsonResponse({'ok': False, 'error': 'کد یکتا و عنوان الزامی‌اند'})
    defn.ach_type      = ach_type
    defn.level         = max(1, _int(request.POST.get('level'), 1))
    defn.title         = title
    defn.description   = request.POST.get('description', '').strip()
    defn.icon          = request.POST.get('icon', 'bi-trophy').strip() or 'bi-trophy'
    defn.reward_zarban = max(0, _int(request.POST.get('reward_zarban'), 0))
    defn.is_active     = request.POST.get('is_active', 'true') == 'true'
    defn.order         = _int(request.POST.get('order'), 0)
    defn.target = max(0, _int(request.POST.get('target'), 0))
    try:
        defn.save()
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)})
    return JsonResponse({'ok': True, 'id': defn.pk})


@login_required
@user_passes_test(is_admin)
def achievement_icon_upload(request):
    """آپلود SVG آیکون برای یک سطح دستاورد"""
    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)
    defn = get_object_or_404(AchievementDefinition, pk=request.POST.get('id'))
    f = request.FILES.get('icon_svg')
    if not f:
        return JsonResponse({'ok': False, 'error': 'فایلی ارسال نشد'})
    if f.size > 2 * 1024 * 1024:
        return JsonResponse({'ok': False, 'error': 'حداکثر ۲ مگابایت'})
    allowed = ('image/svg+xml', 'image/png', 'image/webp', 'image/jpeg')
    if f.content_type not in allowed and not f.name.lower().endswith('.svg'):
        return JsonResponse({'ok': False, 'error': 'فقط SVG / PNG / WebP'})
    if defn.icon_svg:
        defn.icon_svg.delete(save=False)
    defn.icon_svg.save(f.name, f, save=True)
    return JsonResponse({'ok': True, 'url': defn.icon_svg.url})
