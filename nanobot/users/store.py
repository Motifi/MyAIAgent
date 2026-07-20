"""SQLite-backed user store with identity linking.

All public methods are async — the underlying sqlite3 calls run via
``asyncio.to_thread`` so the gateway event loop is never blocked.
"""

from __future__ import annotations

import asyncio
import os
import secrets
import sqlite3
import string
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger

import re as _re

_USERNAME_RE = _re.compile(r"^[a-zA-Z][a-zA-Z0-9_]{1,31}$")


def _validate_username(username: str) -> str:
    """Validate and normalise a username. Raises ValueError on invalid input."""
    username = username.strip()
    if not _USERNAME_RE.match(username):
        raise ValueError(
            "Username must be 2-32 characters, start with a letter, "
            "and contain only letters, digits, and underscores."
        )
    return username


def _user_id_from_username(username: str) -> str:
    """Derive the internal user ID from the validated username."""
    return username

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id              TEXT PRIMARY KEY,
    username        TEXT UNIQUE NOT NULL,
    display_name    TEXT NOT NULL DEFAULT '',
    password_hash   TEXT NOT NULL,
    role            TEXT NOT NULL DEFAULT 'user',
    status          TEXT NOT NULL DEFAULT 'pending',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS identity_links (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    channel     TEXT NOT NULL,
    external_id TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    UNIQUE(channel, external_id)
);
CREATE INDEX IF NOT EXISTS idx_identity_user ON identity_links(user_id);
CREATE INDEX IF NOT EXISTS idx_identity_lookup ON identity_links(channel, external_id);
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _expand_path(raw: str | None) -> Path:
    if raw is None:
        raw = "~/.nanobot/users.db"
    return Path(raw).expanduser().resolve()


