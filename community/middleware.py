"""
Middleware برای ردیابی زمان آنلاین کاربران.
هر درخواست احراز‌هویت‌شده سشن فعال را به‌روز می‌کند.
"""


class OnlineTrackingMiddleware:
    """
    بعد از AuthenticationMiddleware قرار می‌گیرد.
    فقط روی GET/POST های عادی (نه AJAX/API های polling) اجرا می‌شود
    تا تعداد queries را کم نگه دارد.
    """

    # مسیرهایی که نباید session را به‌روز کنند
    SKIP_PATHS = (
        '/api/', '/static/', '/media/',
        '/notifications/count/', '/inbox/count/',
        '/poll/', '/conversation_poll/',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # فقط کاربران لاگین‌کرده
        if not getattr(request, 'user', None) or not request.user.is_authenticated:
            return response

        # رد کردن درخواست‌های polling/API
        path = request.path_info
        if any(path.startswith(p) or path.endswith(p) for p in self.SKIP_PATHS):
            return response

        # به‌روزرسانی یا ایجاد سشن (lazy import تا از circular import جلوگیری شود)
        try:
            from community.models import UserSession
            UserSession.get_or_create_active(request.user)
        except Exception:
            pass  # هیچ‌وقت نباید سایت را خراب کند

        return response
