"""
Middleware برای ردیابی زمان آنلاین کاربران.
هر درخواست احراز‌هویت‌شده سشن فعال را به‌روز می‌کند.
"""

import json


class JsonErrorTranslationMiddleware:
    """
    خطاهای JSON انگلیسی را قبل از رسیدن به فرانت به فارسی تبدیل می‌کند.
    """

    ERROR_MAP = {
        'method': 'متد درخواست مجاز نیست.',
        'method not allowed': 'متد درخواست مجاز نیست.',
        'invalid': 'درخواست نامعتبر است.',
        'invalid action': 'عملیات نامعتبر است.',
        'action نامعتبر': 'عملیات نامعتبر است.',
        'self': 'نمی‌توانید این عملیات را روی خودتان انجام دهید.',
        'empty': 'محتوا نمی‌تواند خالی باشد.',
        'blocked': 'این کاربر شما را بلاک کرده است.',
        'forbidden': 'اجازه انجام این عملیات را ندارید.',
        'premium_required': 'برای استفاده از این قابلیت باید اشتراک پریمیوم داشته باشید.',
        'max_boost_reached': 'بیشتر از این نمی‌توانید پست بوست‌شده فعال داشته باشید.',
        'no name': 'نام الزامی است.',
        'no query': 'عبارت جستجو وارد نشده است.',
        'invalid Steam URL or AppID': 'لینک یا AppID استیم نامعتبر است.',
        'invalid score': 'امتیاز نامعتبر است.',
        'score must be 1-5': 'امتیاز باید بین ۱ تا ۵ باشد.',
        'not in backlog': 'این مورد در بک‌لاگ شما نیست.',
        'not a member': 'شما عضو این بخش نیستید.',
        'invalid_params': 'پارامترهای درخواست نامعتبر است.',
        'invalid_coords': 'مختصات ارسالی نامعتبر است.',
        'rate_limited': 'تعداد درخواست‌ها بیش از حد مجاز است.',
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        content_type = response.get('Content-Type', '')
        if 'application/json' not in content_type:
            return response

        try:
            payload = json.loads(response.content.decode(response.charset or 'utf-8'))
        except Exception:
            return response

        error_value = payload.get('error')
        if isinstance(error_value, str) and error_value in self.ERROR_MAP:
            payload['error'] = self.ERROR_MAP[error_value]
            response.content = json.dumps(payload, ensure_ascii=False).encode(response.charset or 'utf-8')

        return response


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
            session = UserSession.get_or_create_active(request.user)

            # هر ۵ دقیقه یک‌بار چک کن آیا ساعت جدیدی کامل شده
            from django.core.cache import cache
            award_key = f'zarban_check_{request.user.id}'
            if not cache.get(award_key):
                cache.set(award_key, True, 5 * 60)  # هر ۵ دقیقه
                UserSession.check_and_award_zarban(request.user)
        except Exception:
            pass  # هیچ‌وقت نباید سایت را خراب کند

        return response
