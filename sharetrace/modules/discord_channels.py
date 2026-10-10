""" Decode Discord /channels/ links without making a network request."""

from __future__ import annotations

import re
from datetime import datetime, timezone

DISCORD_EPOCH_MS = 1420070400000

CHANNEL_RE = re.compile(
    r"discord\.com/channels/"
    r"(?P<guild>@me|\d+)/"
    r"(?P<channel>\d+)"
    r"(?:/(?P<message>\d+))?"
    r"/?(?:[?#].*)?$"
)


def _snowflake_created_at(snowflake: int) -> str:
    """Return the UTC creation timestamp encoded in a Discord snowflake."""
    timestamp_ms = (snowflake >> 22) + DISCORD_EPOCH_MS
    return datetime.fromtimestamp(
        timestamp_ms / 1000,
        tz=timezone.utc,
    ).isoformat()


def discord_channels(url: str) -> dict:
    """Decode IDs and timestamps from a Discord /channels/ URL."""
    match = CHANNEL_RE.search(url)

    if not match:
        return {"error": "Invalid URL format for Discord channels link"}

    guild = match.group("guild")
    channel_id = int(match.group("channel"))
    message = match.group("message")

    data = {
        "channel_id": channel_id,
        "channel_created_at": _snowflake_created_at(channel_id),
    }

    if guild == "@me":
        data["url_type"] = "DM"
    else:
        guild_id = int(guild)
        data["guild_id"] = guild_id
        data["guild_created_at"] = _snowflake_created_at(guild_id)

        if message:
            data["url_type"] = "Guild message"
        else:
            data["url_type"] = "Guild channel"

    if message:
        message_id = int(message)
        data["message_id"] = message_id
        data["message_created_at"] = _snowflake_created_at(message_id)

    return {"data": data}
