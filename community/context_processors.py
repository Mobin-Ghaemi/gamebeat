from .models import FollowRequest


def nav_badges(request):
    """شمارنده‌های سراسری نوار بالا — مثل درخواست‌های فالوِ در انتظار."""
    count = 0
    if request.user.is_authenticated:
        count = FollowRequest.objects.filter(
            to_user=request.user, status='pending'
        ).count()
    return {'pending_follow_requests': count}
