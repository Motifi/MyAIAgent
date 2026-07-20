"""Cross-channel identity resolution.

Maps external platform identities (Telegram user ID, Discord user ID, etc.)
to nanobot user IDs so the same person can talk through multiple channels
and have all their conversations tied together.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nanobot.users.store import UserStore


class IdentityResolver:
    """Resolve platform identities to nanobot user IDs."""

    def __init__(self, user_store: UserStore) -> None:
        self._store = user_store

    async def resolve(self, channel: str, external_id: str) -> str | None:
        """Look up the nanobot user ID for a platform identity.

        Returns the user ID string, or *None* if no link exists.
        """
        user = await self._store.get_user_by_identity(channel, external_id)
        if user is None:
            return None
        return user["id"]

    async def auto_link(
        self, user_id: str, channel: str, external_id: str
    ) -> bool:
        """Bind an external identity to a nanobot user.

        Returns ``True`` on success, ``False`` if the link already exists
        for a different user (identity conflict).
        """
        return await self._store.link_identity(user_id, channel, external_id)

    async def unlink(self, channel: str, external_id: str) -> bool:
        """Remove an identity link."""
        return await self._store.unlink_identity(channel, external_id)

    async def get_identities(self, user_id: str) -> list[dict]:
        """Return all linked identities for a user."""
        return await self._store.get_identities(user_id)
