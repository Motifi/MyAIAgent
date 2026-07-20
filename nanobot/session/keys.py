"""Shared session key constants and helpers."""

from __future__ import annotations

UNIFIED_SESSION_KEY = "unified:default"


def session_key_for_channel(
    channel: str,
    chat_id: str,
    *,
    unified_session: bool = False,
    user_id: str | None = None,
) -> str:
    """Return the session key for a channel/chat pair.

    When *user_id* is provided, the key is scoped to that user:
    ``user_id:channel:chat_id``.  This enables multi-user isolation while
    keeping backward compatibility with legacy ``channel:chat_id`` keys.
    """
    if unified_session:
        if user_id:
            return f"{user_id}:unified:default"
        return UNIFIED_SESSION_KEY
    if user_id:
        return f"{user_id}:{channel}:{chat_id}"
    return f"{channel}:{chat_id}"
