import jdatetime
from django import template
from django.utils import timezone

register = template.Library()

_PERSIAN_MONTHS = [
    '', 'فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور',
    'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند'
]

_PERSIAN_DIGITS = str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹')


def _to_persian_digits(s):
    return str(s).translate(_PERSIAN_DIGITS)


def _to_jdt(value):
    if value is None:
        return None
    if isinstance(value, jdatetime.datetime):
        return value
    if isinstance(value, jdatetime.date):
        return value
    try:
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        if hasattr(value, 'hour'):
            return jdatetime.datetime.fromgregorian(datetime=value)
        return jdatetime.date.fromgregorian(date=value)
    except Exception:
        return None


@register.filter(name='jalali')
def jalali(value, fmt='Y/m/d'):
    """
    Convert a datetime/date to Jalali string.
    Format codes: Y=year, m=month(0-padded), d=day(0-padded),
                  H=hour, i=minute, s=second, N=month name
    Example: {{ post.created_at|jalali:"Y/m/d H:i" }}
    """
    jdt = _to_jdt(value)
    if jdt is None:
        return ''

    year  = jdt.year
    month = jdt.month
    day   = jdt.day

    # time fields
    hour   = getattr(jdt, 'hour', 0)
    minute = getattr(jdt, 'minute', 0)
    second = getattr(jdt, 'second', 0)

    result = (
        fmt
        .replace('Y', str(year))
        .replace('m', f'{month:02d}')
        .replace('d', f'{day:02d}')
        .replace('H', f'{hour:02d}')
        .replace('i', f'{minute:02d}')
        .replace('s', f'{second:02d}')
        .replace('N', _PERSIAN_MONTHS[month])
        .replace('j', str(day))
    )
    return _to_persian_digits(result)


@register.filter(name='jalali_date')
def jalali_date(value):
    """Shorthand: returns ۱۴۰۳/۰۸/۱۵"""
    return jalali(value, 'Y/m/d')


@register.filter(name='jalali_datetime')
def jalali_datetime(value):
    """Shorthand: returns ۱۴۰۳/۰۸/۱۵ ۱۴:۳۰"""
    return jalali(value, 'Y/m/d H:i')


@register.filter(name='jalali_full')
def jalali_full(value):
    """Returns ۱۵ آبان ۱۴۰۳"""
    jdt = _to_jdt(value)
    if jdt is None:
        return ''
    return _to_persian_digits(f'{jdt.day} {_PERSIAN_MONTHS[jdt.month]} {jdt.year}')
