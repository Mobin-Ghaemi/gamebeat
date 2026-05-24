from django.shortcuts import render, redirect, get_object_or_404
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
from .models import Game, GENRE_CHOICES, PLATFORM_CHOICES
from community.models import Post, Comment, Hashtag, GamerProfile, PostLike, PostReaction, GameBacklog


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
        chart_labels.append(f'{day.month}/{day.day}')
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
def user_list(request):
    q = request.GET.get('q', '').strip()
    filter_type = request.GET.get('filter', 'all')

    users = User.objects.annotate(post_count=Count('posts')).order_by('-date_joined')

    if q:
        users = users.filter(Q(username__icontains=q) | Q(email__icontains=q))

    if filter_type == 'active':
        users = users.filter(is_active=True, is_staff=False)
    elif filter_type == 'banned':
        users = users.filter(is_active=False)
    elif filter_type == 'staff':
        users = users.filter(is_staff=True)

    paginator = Paginator(users, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'dashboard/users.html', {
        'page_obj': page_obj,
        'users': page_obj,  # backward-compat
        'q': q,
        'status': filter_type,
        'filter_type': filter_type,
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
def post_list(request):
    q = request.GET.get('q', '').strip()
    filter_type = request.GET.get('filter', 'all')

    posts = Post.objects.select_related('author').annotate(
        likes_count_ann=Count('likes', distinct=True),
        comments_count_ann=Count('comments', distinct=True),
    ).order_by('-created_at')

    if q:
        posts = posts.filter(Q(content__icontains=q) | Q(author__username__icontains=q))

    if filter_type != 'all':
        posts = posts.filter(post_type=filter_type)

    paginator = Paginator(posts, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'dashboard/posts.html', {
        'page_obj': page_obj,
        'q': q,
        'filter_type': filter_type,
        'post_type_choices': Post.POST_TYPES,
    })


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

    comments = Comment.objects.select_related('post', 'author').order_by('-created_at')

    if q:
        comments = comments.filter(Q(content__icontains=q) | Q(author__username__icontains=q))

    paginator = Paginator(comments, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'dashboard/comments.html', {
        'page_obj': page_obj,
        'q': q,
    })


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
    q = request.GET.get('q', '').strip()
    hashtags = Hashtag.objects.order_by('-post_count')

    if q:
        hashtags = hashtags.filter(name__icontains=q)

    return render(request, 'dashboard/hashtags.html', {
        'hashtags': hashtags,
        'q': q,
    })


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
    q = request.GET.get('q', '')
    genre = request.GET.get('genre', '')
    filter_genre = request.GET.get('filter_genre', genre)
    games = Game.objects.all()
    if q:
        games = games.filter(name__icontains=q)
    if filter_genre and filter_genre != 'all':
        games = games.filter(genre=filter_genre)
    elif genre:
        games = games.filter(genre=genre)
    return render(request, 'dashboard/games.html', {
        'games': games,
        'q': q,
        'genre': genre,
        'filter_genre': filter_genre,
        'genre_choices': GENRE_CHOICES,
    })


@login_required
@user_passes_test(is_admin)
def game_add(request):
    if request.method == 'POST':
        g = Game()
        g.name = request.POST.get('name', '').strip()
        g.genre = request.POST.get('genre', '')
        g.developer = request.POST.get('developer', '')
        g.publisher = request.POST.get('publisher', '')
        g.release_year = request.POST.get('release_year') or None
        g.description = request.POST.get('description', '')
        g.is_featured = 'is_featured' in request.POST
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
        game.name = request.POST.get('name', '').strip()
        game.genre = request.POST.get('genre', '')
        game.developer = request.POST.get('developer', '')
        game.publisher = request.POST.get('publisher', '')
        game.release_year = request.POST.get('release_year') or None
        game.description = request.POST.get('description', '')
        game.is_featured = 'is_featured' in request.POST
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
def comment_bulk_delete(request):
    if request.method == 'POST':
        ids = request.POST.getlist('ids')
        if ids:
            deleted, _ = Comment.objects.filter(pk__in=ids).delete()
            messages.success(request, f'{deleted} کامنت حذف شد.')
        else:
            messages.error(request, 'هیچ کامنتی انتخاب نشده.')
    return redirect('dashboard:comments')
