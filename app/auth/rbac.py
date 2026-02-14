"""Role-based authorization helpers."""

from __future__ import annotations

from app.core.exceptions import AuthorizationError

# Scope strings are kept explicit for endpoint-level declarations.
ROLE_SCOPES: dict[str, set[str]] = {
    "admin": {
        "*",
    },
    "sales": {
        "agents.sales.run",
        "agents.negotiation.run",
        "runs.read",
        "runs.retry",
        "reviews.decision",
        "metrics.read",
        "logs.read",
    },
    "sdr": {
        "agents.sdr.run",
        "runs.read",
        "reviews.decision",
        "metrics.read",
        "logs.read",
    },
    "finance": {
        "agents.finance.run",
        "runs.read",
        "reviews.decision",
        "metrics.read",
        "logs.read",
    },
    "viewer": {
        "runs.read",
        "metrics.read",
        "logs.read",
    },
}


def get_scopes_for_role(role: str) -> set[str]:
    """Return scopes granted to a role."""
    return ROLE_SCOPES.get(role.lower(), set())


def has_scopes(role: str, required_scopes: list[str] | set[str] | tuple[str, ...]) -> bool:
    """Check if role includes every required scope."""
    granted = get_scopes_for_role(role)
    if "*" in granted:
        return True
    return set(required_scopes).issubset(granted)


def require_scopes(role: str, required_scopes: list[str] | set[str] | tuple[str, ...]) -> None:
    """Raise when a role lacks required scopes."""
    if has_scopes(role=role, required_scopes=required_scopes):
        return
    missing = sorted(set(required_scopes) - get_scopes_for_role(role))
    raise AuthorizationError(f"Missing required scopes: {', '.join(missing)}")
