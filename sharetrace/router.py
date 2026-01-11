import re
from importlib import import_module
from typing import Callable, Optional

PLATFORM_PATTERNS = [
    (r'(vm\.tiktok\.com|vt\.tiktok\.com|tiktok\.com/t)/[A-Za-z0-9]+', 'tiktok'),
    (r'chatgpt\.com/share/[a-f0-9-]+', 'chatgpt'),
    (r'(discord\.com/invite|discord\.gg)/[a-zA-Z0-9]+', 'discord'),
    (r'instagram\.com/(reel|p)/[A-Za-z0-9_-]+', 'instagram'),
    (r'sharepoint\.com/:[a-z]:/g/personal/[^/]+/', 'microsoft'),
    (r'perplexity\.ai/search/[A-Za-z0-9._-]+', 'perplexity'),
    (r'pin\.it/[A-Za-z0-9]+', 'pinterest'),
    (r'substack\.com/@[^/]+/note/', 'substack'),
    (r'suno\.com/s/[A-Za-z0-9]+', 'suno'),
    (r't\.me/joinchat/[A-Za-z0-9_-]+', 'telegram'),
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
}


def detect_platform(url: str) -> Optional[str]:
    for pattern, platform in PLATFORM_PATTERNS:
        if re.search(pattern, url):
            return platform
    return None


def get_parser(platform: str) -> Optional[Callable]:
    if platform not in PARSERS:
        return None

    func_name = PARSERS[platform]
    module = import_module(f'sharetrace.modules.{platform}')
    return getattr(module, func_name)


def get_supported_platforms() -> list:
    return list(PARSERS.keys())