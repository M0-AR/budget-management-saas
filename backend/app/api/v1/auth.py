"""Authentication endpoints: register, login, refresh, logout, me.

Browsers receive the refresh token as an HttpOnly, SameSite=Lax cookie
(``bms_refresh``, path-scoped to ``/api/v1/auth``) so JavaScript — and
therefore XSS — can never read or exfiltrate it. API clients keep using the
token in the JSON body; the body takes precedence when both are present.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import AuthenticationError
from app.models import User
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    MeOut,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
)
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "bms_refresh"
_REFRESH_COOKIE_PATH = "/api/v1/auth"


def _set_refresh_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=token,
        max_age=settings.refresh_token_days * 24 * 3600,
        path=_REFRESH_COOKIE_PATH,
        secure=settings.is_production,
        httponly=True,
        samesite="lax",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=REFRESH_COOKIE, path=_REFRESH_COOKIE_PATH)


def _presented_token(request: Request, payload: RefreshRequest | None) -> str | None:
    if payload is not None and payload.refresh_token:
        return payload.refresh_token
    return request.cookies.get(REFRESH_COOKIE)


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    response: Response,
    session: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """Self-serve tenant provisioning (workspace + owner + starter categories)."""
    result = await auth_service.register_tenant(session, payload)
    _set_refresh_cookie(response, result.tokens.refresh_token)
    return result


@router.post("/login", response_model=AuthResponse)
async def login(
    payload: LoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_db),
) -> AuthResponse:
    result = await auth_service.login(session, payload)
    _set_refresh_cookie(response, result.tokens.refresh_token)
    return result


@router.post("/refresh", response_model=TokenPair)
async def refresh(
    request: Request,
    response: Response,
    payload: RefreshRequest | None = None,
    session: AsyncSession = Depends(get_db),
) -> TokenPair:
    token = _presented_token(request, payload)
    if not token:
        raise AuthenticationError("Session expired. Please sign in again.")
    pair = await auth_service.refresh(session, token)
    _set_refresh_cookie(response, pair.refresh_token)
    return pair


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    payload: RefreshRequest | None = None,
    session: AsyncSession = Depends(get_db),
) -> None:
    """Revoke the session's refresh-token family and clear the cookie."""
    await auth_service.logout(session, _presented_token(request, payload))
    _clear_refresh_cookie(response)


@router.get("/me", response_model=MeOut)
async def me(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)
) -> MeOut:
    return await auth_service.get_me(session, user.id)
