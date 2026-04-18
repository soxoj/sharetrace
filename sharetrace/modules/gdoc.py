"""Google Docs / Drive owner-identity extractor.

Reads the public Drive v2beta metadata endpoint used by the Drive web client.
Works for any resource that exposes a /d/{id}/ segment: Docs, Sheets, Slides,
Drawings, Forms, Drive files, Apps Script, Jamboard, and My Maps (mid= param).

The API key below is the public key embedded in the Drive web client. Override
via the SHARETRACE_GDOC_API_KEY environment variable if it ever gets revoked.
"""
from __future__ import annotations

import os
import random
import re
import time
from datetime import datetime
from typing import Optional

from curl_cffi import requests

API_ENDPOINT = "https://clients6.google.com/drive/v2beta/files/{file_id}"
DEFAULT_API_KEY = "AIzaSyC1eQ1xj69IdTMeii5r7brs3R90eck-m7k"

FIELDS = (
    "alternateLink,createdDate,modifiedDate,kind,"
    "permissions(id,name,emailAddress,domain,role,additionalRoles,photoLink,type,withLink),"
    "userPermission(id,role,additionalRoles,type)"
)

MAX_RETRIES = 5
BASE_BACKOFF = 0.5

RATE_LIMIT_SIGNALS = (
    "rateLimitExceeded",
    "userRateLimitExceeded",
    "dailyLimitExceeded",
    "quotaExceeded",
)

URL_MATCH = re.compile(
    r'(docs\.google\.com/(document|spreadsheets|presentation|drawings|forms)/d/'
    r'|drive\.google\.com/file/d/'
    r'|script\.google\.com/d/'
    r'|jamboard\.google\.com/d/'
    r'|google\.com/maps/d/)'
)

# Prefer explicit /d/{id} segment; fall back to ?mid= for My Maps.
DOC_ID_PATTERNS = [
    re.compile(r'/d/([A-Za-z0-9_-]{25,})'),
    re.compile(r'[?&]mid=([A-Za-z0-9_-]{25,})'),
]


def _extract_doc_id(url: str) -> Optional[str]:
    for pat in DOC_ID_PATTERNS:
        m = pat.search(url)
        if m:
            return m.group(1)
    return None


def _parse_gdrive_datetime(value: str) -> Optional[str]:
    if not value:
        return None
    normalized = value[:-1] + "Z" if value.endswith("z") else value
    try:
        dt = datetime.strptime(normalized, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError:
        try:
            dt = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
        except ValueError:
            return None
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


def _fetch(doc_id: str, api_key: str) -> dict:
    url = API_ENDPOINT.format(file_id=doc_id)
    params = {"fields": FIELDS, "supportsTeamDrives": "true", "key": api_key}
    headers = {"X-Origin": "https://drive.google.com"}

    for attempt in range(MAX_RETRIES):
        response = requests.get(url, params=params, headers=headers, timeout=10)
        text = response.text
        status = response.status_code

        is_rate_limited = (
            status == 429
            or any(sig in text for sig in RATE_LIMIT_SIGNALS)
        )
        if is_rate_limited:
            time.sleep(BASE_BACKOFF * (2 ** attempt) + random.uniform(0, 0.25))
            continue

        if status == 404 or "File not found" in text:
            return {"__error__": "not_found"}
        if status in (401, 403):
            return {"__error__": "unauthorized"}
        if 500 <= status < 600:
            time.sleep(BASE_BACKOFF * (2 ** attempt) + random.uniform(0, 0.25))
            continue

        try:
            return response.json()
        except Exception:
            return {"__error__": "bad_json"}

    return {"__error__": "rate_limited"}


def _build_result(doc_id: str, data: dict) -> dict:
    result = {
        "doc_id": doc_id,
        "created_at": _parse_gdrive_datetime(data.get("createdDate", "")),
        "modified_at": _parse_gdrive_datetime(data.get("modifiedDate", "")),
    }

    public_roles = []
    owner = None
    for permission in data.get("permissions") or []:
        if permission.get("id") in ("anyoneWithLink", "anyone"):
            if permission.get("role"):
                public_roles.append(permission["role"])
            public_roles.extend(permission.get("additionalRoles") or [])
        elif permission.get("role") == "owner":
            owner = permission

    if public_roles:
        result["public_permissions"] = ", ".join(sorted(set(public_roles)))

    if owner:
        if owner.get("name"):
            result["name"] = owner["name"]
        if owner.get("emailAddress"):
            result["email"] = owner["emailAddress"]
        if owner.get("id"):
            result["google_id"] = owner["id"]
        if owner.get("photoLink"):
            result["avatar_url"] = owner["photoLink"]

    identity_keys = {"name", "email", "google_id"}
    if not identity_keys.intersection(result):
        return {"error": "Document is public but owner identity is not exposed"}

    return {"data": result}


def gdoc(url: str) -> dict:
    if not URL_MATCH.search(url):
        return {"error": "Invalid URL format for Google Docs link"}

    doc_id = _extract_doc_id(url)
    if not doc_id:
        return {"error": "Could not extract document ID from URL"}

    api_key = os.environ.get("SHARETRACE_GDOC_API_KEY", DEFAULT_API_KEY)

    try:
        data = _fetch(doc_id, api_key)
    except Exception as e:
        return {"error": f"Request failed: {e}"}

    err = data.get("__error__") if isinstance(data, dict) else None
    if err:
        mapping = {
            "not_found": "Document not found or is not public",
            "unauthorized": "Google API key rejected (may have been revoked)",
            "rate_limited": "Rate-limit exceeded after retries",
            "bad_json": "Unexpected response from Google Drive API",
        }
        return {"error": mapping.get(err, "Unknown error")}

    return _build_result(doc_id, data)
