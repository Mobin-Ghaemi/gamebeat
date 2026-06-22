"""
اجرا: python3 manage.py shell -c "exec(open('retry_persian_descs.py').read())"

همه بازی‌ها رو با توضیح فارسی بلند (۶ پاراگراف) regenerate می‌کنه.
اگه 429 گرفتی، چند ساعت صبر کن و دوباره اجرا کن — از همونجا که موند ادامه میده.
"""
import re, urllib.request, json, time
from dashboard.models import Game, GENRE_CHOICES
from django.core.cache import cache

API_KEY = 'aa-vnLiypnK6cjfqse799P15gJP4tCj4maQl9RUVEcnvoX8RMWE'
API_URL = 'https://api.avalai.ir/v1/chat/completions'
genre_map = dict(GENRE_CHOICES)

MIN_LEN = 700  # توضیح باید حداقل ۷۰۰ کاراکتر باشه


def needs_update(text):
    if not text:
        return True
    persian_chars = len(re.findall(r'[؀-ۿ]', text))
    if persian_chars < 50:
        return True
    if len(text) < MIN_LEN:
        return True
    return False


def call_claude(prompt):
    payload = json.dumps({
        'model': 'claude-haiku-4-5-20251001',
        'messages': [{'role': 'user', 'content': prompt}],
        'max_tokens': 1200
    }).encode()
    req = urllib.request.Request(API_URL, data=payload, headers={
        'Authorization': f'Bearer {API_KEY}',
        'Content-Type': 'application/json'
    })
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())['choices'][0]['message']['content'].strip()


def gen_desc(game):
    genres = ', '.join([genre_map.get(g, g) for g in (game.genres or [])])
    prompt = f"""یک توضیح کامل، جذاب و طولانی به زبان فارسی برای بازی زیر بنویس.

قوانین مهم:
- فقط فارسی خالص بنویس
- هیچ عنوان، # یا ** یا markdown نداشته باش
- فقط پاراگراف‌های خالص متن
- دقیقاً ۶ پاراگراف بنویس
- هر پاراگراف حداقل ۳ جمله باشه
- لحن: هیجان‌انگیز، جذاب و اشتیاق‌برانگیز برای گیمرها
- از داستان، مکانیک‌های گیم‌پلی، ویژگی‌های خاص و چرایی باید بازی کرد صحبت کن

نام بازی: {game.name}
ژانر: {genres or 'نامشخص'}
سازنده: {game.developer or 'نامشخص'}
سال انتشار: {game.release_year or 'نامشخص'}"""
    return call_claude(prompt)


games = [g for g in Game.objects.filter(is_active=True).order_by('name') if needs_update(g.description)]
print(f'بازی‌های نیاز به توضیح: {len(games)}')

ok = err = 0
for i, g in enumerate(games, 1):
    try:
        desc = gen_desc(g)
        g.description = desc
        g.save(update_fields=['description'])
        ok += 1
        print(f'[{i}/{len(games)}] ✓ {g.name[:50]} ({len(desc)} chars)')
        time.sleep(3)
    except Exception as e:
        err += 1
        print(f'[{i}/{len(games)}] ✗ {g.name[:40]}: {e}')
        if '429' in str(e):
            print('  Rate limit — توقف. بعداً دوباره اجرا کن.')
            break
        time.sleep(4)

if ok:
    cache.clear()
    print('Cache cleared.')

print(f'\nنتیجه: {ok} موفق، {err} خطا')
