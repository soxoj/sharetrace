"""Reddit share-link resolver.

The mobile app shares posts as reddit.com/r/{subreddit}/s/{token}. The token
30x-redirects to the canonical post, and the post's JSON listing names the
author. Two things the redirect is also used for:

- An unknown or expired token does not 404: it redirects to the subreddit
  itself, so a Location that is not a /comments/ URL means "no post".
- The subreddit and post id come from Reddit's own Location, never from the
  input. Reddit looks posts up by id alone, so /r/anything/comments/{id}
  returns that post whatever subreddit is in the path.

Reddit answers the JSON listing with 403 to many networks that have no session.
The public oEmbed endpoint still names the author and title of the same post,
so it is tried when the listing is refused.
"""
from __future__ import annotations

import re
from urllib.parse import urljoin

from curl_cffi import requests

SHARE_RE = re.compile(r'reddit\.com/r/([A-Za-z0-9_]+)/s/([A-Za-z0-9]+)')
POST_RE = re.compile(
    r'^https?://(?:www\.|old\.|new\.)?reddit\.com'
    r'/r/([A-Za-z0-9_]+)/comments/([a-z0-9]+)(?:/([^/?#]+))?'
)
REDIRECT_CODES = (301, 302, 303, 307, 308)
DELETED_AUTHOR = "[deleted]"
TIMEOUT = 10


def reddit(url: str) -> dict:
    m = SHARE_RE.search(url)
    if not m:
        return {"error": "Invalid URL format for Reddit share link"}

    share_url = f"https://www.reddit.com/r/{m.group(1)}/s/{m.group(2)}"
    try:
        resp = requests.get(share_url, impersonate="chrome", timeout=TIMEOUT, allow_redirects=False)
    except Exception as e:
        return {"error": f"Request failed: {e}"}

    location = _header(resp, "location") if resp.status_code in REDIRECT_CODES else None
    if not location:
        return {"error": f"Reddit did not redirect the share link (HTTP {resp.status_code})"}

    post = POST_RE.match(urljoin(share_url, location))
    if not post:
        return {"error": "Share link does not resolve to a post (invalid or expired token)"}

    subreddit, post_id, slug = post.groups()
    # Rebuilt without the query string: the redirect carries share_id and utm_*
    # tracking parameters that do not belong in a canonical URL.
    post_url = f"https://www.reddit.com/r/{subreddit}/comments/{post_id}/"
    if slug:
        post_url += f"{slug}/"

    details = _from_listing(post_url) or _from_oembed(post_url)
    if details is None:
        return {"error": "Reddit refused both the post listing and oEmbed for this post"}

    author = details.get("author")
    if not author or author == DELETED_AUTHOR:
        return {"error": "Post author is deleted"}

    data = {
        "username": author,
        "profile_url": f"https://www.reddit.com/user/{author}/",
        "subreddit": details.get("subreddit") or subreddit,
        "post_url": post_url,
    }
    if details.get("title"):
        data["post_title"] = details["title"]
    return {"data": data}


def _from_listing(post_url: str) -> dict | None:
    """Author, subreddit and title from the post's comments JSON, or None."""
    try:
        resp = requests.get(post_url + ".json", impersonate="chrome", timeout=TIMEOUT)
        if resp.status_code != 200:
            return None
        post = resp.json()[0]["data"]["children"][0]["data"]
    except Exception:
        return None
    return {
        "author": post.get("author"),
        "subreddit": post.get("subreddit"),
        "title": post.get("title"),
    }


def _from_oembed(post_url: str) -> dict | None:
    """Author and title from the public oEmbed endpoint, or None."""
    try:
        resp = requests.get(
            "https://www.reddit.com/oembed",
            params={"url": post_url},
            impersonate="chrome",
            timeout=TIMEOUT,
        )
        if resp.status_code != 200:
            return None
        payload = resp.json()
    except Exception:
        return None
    if not payload.get("author_name"):
        return None
    return {"author": payload["author_name"], "title": payload.get("title")}


def _header(resp, name: str) -> str | None:
    headers = resp.headers or {}
    return headers.get(name) or headers.get(name.title())
