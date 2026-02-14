"""Auth schema module."""

from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=256)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenClaims(BaseModel):
    sub: str
    tenant_id: int
    role: str
    permissions_version: int = 1
    exp: int
    iat: int
    jti: str
    token_use: str
