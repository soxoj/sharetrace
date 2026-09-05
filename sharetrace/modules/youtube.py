"""YouTube channel/video identity extractor.

Scrapes the public HTML page and pulls fields out of the embedded
`ytInitialData` / `ytInitialPlayerResponse` blobs. No auth, one HTTP call.

Handles:
- youtu.be/{video_id}
- youtube.com/watch?v={video_id}
- youtube.com/shorts/{video_id}
- youtube.com/live/{video_id}
- youtube.com/@handle[/{tab}]
- youtube.com/channel/{ucid}
"""
from __future__ import annotations

import json
import re
from html import unescape
from urllib.parse import parse_qs, urlparse

from curl_cffi import requests

VIDEO_URL_RE = re.compile(
    r'^https?://('
    r'youtu\.be/(?P<short>[A-Za-z0-9_-]{11})'
    r'|(?:www\.|m\.)?youtube\.com/(?:watch\?[^ ]*v=(?P<v>[A-Za-z0-9_-]{11})'
    r'|(?:shorts|live|embed)/(?P<path>[A-Za-z0-9_-]{11}))'
    r')'
)
CHANNEL_URL_RE = re.compile(
    r'^https?://(?:www\.|m\.)?youtube\.com/'
    r'(?:@(?P<handle>[A-Za-z0-9._-]+)|channel/(?P<ucid>UC[A-Za-z0-9_-]{22}))'
)

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    # Bypass the consent.youtube.com interstitial served to EU IPs (no cookie → HTML shell w/o ytInitialData).
    "Cookie": "CONSENT=YES+cb.20210328-17-p0.en+FX+000; SOCS=CAI",
}
TIMEOUT = 15


def youtube(url: str) -> dict:
    video_id = _extract_video_id(url)
    if video_id:
        return _from_video(video_id, url)

    m = CHANNEL_URL_RE.match(url.strip())
    if m:
        target = f"https://www.youtube.com/@{m.group('handle')}/about" if m.group('handle') \
            else f"https://www.youtube.com/channel/{m.group('ucid')}/about"
        return _from_channel(target, url)

    return {"error": "Invalid URL format for YouTube link"}


def _extract_video_id(url: str) -> str | None:
    m = VIDEO_URL_RE.match(url.strip())
    if not m:
        return None
    return m.group('short') or m.group('v') or m.group('path')


def _fetch(url: str) -> str:
    resp = requests.get(url, headers=UA, timeout=TIMEOUT, allow_redirects=True)
    if resp.status_code >= 400:
        raise RuntimeError(f"HTTP {resp.status_code}")
    return resp.text


def _extract_json_blob(html: str, start_marker: str) -> dict | None:
    """Extract a JSON object that follows `start_marker` in the HTML.

    ytInitialData / ytInitialPlayerResponse blobs are assigned like:
        var ytInitialData = { ... };
    We walk brace depth from the first `{` to find the matching close.
    """
    idx = html.find(start_marker)
    if idx == -1:
        return None
    idx = html.find('{', idx)
    if idx == -1:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(idx, len(html)):
        ch = html[i]
        if in_str:
            if esc:
                esc = False
            elif ch == '\\':
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(html[idx:i + 1])
                except json.JSONDecodeError:
                    return None
    return None


SHARE_MARKERS = ("si", "sl", "is")


def _detect_share_marker(url: str) -> str | None:
    """Return the share-token param name if present (opaque; can't be reversed to the sharer)."""
    qs = parse_qs(urlparse(url).query)
    for key in SHARE_MARKERS:
        if key in qs and qs[key]:
            return key
    return None


def _from_video(video_id: str, source_url: str) -> dict:
    try:
        html = _fetch(f"https://www.youtube.com/watch?v={video_id}")
    except Exception as e:
        return {"error": f"Request failed: {e}"}

    player = _extract_json_blob(html, "ytInitialPlayerResponse")
    if not player:
        return {"error": "Could not parse ytInitialPlayerResponse"}

    details = (player.get("videoDetails") or {})
    channel_id = details.get("channelId")
    author = details.get("author")

    micro = (
        player.get("microformat", {}).get("playerMicroformatRenderer", {})
    )
    published = micro.get("publishDate")
    country = micro.get("availableCountries")

    if not channel_id and not author:
        return {"error": "Video metadata is missing author fields"}

    data = {
        "video_id": video_id,
        "video_title": details.get("title"),
        "channel_id": channel_id,
        "name": author,
        "channel_url": f"https://www.youtube.com/channel/{channel_id}" if channel_id else None,
        "view_count": _int_or_none(details.get("viewCount")),
        "published_at": published,
        "video_country": country[0] if isinstance(country, list) and len(country) == 1 else None,
        "share_method": _share_method(source_url),
    }
    return {"data": _prune(data)}


