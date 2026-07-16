import re
import time
import requests
import json
import subprocess
import xml.etree.ElementTree as ET
from urllib.parse import quote, urlencode
from django.conf import settings

STEAM_API_KEY = getattr(settings, 'STEAM_API_KEY', '')
XBOX_API_KEY = getattr(settings, 'XBOX_API_KEY', '')

# steamcommunity.com / steampowered.com اتصال از IP ایران را مسدود می‌کنند؛
# اگر STEAM_PROXY_URL ست شده باشد (آدرس Cloudflare Worker به‌عنوان reverse
# proxy)، همه‌ی درخواست‌های استیم از طریق آن عبور می‌کنند.
STEAM_PROXY_URL = getattr(settings, 'STEAM_PROXY_URL', '')


def _steam_get(url, params=None, headers=None, timeout=8):
    """GET به دامنه‌های استیم — در صورت تنظیم STEAM_PROXY_URL از طریق
    Cloudflare Worker (reverse proxy) عبور می‌کند تا بلاک IP ایران را دور بزند."""
    if params:
        url = url + ('&' if '?' in url else '?') + urlencode(params)
    if STEAM_PROXY_URL:
        url = f'{STEAM_PROXY_URL.rstrip("/")}/?url=' + quote(url, safe='')
    return requests.get(url, headers=headers, timeout=timeout)


def _steam_post(url, data=None, timeout=8):
    """POST به دامنه‌های استیم از طریق همان Worker (در صورت تنظیم)."""
    if STEAM_PROXY_URL:
        url = f'{STEAM_PROXY_URL.rstrip("/")}/?url=' + quote(url, safe='')
    return requests.post(url, data=data, timeout=timeout)


