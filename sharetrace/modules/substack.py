from curl_cffi import requests
import json
import re


def substack(url):
    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-language': 'en-US,en;q=0.9',
        'cache-control': 'no-cache',
        'pragma': 'no-cache',
        'priority': 'u=0, i',
        'sec-ch-ua': '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'none',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        match = re.search(r'window\._preloads\s*=\s*JSON\.parse\("(.+?)"\)', response.text)
        if not match:
            return {"error": "Could not find preload data in response"}

        json_str = match.group(1)
        json_str = json_str.encode('utf-8').decode('unicode_escape')

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            return {"error": "Failed to parse preload data"}

        referring_user = data.get('referringUser')
        if not referring_user:
            return {"error": "No referring user found in the link"}

        return {
            "data": {
                "user_id": referring_user.get("id"),
                "name": referring_user.get("name"),
                "handle": referring_user.get("handle"),
                "previous_name": referring_user.get("previous_name"),
                "photo_url": referring_user.get("photo_url"),
                "bio": referring_user.get("bio"),
                "profile_set_up_at": referring_user.get("profile_set_up_at"),
                "reader_installed_at": referring_user.get("reader_installed_at"),
                "profile_url": f"https://substack.com/@{referring_user.get('handle')}" if referring_user.get('handle') else None
            }
        }

    except requests.RequestException as e:
        return {"error": f"Request failed: {str(e)}"}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}