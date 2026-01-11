from curl_cffi import requests
import re


def discord(url):
    match = re.search(r'(?:discord\.com/invite/|discord\.gg/)([a-zA-Z0-9]+)', url)
    if not match:
        return {"error": "Invalid Discord invite URL format"}

    invite_code = match.group(1)

    try:
        response = requests.get(f'https://discord.com/api/v9/invites/{invite_code}')
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        return {"error": f"Request failed: {str(e)}"}
    except ValueError:
        return {"error": "Failed to parse response JSON"}

    def snowflake_to_timestamp(snowflake_id):
        from datetime import datetime, timezone
        timestamp = ((int(snowflake_id) >> 22) + 1420070400000) / 1000
        return datetime.fromtimestamp(timestamp, timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

    inviter = data.get('inviter', {})
    if not inviter:
        return {"error": "No inviter found in invite data"}

    user_id = inviter.get('id')
    avatar = inviter.get('avatar')

    avatar_url = None
    if user_id and avatar:
        ext = 'gif' if avatar.startswith('a_') else 'png'
        avatar_url = f"https://cdn.discordapp.com/avatars/{user_id}/{avatar}.{ext}"

    return {
        "data": {
            "user_id": user_id,
            "username": inviter.get('username'),
            "name": inviter.get('global_name'),
            "avatar_url": avatar_url,
            "created_at": snowflake_to_timestamp(user_id)
        }
    }