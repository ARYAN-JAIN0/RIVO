"""Tenant context extraction and enforcement utilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.exceptions import AuthenticationError, AuthorizationError


@dataclass(frozen=True)
class TenantContext:
    tenant_id: int
    user_id: int
    role: str
    permissions_version: int = 1


def from_claims(
    claims: dict[str, Any],
    header_tenant_id: int | None = None,
    allow_admin_header_override: bool = False,
) -> TenantContext:
    """Build tenant context from JWT claims and optional support override."""
    try:
        claim_tenant_id = int(claims["tenant_id"])
        user_id = int(claims["sub"])
        role = str(claims["role"]).lower()
    except (KeyError, TypeError, ValueError) as exc:
        raise AuthenticationError("Token claims are missing tenant/user context.") from exc

    resolved_tenant = claim_tenant_id
    if header_tenant_id is not None:
        if not allow_admin_header_override or role != "admin":
            raise AuthorizationError("Tenant override is admin-only.")
        resolved_tenant = int(header_tenant_id)

    return TenantContext(
        tenant_id=resolved_tenant,
        user_id=user_id,
        role=role,
        permissions_version=int(claims.get("permissions_version", 1)),
    )


def enforce_tenant_match(entity_tenant_id: int, context: TenantContext) -> None:
    """Ensure entity access stays inside context tenant."""
    if int(entity_tenant_id) != int(context.tenant_id):
        raise AuthorizationError("Cross-tenant access denied.")
