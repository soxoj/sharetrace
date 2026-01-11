from curl_cffi import requests
import base64
import json
import time
import re


def browser_token():
    payload = {"timestamp": int(time.time() * 1000)}
    token = base64.b64encode(json.dumps(payload).encode()).decode()
    return json.dumps({"token": token})


def suno(url):
    match = re.search(r'suno\.com/s/([A-Za-z0-9]+)', url)
    if not match:
        return {"error": "Invalid URL format for Suno share link"}

    share_code = match.group(1)

    headers = {
        'accept': '*/*',
        'accept-language': 'en-US,en;q=0.9',
        'browser-token': browser_token(),
        'cache-control': 'no-cache',
        'origin': 'https://suno.com',
        'pragma': 'no-cache',
        'referer': 'https://suno.com/',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
    }

    response = requests.get(
        f'https://studio-api.prod.suno.com/api/share/code/{share_code}',
        headers=headers
    )

    data = response.json()

    if not data.get('success'):
        return {"error": "Failed to fetch Suno share data"}

    handle = data.get('sharer_handle')

    return {
        "data": {
            "profile_url": f"https://suno.com/@{handle}/" if handle else None,
            "username": handle,
            "name": data.get('sharer_display_name'),
            "avatar_url": data.get('sharer_avatar_url')
        }
    }