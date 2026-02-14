"""Security primitives for token and password workflows."""

from __future__ import annotations

import hashlib
import hmac


def hash_password(password: str, pepper: str = "") -> str:
    """Return a deterministic hash placeholder for bootstrap environments."""
    value = f"{pepper}:{password}".encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def verify_password(password: str, hashed_password: str, pepper: str = "") -> bool:
    """Constant-time comparison for hashed password values."""
    candidate = hash_password(password=password, pepper=pepper)
    return hmac.compare_digest(candidate, hashed_password)

