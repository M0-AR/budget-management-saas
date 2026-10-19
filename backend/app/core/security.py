"""Password hashing and JWT issuance/verification.

Design notes
------------
* bcrypt is used directly (passlib is unmaintained as of 2026).
* bcrypt only consumes the first 72 bytes of a password: registration
  rejects longer secrets instead of silently truncating them.
* Access and refresh tokens carry an explicit ``typ`` claim so a refresh
  token can never be replayed as an access token.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import bcrypt
import jwt

from app.core.config import get_settings

MAX_PASSWORD_BYTES = 72
TokenType = Literal["access", "refresh", "invite"]


class TokenError(Exception):
    """Raised when a token is malformed, expired, or of the wrong type."""


def validate_password_length(password: str) -> None:
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError(f"Password must be at most {MAX_PASSWORD_BYTES} bytes")


def hash_password(password: str) -> str:
    validate_password_length(password)
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def hash_jti(jti: str) -> str:
    """SHA-256 of a token id; only this hash is persisted (never the id)."""
    return hashlib.sha256(jti.encode("utf-8")).hexdigest()


def _create_token(
    *,
    subject: uuid.UUID,
    tenant_id: uuid.UUID,
    role: str,
    token_type: TokenType,
    expires_delta: timedelta,
    jti: str | None = None,
) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "tid": str(tenant_id),
        "role": role,
        "typ": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
        "jti": jti or uuid.uuid4().hex,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(*, subject: uuid.UUID, tenant_id: uuid.UUID, role: str) -> str:
    settings = get_settings()
    return _create_token(
        subject=subject,
        tenant_id=tenant_id,
        role=role,
        token_type="access",
        expires_delta=timedelta(minutes=settings.access_token_minutes),
    )


def create_refresh_token(
    *, subject: uuid.UUID, tenant_id: uuid.UUID, role: str, jti: str | None = None
) -> str:
    """Mint a refresh token.

    ``jti`` may be supplied by the caller so it can persist a hash of it and
    later enforce rotation / reuse detection (app.services.auth).
    """
    settings = get_settings()
    return _create_token(
        subject=subject,
        tenant_id=tenant_id,
        role=role,
        token_type="refresh",
        expires_delta=timedelta(days=settings.refresh_token_days),
        jti=jti,
    )


def create_invite_token(
    *, invite_id: uuid.UUID, tenant_id: uuid.UUID, role: str, jti: str | None = None
) -> str:
    """Mint a workspace-invite token.

    The ``tid`` claim is what lets the pre-auth acceptance flow pin the
    tenant before touching the RLS-protected ``invites`` table — exactly the
    trick ``refresh`` uses. ``sub`` is the invite row id, never a user.
    """
    settings = get_settings()
    return _create_token(
        subject=invite_id,
        tenant_id=tenant_id,
        role=role,
        token_type="invite",
        expires_delta=timedelta(days=settings.invite_token_days),
        jti=jti,
    )


def decode_token(token: str, *, expected_type: TokenType) -> dict[str, Any]:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "tid", "typ", "exp"]},
        )
    except jwt.PyJWTError as exc:
        raise TokenError("Invalid or expired token") from exc

    if payload.get("typ") != expected_type:
        raise TokenError(f"Token is not a valid {expected_type} token")
    return payload
