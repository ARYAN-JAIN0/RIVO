"""Shared authorization helpers for API v1 route modules."""

from __future__ import annotations

from app.auth.rbac import require_scopes
from app.core.config import get_config
from app.core.dependencies import CurrentUser, get_current_user
from app.core.exceptions import AuthenticationError, AuthorizationError


def _extract_bearer_token(authorization: str | None) -> str:
    if authorization is None or not authorization.strip():
        raise AuthenticationError("Authorization header is required.")
    parts = authorization.strip().split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise AuthenticationError("Authorization header must use Bearer token.")
    return parts[1].strip()


def authorize(authorization: str | None, scopes: list[str]) -> CurrentUser:
    token = _extract_bearer_token(authorization)
    user = get_current_user(token=token, settings=get_config())
    require_scopes(user.role, scopes)
    return user


def map_auth_error(exc: Exception) -> tuple[int, str]:
    if isinstance(exc, AuthenticationError):
        return 401, str(exc)
    if isinstance(exc, AuthorizationError):
        return 403, str(exc)
    return 401, "Unauthorized."
