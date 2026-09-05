from datetime import datetime, timezone
from curl_cffi import requests
from ..utils import COUNTRY_CODES
import json
import re

TIKTOK_URL_RE = re.compile(
    r'(vm\.tiktok\.com|vt\.tiktok\.com|tiktok\.com/t)/[A-Za-z0-9]+'
    r'|tiktok\.com/@[A-Za-z0-9._]+(?:/video/\d+)?/?'
)


def tiktok(url):
    if not TIKTOK_URL_RE.search(url):
        return {"error": "Invalid URL format for TikTok share link"}

    headers = {
        "user-agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Mobile Safari/537.36",
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "accept-language": "en-US,en;q=0.9",
    }

    try:
        session = requests.Session(impersonate="chrome", allow_redirects=True)
        response = session.get(url)
        final_url = response.url

        response = session.get(final_url, headers=headers)

        match = re.search(
            r'"webapp\.reflow\.global\.shareUser":\s*(\{[^}]+\{[^}]+\}[^}]*\})',
            response.text
        )

        if not match:
            # Fallback: direct profile/video pages don't ship the reflow.shareUser blob,
            # but do embed __UNIVERSAL_DATA_FOR_REHYDRATION__ with webapp.user-detail / video-detail.
            fallback = _from_universal_data(response.text)
            if fallback is not None:
                return fallback
            return {"error": "Could not find share user data in response"}

        json_str = match.group(1)
        json_str = json_str.replace('\\u002F', '/')

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            return {"error": "Failed to parse share user data"}

        share_user = data.get('shareUser', {})
        if not share_user:
            return {"error": "No share user found in response"}

        username = share_user.get('uniqueId')

        country = None
        region_match = re.search(r'"share_region"\s*:\s*"([A-Z]{2})"', response.text)
        if region_match:
            country_code = region_match.group(1)
            country = COUNTRY_CODES.get(country_code, country_code)

        device = None
        device_match = re.search(r'"utm_medium"\s*:\s*"([^"]+)"', response.text)
        if device_match:
            device = device_match.group(1)

        share_method = None
        method_match = re.search(r'"utm_source"\s*:\s*"([^"]+)"', response.text)
        if method_match:
            share_method = method_match.group(1)

        shared_at = None
        timestamp_match = re.search(r'"timestamp"\s*:\s*"(\d+)"', response.text)
        if timestamp_match:

            timestamp = int(timestamp_match.group(1))
            shared_at = datetime.fromtimestamp(timestamp, timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

        return {
            "data": {
                "profile": f"https://www.tiktok.com/@{username}",
                "user_id": share_user.get('id'),
                "username": username,
                "nickname": share_user.get('nickname'),
                "country": country,
                "avatar_url": share_user.get('avatarLarger', '').replace('\\u002F', '/'),
                "signature": share_user.get('signature'),
                "device": device,
                "share_method": share_method,
                "shared_at": shared_at,
                "follower_count": share_user.get('followerCount'),
                "following_count": share_user.get('followingCount'),
                "video_count": share_user.get('videoCount'),
                "heart_count": share_user.get('heartCount'),
                "private_account": share_user.get('privateAccount'),
                "dm_available": share_user.get('dmAvailable')
            }
        }

    except Exception as e:
        return {"error": f"Request failed: {str(e)}"}


UNIVERSAL_RE = re.compile(
    r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>',
    re.DOTALL,
)


def _from_universal_data(html):
    """Extract profile/video author from the __UNIVERSAL_DATA_FOR_REHYDRATION__ blob."""
    m = UNIVERSAL_RE.search(html)
    if not m:
        return None
    try:
        blob = json.loads(m.group(1))
    except json.JSONDecodeError:
        return None
    scope = (blob.get('__DEFAULT_SCOPE__') or {})
    # Profile page: webapp.user-detail carries userInfo.user + stats.
    # Video page: webapp.video-detail carries itemInfo.itemStruct.author + .stats.
    detail = scope.get('webapp.user-detail')
    if isinstance(detail, dict):
        info = detail.get('userInfo') or {}
        user, stats = info.get('user') or {}, info.get('stats') or {}
        if user.get('uniqueId'):
            return {"data": _profile_data(user, stats)}
    detail = scope.get('webapp.video-detail')
    if isinstance(detail, dict):
        item = ((detail.get('itemInfo') or {}).get('itemStruct')) or {}
        user, stats = item.get('author') or {}, item.get('authorStats') or {}
        if user.get('uniqueId'):
            return {"data": _profile_data(user, stats)}
    return None


def _profile_data(user, stats):
    username = user.get('uniqueId')
    return {
        "profile": f"https://www.tiktok.com/@{username}",
        "user_id": user.get('id'),
        "username": username,
        "nickname": user.get('nickname'),
        "country": COUNTRY_CODES.get(user.get('region', ''), user.get('region')),
        "avatar_url": user.get('avatarLarger'),
        "signature": user.get('signature'),
        "follower_count": stats.get('followerCount'),
        "following_count": stats.get('followingCount'),
        "video_count": stats.get('videoCount'),
        "heart_count": stats.get('heartCount') or stats.get('heart'),
        "private_account": user.get('privateAccount'),
    }