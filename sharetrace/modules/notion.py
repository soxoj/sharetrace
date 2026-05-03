from curl_cffi import requests
import re


API_BASE = "https://www.notion.so/api/v3"

UUID_RE = re.compile(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}')
HEX32_RE = re.compile(r'([a-f0-9]{32})')


def _dashed(h):
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:]}"


def _extract_page_id(url):
    """Extract a Notion page UUID from a URL path, if present."""
    path = url.split("?")[0].split("#")[0].rstrip("/")
    last = path.split("/")[-1]
    m = HEX32_RE.search(last.replace("-", ""))
    if m:
        return _dashed(m.group(1))
    return None


def _resolve_page_id_from_site(url):
    """For a notion.site URL without an embedded UUID, fetch HTML and read pageId."""
    try:
        r = requests.get(url, impersonate="chrome")
        m = re.search(r'"pageId"\s*:\s*"([a-f0-9-]{36})"', r.text)
        if m:
            return m.group(1)
    except Exception:
        pass
    return None


def _post(endpoint, payload, retries=4):
    """POST to Notion API with retries — the public endpoints return sporadic 502s."""
    last = None
    for _ in range(retries):
        r = requests.post(f"{API_BASE}/{endpoint}", json=payload, impersonate="chrome")
        last = r
        try:
            data = r.json()
        except Exception:
            continue
        if not data.get("errorId"):
            return r
    return last


def _get_public_page_data(page_id):
    return _post("getPublicPageData", {"blockId": page_id}).json()


def _load_page_chunk(page_id):
    return _post("loadPageChunk", {
        "pageId": page_id,
        "limit": 100,
        "cursor": {"stack": []},
        "chunkNumber": 0,
        "verticalColumns": False,
    }).text


def _extract_user_uuids(chunk_text):
    """Collect all editor/creator UUIDs leaked in block permissions and metadata."""
    uuids = set()
    for key in ("created_by_id", "last_edited_by_id", "block_locked_by", "user_id"):
        uuids.update(re.findall(rf'"{key}"\s*:\s*"([a-f0-9-]{{36}})"', chunk_text))
    return uuids


def _sync_record_values(user_ids):
    """Batch-resolve notion_user UUIDs via syncRecordValuesMain. One POST, no auth."""
    if not user_ids:
        return {}
    payload = {
        "requests": [
            {"pointer": {"table": "notion_user", "id": uid, "spaceId": ""},
             "version": -1}
            for uid in user_ids
        ]
    }
    r = _post("syncRecordValuesMain", payload)
    users = {}
    for uid, rec in r.json().get("recordMap", {}).get("notion_user", {}).items():
        val = (rec or {}).get("value", {}).get("value")
        if val:
            users[uid] = val
    return users


def _format_user(u):
    name = u.get("name") or " ".join(
        filter(None, [u.get("given_name"), u.get("family_name")])
    ).strip() or None
    return {
        "user_id": u.get("id"),
        "name": name,
        "email": u.get("email"),
        "avatar_url": u.get("profile_photo"),
    }


def notion(url):
    page_id = _extract_page_id(url)
    if not page_id and "notion.site" in url:
        page_id = _resolve_page_id_from_site(url)
    if not page_id:
        return {"error": "Could not extract page ID from URL"}

    try:
        page_data = _get_public_page_data(page_id)
        if page_data.get("errorId") or not page_data.get("spaceId"):
            return {"error": "Page is not public or does not exist"}

        space = {
            "space_name": page_data.get("spaceName"),
            "space_domain": page_data.get("spaceDomain"),
            "space_id": page_data.get("spaceId"),
        }

        chunk_text = _load_page_chunk(page_id)
        uuids = _extract_user_uuids(chunk_text)

        if not uuids:
            return {"data": {k: v for k, v in space.items() if v}}

        users_map = _sync_record_values(uuids)
        users = [_format_user(u) for u in users_map.values()]
        users = [u for u in users if u.get("email") or u.get("name")]

        if not users:
            return {"data": {k: v for k, v in space.items() if v}}

        primary = users[0]
        data = {
            "name": primary.get("name"),
            "email": primary.get("email"),
            "user_id": primary.get("user_id"),
            "avatar_url": primary.get("avatar_url"),
            "space_name": space["space_name"],
            "space_domain": space["space_domain"],
        }
        if len(users) > 1:
            data["other_editors"] = [
                {"name": u["name"], "email": u["email"]} for u in users[1:]
            ]
        return {"data": data}

    except Exception as e:
        return {"error": f"Request failed: {str(e)}"}
