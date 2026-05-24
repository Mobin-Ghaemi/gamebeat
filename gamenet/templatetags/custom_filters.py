from django import template

register = template.Library()

@register.filter
def persian_comma(value):
    """جداسازی اعداد با کاما به سبک فارسی"""
    try:
        # تبدیل به عدد صحیح (بدون اعشار)
        value = int(float(value))
        # تبدیل به رشته
        s = str(value)
        # اضافه کردن کاما هر 3 رقم از راست
        result = []
        for i, digit in enumerate(reversed(s)):
            if i > 0 and i % 3 == 0:
                result.append(',')
            result.append(digit)
        return ''.join(reversed(result))
    except (ValueError, TypeError):
        return value

@register.filter
def format_price(value):
    """فرمت کردن قیمت با کاما"""
    try:
        value = int(float(value))
        return f"{value:,}"
    except:
        return value

@register.filter
def round_thousands(value):
    """رند کردن ۳ رقم آخر به ۰۰۰ — مثلاً ۱۸,۶۳۵,۶۱۵ → ۱۸,۶۳۵,۰۰۰"""
    try:
        value = int(float(value))
        rounded = (value // 1000) * 1000
        return f"{rounded:,}"
    except (ValueError, TypeError):
        return value
