from django import template
from django.urls import reverse
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.utils.timesince import timesince
import re

register = template.Library()


@register.filter
def smart_time(value):
    """مثل timesince ولی وقتی کمتر از ۱ دقیقه‌ست می‌نویسد «همین الان»."""
    if not value:
        return ''
    result = timesince(value)
    # Django timesince در حالت زیر یک دقیقه می‌نویسد "0\xa0minutes"
    if result.startswith('0'):
        return 'همین الان'
    return result + ' پیش'

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
            return '۰ دقیقه'
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


@register.simple_tag
def avatar_with_frame(profile, size='md', css_class=''):
    """نمایش آواتار با فریم طلایی برای کاربران پریمیوم
    size: sm | md | lg
    """
    size_map = {'sm': '32px', 'md': '46px', 'lg': '90px', 'xl': '120px'}
    px = size_map.get(size, '46px')
    is_premium = getattr(profile, 'is_premium', False)
    initial = profile.user.username[0].upper() if profile and profile.user else '?'
    avatar_url = profile.avatar.url if profile and profile.avatar else None

    if avatar_url:
        img = f'<img src="{avatar_url}" style="width:{px};height:{px};border-radius:50%;object-fit:cover;display:block;{("border:2px solid var(--bg-dark);" if is_premium else "")} {css_class}" alt="">'
    else:
        bg = 'linear-gradient(135deg,#4c1d95,#6d28d9)'
        img = f'<div style="width:{px};height:{px};border-radius:50%;background:{bg};display:flex;align-items:center;justify-content:center;color:#fff;font-weight:700;font-size:calc({px} * 0.4);{("border:2px solid var(--bg-dark);" if is_premium else "")} {css_class}">{initial}</div>'

    if is_premium:
        frame_size = {'sm': 'frame-sm', 'md': '', 'lg': 'frame-lg', 'xl': 'frame-lg'}.get(size, '')
        return mark_safe(f'<div class="premium-frame {frame_size}" style="display:inline-flex;">{img}</div>')
    return mark_safe(img)


@register.simple_tag
def verified_badge(profile, size='md'):
    """بج فیروزه‌ای «تأیید‌شده» کنار نام کاربرانی که is_verified هستن (ادمین کلاب/استریمر شناخته‌شده)
    size: sm | md | lg
    """
    if not profile or not getattr(profile, 'is_verified', False):
        return ''
    px_map   = {'sm': '16px', 'md': '20px', 'lg': '24px'}
    icon_map = {'sm': '9',    'md': '12',   'lg': '14'}
    px      = px_map.get(size, '20px')
    icon_px = icon_map.get(size, '12')
    return mark_safe(
        f'<span title="تأیید‌شده" style="display:inline-flex;align-items:center;justify-content:center;'
        f'width:{px};height:{px};background:linear-gradient(135deg,#22d3ee,#0891b2);border-radius:50%;'
        f'flex-shrink:0;box-shadow:0 2px 8px rgba(34,211,238,.45);">'
        f'<svg viewBox="0 0 24 24" fill="white" width="{icon_px}" height="{icon_px}">'
        f'<path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg></span>'
    )
