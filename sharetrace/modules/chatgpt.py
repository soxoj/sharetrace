from curl_cffi import requests
import re


def chatgpt(url):
    if not re.search(r'chatgpt\.com/share/[a-f0-9-]+', url):
        return {"error": "Invalid URL format for ChatGPT share link"}

    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'accept-language': 'en-US,en;q=0.9',
        'cache-control': 'no-cache',
        'pragma': 'no-cache',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        match = re.search(r'<meta property="og:description" content="Shared by (.+?) via ChatGPT"', response.text)
        if not match:
            return {"error": "Could not find sharer name in response"}

        return {
            "data": {
                "name": match.group(1)
            }
        }

    except requests.RequestException as e:
        return {"error": f"Request failed: {str(e)}"}