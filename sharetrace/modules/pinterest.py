from curl_cffi import requests
import json
import time
import re

# Matches pin.it short links, direct pin URLs on any subdomain
# (www., in., ru., country subdomains) and profile URLs (@handle).
_PIN_IT_RE = re.compile(r'pin\.it/([A-Za-z0-9]+)')
_PIN_URL_RE = re.compile(
    r'^https?://(?:[a-z]{2,3}\.)?pinterest\.(?:com|[a-z.]+)/pin/([0-9]+)/?', re.IGNORECASE
)
_PROFILE_URL_RE = re.compile(
    r'^https?://(?:[a-z]{2,3}\.)?pinterest\.(?:com|[a-z.]+)/@([A-Za-z0-9._]+)/?', re.IGNORECASE
)

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"
)

_HTML_HEADERS = {
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'accept-language': 'en-US,en;q=0.9',
    'user-agent': _UA,
}

_JSON_LD_RE = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.+?)</script>',
    re.IGNORECASE | re.DOTALL,
)

_OG_RE = {
    'title': re.compile(
        r'<meta\s+(?:property|name)=["\']og:title["\']\s+content=["\'](.*?)["\']',
        re.IGNORECASE | re.DOTALL,
    ),
    'description': re.compile(
        r'<meta\s+(?:property|name)=["\']og:description["\']\s+content=["\'](.*?)["\']',
        re.IGNORECASE | re.DOTALL,
    ),
    'image': re.compile(
        r'<meta\s+(?:property|name)=["\']og:image["\']\s+content=["\'](.*?)["\']',
        re.IGNORECASE | re.DOTALL,
    ),
}


def _extract_json_ld(body):
    """Return the parsed main JSON-LD object, or None."""
    m = _JSON_LD_RE.search(body)
    if not m:
        return None
    try:
        data = json.loads(m.group(1))
    except (ValueError, json.JSONDecodeError):
        return None
    if isinstance(data, list):
        data = data[0] if data else None
    return data if isinstance(data, dict) else None


def _extract_og(body):
    out = {}
    for key, rx in _OG_RE.items():
        m = rx.search(body)
        if m:
            out[key] = m.group(1)
    return out


def _pin_page(pin_id, url):
    """Extract uploader identity from a direct pin URL via OG tags + JSON-LD."""
    try:
        response = requests.get(url, headers=_HTML_HEADERS, impersonate='chrome', timeout=15)
    except Exception as e:
        return {"error": f"Request failed: {str(e)}"}

    body = response.text
    data = {
        "pin_id": pin_id,
        "url_type": "pin",
    }

    og = _extract_og(body)
    if og.get('title'):
        data['name'] = og['title']
    if og.get('description'):
        data['description'] = og['description']
    if og.get('image'):
        data['image_url'] = og['image']

    # JSON-LD may carry the creator; Pinterest pins expose Person objects.
    ld = _extract_json_ld(body)

    candidates = []
    if isinstance(ld, dict):
        candidates.append(ld)
        for key in ('creator', 'author'):
            val = ld.get(key)
            if isinstance(val, list) and val:
                val = val[0]
            if isinstance(val, dict):
                candidates.append(val)

    for cand in candidates:
        username = cand.get('alternateName') or cand.get('name')
        profile_url = cand.get('url')
        if username and profile_url and '/@' in str(profile_url) or (username and str(username).startswith('@')):
            data['username'] = str(username).lstrip('@')
            if profile_url:
                data['profile_url'] = profile_url
            image = cand.get('image')
            if isinstance(image, dict):
                image = image.get('url')
            if isinstance(image, str):
                data['avatar_url'] = image
            break

    # Nothing usable beyond OG tags — still return what we have.
    if len(data) <= 3:
        if not og:
            return {"error": "Could not extract Pinterest pin data from response"}
        if 'name' not in data:
            return {"error": "Could not extract Pinterest pin data from response"}

    return {"data": data}


def _profile_page(handle, url):
    """Extract identity from a direct profile URL (@handle) via OG tags + JSON-LD."""
    try:
        response = requests.get(url, headers=_HTML_HEADERS, impersonate='chrome', timeout=15)
    except Exception as e:
        return {"error": f"Request failed: {str(e)}"}

    body = response.text
    og = _extract_og(body)

    data = {
        "username": handle,
        "profile_url": f"https://www.pinterest.com/{handle}/",
        "url_type": "profile",
    }

    if og.get('title'):
        # OG title is typically "<Display Name> (@handle) on Pinterest"
        display_name = re.sub(r'\s*\(@[^)]*\)\s*(on Pinterest)?\s*$', '', og['title']).strip()
        data['name'] = display_name or og['title']
    if og.get('description'):
        data['description'] = og['description']
    if og.get('image'):
        data['avatar_url'] = og['image']

    ld = _extract_json_ld(body)
    if isinstance(ld, dict):
        if ld.get('image'):
            image = ld.get('image')
            if isinstance(image, dict):
                image = image.get('url')
            if isinstance(image, str):
                data['avatar_url'] = image
        if ld.get('interactionStatistic'):
            stats = ld.get('interactionStatistic')
            if isinstance(stats, dict) and stats.get('userInteractionCount'):
                data['follower_count'] = stats['userInteractionCount']

    return {"data": data}


def pinterest(url):
    match = _PIN_URL_RE.search(url)
    if match:
        return _pin_page(match.group(1), url)

    profile_match = _PROFILE_URL_RE.search(url)
    if profile_match:
        return _profile_page(profile_match.group(1), url)

    match = _PIN_IT_RE.search(url)
    if not match:
        return {"error": "Invalid URL format for Pinterest share link"}

    short_code = match.group(1)

    try:
        response = requests.get(
            f'https://api.pinterest.com/url_shortener/{short_code}/redirect/',
            headers=_HTML_HEADERS,
            allow_redirects=False
        )

        location = response.headers.get('Location', '')

        invite_match = re.search(r'invite_code=([a-f0-9]+)', location)
        if not invite_match:
            return {"error": "No invite code found in Pinterest link"}

        invite_code = invite_match.group(1)
        pin_id_match = re.search(r'/pin/(\d+)/', location)
        pin_id = pin_id_match.group(1) if pin_id_match else "0"

        api_headers = {
            'accept': 'application/json, text/javascript, */*, q=0.01',
            'accept-language': 'en-US,en;q=0.9',
            'referer': 'https://www.pinterest.com/',
            'user-agent': _UA,
            'x-requested-with': 'XMLHttpRequest',
            'x-pinterest-appstate': 'active',
            'x-pinterest-pws-handler': 'www/pin/[id]/sent.js',
            'x-pinterest-source-url': f'/pin/{pin_id}/sent/?invite_code={invite_code}',
        }

        params = {
            'source_url': f'/pin/{pin_id}/sent/?invite_code={invite_code}',
            'data': json.dumps({"options": {"invite_code": invite_code, "field_set_key": "default"}, "context": {}}),
            '_': str(int(time.time() * 1000)),
        }

        response = requests.get(
            'https://www.pinterest.com/resource/InviteCodeMetadataResource/get/',
            params=params,
            headers=api_headers
        )

        data = response.json()
        sender = data.get('resource_response', {}).get('data', {}).get('sender', {})

        if not sender:
            return {"error": "No sender data found"}

        username = sender.get('username')

        return {
            "data": {
                "profile_url": f"https://www.pinterest.com/{username}/" if username else None,
                "username": username,
                "user_id": sender.get('id'),
                "name": sender.get('full_name'),
                "avatar_url": sender.get('image_large_url')
            }
        }

    except Exception as e:
        return {"error": f"Request failed: {str(e)}"}