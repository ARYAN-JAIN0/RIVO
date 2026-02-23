"""Security primitives for token and password workflows."""

from __future__ import annotations

import hashlib
import hmac

import bcrypt


def _with_pepper(password: str, pepper: str) -> bytes:
    return f"{pepper}:{password}".encode("utf-8")


def _legacy_hash(password: str, pepper: str = "") -> str:
    value = _with_pepper(password=password, pepper=pepper)
    return hashlib.sha256(value).hexdigest()


def hash_password(password: str, pepper: str = "") -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(_with_pepper(password=password, pepper=pepper), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed_password: str, pepper: str = "") -> bool:
    """Verify bcrypt hashes with legacy SHA-256 compatibility fallback."""
    if not hashed_password:
        return False

    encoded_password = _with_pepper(password=password, pepper=pepper)
    if hashed_password.startswith("$2"):
        try:
            return bcrypt.checkpw(encoded_password, hashed_password.encode("utf-8"))
        except ValueError:
            return False

    # Backward-compatible fallback for pre-bcrypt records.
    return hmac.compare_digest(_legacy_hash(password=password, pepper=pepper), hashed_password)
