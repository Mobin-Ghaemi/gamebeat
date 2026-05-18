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
            return {
                'ok': True,
                'display_name': p.get('personaname', ''),
                'avatar_url': p.get('avatarfull', ''),
                'profile_url': p.get('profileurl', ''),
                'steam64': steam64,
                'extra': {
                    'state': p.get('personastate', 0),
                    'country': p.get('loccountrycode', ''),
                }
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
