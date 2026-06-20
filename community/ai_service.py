# -*- coding: utf-8 -*-
"""
سرویس هوش مصنوعی (AvalAI / OpenAI-compatible) برای بازی‌ها:
- تولید نام فارسی/فینگلیشِ خلاصه (همان‌طور که گیمر ایرانی سرچ می‌کند)
- کمک به تشخیص پلتفرم‌های هر بازی
"""
import json
import re
import time
import requests
from django.conf import settings

AVALAI_API_KEY = getattr(settings, 'AVALAI_API_KEY', '')
AVALAI_BASE = getattr(settings, 'AVALAI_BASE_URL', 'https://api.avalai.ir/v1')
AVALAI_MODEL = getattr(settings, 'AVALAI_MODEL', 'gpt-4o-mini')

_VALID_PLATFORMS = {'pc', 'ps4', 'ps5', 'xbox', 'switch', 'mobile'}


def _has_persian(text):
    return any('؀' <= ch <= 'ۿ' for ch in (text or '')[:40])


def enrich_game_with_ai(game):
    """یک بازی را با AI غنی می‌کند: name_fa، پلتفرم (اتحاد)، توضیح فارسی.
    خروجی: True اگر چیزی تغییر کرد."""
    info = ai_game_info(game.name)
    if not info:
        return False
    changed = []
    if info.get('name_fa'):
        game.name_fa = info['name_fa']
        changed.append('name_fa')
    if info.get('description'):
        game.description = info['description']
        changed.append('description')
    existing = list(game.platforms or [])
    merged = list(dict.fromkeys(existing + info.get('platforms', [])))
    if merged != existing:
        game.platforms = merged
        changed.append('platforms')
    if changed:
        game.save(update_fields=changed)
    return bool(changed)


def enrich_games(queryset, resume=True):
    """مجموعه‌ای از بازی‌ها را با AI غنی می‌کند. با resume، بازی‌هایی که
    قبلاً توضیح فارسی دارند را رد می‌کند (قابل ادامه و امن برای اجرای مجدد)."""
    n = 0
    for game in queryset:
        if resume and game.name_fa and _has_persian(game.description):
            continue
        if enrich_game_with_ai(game):
            n += 1
    return n


def normalize_fa(text):
    """نرمال‌سازی متن فارسی برای جستجوی بهتر:
    نیم‌فاصله→فاصله، یکدست‌کردن ی/ک عربی، حذف فاصله‌های اضافه."""
    if not text:
        return ''
    text = text.replace('‌', ' ')           # نیم‌فاصله (ZWNJ) → فاصله
    text = text.replace('ي', 'ی')       # ي عربی → ی فارسی
    text = text.replace('ك', 'ک')       # ك عربی → ک فارسی
    text = text.replace('،', ' ').replace(',', ' ')
    return re.sub(r'\s+', ' ', text).strip()


