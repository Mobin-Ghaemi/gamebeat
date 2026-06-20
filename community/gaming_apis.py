import re
import time
import requests
import xml.etree.ElementTree as ET
from django.conf import settings

STEAM_API_KEY = getattr(settings, 'STEAM_API_KEY', '')
XBOX_API_KEY = getattr(settings, 'XBOX_API_KEY', '')


def _steam_lookup_by_xml(vanity_or_id):
    """
    Fallback: use Steam Community public XML profile (no API key needed).
    Works for both vanity URLs and steam64 IDs.
    """
    if vanity_or_id.isdigit():
        url = f'https://steamcommunity.com/profiles/{vanity_or_id}/?xml=1'
    else:
        url = f'https://steamcommunity.com/id/{vanity_or_id}/?xml=1'

    r = requests.get(url, timeout=8, headers={'User-Agent': 'GameBeat/1.0'})
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
        r = requests.get(
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
        r = requests.get(
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
        r = requests.get(
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
                from .game_aliases import persian_aliases_for
                game = Game(
                    name=name,
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
                    ir = requests.get(header, timeout=8, headers={'User-Agent': 'GameBeat/1.0'})
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
            ir = requests.get(url, timeout=12, headers={'User-Agent': 'Mozilla/5.0'})
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
        r = requests.get(
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
            r = requests.get(
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
                r = requests.get(
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
        r = requests.get(
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
                r = requests.get(
                    'https://api.steampowered.com/ISteamUser/ResolveVanityURL/v1/',
                    params={'key': STEAM_API_KEY, 'vanityurl': steam_id_or_vanity},
                    timeout=6
                )
                data = r.json().get('response', {})
                if data.get('success') == 1:
                    steam64 = data['steamid']
                else:
                    # vanity not found via API – try XML fallback
                    return _steam_lookup_by_xml(steam_id_or_vanity) or result
            else:
                steam64 = steam_id_or_vanity

            r = requests.get(
                'https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/',
                params={'key': STEAM_API_KEY, 'steamids': steam64},
                timeout=6
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
