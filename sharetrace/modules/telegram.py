import base64
import struct
import re


def telegram(url):
    match = re.search(r't\.me/joinchat/([A-Za-z0-9_-]+)', url)
    if not match:
        return {"error": "Invalid URL format for Telegram invite link decoder"}

    hash_str = match.group(1)

    padding = 4 - (len(hash_str) % 4)
    if padding != 4:
        hash_str += '=' * padding

    try:
        decoded = base64.urlsafe_b64decode(hash_str)
    except Exception:
        return {"error": "Invalid URL format for Telegram invite link decoder"}

    if len(decoded) < 16:
        return {"error": "Invalid URL format for Telegram invite link decoder"}

    creator_id = struct.unpack('<I', decoded[:4])[0]

    return {
        "data": {
            "user_id": creator_id
        }
    }