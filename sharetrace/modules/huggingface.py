"""Hugging Face profile identity extractor.

Resolves profile, repo, Space and dataset URLs to the owner's public identity
via the undocumented-but-stable /api/users/<name>/overview endpoint, falling
back to /api/organizations/<name>/overview when the owner is an organization.

Denylist: reserved first-segment paths that are HF service pages, not owners.
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit

from curl_cffi import requests

HOST_RE = re.compile(r'^(?:www\.)?huggingface\.co$', re.IGNORECASE)
NAME_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,94}$')

# First segments that namespace somebody else's repo: the owner is the segment
# after them, at any depth. HF itself treats them that way — /datasets/<name>
# and /spaces/<name> both 302 to /<name>/datasets and /<name>/spaces.
NAMESPACE_PREFIXES = frozenset({"spaces", "datasets"})

# Reserved first-segment paths that are HF service pages, not owners. `models`
# belongs here rather than above: huggingface.co/models/<owner>/<repo> is a 404,
# model URLs carry no prefix at all.
DENYLIST = frozenset({
    "models", "docs", "blog", "api",
    "pricing", "login", "join", "settings", "new", "tasks", "chat",
})

UA = {"User-Agent": "sharetrace/1.0"}
TIMEOUT = 10


def huggingface(url: str) -> dict:
    parts = urlsplit(url.strip())
    if parts.scheme not in ("http", "https") or not HOST_RE.match(parts.netloc):
        return {"error": "Invalid URL format for Hugging Face link"}

    segments = [s for s in parts.path.split("/") if s]
    owner, error = _owner(segments)
    if error:
        return {"error": error}
    if not NAME_RE.match(owner):
        return {"error": "Invalid URL format for Hugging Face link"}

    return _fetch_profile(owner)


def _owner(segments: list[str]) -> tuple[str, str]:
    """Pick the owner out of the path, or explain why there is not one.

    Returns (owner, "") or ("", error). Anything after the owner is ignored:
    /<user>/<repo>/tree/main and /spaces/<user>/<space>/discussions both name
    the same person as /<user>.
    """
    if not segments:
        return "", "Hugging Face URL has no owner in it"

    first = segments[0]
    if first.lower() in NAMESPACE_PREFIXES:
        if len(segments) < 2:
            return "", f"'{first}' is a Hugging Face listing page, not an owner"
        return segments[1], ""

    if first.lower() in DENYLIST:
        return "", f"'{first}' is a reserved Hugging Face path, not a user profile"

    return first, ""


def _overview(api_url: str) -> dict | None:
    """Fetch one overview endpoint. None means 404, so the caller can try another."""
    try:
        resp = requests.get(api_url, headers=UA, timeout=TIMEOUT)
    except Exception as e:
        return {"error": f"Request failed: {e}"}

    if resp.status_code == 404:
        return None
    if resp.status_code >= 400:
        return {"error": f"Hugging Face returned HTTP {resp.status_code}"}

    try:
        return {"payload": resp.json()}
    except Exception:
        return {"error": "Unexpected response from Hugging Face"}


def _fetch_profile(owner: str) -> dict:
    result = _overview(f"https://huggingface.co/api/users/{owner}/overview")
    if result is None:
        # Organizations are not users and 404 on the users endpoint — which is
        # why owners like `google` and `gradio` used to come back "not found".
        result = _overview(f"https://huggingface.co/api/organizations/{owner}/overview")
        if result is None:
            return {"error": "Hugging Face user not found"}
    if "error" in result:
        return result

    return {"data": _profile_data(result["payload"], owner)}


def _profile_data(payload: dict, owner: str) -> dict:
    # The two endpoints disagree on where the handle lives: users put it in
    # `user`, organizations in `name`. Only users carry `type` and `orgs`.
    handle = payload.get("user") or payload.get("name") or owner
    raw_orgs = payload.get("orgs") or []
    account_type = payload.get("type") or ("org" if "name" in payload else "user")

    return {
        "username": handle,
        "fullname": payload.get("fullname") or None,
        "avatar_url": payload.get("avatarUrl"),
        "account_type": account_type,
        "num_followers": payload.get("numFollowers", 0),
        "orgs": [o["name"] for o in raw_orgs if isinstance(o, dict) and o.get("name")],
        "profile_url": f"https://huggingface.co/{handle}",
    }
