"""GitLab email/identity extractor.

Two routes:
- Commit URL → append .patch → parse mbox 'From: Name <email>' header.
- Profile URL → /api/v4/users?username=<name> → return public profile fields.
  Note: GitLab v4 API does NOT expose email in push events for unauthenticated
  requests. Only public_email is returned, and only if the user opted in.

Supports gitlab.com only — self-hosted instances are out of scope.
Nested groups are supported: gitlab.com/<group>/<sub>/<repo>/-/commit/<sha>
"""
from __future__ import annotations

import re
from email.utils import parseaddr

from curl_cffi import requests

# Matches commit URLs with arbitrary nesting of groups before /-/commit/<sha>.
# Capture group 1: full path (group/.../project), group 2: sha.
COMMIT_RE = re.compile(
    r'gitlab\.com/((?:[^/]+/)+[^/]+)/-/commit/([0-9a-f]{7,40})'
)

# Profile: https://gitlab.com/<username> with no path beyond an optional slash.
# Username rules: starts with alnum, up to 255 chars, alnum + dots/underscores/hyphens.
PROFILE_RE = re.compile(
    r'^https?://(?:www\.)?gitlab\.com/'
    r'([A-Za-z0-9][A-Za-z0-9._-]{0,254})'
    r'/?$'
)

# Reserved top-level paths that must not be treated as usernames.
_RESERVED = frozenset({
    "explore", "users", "help", "admin", "api", "-",
    "dashboard", "profile", "groups", "projects",
    "search", "public", "snippets", "health_check",
    "assets", "uploads", "robots.txt", "favicon.ico",
})

NOREPLY_DOMAIN = "users.noreply.gitlab.com"

UA = {"User-Agent": "sharetrace/1.0"}
TIMEOUT = 10


def _parse_from_header(text: str) -> tuple[str, str] | None:
    """Extract name and email from an mbox 'From:' header line.

    Uses RFC 5322 parser to handle quoted display names containing '<'
    correctly — plain regex cannot do this reliably.
    """
    for line in text.splitlines():
        if line.startswith("From: "):
            name, email = parseaddr(line[len("From: "):])
            if email and "@" in email:
                return name.strip(), email.strip()
    return None


def gitlab(url: str) -> dict:
    """Dispatch a GitLab URL to the correct extraction route."""
    m = COMMIT_RE.search(url)
    if m:
        return _from_commit(m.group(1), m.group(2))

    m = PROFILE_RE.match(url.strip())
    if m:
        username = m.group(1)
        if username.lower() in _RESERVED:
            return {"error": "Invalid URL format for GitLab link"}
        return _from_profile(username)

    return {"error": "Invalid URL format for GitLab link"}


def _from_commit(project_path: str, sha: str) -> dict:
    """Fetch commit patch and parse author name + email from mbox From header."""
    patch_url = f"https://gitlab.com/{project_path}/-/commit/{sha}.patch"
    try:
        resp = requests.get(patch_url, headers=UA, timeout=TIMEOUT, allow_redirects=True)
    except Exception as e:
        return {"error": f"Request failed: {e}"}

    if resp.status_code == 404:
        return {"error": "Commit not found or repository is private"}
    if resp.status_code == 429:
        return {"error": "GitLab rate-limit exceeded"}
    if resp.status_code >= 400:
        return {"error": f"GitLab returned HTTP {resp.status_code}"}

    parsed = _parse_from_header(resp.text[:4096])
    if not parsed:
        return {"error": "Could not parse author email from commit patch"}

    name, email = parsed
    data: dict = {
        "name": name,
        "email": email,
        "commit_sha": sha,
        "project": project_path,
    }
    if email.endswith(NOREPLY_DOMAIN):
        data["is_noreply"] = True
    return {"data": data}


def _from_profile(username: str) -> dict:
    """Look up a GitLab user profile via the v4 API.

    Two-step: resolve username → numeric id, then fetch full user object for
    public_email. Email is only present if the user opted in to public_email.
    GitLab v4 API strips push-event emails for unauthenticated callers — this
    is by design. We return public_email as-is (may be None).
    """
    search_url = f"https://gitlab.com/api/v4/users?username={username}"
    try:
        resp = requests.get(search_url, headers=UA, timeout=TIMEOUT)
    except Exception as e:
        return {"error": f"Request failed: {e}"}

    if resp.status_code == 429:
        return {"error": "GitLab API rate-limit exceeded"}
    if resp.status_code >= 400:
        return {"error": f"GitLab API returned HTTP {resp.status_code}"}

    try:
        users = resp.json()
    except Exception:
        return {"error": "Unexpected response from GitLab API"}

    if not isinstance(users, list) or not users:
        return {"error": "GitLab user not found"}

    user = users[0]
    user_id: int = user.get("id")

    # Fetch the individual user object which includes public_email when set.
    user_url = f"https://gitlab.com/api/v4/users/{user_id}"
    try:
        detail_resp = requests.get(user_url, headers=UA, timeout=TIMEOUT)
    except Exception as e:
        return {"error": f"Request failed fetching user detail: {e}"}

    if detail_resp.status_code >= 400:
        # Fall back to search result — public_email may not be present.
        detail = user
    else:
        try:
            detail = detail_resp.json()
        except Exception:
            detail = user

    data: dict = {
        "username": detail.get("username") or user.get("username"),
        "display_name": detail.get("name") or user.get("name"),
        "user_id": user_id,
        "avatar_url": detail.get("avatar_url") or user.get("avatar_url"),
        "public_email": detail.get("public_email"),  # None when not set — by design
    }
    return {"data": data}