class UserStore:
    """Async wrapper around a local SQLite user database."""

    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = _expand_path(db_path)
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self, config: Any | None = None) -> None:
        """Create tables and seed the initial super-admin if the DB is empty."""
        await asyncio.to_thread(self._init_sync, config)

    def _init_sync(self, config: Any | None) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA)
            conn.commit()

        # Seed super-admin from config on first run
        row = self._raw_one("SELECT COUNT(*) AS cnt FROM users")
        if row is not None and row["cnt"] > 0:
            return

        username = "admin"
        password = None  # will be randomly generated
        if config is not None:
            username = getattr(config, "admin_username", "admin") or "admin"
            password = getattr(config, "admin_password", None) or None

        if password is None:
            import secrets
            import string

            alphabet = string.ascii_letters + string.digits
            password = "".join(secrets.choice(alphabet) for _ in range(20))

        from nanobot.users.auth import hash_password

        user_id = _user_id_from_username(username)
        now = _now_iso()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO users (id, username, display_name, password_hash, role, status, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, 'super_admin', 'active', ?, ?)",
                (user_id, username, username, hash_password(password), now, now),
            )
            conn.commit()

        logger.warning(
            "super_admin user created: username={} — "
            "set users.admin_password in config to avoid a random password on next fresh DB",
            username,
        )

    # ------------------------------------------------------------------
    # User CRUD
    # ------------------------------------------------------------------

    async def create_user(
        self,
        username: str,
        password: str,
        *,
        role: str = "user",
        status: str = "pending",
        display_name: str = "",
        require_admin_approval: bool = True,
    ) -> dict[str, Any]:
        """Create a new user.  Returns the user row as a dict."""
        from nanobot.users.auth import hash_password

        username = _validate_username(username)
        user_id = _user_id_from_username(username)
        now = _now_iso()
        actual_status = "pending" if require_admin_approval and role == "user" else status

        def _insert() -> dict[str, Any]:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO users (id, username, display_name, password_hash, role, status, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        user_id,
                        username.strip(),
                        (display_name or username).strip(),
                        hash_password(password),
                        role,
                        actual_status,
                        now,
                        now,
                    ),
                )
                conn.commit()
            return self._raw_one("SELECT * FROM users WHERE id = ?", (user_id,))

        return await asyncio.to_thread(_insert)

    async def authenticate(self, username: str, password: str) -> dict[str, Any] | None:
        """Verify credentials and return the user dict, or *None*."""
        from nanobot.users.auth import verify_password

        def _auth() -> dict[str, Any] | None:
            row = self._raw_one(
                "SELECT * FROM users WHERE username = ? AND status = 'active'",
                (username.strip(),),
            )
            if row is None:
                return None
            if not verify_password(password, row["password_hash"]):
                return None
            return dict(row)

        return await asyncio.to_thread(_auth)

    async def get_user(self, user_id: str) -> dict[str, Any] | None:
        def _get() -> dict[str, Any] | None:
            row = self._raw_one("SELECT * FROM users WHERE id = ?", (user_id,))
            return dict(row) if row else None

        return await asyncio.to_thread(_get)

    async def get_user_by_username(self, username: str) -> dict[str, Any] | None:
        def _get() -> dict[str, Any] | None:
            row = self._raw_one(
                "SELECT * FROM users WHERE username = ?", (username.strip(),)
            )
            return dict(row) if row else None

        return await asyncio.to_thread(_get)

    async def list_users(self, *, status: str | None = None) -> list[dict[str, Any]]:
        def _list() -> list[dict[str, Any]]:
            if status:
                rows = self._raw_all(
                    "SELECT * FROM users WHERE status = ? ORDER BY created_at DESC",
                    (status,),
                )
            else:
                rows = self._raw_all("SELECT * FROM users ORDER BY created_at DESC")
            return [dict(r) for r in rows]

        return await asyncio.to_thread(_list)

    async def set_status(self, user_id: str, status: str) -> bool:
        """Approve, disable, or re-enable a user.  Cannot change super_admin status."""
        def _set() -> bool:
            user = self._raw_one("SELECT role FROM users WHERE id = ?", (user_id,))
            if user is None:
                return False
            if user["role"] == "super_admin" and status != "active":
                return False
            now = _now_iso()
            with self._connect() as conn:
                conn.execute(
                    "UPDATE users SET status = ?, updated_at = ? WHERE id = ?",
                    (status, now, user_id),
                )
                conn.commit()
            return True

        return await asyncio.to_thread(_set)

    async def change_role(self, user_id: str, new_role: str) -> bool:
        """Change a user's role.  super_admin role is immutable (cannot be demoted)."""
        def _change() -> bool:
            user = self._raw_one("SELECT role FROM users WHERE id = ?", (user_id,))
            if user is None:
                return False
            if user["role"] == "super_admin":
                return False  # super_admin is immutable
            now = _now_iso()
            with self._connect() as conn:
                conn.execute(
                    "UPDATE users SET role = ?, updated_at = ? WHERE id = ?",
                    (new_role, now, user_id),
                )
                conn.commit()
            return True

        return await asyncio.to_thread(_change)

    async def change_password(self, user_id: str, new_password: str) -> bool:
        from nanobot.users.auth import hash_password

        def _change() -> bool:
            now = _now_iso()
            with self._connect() as conn:
                cur = conn.execute(
                    "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
                    (hash_password(new_password), now, user_id),
                )
                conn.commit()
                return cur.rowcount > 0

        return await asyncio.to_thread(_change)

    async def delete_user(self, user_id: str) -> bool:
        """Delete a user.  super_admin cannot be deleted."""
        def _del() -> bool:
            user = self._raw_one("SELECT role FROM users WHERE id = ?", (user_id,))
            if user is None:
                return False
            if user["role"] == "super_admin":
                return False
            with self._connect() as conn:
                conn.execute("DELETE FROM identity_links WHERE user_id = ?", (user_id,))
                conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
                conn.commit()
            return True

        return await asyncio.to_thread(_del)

    # ------------------------------------------------------------------
    # Identity linking
    # ------------------------------------------------------------------

    async def link_identity(
        self, user_id: str, channel: str, external_id: str
    ) -> bool:
        """Bind an external platform identity to a nanobot user."""
        def _link() -> bool:
            now = _now_iso()
            link_id = str(uuid.uuid4())
            try:
                with self._connect() as conn:
                    conn.execute(
                        "INSERT INTO identity_links (id, user_id, channel, external_id, created_at) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (link_id, user_id, channel, external_id, now),
                    )
                    conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False  # duplicate

        return await asyncio.to_thread(_link)

    async def unlink_identity(self, channel: str, external_id: str) -> bool:
        def _unlink() -> bool:
            with self._connect() as conn:
                cur = conn.execute(
                    "DELETE FROM identity_links WHERE channel = ? AND external_id = ?",
                    (channel, external_id),
                )
                conn.commit()
                return cur.rowcount > 0

        return await asyncio.to_thread(_unlink)

    async def get_user_by_identity(
        self, channel: str, external_id: str
    ) -> dict[str, Any] | None:
        def _get() -> dict[str, Any] | None:
            row = self._raw_one(
                "SELECT u.* FROM users u "
                "INNER JOIN identity_links il ON il.user_id = u.id "
                "WHERE il.channel = ? AND il.external_id = ? AND u.status = 'active'",
                (channel, external_id),
            )
            return dict(row) if row else None

        return await asyncio.to_thread(_get)

    async def get_identities(self, user_id: str) -> list[dict[str, Any]]:
        def _get() -> list[dict[str, Any]]:
            rows = self._raw_all(
                "SELECT * FROM identity_links WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,),
            )
            return [dict(r) for r in rows]

        return await asyncio.to_thread(_get)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _raw_one(
        self, sql: str, params: tuple = ()
    ) -> sqlite3.Row | None:
        with self._connect() as conn:
            return conn.execute(sql, params).fetchone()

    def _raw_all(
        self, sql: str, params: tuple = ()
    ) -> list[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute(sql, params).fetchall()
