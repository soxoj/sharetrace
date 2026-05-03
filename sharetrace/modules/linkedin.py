"""LinkedIn public profile / post / pulse identity extractor.

Fetches HTML with a realistic Chromium UA and parses OG meta tags.
LinkedIn aggressively blocks unauthenticated requests — callers should
treat `is_blocked: True` responses as expected, not as errors.

No retries: retrying does not help against LinkedIn's bot detection.
"""
from __future__ import annotations

import json
import re
from curl_cffi import requests

URL_RE = re.compile(r'linkedin\.com/(in|posts|pulse)/([A-Za-z0-9_%-]+)')

_JSON_LD_RE = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.+?)</script>',
    re.IGNORECASE | re.DOTALL,
)

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
    re.IGNORECASE | re.DOTALL,
)
_OG_DESC_RE = re.compile(
    r'<meta\s+property=["\']og:description["\']\s+content=["\'](.*?)["\']',
    re.IGNORECASE | re.DOTALL,
)
_OG_IMAGE_RE = re.compile(
    r'<meta\s+property=["\']og:image["\']\s+content=["\'](.*?)["\']',
    re.IGNORECASE | re.DOTALL,
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


def _parse_json_ld(body: str) -> dict | None:
    """Extract author info from JSON-LD structured data (posts and pulse have rich data)."""
    m = _JSON_LD_RE.search(body)
    if not m:
        return None
    try:
        data = json.loads(m.group(1))
    except (ValueError, json.JSONDecodeError):
        return None

    # SocialMediaPosting (posts) and NewsArticle (pulse) carry an `author` block
    author = data.get("author") or data.get("creator")
    if isinstance(author, list) and author:
        author = author[0]
    if not isinstance(author, dict) or not author.get("name"):
        return None

    out = {"display_name": author["name"]}
    if author.get("url"):
        out["profile_url"] = author["url"]
    image = author.get("image")
    if isinstance(image, dict) and image.get("url"):
        out["avatar_url"] = image["url"]
    elif isinstance(image, str):
        out["avatar_url"] = image

    interaction = author.get("interactionStatistic")
    if isinstance(interaction, dict) and interaction.get("userInteractionCount"):
        out["follower_count"] = interaction["userInteractionCount"]

    if data.get("headline"):
        out["headline"] = data["headline"]
    if data.get("datePublished"):
        out["published_at"] = data["datePublished"]
    return out


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

    # Try JSON-LD first — posts and pulse expose author as structured data,
    # which is more reliable than the multi-line og:title format.
    json_ld_data = _parse_json_ld(body)
    if json_ld_data:
        json_ld_data["url_type"] = url_type
        json_ld_data.setdefault("profile_url", canonical_url)
        return {"data": json_ld_data}

    # OG fallback — primary path for profile (`/in/`) URLs
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
