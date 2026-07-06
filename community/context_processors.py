from .seo import DEFAULT_DESCRIPTION, DEFAULT_ROBOTS, build_seo
from .models import FollowRequest, GameReview


def nav_badges(request):
    """شمارنده‌های سراسری نوار بالا — مثل درخواست‌های فالوِ در انتظار."""
    ctx = {'pending_follow_requests': 0, 'pending_reviews_count': 0}
    if request.user.is_authenticated:
        ctx['pending_follow_requests'] = FollowRequest.objects.filter(
            to_user=request.user, status='pending'
        ).count()
        if request.user.is_staff:
            ctx['pending_reviews_count'] = GameReview.objects.filter(is_approved=False).count()
    return ctx


def seo_defaults(request):
    resolver_name = getattr(getattr(request, 'resolver_match', None), 'url_name', '') or ''
    path = request.path or '/'
    robots = DEFAULT_ROBOTS

    noindex_prefixes = (
        '/account/',
        '/admin-panel/',
        '/notifications/',
        '/inbox/',
        '/dm/',
        '/groups/',
        '/settings/',
        '/follow-requests/',
        '/onboarding/',
        '/profile/edit/',
        '/profile/me/',
        '/profile/set-pinned-game/',
        '/gaming/',
        '/api/',
        '/heartbeat/',
    )
    noindex_names = {
        'search',
        'global_search',
        'create_post',
        'create_post_page',
        'conversation',
        'group_chat',
        'settings',
        'my_profile',
        'notifications',
        'daily_missions',
        'profile_stats',
        'gamer_finder',
    }
    if path.startswith(noindex_prefixes) or resolver_name in noindex_names or request.GET.get('q'):
        robots = 'noindex,follow'

    seo = build_seo(
        request,
        title='GameBeat | کامیونیتی فارسی گیمرها',
        description=DEFAULT_DESCRIPTION,
        robots=robots,
    )
    return {'default_seo': seo}
