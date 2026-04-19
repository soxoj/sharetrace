"""Hugging Face profile identity extractor.

Resolves profile and repo URLs to the owner's public identity via
the undocumented-but-stable /api/users/<name>/overview endpoint.

Denylist: reserved first-segment paths that are HF service pages,
not user profiles.
"""
from __future__ import annotations

import re

from curl_cffi import requests

# Matches:
#   huggingface.co/<user>
#   huggingface.co/<user>/<repo>
# Caps at exactly one optional sub-path segment so deeper paths are rejected.
URL_RE = re.compile(
    r'^https?://(?:www\.)?huggingface\.co/'
    r'([A-Za-z0-9][A-Za-z0-9._-]{0,94})'
    r'(?:/[^/?#]+)?/?(?:[?#].*)?$'
)

DENYLIST = frozenset({
    "spaces", "datasets", "models", "docs", "blog", "api",
    "pricing", "login", "join", "settings", "new", "tasks", "chat",
})

UA = {"User-Agent": "sharetrace/1.0"}
TIMEOUT = 10


def huggingface(url: str) -> dict:
    m = URL_RE.match(url.strip())
    if not m:
        return {"error": "Invalid URL format for Hugging Face link"}

    username = m.group(1)

    if username.lower() in DENYLIST:
        return {"error": f"'{username}' is a reserved Hugging Face path, not a user profile"}

    return _fetch_profile(username)


def _fetch_profile(username: str) -> dict:
    api_url = f"https://huggingface.co/api/users/{username}/overview"
    try:
        resp = requests.get(api_url, headers=UA, timeout=TIMEOUT)
    except Exception as e:
        return {"error": f"Request failed: {e}"}

    if resp.status_code == 404:
        return {"error": "Hugging Face user not found"}
    if resp.status_code >= 400:
        return {"error": f"Hugging Face returned HTTP {resp.status_code}"}

    try:
        payload = resp.json()
    except Exception:
        return {"error": "Unexpected response from Hugging Face"}

    # Flatten orgs: each org object has a "name" key (the handle).
    raw_orgs = payload.get("orgs") or []
    org_handles = [o["name"] for o in raw_orgs if isinstance(o, dict) and o.get("name")]

    # fullname may be an empty string — normalise to None.
    fullname = payload.get("fullname") or None

    data: dict = {
        "username": payload.get("user", username),
        "fullname": fullname,
        "avatar_url": payload.get("avatarUrl"),
        "account_type": payload.get("type", "user"),
        "num_followers": payload.get("numFollowers", 0),
        "orgs": org_handles,
        "profile_url": f"https://huggingface.co/{payload.get('user', username)}",
    }
    return {"data": data}
