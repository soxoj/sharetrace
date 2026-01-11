from curl_cffi import requests
import json
import time
import re


def pinterest(url):
    match = re.search(r'pin\.it/([A-Za-z0-9]+)', url)
    if not match:
        return {"error": "Invalid URL format for Pinterest share link"}

    short_code = match.group(1)

    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'accept-language': 'en-US,en;q=0.9',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
    }

    try:
        response = requests.get(
            f'https://api.pinterest.com/url_shortener/{short_code}/redirect/',
            headers=headers,
            allow_redirects=False
        )

        location = response.headers.get('Location', '')

        invite_match = re.search(r'invite_code=([a-f0-9]+)', location)
        if not invite_match:
            return {"error": "No invite code found in Pinterest link"}

        invite_code = invite_match.group(1)
        pin_id_match = re.search(r'/pin/(\d+)/', location)
        pin_id = pin_id_match.group(1) if pin_id_match else "0"

        api_headers = {
            'accept': 'application/json, text/javascript, */*, q=0.01',
            'accept-language': 'en-US,en;q=0.9',
            'referer': 'https://www.pinterest.com/',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
            'x-requested-with': 'XMLHttpRequest',
            'x-pinterest-appstate': 'active',
            'x-pinterest-pws-handler': 'www/pin/[id]/sent.js',
            'x-pinterest-source-url': f'/pin/{pin_id}/sent/?invite_code={invite_code}',
        }

        params = {
            'source_url': f'/pin/{pin_id}/sent/?invite_code={invite_code}',
            'data': json.dumps({"options": {"invite_code": invite_code, "field_set_key": "default"}, "context": {}}),
            '_': str(int(time.time() * 1000)),
        }

        response = requests.get(
            'https://www.pinterest.com/resource/InviteCodeMetadataResource/get/',
            params=params,
            headers=api_headers
        )

        data = response.json()
        sender = data.get('resource_response', {}).get('data', {}).get('sender', {})

        if not sender:
            return {"error": "No sender data found"}

        username = sender.get('username')

        return {
            "data": {
                "profile_url": f"https://www.pinterest.com/{username}/" if username else None,
                "username": username,
                "user_id": sender.get('id'),
                "name": sender.get('full_name'),
                "avatar_url": sender.get('image_large_url')
            }
        }

    except Exception as e:
        return {"error": f"Request failed: {str(e)}"}