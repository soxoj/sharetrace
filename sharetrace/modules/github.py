"""GitHub email/identity extractor.

Two routes:
- Commit URL → append .patch → parse mbox 'From: Name <email>' header.
- Profile URL → /users/{user}/events/public → scan PushEvents for author emails.

No auth. Subject to GitHub's 60/hr unauth rate limit on the profile route.
"""
from __future__ import annotations

import re
from email.utils import parseaddr

from curl_cffi import requests

COMMIT_RE = re.compile(
    r'github\.com/([^/]+)/([^/]+)/(?:commit|pull/\d+/commits)/([0-9a-f]{7,40})'
)
# Username: 1–39 chars, alnum + internal hyphens only (no leading/trailing hyphen).
PROFILE_RE = re.compile(
    r'^https?://(?:www\.)?github\.com/'
    r'([A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?)'
    r'/?(?:\?.*)?$'
)
NOREPLY_DOMAIN = "users.noreply.github.com"

UA = {"User-Agent": "sharetrace/1.0"}
TIMEOUT = 10


def _parse_from_header(text: str) -> tuple[str, str] | None:
    for line in text.splitlines():
        if line.startswith("From: "):
            name, email = parseaddr(line[len("From: "):])
            if email and "@" in email:
                return name.strip(), email.strip()
    return None


def github(url: str) -> dict:
    m = COMMIT_RE.search(url)
    if m:
        return _from_commit(*m.groups())

    m = PROFILE_RE.match(url.strip())
    if m:
        return _from_profile(m.group(1))

    return {"error": "Invalid URL format for GitHub link"}


def _from_commit(owner: str, repo: str, sha: str) -> dict:
    patch_url = f"https://github.com/{owner}/{repo}/commit/{sha}.patch"
    try:
        resp = requests.get(patch_url, headers=UA, timeout=TIMEOUT, allow_redirects=True)
    except Exception as e:
        return {"error": f"Request failed: {e}"}

    if resp.status_code == 404:
        return {"error": "Commit not found or repository is private"}
    if resp.status_code >= 400:
        return {"error": f"GitHub returned HTTP {resp.status_code}"}

    # Parse the mbox From: header with RFC 5322 parser — handles quoted
    # display names containing '<' correctly (plain regex does not).
    parsed = _parse_from_header(resp.text[:4096])
    if not parsed:
        return {"error": "Could not parse author email from commit patch"}

    name, email = parsed
    data = {
        "name": name,
        "email": email,
        "commit_sha": sha,
        "repo": f"{owner}/{repo}",
    }
    if email.endswith(NOREPLY_DOMAIN):
        data["is_noreply"] = True
    return {"data": data}


def _from_profile(username: str) -> dict:
    api_url = f"https://api.github.com/users/{username}/events/public"
    try:
        resp = requests.get(
            api_url,
            headers={**UA, "Accept": "application/vnd.github+json"},
            timeout=TIMEOUT,
        )
    except Exception as e:
        return {"error": f"Request failed: {e}"}

    if resp.status_code == 404:
        return {"error": "GitHub user not found"}
    if resp.status_code == 403:
        return {"error": "GitHub API rate-limit exceeded (60/hr unauth)"}
    if resp.status_code >= 400:
        return {"error": f"GitHub returned HTTP {resp.status_code}"}

    try:
        events = resp.json()
    except Exception:
        return {"error": "Unexpected response from GitHub API"}

    found: dict[str, str] = {}        # email -> name
    noreply: list[str] = []           # preserves first-seen order

    for event in events or []:
        if event.get("type") != "PushEvent":
            continue
        for commit in (event.get("payload") or {}).get("commits") or []:
            author = commit.get("author") or {}
            email = author.get("email")
            name = author.get("name")
            if not email:
                continue
            if email.endswith(NOREPLY_DOMAIN):
                if email not in noreply:
                    noreply.append(email)
                continue
            if email not in found and name:
                found[email] = name

    if not found and not noreply:
        return {"error": "No email addresses found in recent public PushEvents"}

    data = {
        "username": username,
        "emails": [{"name": n, "email": e} for e, n in found.items()],
    }
    if noreply:
        data["noreply_emails"] = noreply
    return {"data": data}
