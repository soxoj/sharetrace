"""Reddit share link extractor.

reddit.com/r/{subreddit}/s/{token} 302-redirects to the canonical post URL.
The token itself carries nothing; the post's public JSON listing
({canonical}.json) supplies the author. Comment authors and user profiles
are out of scope.
"""
from __future__ import annotations

import re
import urllib.parse

from curl_cffi import requests

SHARE_RE = re.compile(r'reddit\.com/r/([A-Za-z0-9_]+)/s/([A-Za-z0-9]+)')
POST_RE = re.compile(r'reddit\.com/r/[A-Za-z0-9_]+/comments/[A-Za-z0-9]+')

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"
}
TIMEOUT = 10
MAX_HOPS = 5


def reddit(url: str) -> dict:
    if not SHARE_RE.search(url):
        return {"error": "Invalid URL format for Reddit share link"}

    resolved = _resolve_share(url)
    if "error" in resolved:
        return resolved
    post_url = resolved["url"]

    try:
        resp = requests.get(f"{post_url}.json", headers=UA, timeout=TIMEOUT)
    except Exception as e:
        return {"error": f"Request failed: {e}"}
    if resp.status_code >= 400:
        return {"error": f"Reddit returned HTTP {resp.status_code}"}

    try:
        post = resp.json()[0]["data"]["children"][0]["data"]
    except (ValueError, LookupError, TypeError):
        return {"error": "Unexpected Reddit JSON structure"}

    author = post.get("author")
    if not author or author == "[deleted]":
        return {"error": "Post author is deleted or unavailable"}

    return {
        "data": {
            "username": author,
            "profile_url": f"https://www.reddit.com/user/{author}",
            "subreddit": post.get("subreddit"),
            "post_url": post_url,
            "post_title": post.get("title"),
        }
    }


def _resolve_share(url: str) -> dict:
    current = url
    for _ in range(MAX_HOPS):
        try:
            resp = requests.get(current, headers=UA, timeout=TIMEOUT, allow_redirects=False)
        except Exception as e:
            return {"error": f"Request failed: {e}"}
        if resp.status_code not in (301, 302, 303, 307, 308):
            break
        location = resp.headers.get("location")
        if not location:
            break
        current = urllib.parse.urljoin(current, location)
        if POST_RE.search(current):
            # Drop share tracking params and the trailing slash so `.json` appends cleanly.
            parts = urllib.parse.urlsplit(current)
            return {"url": urllib.parse.urlunsplit(
                (parts.scheme, parts.netloc, parts.path.rstrip("/"), "", ""))}
    return {"error": "Share link did not redirect to a Reddit post"}
