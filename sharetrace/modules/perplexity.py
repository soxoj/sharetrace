from curl_cffi import requests
import re


def perplexity(url):
    match = re.search(r'perplexity\.ai/search/([A-Za-z0-9._-]+)', url)
    if not match:
        return {"error": "Invalid URL format for Perplexity share link"}

    thread_slug = match.group(1)

    headers = {
        'accept': 'application/json',
        'accept-language': 'en-US,en;q=0.9',
        'cache-control': 'no-cache',
        'pragma': 'no-cache',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
    }

    try:
        response = requests.get(
            f'https://www.perplexity.ai/rest/thread/{thread_slug}',
            impersonate="chrome",
            headers=headers
        )
        data = response.json()

        if data.get('status') != 'success':
            return {"error": "Failed to fetch Perplexity thread data"}

        entries = data.get('entries', [])
        if not entries:
            return {"error": "No entries found in response"}

        entry = entries[0]

        username = entry.get('author_username')

        return {
            "data": {
                "username": username,
                "avatar_url": entry.get('author_image'),
                "user_id": entry.get('author_id')
            }
        }

    except Exception as e:
        return {"error": f"Request failed: {str(e)}"}