def _share_method(url: str) -> str | None:
    marker = _detect_share_marker(url)
    # ponytail: si/sl/is are opaque per-share tokens tied to the sharer's
    # account server-side; not publicly reversible. We only surface presence.
    return f"youtube_share_button ({marker}=…)" if marker else None


def _from_channel(about_url: str, source_url: str) -> dict:
    try:
        html = _fetch(about_url)
    except Exception as e:
        return {"error": f"Request failed: {e}"}

    initial = _extract_json_blob(html, "ytInitialData")
    if not initial:
        return {"error": "Could not parse ytInitialData"}

    header = _find_key(initial, "pageHeaderRenderer") or {}
    metadata = _find_key(initial, "channelMetadataRenderer") or {}
    about = _find_key(initial, "aboutChannelViewModel") or {}

    channel_id = metadata.get("externalId") or _find_first_ucid(initial)
    if not channel_id:
        return {"error": "Could not find channel_id"}

    handle = _extract_handle(metadata, initial, html)

    data = {
        "channel_id": channel_id,
        "username": handle,
        "name": metadata.get("title") or header.get("pageTitle"),
        "bio": metadata.get("description") or about.get("description"),
        "country": about.get("country"),
        "joined_date": _extract_join_date(about),
        "subscriber_count": _extract_subscribers(about),
        "view_count": _int_or_none(about.get("viewCountText")),
        "video_count": _int_or_none(_extract_video_count(about)),
        "external_links": _extract_links(about),
        "avatar_url": (metadata.get("avatar") or {}).get("thumbnails", [{}])[-1].get("url")
                      if isinstance(metadata.get("avatar"), dict) else None,
        "share_method": _share_method(source_url),
    }
    return {"data": _prune(data)}


def _prune(d: dict) -> dict:
    return {k: v for k, v in d.items() if v not in (None, "", [], {})}


def _int_or_none(value) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    digits = re.sub(r'\D', '', str(value))
    return int(digits) if digits else None


def _find_key(obj, key):
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            hit = _find_key(v, key)
            if hit is not None:
                return hit
    elif isinstance(obj, list):
        for item in obj:
            hit = _find_key(item, key)
            if hit is not None:
                return hit
    return None


def _find_first_ucid(obj) -> str | None:
    stack = [obj]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            for k, v in cur.items():
                if k == "browseId" and isinstance(v, str) and v.startswith("UC") and len(v) == 24:
                    return v
                stack.append(v)
        elif isinstance(cur, list):
            stack.extend(cur)
    return None


def _extract_join_date(about: dict) -> str | None:
    joined = about.get("joinedDateText")
    if isinstance(joined, dict):
        content = joined.get("content")
        if content:
            return content.replace("Joined ", "").strip()
    return None


def _extract_subscribers(about: dict) -> int | None:
    return _parse_count(about.get("subscriberCountText"))


def _extract_video_count(about: dict) -> int | None:
    return _parse_count(about.get("videoCountText"))


_SUFFIXES = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}


def _parse_count(text) -> int | None:
    """Parse strings like "45.6K subscribers", "1.2M", "1,234 videos"."""
    if not text:
        return None
    s = str(text).strip()
    m = re.match(r'([\d\.,]+)\s*([KMB])?', s, re.IGNORECASE)
    if not m:
        return None
    num_str = m.group(1).replace(',', '')
    try:
        num = float(num_str)
    except ValueError:
        return None
    mult = _SUFFIXES.get((m.group(2) or "").upper(), 1)
    return int(num * mult)


def _extract_links(about: dict) -> list[str]:
    links = []
    for link in about.get("links") or []:
        vm = link.get("channelExternalLinkViewModel") or {}
        title = (vm.get("title") or {}).get("content")
        url = ((vm.get("link") or {}).get("content"))
        if url:
            links.append({"title": title, "url": url} if title else {"url": url})
    return links


def _first_group(pattern: str, text: str) -> str | None:
    m = re.search(pattern, text)
    return m.group(1) if m else None


def _extract_handle(metadata: dict, initial: dict, html: str) -> str | None:
    """Return @handle without the leading '@', or None. Live pages expose it via
    metadata.vanityChannelUrl / ownerUrls; older mocks used channelHandleText."""
    for url_field in ("vanityChannelUrl",):
        val = metadata.get(url_field)
        if isinstance(val, str):
            m = re.search(r'/@([A-Za-z0-9._-]+)', val)
            if m:
                return m.group(1)
    owner_urls = metadata.get("ownerUrls") or []
    for val in owner_urls:
        if isinstance(val, str):
            m = re.search(r'/@([A-Za-z0-9._-]+)', val)
            if m:
                return m.group(1)
    handle_hit = _find_key(initial, "channelHandleText")
    if isinstance(handle_hit, dict):
        runs = handle_hit.get("runs") or []
        if runs:
            text = runs[0].get("text")
            if text:
                return text.lstrip('@')
    canonical = _first_group(r'<link rel="canonical" href="https://www\.youtube\.com/@([A-Za-z0-9._-]+)"', html)
    return canonical
