from curl_cffi import requests
import urllib.parse
import json
import re


def instagram(url):
    if not re.search(r'instagram\.com/(reel|p)/[A-Za-z0-9_-]+', url):
        return {"error": "Invalid URL format for Instagram share link"}

    headers = {
        "host": "www.instagram.com",
        "connection": "keep-alive",
        "dpr": "2",
        "viewport-width": "980",
        "sec-ch-ua-mobile": "?1",
        "sec-ch-ua-platform": "\"Android\"",
        "sec-ch-ua-platform-version": "\"12.0.0\"",
        "sec-ch-prefers-color-scheme": "light",
        "upgrade-insecure-requests": "1",
        "user-agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Mobile Safari/537.36",
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "sec-fetch-site": "none",
        "sec-fetch-mode": "navigate",
        "sec-fetch-dest": "document",
        "accept-encoding": "gzip, deflate, br, zstd",
        "accept-language": "en-US,en;q=0.9",
    }

    try:
        response = requests.get(url, impersonate="chrome", headers=headers)

        def extract_json_object(text, key):
            pattern = rf'"{key}"\s*:\s*(\{{[^{{}}]*\}})'
            match = re.search(pattern, text)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    return None
            return None

        user_data = extract_json_object(response.text, "user_for_shid_logged_out")
        if not user_data:
            return {"error": "Could not find share user data in response"}

        username = user_data.get("username")
        profile_pic_url = user_data.get("profile_pic_url")

        if profile_pic_url:
            profile_pic_url = urllib.parse.unquote(profile_pic_url)

        return {
            "data": {
                "username": username,
                "user_id": user_data.get("id"),
                "name": user_data.get("full_name"),
                "profile_url": f"https://www.instagram.com/{username}/" if username else None,
                "avatar_url": profile_pic_url
            }
        }

    except Exception as e:
        return {"error": f"Request failed: {str(e)}"}