import sys
from typing import Any, Dict

class Colors:
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RESET = '\033[0m'
    
    GRADIENT_1 = '\033[38;5;52m'
    GRADIENT_2 = '\033[38;5;88m'
    GRADIENT_3 = '\033[38;5;124m'
    GRADIENT_4 = '\033[38;5;160m'
    GRADIENT_5 = '\033[38;5;196m'

if not sys.stdout.isatty():
    Colors.CYAN = ''
    Colors.GREEN = ''
    Colors.YELLOW = ''
    Colors.RED = ''
    Colors.BOLD = ''
    Colors.DIM = ''
    Colors.RESET = ''
    Colors.GRADIENT_1 = ''
    Colors.GRADIENT_2 = ''
    Colors.GRADIENT_3 = ''
    Colors.GRADIENT_4 = ''
    Colors.GRADIENT_5 = ''

PLATFORM_NAMES = {
    'tiktok': 'TikTok',
    'chatgpt': 'ChatGPT',
    'discord': 'Discord',
    'instagram': 'Instagram',
    'microsoft': 'Microsoft',
    'perplexity': 'Perplexity',
    'pinterest': 'Pinterest',
    'substack': 'Substack',
    'telegram': 'Telegram',
    'suno': 'Suno',
}

FIELD_LABELS = {
    'user_id': 'User ID',
    'username': 'Username',
    'name': 'Name',
    'email': 'Email',
    'profile_url': 'Profile',
    'avatar_url': 'Avatar',
    'created_at': 'Created',
    'country': 'Country',
    'device': 'Device',
    'share_method': 'Share Method',
    'shared_at': 'Shared At',
    'follower_count': 'Followers',
    'following_count': 'Following',
    'video_count': 'Videos',
    'heart_count': 'Hearts',
    'private_account': 'Private',
    'dm_available': 'DMs Available',
    'bio': 'Bio',
    'signature': 'Signature',
    'previous_name': 'Previous Name',
    'profile_set_up_at': 'Profile Set Up',
    'reader_installed_at': 'Reader Installed',
}


def print_banner():
    line1 = f"{Colors.GRADIENT_1}   _____ __                   ______"
    line2 = f"{Colors.GRADIENT_2}  / ___// /_  ____ _________ /_  __/________ _________"
    line3 = f"{Colors.GRADIENT_3}  \\__ \\/ __ \\/ __ `/ ___/ _ \\ / / / ___/ __ `/ ___/ _ \\"
    line4 = f"{Colors.GRADIENT_4} ___/ / / / / /_/ / /  /  __// / / /  / /_/ / /__/  __/"
    line5 = f"{Colors.GRADIENT_5}/____/_/ /_/\\__,_/_/   \\___//_/ /_/   \\__,_/\\___/\\___/"
    
    banner = f"""
{line1}
{line2}
{line3}
{line4}
{line5}{Colors.RESET}

      🎭 Reveal the identity behind a share link{Colors.RESET}
"""
    print(banner)


def print_result(platform: str, result: Dict[str, Any], quiet: bool = False):
    if not quiet:
        print_banner()

    platform_name = PLATFORM_NAMES.get(platform, platform.title())

    if 'error' in result:
        print(f"{Colors.RED}{Colors.BOLD}[ERROR]{Colors.RESET} {result['error']}\n")
        return

    data = result.get('data', {})

    print(f"{Colors.GREEN}{Colors.BOLD}[SUCCESS]{Colors.RESET} Identity extracted")

    for key, value in data.items():
        if value is None:
            continue

        label = FIELD_LABELS.get(key, key.replace('_', ' ').title())

        if isinstance(value, bool):
            value = 'Yes' if value else 'No'

        if isinstance(value, int) and key.endswith('_count'):
            value = f"{value:,}"

        if isinstance(value, str) and value.startswith('http'):
            value = f"{Colors.CYAN}{value}{Colors.RESET}"

        print(f"  ├─ {Colors.BOLD}{label}:{Colors.RESET} {value}")

    print()


def print_error(message: str, quiet: bool = False):
    if not quiet:
        print_banner()
    print(f"{Colors.RED}{Colors.BOLD}[ERROR]{Colors.RESET} {message}\n")


def print_supported_platforms():
    print(f"\n{Colors.BOLD}Supported platforms:{Colors.RESET}")
    for platform, name in PLATFORM_NAMES.items():
        print(f"  - {name}")
    print()