from __future__ import annotations

import pytest

from app.auth.jwt import create_token_pair, decode_jwt
from app.auth.rbac import require_scopes
from app.core.exceptions import AuthorizationError


def test_jwt_roundtrip_contains_required_claims():
    tokens = create_token_pair(user_id=10, tenant_id=20, role="admin", secret="test-secret")
    claims = decode_jwt(tokens.access_token, secret="test-secret")
    assert claims["sub"] == "10"
    assert claims["tenant_id"] == 20
    assert claims["role"] == "admin"
    assert "exp" in claims
    assert "iat" in claims
    assert "jti" in claims


def test_rbac_blocks_missing_scope():
    require_scopes("viewer", ["runs.read"])
    with pytest.raises(AuthorizationError):
        require_scopes("viewer", ["runs.retry"])
