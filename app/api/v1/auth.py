"""Auth endpoints for API v1."""

from __future__ import annotations

from sqlalchemy import func

from app.api._compat import APIRouter, HTTPException, status
from app.auth.jwt import create_token_pair, decode_jwt
from app.core.config import get_config
from app.core.security import verify_password
from app.database.db import get_db_session
from app.database.models import User
from app.core.exceptions import AuthenticationError
from app.schemas.auth import LoginRequest, RefreshRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest) -> TokenResponse:
    email = payload.email.strip().lower()
    password = payload.password.strip()
    if not email or not password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")

    cfg = get_config()
    with get_db_session() as session:
        user = session.query(User).filter(func.lower(User.email) == email).first()
        if not user or not user.is_active or not verify_password(password=password, hashed_password=user.hashed_password, pepper=cfg.PASSWORD_PEPPER):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")
    tokens = create_token_pair(
        user_id=int(user.id),
        tenant_id=int(user.tenant_id),
        role=str(user.role),
        secret=cfg.JWT_SECRET,
        permissions_version=cfg.JWT_PERMISSIONS_VERSION,
        access_ttl_minutes=cfg.JWT_ACCESS_TTL_MINUTES,
        refresh_ttl_days=cfg.JWT_REFRESH_TTL_DAYS,
    )
    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type=tokens.token_type,
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest) -> TokenResponse:
    cfg = get_config()
    try:
        claims = decode_jwt(payload.refresh_token, secret=cfg.JWT_SECRET)
    except AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    if claims.get("token_use") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token is not a refresh token.")

    tokens = create_token_pair(
        user_id=int(claims["sub"]),
        tenant_id=int(claims["tenant_id"]),
        role=str(claims["role"]),
        secret=cfg.JWT_SECRET,
        permissions_version=int(claims.get("permissions_version", cfg.JWT_PERMISSIONS_VERSION)),
        access_ttl_minutes=cfg.JWT_ACCESS_TTL_MINUTES,
        refresh_ttl_days=cfg.JWT_REFRESH_TTL_DAYS,
    )
    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type=tokens.token_type,
    )
