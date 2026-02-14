"""Dependency providers for API handlers and background workers."""

from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.auth.jwt import decode_jwt
from app.auth.tenant_context import TenantContext, from_claims
from app.core.config import Config, get_config
from app.core.exceptions import AuthenticationError
from app.database.db import get_db
from app.orchestrator import RevoOrchestrator


@dataclass(frozen=True)
class CurrentUser:
    user_id: int
    role: str
    tenant_id: int
    permissions_version: int
    claims: dict[str, Any]


def get_settings() -> Config:
    """Return validated application configuration."""
    return get_config()


def get_db_session() -> Generator[Session, None, None]:
    """Yield SQLAlchemy session for dependency injection."""
    yield from get_db()


def get_current_user(token: str | None = None, settings: Config | None = None) -> CurrentUser:
    """Resolve current user from bearer token.

    If token is omitted, returns a bootstrap local-admin context for script mode.
    """
    cfg = settings or get_settings()
    if token is None:
        claims = {
            "sub": "1",
            "tenant_id": 1,
            "role": "admin",
            "permissions_version": cfg.JWT_PERMISSIONS_VERSION,
        }
    else:
        claims = decode_jwt(token=token, secret=cfg.JWT_SECRET)

    try:
        return CurrentUser(
            user_id=int(claims["sub"]),
            role=str(claims["role"]).lower(),
            tenant_id=int(claims["tenant_id"]),
            permissions_version=int(claims.get("permissions_version", 1)),
            claims=claims,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise AuthenticationError("Invalid auth claims.") from exc


def get_tenant_context(
    token: str | None = None,
    header_tenant_id: int | None = None,
    allow_admin_header_override: bool = False,
) -> TenantContext:
    """Resolve tenant context with optional admin-only tenant override."""
    current_user = get_current_user(token=token)
    return from_claims(
        claims=current_user.claims,
        header_tenant_id=header_tenant_id,
        allow_admin_header_override=allow_admin_header_override,
    )


def get_orchestrator() -> RevoOrchestrator:
    """Create orchestrator instance for API/request scope."""
    return RevoOrchestrator()


def get_agent_registry() -> dict[str, Any]:
    """Return a mapping of registered agent executors."""
    orchestrator = get_orchestrator()
    return dict(orchestrator.agents)