def _steam_inventory_payload(url, params=None, timeout=20):
    """Inventory روی بعضی IPها درخواست‌های python-requests را 429 می‌کند.
    در این حالت curl با TLS/browser fingerprint متفاوت fallback مطمئن‌تری است."""
    response = _steam_get(
        url,
        params=params,
        headers={
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/124.0 Safari/537.36',
            'Accept': 'application/json,text/plain,*/*',
            'Referer': url.rsplit('/inventory/', 1)[0] + '/inventory/',
        },
        timeout=timeout,
    )
    if response.status_code == 200:
        return response.json()
    if response.status_code != 429:
        response.raise_for_status()

    query = urlencode(params or {})
    final_url = url + (('?' + query) if query else '')
    completed = subprocess.run(
        [
            'curl', '--silent', '--show-error', '--fail', '--location',
            '--max-time', str(timeout),
            '--header', 'Accept: application/json,text/plain,*/*',
            '--header', 'User-Agent: Mozilla/5.0',
            final_url,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def _curl_json(url, params=None, timeout=15):
    command = [
        'curl', '--silent', '--show-error', '--fail', '--location',
        '--max-time', str(timeout),
        '--header', 'Accept: application/json',
        '--header', 'User-Agent: Mozilla/5.0',
    ]
    if params:
        command.extend(['--get', url])
        for key, value in params.items():
            command.extend(['--data-urlencode', f'{key}={value}'])
    else:
        command.append(url)
    completed = subprocess.run(
        command, check=True, capture_output=True, text=True,
    )
    return json.loads(completed.stdout)


def get_live_usd_to_toman():
    """نرخ لحظه‌ای USDT/IRT نوبیتکس؛ fallback به مقدار تنظیمات پروژه."""
    from decimal import Decimal
    from django.core.cache import cache

    cache_key = 'shop_live_usd_to_toman'
    cached = cache.get(cache_key)
    if cached:
        return int(cached)
    fallback = int(getattr(settings, 'USD_TO_TOMAN', 60000))
    try:
        params = {'srcCurrency': 'usdt', 'dstCurrency': 'rls'}
        response = requests.get(
            'https://apiv2.nobitex.ir/market/stats', params=params, timeout=10,
            headers={'Accept': 'application/json', 'User-Agent': 'GameBeat/1.0'},
        )
        payload = response.json() if response.status_code == 200 else _curl_json(
            'https://apiv2.nobitex.ir/market/stats', params=params, timeout=10,
        )
        stats = payload.get('stats', {}).get('usdt-rls', {})
        # API بازار RLS مبلغ را به ریال می‌دهد؛ فروشگاه با تومان کار می‌کند.
        rial_rate = Decimal(str(stats.get('latest') or stats.get('mark') or stats.get('bestSell')))
        toman_rate = int(rial_rate / 10)
        if toman_rate > 10000:
            cache.set(cache_key, toman_rate, 300)
            return toman_rate
    except Exception:
        pass
    return fallback


def _steam_lookup_by_xml(vanity_or_id):
    """
    Fallback: use Steam Community public XML profile (no API key needed).
    Works for both vanity URLs and steam64 IDs.
    """
    if vanity_or_id.isdigit():
        url = f'https://steamcommunity.com/profiles/{vanity_or_id}/?xml=1'
    else:
        url = f'https://steamcommunity.com/id/{vanity_or_id}/?xml=1'

    r = _steam_get(url, timeout=8, headers={'User-Agent': 'GameBeat/1.0'})
    if r.status_code != 200:
        return None

    root = ET.fromstring(r.content)
    error_el = root.find('error')
    if error_el is not None:
        return None

    steam64 = root.findtext('steamID64', '')
    persona = root.findtext('steamID', '')
    avatar = root.findtext('avatarFull', '') or root.findtext('avatarMedium', '')
    profile_url = root.findtext('customURL', '')
    if profile_url:
        profile_url = f'https://steamcommunity.com/id/{profile_url}'
    elif steam64:
        profile_url = f'https://steamcommunity.com/profiles/{steam64}'

    return {
        'ok': True,
        'display_name': persona,
        'avatar_url': avatar,
        'profile_url': profile_url,
        'steam64': steam64,
        'extra': {
            'country': root.findtext('location', ''),
            'member_since': root.findtext('memberSince', ''),
        }
    }


def fetch_steam_games(steam64):
    """ساعت بازی و بازی‌های برتر کاربر استیم را برمی‌گرداند.
    نیازمند STEAM_API_KEY و عمومی‌بودن پروفایل کاربر است.
    خروجی: dict شامل total_hours, game_count, top_games یا None."""
    if not STEAM_API_KEY or not steam64:
        return None
    try:
        r = _steam_get(
            'https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/',
            params={
                'key': STEAM_API_KEY, 'steamid': steam64,
                'include_appinfo': 1, 'include_played_free_games': 1, 'format': 'json',
            },
            timeout=8,
        )
        games = r.json().get('response', {}).get('games', [])
        if not games:
            return None
        total_minutes = sum(g.get('playtime_forever', 0) for g in games)
        top = sorted(games, key=lambda g: g.get('playtime_forever', 0), reverse=True)[:5]
        top_games = [{
            'name': g.get('name', ''),
            'hours': round(g.get('playtime_forever', 0) / 60, 1),
            'icon': (f"https://media.steampowered.com/steamcommunity/public/images/apps/"
                     f"{g.get('appid')}/{g.get('img_icon_url')}.jpg") if g.get('img_icon_url') else '',
        } for g in top if g.get('playtime_forever', 0) > 0]
        return {
            'total_hours': round(total_minutes / 60),
            'game_count': len(games),
            'top_games': top_games,
        }
    except Exception:
        return None


def get_steam_owned_games(steam64):
    """لیست کامل بازی‌های مالک‌شده‌ی کاربر (برای ایمپورت به کاتالوگ).
    خروجی: لیست dict شامل appid, name, playtime_hours, img_icon_url."""
    if not STEAM_API_KEY or not steam64:
        return []
    try:
        r = _steam_get(
            'https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/',
            params={
                'key': STEAM_API_KEY, 'steamid': steam64,
                'include_appinfo': 1, 'include_played_free_games': 1, 'format': 'json',
            },
            timeout=10,
        )
        games = r.json().get('response', {}).get('games', [])
        return [{
            'appid': g.get('appid'),
            'name': g.get('name', ''),
            'playtime_hours': round(g.get('playtime_forever', 0) / 60, 1),
            'img_icon_url': g.get('img_icon_url', ''),
        } for g in games if g.get('appid') and g.get('name')]
    except Exception:
        return []


# دسته‌بندی‌های استیم که یعنی بازی آنلاین/چندنفره است
_ONLINE_CATEGORIES = {
    'Multi-player', 'Online PvP', 'Online Co-op', 'PvP', 'Co-op',
    'MMO', 'Cross-Platform Multiplayer', 'Shared/Split Screen PvP',
}

# نگاشت ژانرهای استیم به کدهای ژانرِ سامانه (GENRE_CHOICES)
_STEAM_GENRE_MAP = {
    'action': 'action', 'adventure': 'adventure',
    'rpg': 'rpg', 'role-playing': 'rpg',
    'strategy': 'strategy', 'simulation': 'simulation',
    'sports': 'sports', 'racing': 'racing',
    'fighting': 'fighting', 'shooter': 'fps', 'fps': 'fps',
    'horror': 'horror', 'puzzle': 'puzzle',
    'massively multiplayer': 'moba', 'casual': 'other', 'indie': 'other',
}


def _map_steam_genres(names):
    """ژانرهای استیم را به کدهای سامانه تبدیل می‌کند (موارد ناشناخته حذف می‌شوند)."""
    codes = []
    for n in names:
        code = _STEAM_GENRE_MAP.get((n or '').strip().lower())
        if code and code not in codes:
            codes.append(code)
    return codes


def fetch_steam_appdetails(appid):
    """جزئیات یک بازی از Steam Store — برای is_online، ژانر، توضیحات، کاور.
    خروجی: dict یا None."""
    try:
        r = _steam_get(
            'https://store.steampowered.com/api/appdetails',
            params={'appids': appid, 'cc': 'us', 'l': 'english'},
            timeout=8, headers={'User-Agent': 'GameBeat/1.0'},
        )
        payload = r.json().get(str(appid), {})
        if not payload.get('success'):
            return None
        d = payload.get('data', {})
        cats = {c.get('description', '') for c in d.get('categories', [])}
        genre_names = [g.get('description', '') for g in d.get('genres', []) if g.get('description')]
        rel = d.get('release_date', {}).get('date', '')
        year = None
        m = re.search(r'(\d{4})', rel or '')
        if m:
            year = int(m.group(1))
        return {
            'type': d.get('type', 'game'),
            'is_online': bool(cats & _ONLINE_CATEGORIES),
            'genres': _map_steam_genres(genre_names),
            'description': (d.get('short_description', '') or '')[:500],
            'release_year': year,
            'header_image': d.get('header_image', ''),
            'developer': (d.get('developers') or [''])[0],
            'publisher': (d.get('publishers') or [''])[0],
            'is_free': d.get('is_free', False),
            'reviews': d.get('recommendations', {}).get('total', 0),
            'metacritic': d.get('metacritic', {}).get('score'),
        }
    except Exception:
        return None


# آستانه‌ی پرطرفداری: تعداد ریویوهای استیم یا امتیاز متاکریتیک
_POPULAR_REVIEWS = 20000
_POPULAR_METACRITIC = 85


def _is_popular(details):
    return (details.get('reviews', 0) or 0) >= _POPULAR_REVIEWS or \
           (details.get('metacritic') or 0) >= _POPULAR_METACRITIC


def import_steam_games_to_catalog(steam64, max_games=200):
    """همه‌ی بازی‌های کاربر را که در کاتالوگ نیستند، به‌عنوان Game اضافه می‌کند.
    برای جلوگیری از بلاک‌شدن اتصال، در یک thread پس‌زمینه صدا زده می‌شود."""
    from dashboard.models import Game
    from django.core.files.base import ContentFile
    from django.db import connection

    created = 0
    try:
        owned = get_steam_owned_games(steam64)
        # همه‌ی بازی‌ها — پرساعت‌ترین‌ها اول (در صورت رسیدن به سقف، مهم‌ترها اول می‌آیند)
        games = sorted(owned, key=lambda g: g['playtime_hours'], reverse=True)[:max_games]

        for g in games:
            appid, name = g['appid'], g['name'].strip()
            if not name:
                continue
            if Game.objects.filter(steam_appid=appid).exists():
                continue
            # اگر نام موجود است، فقط appid را به آن وصل کن (تکراری نساز)
            existing = Game.objects.filter(name__iexact=name).first()
            if existing:
                if not existing.steam_appid:
                    existing.steam_appid = appid
                    existing.save(update_fields=['steam_appid'])
                continue

            details = fetch_steam_appdetails(appid) or {}
            # موارد غیر بازی (DLC، ساندترک، ابزار) را رد کن
            if details.get('type') and details['type'] != 'game':
                continue
            try:
                from .game_aliases import persian_aliases_for, primary_persian_name_for
                game = Game(
                    name=name,
                    title_fa=primary_persian_name_for(name),
                    name_fa=persian_aliases_for(name),
                    steam_appid=appid,
                    steam_url=f'https://store.steampowered.com/app/{appid}/',
                    platforms=['pc'],
                    genres=details.get('genres', []),
                    description=details.get('description', ''),
                    release_year=details.get('release_year'),
                    developer=details.get('developer', ''),
                    publisher=details.get('publisher', ''),
                    is_online=details.get('is_online', False),
                    is_popular=_is_popular(details),
                    metacritic=details.get('metacritic'),
                    is_active=True,
                    auto_imported=True,
                )
                # دانلود کاور از استیم
                header = details.get('header_image') or \
                    f'https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/header.jpg'
                try:
                    ir = _steam_get(header, timeout=8, headers={'User-Agent': 'GameBeat/1.0'})
                    if ir.status_code == 200 and ir.content:
                        game.cover.save(f'steam_{appid}.jpg', ContentFile(ir.content), save=False)
                except Exception:
                    pass
                game.save()
                created += 1
            except Exception:
                continue
    finally:
        connection.close()  # بستن کانکشن thread
    return created


def _localize_badge_image(url):
    """عکس نشان را در media سایت دانلود می‌کند تا محلی شود (دور زدنِ adblock/CSP).
    URL محلی برمی‌گرداند؛ در صورت خطا همان URL خارجی."""
    if not url:
        return ''
    try:
        import hashlib
        from django.core.files.base import ContentFile
        from django.core.files.storage import default_storage
        h = hashlib.md5(url.encode()).hexdigest()[:18]
        path = f'steam_badges/{h}.png'
        if not default_storage.exists(path):
            ir = _steam_get(url, timeout=12, headers={'User-Agent': 'Mozilla/5.0'})
            if ir.status_code != 200 or not ir.content:
                return url
            default_storage.save(path, ContentFile(ir.content))
        return default_storage.url(path)
    except Exception:
        return url


def fetch_steam_badges(steam64):
    """نشان‌های استیم با عکس‌های واقعی (اسکرپ صفحه‌ی badges) + fallback به API.
    عکس‌ها در media سایت دانلود می‌شوند تا محلی و قابل‌نمایش باشند.
    خروجی: {'level': int, 'badges': [{appid, level, xp, game_name, cover}]}"""
    import html as _html
    empty = {'level': 0, 'badges': []}
    if not steam64:
        return empty

    # ── ۱) اسکرپ صفحه‌ی badges استیم — برای عکس و نام واقعیِ هر نشان ──
    try:
        r = _steam_get(
            f'https://steamcommunity.com/profiles/{steam64}/badges/?l=english',
            timeout=25, headers={'User-Agent': 'Mozilla/5.0'},
        )
        if r.status_code == 200 and 'badge_row_inner' in r.text:
            page = r.text
            lvl_m = re.search(r'friendPlayerLevelNum">(\d+)', page) or re.search(r'Steam Level: (\d+)', page)
            steam_level = int(lvl_m.group(1)) if lvl_m else 0
            out = []
            for blk in page.split('badge_row_inner')[1:]:
                title_m = re.search(r'badge_title">\s*([^<]+?)\s*(?:<span|</div)', blk)
                img_m = re.search(r'data-delayed-image="([^"]+)"', blk)
                if not title_m or not img_m:
                    continue
                lvl = re.search(r'Level (\d+)', blk)
                xp = re.search(r'([\d,]+) XP', blk)
                appid = re.search(r'/gamecards/(\d+)', blk)
                out.append({
                    'appid': int(appid.group(1)) if appid else None,
                    'game_name': _html.unescape(title_m.group(1).strip()),
                    'cover': _localize_badge_image(img_m.group(1)),
                    'level': int(lvl.group(1)) if lvl else 0,
                    'xp': int(xp.group(1).replace(',', '')) if xp else 0,
                })
            if out:
                return {'level': steam_level, 'badges': out}
    except Exception:
        pass

    # ── ۲) fallback: GetBadges API (بدون عکس) ──
    if not STEAM_API_KEY:
        return empty
    for _ in range(3):
        try:
            r = _steam_get(
                'https://api.steampowered.com/IPlayerService/GetBadges/v1/',
                params={'key': STEAM_API_KEY, 'steamid': steam64}, timeout=25,
            )
            d = r.json().get('response', {})
            from dashboard.models import Game
            out = []
            for b in d.get('badges', []):
                appid = b.get('appid')
                item = {'appid': appid, 'level': b.get('level', 0), 'xp': b.get('xp', 0),
                        'game_name': '', 'cover': ''}
                if appid:
                    g = Game.objects.filter(steam_appid=appid).first()
                    item['game_name'] = g.name if g else f'AppID {appid}'
                    item['cover'] = (g.cover.url if (g and g.cover) else
                                     f'https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/header.jpg')
                else:
                    item['game_name'] = 'نشان ویژه استیم'
                out.append(item)
            return {'level': d.get('player_level', 0), 'badges': out}
        except Exception:
            time.sleep(1.5)
    return empty


def fetch_steam_achievements(steam64, owned_games=None, max_games=120):
    """دستاوردهای داخل بازیِ کاربر را برمی‌گرداند (per-game).
    خروجی: [{appid, game_name, cover, total, unlocked, names:[...]}]"""
    if not STEAM_API_KEY or not steam64:
        return []
    if owned_games is None:
        owned_games = get_steam_owned_games(steam64)
    played = sorted([g for g in owned_games if g['playtime_hours'] > 0],
                    key=lambda g: g['playtime_hours'], reverse=True)[:max_games]
    from dashboard.models import Game
    out = []
    for g in played:
        appid = g['appid']
        data = None
        for _ in range(2):  # retry برای خطای SSL موقتی
            try:
                r = _steam_get(
                    'https://api.steampowered.com/ISteamUserStats/GetPlayerAchievements/v1/',
                    params={'key': STEAM_API_KEY, 'steamid': steam64, 'appid': appid, 'l': 'english'},
                    timeout=20,
                )
                data = r.json().get('playerstats', {})
                break
            except Exception:
                time.sleep(1)
        if not data or not data.get('success'):
            continue
        achs = data.get('achievements', [])
        unlocked = [a for a in achs if a.get('achieved') == 1]
        if not unlocked:
            continue
        gobj = Game.objects.filter(steam_appid=appid).first()
        out.append({
            'appid': appid,
            'game_name': data.get('gameName') or g['name'],
            'cover': (gobj.cover.url if (gobj and gobj.cover)
                      else f'https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/header.jpg'),
            'total': len(achs),
            'unlocked': len(unlocked),
            'items': [{'name': a.get('name') or a.get('apiname'),
                       'desc': (a.get('description') or '').strip()} for a in unlocked][:40],
        })
    return out


def fetch_cs2_medals(steam64):
    """مدال‌ها و سکه‌های CS2 را از Steam Inventory کاربر می‌خواند.
    خروجی: list of {name, icon_url, desc, date_issued}"""
    STEAM_CDN = 'https://community.cloudflare.steamstatic.com/economy/image/'
    try:
        r = _steam_get(
            f'https://steamcommunity.com/inventory/{steam64}/730/2',
            params={'l': 'english', 'count': 500},
            headers={'User-Agent': 'Mozilla/5.0'},
            timeout=20,
        )
        if r.status_code != 200:
            return []
        data = r.json()
        if not data.get('success'):
            return []
        descriptions = {
            (d['classid'], d['instanceid']): d
            for d in data.get('descriptions', [])
        }
        seen, out = set(), []
        for a in data.get('assets', []):
            key = (a['classid'], a['instanceid'])
            if key in seen:
                continue
            seen.add(key)
            d = descriptions.get(key, {})
            tags = {t['category']: t['localized_tag_name'] for t in d.get('tags', [])}
            if tags.get('Type') != 'Collectible':
                continue
            raw_descs = [x.get('value', '').strip() for x in d.get('descriptions', []) if x.get('value', '').strip()]
            main_desc = raw_descs[0] if raw_descs else ''
            date_issued = next((x for x in raw_descs if x.startswith('Date of Issue')), '')
            out.append({
                'name': d.get('market_name') or d.get('name', ''),
                'icon_url': STEAM_CDN + (d.get('icon_url_large') or d.get('icon_url', '')),
                'desc': main_desc,
                'date_issued': date_issued,
            })
        return out
    except Exception:
        return []


def fetch_steam_inventory(steam64, app_id=730, context_id='2', count=500):
    """موجودی قابل معاملهٔ استیم را با اطلاعات لازم برای فروشگاه برمی‌گرداند."""
    from decimal import Decimal
    from django.conf import settings

    cdn = 'https://community.cloudflare.steamstatic.com/economy/image/'
    from django.core.cache import cache

    cache_key = f'steam_inventory_{steam64}_{app_id}_{context_id}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    try:
        payload = _steam_inventory_payload(
            f'https://steamcommunity.com/inventory/{steam64}/{int(app_id)}/{context_id}',
            params={'l': 'english', 'count': min(int(count), 1000)},
            timeout=20,
        )
        if not payload.get('success'):
            return []
        descriptions = {
            (str(item.get('classid')), str(item.get('instanceid', '0'))): item
            for item in payload.get('descriptions', [])
        }
        usd_to_toman = Decimal(str(getattr(settings, 'USD_TO_TOMAN', 60000)))
        result = []
        for asset in payload.get('assets', []):
            desc = descriptions.get((str(asset.get('classid')), str(asset.get('instanceid', '0'))), {})
            if not desc or desc.get('tradable') != 1 or not desc.get('marketable'):
                continue
            tags = {tag.get('category'): tag.get('localized_tag_name', '') for tag in desc.get('tags', [])}
            result.append({
                'app_id': int(app_id),
                'context_id': str(context_id),
                'asset_id': str(asset.get('assetid', '')),
                'class_id': str(asset.get('classid', '')),
                'instance_id': str(asset.get('instanceid', '0')),
                'name': desc.get('market_name') or desc.get('name', ''),
                'market_hash_name': desc.get('market_hash_name') or desc.get('market_name') or desc.get('name', ''),
                'icon_url': cdn + (desc.get('icon_url_large') or desc.get('icon_url', '')),
                'exterior': tags.get('Exterior', ''),
                'rarity': tags.get('Rarity', ''),
                'amount': int(asset.get('amount', 1)),
                'estimated_usd': None,
                'estimated_toman': None,
                'usd_to_toman': int(usd_to_toman),
            })
        cache.set(cache_key, result, 300)
        return result
    except Exception:
        return []


def enrich_steam_inventory_prices(items, max_items=32, usd_to_toman=None):
    """قیمت دلاری Steam Community Market را موازی می‌خواند و به تومان تبدیل می‌کند."""
    import re
    from concurrent.futures import ThreadPoolExecutor
    from decimal import Decimal, InvalidOperation
    from django.conf import settings

    from django.core.cache import cache
    from hashlib import sha256

    usd_to_toman = Decimal(str(usd_to_toman or get_live_usd_to_toman()))

    def fetch_price(item):
        price_key = sha256(item['market_hash_name'].encode('utf-8')).hexdigest()[:24]
        cache_key = f"steam_market_price_{item['app_id']}_{price_key}"
        try:
            cached_usd = cache.get(cache_key)
            if cached_usd is not None:
                usd = Decimal(str(cached_usd))
                item['estimated_usd'] = usd
                item['estimated_toman'] = int(usd * usd_to_toman)
                return item
            params = {
                'appid': item['app_id'],
                'currency': 1,
                'market_hash_name': item['market_hash_name'],
            }
            # search/render نسبت به priceoverview محدودیت نرخ بسیار کمتری دارد
            # و پایین‌ترین قیمت فروش را مستقیماً به سنت برمی‌گرداند.
            search_payload = _curl_json(
                'https://steamcommunity.com/market/search/render/',
                params={
                    'query': item['market_hash_name'],
                    'start': 0,
                    'count': 10,
                    'search_descriptions': 0,
                    'sort_column': 'popular',
                    'sort_dir': 'desc',
                    'appid': item['app_id'],
                    'norender': 1,
                },
                timeout=10,
            )
            exact = next(
                (
                    result for result in search_payload.get('results', [])
                    if result.get('hash_name') == item['market_hash_name']
                ),
                None,
            )
            if not exact or exact.get('sell_price') is None:
                return item
            usd = Decimal(str(exact['sell_price'])) / Decimal('100')

            if usd >= 0:
                item['estimated_usd'] = usd
                item['estimated_toman'] = int(usd * usd_to_toman)
                cache.set(cache_key, str(usd), 60 * 60)
        except (InvalidOperation, ValueError, TypeError, Exception):
            pass
        return item

    priced = list(items[:max(max_items, len(items))])
    # Steam برای priceoverview روی درخواست‌های هم‌زمان زیاد 429 می‌دهد.
    with ThreadPoolExecutor(max_workers=2) as executor:
        priced = list(executor.map(fetch_price, priced))
    return priced + list(items[max_items:])


def import_and_enrich_steam(steam64, user_id=None):
    """import بازی‌ها + غنی‌سازی AI + واکشی و ذخیره‌ی نشان‌های استیم.
    در thread پس‌زمینه‌ی steam_callback اجرا می‌شود تا اتصال بلاک نشود."""
    from django.db import connection
    created = 0
    try:
        created = import_steam_games_to_catalog(steam64)
        try:
            from .ai_service import enrich_games, AVALAI_API_KEY
            if AVALAI_API_KEY:
                from dashboard.models import Game
                enrich_games(Game.objects.filter(auto_imported=True), resume=True)
        except Exception:
            pass
        # نشان‌ها را واکشی و روی اکانت گیمینگِ همین کاربر ذخیره کن
        if user_id:
            try:
                from .models import GamingAccount
                bdata = fetch_steam_badges(steam64)
                badges = bdata.get('badges', [])
                # توضیح فارسیِ نشان‌ها با AI (مَچ انعطاف‌پذیر)
                try:
                    from .ai_service import ai_badge_descriptions
                    descs = ai_badge_descriptions([b['game_name'] for b in badges])
                    if descs:
                        norm = lambda s: re.sub(r'[^a-z0-9]', '', (s or '').lower())
                        dn = {norm(k): v for k, v in descs.items()}
                        for b in badges:
                            b['desc_fa'] = descs.get(b['game_name']) or dn.get(norm(b['game_name']), '')
                except Exception:
                    pass
                ga = GamingAccount.objects.filter(user_id=user_id, platform='steam').first()
                if ga:
                    extra = dict(ga.extra_data or {})
                    extra['steam_level'] = bdata.get('level', 0)
                    extra['badges'] = badges
                    extra['achievements'] = fetch_steam_achievements(steam64)
                    extra['cs2_medals'] = fetch_cs2_medals(steam64)
                    ga.extra_data = extra
                    ga.save(update_fields=['extra_data'])
            except Exception:
                pass
    finally:
        connection.close()
    return created


def lookup_steam(steam_id_or_vanity):
    """Look up Steam profile by vanity URL or steam64 ID"""
    result = {'ok': False, 'error': 'پروفایل Steam پیدا نشد'}
    try:
        if STEAM_API_KEY:
            # ── Official API path (faster, more data) ──
            if not steam_id_or_vanity.isdigit():
                r = _steam_get(
                    'https://api.steampowered.com/ISteamUser/ResolveVanityURL/v1/',
                    params={'key': STEAM_API_KEY, 'vanityurl': steam_id_or_vanity},
                    timeout=6,
                )
                data = r.json().get('response', {})
                if data.get('success') == 1:
                    steam64 = data['steamid']
                else:
                    # vanity not found via API – try XML fallback
                    return _steam_lookup_by_xml(steam_id_or_vanity) or result
            else:
                steam64 = steam_id_or_vanity

            r = _steam_get(
                'https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/',
                params={'key': STEAM_API_KEY, 'steamids': steam64},
                timeout=6,
            )
            players = r.json().get('response', {}).get('players', [])
            if not players:
                return result
            p = players[0]
            extra = {
                'state': p.get('personastate', 0),
                'country': p.get('loccountrycode', ''),
            }
            # ساعت بازی و بازی‌های برتر (در صورت عمومی‌بودن پروفایل)
            games = fetch_steam_games(steam64)
            if games:
                extra.update(games)
            return {
                'ok': True,
                'display_name': p.get('personaname', ''),
                'avatar_url': p.get('avatarfull', ''),
                'profile_url': p.get('profileurl', ''),
                'steam64': steam64,
                'extra': extra,
            }
        else:
            # ── No API key: use public XML endpoint (no key needed) ──
            xml_result = _steam_lookup_by_xml(steam_id_or_vanity)
            return xml_result if xml_result else result

    except Exception as e:
        return {'ok': False, 'error': str(e)}


def lookup_xbox(gamertag):
    """Look up Xbox Live gamertag via free Xbox API"""
    result = {'ok': False, 'error': 'گیمرتگ پیدا نشد'}
    try:
        # Use xboxapi.com or OpenXBL
        headers = {'X-Authorization': XBOX_API_KEY} if XBOX_API_KEY else {}
        r = requests.get(
            f'https://xbl.io/api/v2/friends/search?gt={requests.utils.quote(gamertag)}',
            headers=headers, timeout=6
        )
        if r.status_code == 200:
            data = r.json()
            people = data.get('profileUsers', data.get('people', []))
            if people:
                p = people[0]
                settings_data = {s['id']: s.get('value','') for s in p.get('settings', [])}
                return {
                    'ok': True,
                    'display_name': settings_data.get('Gamertag', gamertag),
                    'avatar_url': settings_data.get('GameDisplayPicRaw', ''),
                    'profile_url': f'https://www.xbox.com/en-US/play/user/{requests.utils.quote(gamertag)}',
                    'extra': {
                        'gamerscore': settings_data.get('Gamerscore', '0'),
                        'tier': settings_data.get('AccountTier', ''),
                        'location': settings_data.get('Location', ''),
                    }
                }
        # Fallback: just confirm the gamertag
        return {
            'ok': True,
            'display_name': gamertag,
            'avatar_url': '',
            'profile_url': f'https://www.xbox.com/en-US/play/user/{requests.utils.quote(gamertag)}',
            'extra': {}
        }
    except Exception as e:
        return {'ok': False, 'error': str(e)}


def lookup_psn(psn_id):
    """Look up PSN profile"""
    result = {'ok': False, 'error': 'آیدی PSN پیدا نشد'}
    try:
        # PSN doesn't have a public unauthenticated API, so we confirm the ID and link to profile
        return {
            'ok': True,
            'display_name': psn_id,
            'avatar_url': '',
            'profile_url': f'https://my.playstation.com/profile/{psn_id}',
            'extra': {'platform': 'PlayStation'}
        }
    except Exception as e:
        return {'ok': False, 'error': str(e)}


def lookup_ea(ea_username):
    """Look up EA / Origin profile"""
    try:
        return {
            'ok': True,
            'display_name': ea_username,
            'avatar_url': '',
            'profile_url': f'https://www.ea.com/games/library/player?persona={ea_username}&nucleusId=',
            'extra': {'platform': 'EA'}
        }
    except Exception as e:
        return {'ok': False, 'error': str(e)}


def lookup_epic(epic_username):
    """Look up Epic Games profile"""
    try:
        return {
            'ok': True,
            'display_name': epic_username,
            'avatar_url': '',
            'profile_url': f'https://www.epicgames.com/id/profile/{epic_username}',
            'extra': {'platform': 'Epic Games'}
        }
    except Exception as e:
        return {'ok': False, 'error': str(e)}


LOOKUP_MAP = {
    'steam': lookup_steam,
    'xbox': lookup_xbox,
    'psn': lookup_psn,
    'ea': lookup_ea,
    'epic': lookup_epic,
}

def lookup_account(platform, username):
    fn = LOOKUP_MAP.get(platform)
    if fn:
        return fn(username)
    return {'ok': False, 'error': 'پلتفرم پشتیبانی نمیشه'}
