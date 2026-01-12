from cloudscraper import CloudScraper
import re


def claude(url):
    match = re.search(r'claude\.ai/share/([a-f0-9-]+)', url)
    if not match:
        return {"error": "Invalid URL format for Claude share link"}
    
    share_id = match.group(1)
    api_url = f"https://claude.ai/api/chat_snapshots/{share_id}"

    headers = {
        'pragma': 'no-cache',
        'priority': 'u=0, i',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
    }

    try:
        scraper = CloudScraper()
        response = scraper.get(api_url, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        if "creator" not in data or "full_name" not in data["creator"]:
            return {"error": "Could not find creator information in response"}

        return {
            "data": {
                "name": data["creator"]["full_name"],
                "user_id": data["creator"]["uuid"]
            }
        }

    except Exception as e:
        return {"error": f"Request failed: {str(e)}"}
