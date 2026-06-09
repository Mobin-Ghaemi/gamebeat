from django import template
from django.urls import reverse
from django.utils.html import escape
from django.utils.safestring import mark_safe
import re

register = template.Library()

MONTHS_FA = [
    '', 'فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور',
    'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند'
]

def _to_fa_digits(n):
    return str(n).translate(str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹'))

@register.filter
def jalali_date(value):
    """تبدیل تاریخ میلادی به شمسی — مثال: ۱۲ اردیبهشت ۱۴۰۳"""
    if not value:
        return ''
    try:
        import jdatetime
        jd = jdatetime.datetime.fromgregorian(datetime=value)
        return f'{_to_fa_digits(jd.day)} {MONTHS_FA[jd.month]} {_to_fa_digits(jd.year)}'
    except ImportError:
        # jdatetime نصب نیست — تاریخ میلادی نشون بده
        try:
            return f'{value.day} / {value.month} / {value.year}'
        except Exception:
            return str(value)
    except Exception:
        return str(value)


@register.filter
def secs_to_time(value):
    """تبدیل ثانیه به فرمت فارسی: ۶ ساعت ۳۴ دقیقه"""
    try:
        secs = int(value or 0)
        if secs <= 0:
            return ''
        hours   = secs // 3600
        minutes = (secs % 3600) // 60
        if hours and minutes:
            return f'{_to_fa_digits(hours)} ساعت و {_to_fa_digits(minutes)} دقیقه'
        elif hours:
            return f'{_to_fa_digits(hours)} ساعت'
        elif minutes:
            return f'{_to_fa_digits(minutes)} دقیقه'
        return 'کمتر از یک دقیقه'
    except (TypeError, ValueError):
        return ''


@register.simple_tag
def zarban_balance(user):
    """موجودی ضربان یک کاربر را برمی‌گرداند"""
    try:
        return user.zarban_wallet.balance
    except Exception:
        return 0


@register.filter
def hashtagify(text):
    escaped = escape(text)

    def replace(m):
        tag = m.group(1)
        url = reverse('community:hashtag_feed', args=[tag.lower()])
        return f'<a href="{url}" class="hashtag-link">#{tag}</a>'

    return mark_safe(re.sub(r'#([a-zA-Z؀-ۿ\w]{2,50})', replace, escaped))
