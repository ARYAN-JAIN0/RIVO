"""JWT token utilities using HS256 signing."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.exceptions import AuthenticationError


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(f"{data}{padding}".encode("ascii"))


def _sign(message: str, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).digest()
    return _b64url_encode(digest)


def _json_dumps(payload: dict[str, Any]) -> str:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


def encode_jwt(payload: dict[str, Any], secret: str, ttl: timedelta) -> str:
    """Encode a signed JWT using HS256."""
    if not secret:
        raise AuthenticationError("JWT secret must be configured.")

    now = datetime.now(timezone.utc)
    body = dict(payload)
    body.setdefault("iat", int(now.timestamp()))
    body.setdefault("exp", int((now + ttl).timestamp()))
    body.setdefault("jti", str(uuid.uuid4()))
    header = {"alg": "HS256", "typ": "JWT"}

    header_segment = _b64url_encode(_json_dumps(header).encode("utf-8"))
    payload_segment = _b64url_encode(_json_dumps(body).encode("utf-8"))
    signing_input = f"{header_segment}.{payload_segment}"
    signature = _sign(signing_input, secret=secret)
    return f"{signing_input}.{signature}"


def decode_jwt(token: str, secret: str, verify_exp: bool = True) -> dict[str, Any]:
    """Decode and validate a signed JWT token."""
    if not secret:
        raise AuthenticationError("JWT secret must be configured.")
    try:
        header_segment, payload_segment, signature_segment = token.split(".")
    except ValueError as exc:
        raise AuthenticationError("Invalid token format.") from exc

    signing_input = f"{header_segment}.{payload_segment}"
    expected_signature = _sign(signing_input, secret=secret)
    if not hmac.compare_digest(expected_signature, signature_segment):
        raise AuthenticationError("Invalid token signature.")

    try:
        payload = json.loads(_b64url_decode(payload_segment).decode("utf-8"))
    except (json.JSONDecodeError, ValueError) as exc:
        raise AuthenticationError("Invalid token payload.") from exc

    if verify_exp:
        exp = payload.get("exp")
        if exp is None:
            raise AuthenticationError("Token is missing exp claim.")
        if int(exp) < int(datetime.now(timezone.utc).timestamp()):
            raise AuthenticationError("Token has expired.")
    return payload


def create_access_token(
    user_id: int,
    tenant_id: int,
    role: str,
    secret: str,
    permissions_version: int = 1,
    ttl_minutes: int = 15,
) -> str:
    """Create short-lived access token with tenant and role claims."""
    payload = {
        "sub": str(user_id),
        "tenant_id": tenant_id,
        "role": role,
        "permissions_version": permissions_version,
        "token_use": "access",
    }
    return encode_jwt(payload=payload, secret=secret, ttl=timedelta(minutes=ttl_minutes))


def create_refresh_token(
    user_id: int,
    tenant_id: int,
    role: str,
    secret: str,
    permissions_version: int = 1,
    ttl_days: int = 14,
) -> str:
    """Create long-lived refresh token with tenant and role claims."""
    payload = {
        "sub": str(user_id),
        "tenant_id": tenant_id,
        "role": role,
        "permissions_version": permissions_version,
        "token_use": "refresh",
    }
    return encode_jwt(payload=payload, secret=secret, ttl=timedelta(days=ttl_days))


def create_token_pair(
    user_id: int,
    tenant_id: int,
    role: str,
    secret: str,
    permissions_version: int = 1,
    access_ttl_minutes: int = 15,
    refresh_ttl_days: int = 14,
) -> TokenPair:
    """Create access + refresh token pair."""
    return TokenPair(
        access_token=create_access_token(
            user_id=user_id,
            tenant_id=tenant_id,
            role=role,
            secret=secret,
            permissions_version=permissions_version,
            ttl_minutes=access_ttl_minutes,
        ),
        refresh_token=create_refresh_token(
            user_id=user_id,
            tenant_id=tenant_id,
            role=role,
            secret=secret,
            permissions_version=permissions_version,
            ttl_days=refresh_ttl_days,
        ),
    )
