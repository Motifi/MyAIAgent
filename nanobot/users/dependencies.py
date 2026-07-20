"""Auth middleware / dependency injection for HTTP and WebSocket handlers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from nanobot.users.auth import decode_jwt
from nanobot.webui.http_utils import bearer_token as _bearer_token

if TYPE_CHECKING:
    from nanobot.users.store import UserStore


_BEARER_RE = re.compile(r"^Bearer\s+(.+)$", re.IGNORECASE)

# Sentinel to distinguish "not checked yet" from None (unknown/invalid user).
_UNCHECKED = object()


@dataclass
class AuthDependency:
    """Holds the shared UserStore and JWT secret for route handlers."""

    user_store: UserStore
    jwt_secret: str

    # -- JWT helpers -------------------------------------------------------

    def decode_bearer_jwt(self, request: Any) -> dict[str, Any] | None:
        """Extract and decode a JWT from the ``Authorization: Bearer`` header."""
        token = _bearer_token(request)
        if token is None:
            return None
        return decode_jwt(token, self.jwt_secret)

    def check_jwt_token(self, request: Any) -> bool:
        """Validate JWT signature and expiry without a DB round-trip.

        Returns ``True`` if the request carries a valid, non-expired JWT.
        This is suitable for sync route handlers that just need to gate
        access (no per-user data filtering).
        """
        payload = self.decode_bearer_jwt(request)
        return payload is not None and payload.get("sub") is not None

    # -- Async auth checks -------------------------------------------------

    async def require_auth(self, request: Any) -> dict[str, Any] | None:
        """Validate JWT and return the corresponding user dict, or *None*.

        The returned dict has keys: ``id``, ``username``, ``role``, ``status``, …
        """
        payload = self.decode_bearer_jwt(request)
        if payload is None:
            return None
        user_id = payload.get("sub")
        if not user_id:
            return None
        user = await self.user_store.get_user(user_id)
        if user is None or user.get("status") != "active":
            return None
        return user

    async def require_admin(self, request: Any) -> dict[str, Any] | None:
        """Like ``require_auth`` but additionally requires admin / super_admin role."""
        user = await self.require_auth(request)
        if user is None:
            return None
        if user.get("role") not in ("admin", "super_admin"):
            return None
        return user

    async def require_super_admin(self, request: Any) -> dict[str, Any] | None:
        """Like ``require_auth`` but additionally requires the super_admin role."""
        user = await self.require_auth(request)
        if user is None:
            return None
        if user.get("role") != "super_admin":
            return None
        return user
