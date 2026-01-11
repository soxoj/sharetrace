import re


def microsoft(url):
    match = re.search(r'sharepoint\.com/:[a-z]:/g/personal/([^/]+)/', url)
    if not match:
        return {"error": "Invalid URL format for Microsoft SharePoint link"}

    encoded = match.group(1)
    parts = encoded.split('_')

    if len(parts) < 3:
        return {"error": "Invalid URL format for Microsoft SharePoint link"}

    tld = parts[-1]

    domain_idx = len(parts) - 2
    while domain_idx > 0 and '-' in parts[domain_idx]:
        domain_idx -= 1

    if domain_idx < 1:
        return {"error": "Invalid URL format for Microsoft SharePoint link"}

    domain = parts[domain_idx]
    username_parts = parts[:domain_idx]
    username = '.'.join(username_parts)

    email = f"{username}@{domain}.{tld}"

    return {
        "data": {
            "email": email
        }
    }