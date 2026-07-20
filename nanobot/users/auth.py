"""JWT token creation / validation and bcrypt password helpers."""

from __future__ import annotations

import secrets
from typing import Any

import bcrypt
import jwt


def hash_password(password: str) -> str:
    """Return a bcrypt hash of *password*."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Check *password* against a bcrypt hash."""
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_jwt(
    user_id: str,
    role: str,
    secret: str,
    ttl_s: int = 3600,
) -> str:
    """Encode a signed JWT with ``sub``, ``role``, and ``exp`` claims."""
    import datetime as _dt
    import time as _time

    now = int(_time.time())
    payload: dict[str, Any] = {
        "sub": user_id,
        "role": role,
        "iat": now,
        "exp": now + ttl_s,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_jwt(token: str, secret: str) -> dict[str, Any] | None:
    """Decode and validate a JWT.  Returns the payload dict or *None*."""
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
    return payload


def generate_jwt_secret() -> str:
    """Generate a random 64-character secret suitable for JWT signing."""
    return secrets.token_urlsafe(48)