def ai_game_info(name):
    """برای یک بازی، نام فارسی و پلتفرم‌ها را از AI می‌گیرد.
    خروجی: {'name_fa': str, 'platforms': [..]} یا None در صورت خطا."""
    if not AVALAI_API_KEY or not name:
        return None
    user_prompt = (
        f'بازی: "{name}"\n'
        '۱) این بازی رو گیمرهای ایرانی با چه اسم‌های کوتاهِ فارسی/فینگلیشی می‌شناسن و سرچ می‌کنن؟ '
        'چند املای رایج بده (مثلاً برای Call of Duty: کالاف، کالاف دیوتی، کالاف دی یو تی). '
        'کوتاه و محاوره‌ای، نه ترجمه‌ی تحت‌اللفظی.\n'
        '۲) این بازی روی چه پلتفرم‌هاییه؟\n'
        '۳) یه توضیح کاملِ فارسیِ خفن و جذاب درباره‌ی بازی بنویس (حدود ۴ تا ۶ جمله، یک پاراگراف خوب). '
        'به این‌ها بپرداز: داستان/زمینه‌ی بازی، نوع گیم‌پلی و ژانر، حال‌وهوا و گرافیک، '
        'و چیزی که این بازی رو خاص و دیدنی می‌کنه. لحن گیمری و گیرا، نه خشک و ویکی‌پدیایی.\n'
        'فقط JSON معتبر برگردون با این ساختار:\n'
        '{"name_fa": "اسم‌های فارسی جدا با فاصله", '
        '"platforms": ["زیرمجموعه‌ای از: pc, ps4, ps5, xbox, switch, mobile"], '
        '"description": "توضیح فارسی خفن"}'
    )
    payload = {
        'model': AVALAI_MODEL,
        'temperature': 0.4,
        'messages': [
            {'role': 'system', 'content': 'تو یه دستیار دیتابیس بازی‌های ویدیویی هستی. فقط JSON معتبر برگردون، بدون هیچ توضیح اضافه.'},
            {'role': 'user', 'content': user_prompt},
        ],
    }
    # تا ۳ بار تلاش — برای مقابله با خطاهای موقتی SSL/شبکه
    for attempt in range(3):
        try:
            r = requests.post(
                f'{AVALAI_BASE}/chat/completions',
                headers={'Authorization': f'Bearer {AVALAI_API_KEY}', 'Content-Type': 'application/json'},
                json=payload, timeout=40,
            )
            if r.status_code != 200:
                time.sleep(1.5)
                continue
            content = r.json()['choices'][0]['message']['content']
            m = re.search(r'\{.*\}', content, re.S)  # استخراج JSON (احتمال ```json ... ```)
            if not m:
                return None
            data = json.loads(m.group(0))
            return {
                'name_fa': normalize_fa(data.get('name_fa') or ''),
                'platforms': [p for p in (data.get('platforms') or []) if p in _VALID_PLATFORMS],
                'description': (data.get('description') or '').strip(),
            }
        except Exception:
            time.sleep(1.5)
            continue
    return None


def ai_badge_descriptions(names):
    """برای لیستی از نام نشان‌های استیم، توضیح کوتاهِ فارسی و خفن می‌سازد.
    خروجی: dict {name: 'توضیح فارسی'} یا {} در صورت خطا."""
    if not AVALAI_API_KEY or not names:
        return {}
    uniq = list(dict.fromkeys([n for n in names if n]))
    lst = '\n'.join(f'- {n}' for n in uniq)
    user_prompt = (
        'این‌ها نام نشان‌های (badge) استیم هستن. برای هر نشان یه توضیح کوتاهِ فارسی بنویس '
        '(یک جمله) که فقط خودِ نشان رو توضیح بده — نشان چیه، چه رویدادی یا شرطی داره، '
        'یا چه دستاوردی رو نشون میده. هیچ‌وقت از «کسانی که» یا «افرادی که» یا ساختار '
        'شخصی استفاده نکن؛ مستقیم نشان رو توصیف کن. لحن خلاصه و واقعی.\n'
        f'نشان‌ها:\n{lst}\n\n'
        'فقط JSON معتبر برگردون: کلید = نام دقیقِ نشان (همون انگلیسی)، مقدار = توضیح فارسی.'
    )
    payload = {
        'model': AVALAI_MODEL, 'temperature': 0.5,
        'messages': [
            {'role': 'system', 'content': 'تو یه دستیار گیمینگ هستی. فقط JSON معتبر برگردون.'},
            {'role': 'user', 'content': user_prompt},
        ],
    }
    for _ in range(3):
        try:
            r = requests.post(
                f'{AVALAI_BASE}/chat/completions',
                headers={'Authorization': f'Bearer {AVALAI_API_KEY}', 'Content-Type': 'application/json'},
                json=payload, timeout=45,
            )
            if r.status_code != 200:
                time.sleep(1.5); continue
            content = r.json()['choices'][0]['message']['content']
            m = re.search(r'\{.*\}', content, re.S)
            if not m:
                return {}
            data = json.loads(m.group(0))
            return {k: (v or '').strip() for k, v in data.items() if isinstance(v, str)}
        except Exception:
            time.sleep(1.5); continue
    return {}
