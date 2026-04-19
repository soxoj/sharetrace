"""LinkedIn public profile / post / pulse identity extractor.

Fetches HTML with a realistic Chromium UA and parses OG meta tags.
LinkedIn aggressively blocks unauthenticated requests — callers should
treat `is_blocked: True` responses as expected, not as errors.

No retries: retrying does not help against LinkedIn's bot detection.
"""
from __future__ import annotations

import re
from curl_cffi import requests

URL_RE = re.compile(r'linkedin\.com/(in|posts|pulse)/([A-Za-z0-9_%-]+)')

# Chromium UA — realistic desktop Linux Chrome fingerprint.
# Do NOT use sharetrace/1.0 — LinkedIn rejects non-browser UAs instantly.
_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

_HEADERS = {
    "User-Agent": _UA,
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Upgrade-Insecure-Requests": "1",
}

_BLOCKED_STATUSES = {999, 403, 429}
_MIN_CONTENT_BYTES = 5_000

_OG_TITLE_RE = re.compile(
    r'<meta\s+property=["\']og:title["\']\s+content=["\'](.*?)["\']',
    re.IGNORECASE,
)
_OG_DESC_RE = re.compile(
    r'<meta\s+property=["\']og:description["\']\s+content=["\'](.*?)["\']',
    re.IGNORECASE,
)
_OG_IMAGE_RE = re.compile(
    r'<meta\s+property=["\']og:image["\']\s+content=["\'](.*?)["\']',
    re.IGNORECASE,
)

_BLOCKED_RESPONSE = {
    "error": "LinkedIn blocked the request (bot protection)",
    "is_blocked": True,
}

_URL_TYPE_MAP = {
    "in": "profile",
    "posts": "post",
    "pulse": "pulse",
}


def linkedin(url: str) -> dict:
    """Extract identity info from a LinkedIn profile / post / pulse URL."""
    m = URL_RE.search(url)
    if not m:
        return {"error": "Invalid URL format for LinkedIn link"}

    path_segment, _slug = m.group(1), m.group(2)
    url_type = _URL_TYPE_MAP.get(path_segment, path_segment)

    # Normalise URL to canonical LinkedIn form
    canonical_url = f"https://www.linkedin.com/{path_segment}/{_slug}"

    try:
        resp = requests.get(
            canonical_url,
            headers=_HEADERS,
            impersonate="chrome124",
            timeout=15,
            allow_redirects=True,
        )
    except Exception as exc:
        return {"error": f"Request failed: {exc}"}

    if resp.status_code in _BLOCKED_STATUSES:
        return _BLOCKED_RESPONSE

    body = resp.text

    # Auth-wall detection #1: explicit authwall marker in HTML
    if "authwall" in body.lower():
        return _BLOCKED_RESPONSE

    # Auth-wall detection #2: response too small AND no og:title
    og_title_m = _OG_TITLE_RE.search(body)
    if len(body) < _MIN_CONTENT_BYTES and not og_title_m:
        return _BLOCKED_RESPONSE

    if not og_title_m:
        return {"error": "Could not find og:title in LinkedIn response"}

    raw_title = og_title_m.group(1).strip()

    # Strip " | LinkedIn" suffix (case-insensitive)
    title = re.sub(r'\s*\|\s*LinkedIn\s*$', '', raw_title, flags=re.IGNORECASE).strip()

    # Split name and headline on first " - "
    if " - " in title:
        name_part, headline_part = title.split(" - ", 1)
        display_name = name_part.strip()
        headline = headline_part.strip() or None
    else:
        display_name = title
        headline = None

    og_image_m = _OG_IMAGE_RE.search(body)
    avatar_url = og_image_m.group(1).strip() if og_image_m else None

    return {
        "data": {
            "display_name": display_name,
            "headline": headline,
            "profile_url": canonical_url,
            "avatar_url": avatar_url,
            "url_type": url_type,
        }
    }
