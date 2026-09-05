"""Telegram identity extractor.

Three routes:
- t.me/joinchat/{hash} or t.me/+{hash} → decode creator user_id from the base64 invite payload.
- t.me/{username}[/{msg_id}] → scrape the public preview at t.me/s/{username} for channel/user metadata.
- t.me/c/{id}/{id} → private channel; nothing extractable anonymously.
"""
from __future__ import annotations

import base64
import re
import struct
from html import unescape

from curl_cffi import requests

INVITE_RE = re.compile(r't\.me/(?:joinchat/|\+)([A-Za-z0-9_-]+)')
PUBLIC_RE = re.compile(r't\.me/(?!joinchat/|c/|\+)([A-Za-z0-9_]{5,32})(?:/(\d+))?')
PRIVATE_CHANNEL_RE = re.compile(r't\.me/c/(\d+)(?:/(\d+))?')

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"
}
TIMEOUT = 10


def telegram(url: str) -> dict:
    m = PRIVATE_CHANNEL_RE.search(url)
    if m:
        return _from_private(int(m.group(1)), int(m.group(2)) if m.group(2) else None)

    m = INVITE_RE.search(url)
    if m:
        return _from_invite(m.group(1))

    m = PUBLIC_RE.search(url)
    if m:
        return _from_public(m.group(1))

    return {"error": "Invalid URL format for Telegram link"}


def _from_private(internal_id: int, message_id: int | None) -> dict:
    # t.me/c/{internal_id}/{message_id} — private channel. Anonymous scrape
    # is impossible, but the URL still encodes the channel's Bot-API id.
    data = {
        "channel_id": -1_000_000_000_000 - internal_id,
        "channel_internal_id": internal_id,
        "url_type": "Private channel (membership required to view content)",
    }
    if message_id is not None:
        data["message_id"] = message_id
    return {"data": data}


def _from_invite(hash_str: str) -> dict:
    padding = 4 - (len(hash_str) % 4)
    if padding != 4:
        hash_str += '=' * padding
    try:
        decoded = base64.urlsafe_b64decode(hash_str)
    except Exception:
        return {"error": "Invalid Telegram invite hash"}
    # Legacy joinchat/ format: 16-byte payload = creator_id(u32) + chat_id(u64) + random(u32).
    # Newer +hash invites are opaque ~12-byte tokens with no creator field.
    if len(decoded) >= 16:
        creator_id = struct.unpack('<I', decoded[:4])[0]
        return {"data": {"user_id": creator_id}}
    return {"error": "Opaque invite hash (new-format token — no creator id encoded)"}


def _from_public(username: str) -> dict:
    preview_url = f"https://t.me/s/{username}"
    try:
        resp = requests.get(preview_url, headers=UA, timeout=TIMEOUT, allow_redirects=True)
    except Exception as e:
        return {"error": f"Request failed: {e}"}

    if resp.status_code >= 400:
        return {"error": f"Telegram returned HTTP {resp.status_code}"}

    html = resp.text
    if 'tgme_page_action' in html and 'tgme_channel_info' not in html and 'tgme_page_extra' not in html:
        return {"error": "No public preview — user is not a channel/bot or has no public content"}

    data: dict = {"username": username}

    title = _first_group(r'<meta property="og:title" content="([^"]+)"', html)
    if title:
        data["name"] = unescape(title)

    description = _first_group(r'<meta property="og:description" content="([^"]+)"', html)
    if description:
        data["bio"] = unescape(description)

    avatar = _first_group(r'<meta property="og:image" content="([^"]+)"', html)
    if avatar and not avatar.endswith('/img/t_logo.png'):
        data["avatar_url"] = avatar

    subs = _first_group(
        r'<span class="counter_value">([^<]+)</span>\s*<span class="counter_type">subscribers?</span>',
        html,
    )
    if subs:
        n = _parse_count(subs)
        if n is not None:
            data["follower_count"] = n

    if not any(k in data for k in ("name", "bio", "follower_count", "avatar_url")):
        return {"error": "No public metadata found"}

    return {"data": data}


def _first_group(pattern: str, text: str) -> str | None:
    m = re.search(pattern, text)
    return m.group(1) if m else None


_SUFFIXES = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}


def _parse_count(text: str) -> int | None:
    """Parse '9.73M subscribers', '1,234', '12 345 678'. Handles K/M/B, commas, spaces."""
    # Space-as-thousands-separator (fr/ru style) is common in Telegram's HTML.
    normalized = re.sub(r'(\d)\s+(\d)', r'\1\2', text.strip())
    m = re.match(r'([\d\.,]+)\s*([KMB])?', normalized, re.IGNORECASE)
    if not m:
        return None
    try:
        num = float(m.group(1).replace(',', ''))
    except ValueError:
        return None
    return int(num * _SUFFIXES.get((m.group(2) or "").upper(), 1))
