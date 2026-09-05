import re
import urllib.parse
from importlib import import_module
from typing import Callable, Optional

SHORTENER_PATTERNS = [
    r'^https?://share\.google/',
    r'^https?://(?:www\.)?google\.com/share\.google(?:/|\?|$)',
]

PLATFORM_PATTERNS = [
    (r'(vm\.tiktok\.com|vt\.tiktok\.com|tiktok\.com/t)/[A-Za-z0-9]+', 'tiktok'),
    (r'tiktok\.com/@[A-Za-z0-9._]+(?:/video/\d+)?/?', 'tiktok'),
    (r'chatgpt\.com/share/[a-f0-9-]+', 'chatgpt'),
    (r'claude\.ai/share/[a-f0-9-]+', 'claude'),
    (r'(discord\.com/invite|discord\.gg)/[a-zA-Z0-9]+', 'discord'),
    (r'instagram\.com/(reel|p)/[A-Za-z0-9_-]+', 'instagram'),
    (r'sharepoint\.com/:[a-z]:/g/personal/[^/]+/', 'microsoft'),
    (r'perplexity\.ai/search/[A-Za-z0-9._-]+', 'perplexity'),
    (r'pin\.it/[A-Za-z0-9]+', 'pinterest'),
    (r'substack\.com/@[^/]+/note/', 'substack'),
    (r'suno\.com/s/[A-Za-z0-9]+', 'suno'),
    (r't\.me/joinchat/[A-Za-z0-9_-]+', 'telegram'),
    (r't\.me/\+[A-Za-z0-9_-]+', 'telegram'),
    (r't\.me/c/\d+/\d+', 'telegram'),
    (
        # Public username or public username + message id.
        # Excludes reserved segments (joinchat, c, +…) via lookahead.
        r't\.me/(?!joinchat/|c/|\+)([A-Za-z0-9_]{5,32})(?:/\d+)?/?(?:[?#].*)?$',
        'telegram',
    ),
    (
        r'(docs\.google\.com/(document|spreadsheets|presentation|drawings|forms)/d/'
        r'|drive\.google\.com/file/d/'
        r'|drive\.google\.com/drive/(?:mobile/|u/\d+/)?folders/'
        r'|script\.google\.com/d/'
        r'|jamboard\.google\.com/d/'
        r'|google\.com/maps/d/)',
        'gdoc',
    ),
    (r'(notion\.so/|\.notion\.site(/|$))', 'notion'),
    (r'github\.com/[^/]+/[^/]+/(?:commit|pull/\d+/commits)/[0-9a-f]{7,40}', 'github'),
    (
        r'^https?://(?:www\.)?github\.com/'
        r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?'
        r'/?(?:\?.*)?$',
        'github',
    ),
    # GitHub owner/repo (no /commit, /pull, /issues, /tree, etc.).
    (
        r'^https?://(?:www\.)?github\.com/'
        r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?'
        r'/[A-Za-z0-9._-]+/?(?:\?.*)?$',
        'github',
    ),
    # GitLab — commit pattern (specific) before profile pattern (broad).
    (r'gitlab\.com/(?:[^/]+/)+[^/]+/-/commit/[0-9a-f]{7,40}', 'gitlab'),
    (
        r'^https?://(?:www\.)?gitlab\.com/'
        r'[A-Za-z0-9][A-Za-z0-9._-]{0,254}'
        r'/?$',
        'gitlab',
    ),
    # Hugging Face — profile or profile/repo URLs. Module handles denylist.
    (
        r'^https?://(?:www\.)?huggingface\.co/'
        r'[A-Za-z0-9][A-Za-z0-9._-]{0,94}'
        r'(?:/[^/?#]+)?/?(?:[?#].*)?$',
        'huggingface',
    ),
    # LinkedIn — /in, /posts, /pulse only. Module handles bot-block detection.
    (r'linkedin\.com/(?:in|posts|pulse)/[A-Za-z0-9_%-]+', 'linkedin'),
    # YouTube — video (short/watch/shorts/live/embed) or channel (@handle, /channel/UC…).
    (
        r'^https?://(?:'
        r'youtu\.be/[A-Za-z0-9_-]{11}'
        r'|(?:www\.|m\.)?youtube\.com/(?:watch\?[^ ]*v=[A-Za-z0-9_-]{11}'
        r'|(?:shorts|live|embed)/[A-Za-z0-9_-]{11}'
        r'|@[A-Za-z0-9._-]+'
        r'|channel/UC[A-Za-z0-9_-]{22}))',
        'youtube',
    ),
]

PARSERS = {
    'tiktok': 'tiktok',
    'chatgpt': 'chatgpt',
    'discord': 'discord',
    'instagram': 'instagram',
    'microsoft': 'microsoft',
    'perplexity': 'perplexity',
    'pinterest': 'pinterest',
    'substack': 'substack',
    'suno': 'suno',
    'telegram': 'telegram',
    'claude': 'claude',
    'gdoc': 'gdoc',
    'github': 'github',
    'gitlab': 'gitlab',
    'huggingface': 'huggingface',
    'linkedin': 'linkedin',
    'notion': 'notion',
    'youtube': 'youtube',
}


def detect_platform(url: str) -> Optional[str]:
    for pattern, platform in PLATFORM_PATTERNS:
        if re.search(pattern, url):
            return platform
    return None


def _is_shortener(url: str) -> bool:
    return any(re.search(p, url) for p in SHORTENER_PATTERNS)


def resolve_url(url: str, max_hops: int = 5) -> str:
    if not _is_shortener(url):
        return url

    from curl_cffi import requests as _cffi_requests

    seen = set()
    current = url
    for _ in range(max_hops):
        if not _is_shortener(current) or current in seen:
            return current
        seen.add(current)
        try:
            r = _cffi_requests.get(current, impersonate='chrome', allow_redirects=False)
        except Exception:
            return current
        if r.status_code not in (301, 302, 303, 307, 308):
            return current
        loc = r.headers.get('location')
        if not loc:
            return current
        current = urllib.parse.urljoin(current, loc)
    return current


def get_parser(platform: str) -> Optional[Callable]:
    if platform not in PARSERS:
        return None

    func_name = PARSERS[platform]
    module = import_module(f'sharetrace.modules.{platform}')
    return getattr(module, func_name)


def get_supported_platforms() -> list:
    return list(PARSERS.keys())
