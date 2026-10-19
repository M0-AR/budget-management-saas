"""Authentication and identity schemas."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from app.schemas.common import EmailStr, ORMModel, SlugStr


class RegisterRequest(BaseModel):
    """Self-serve registration, or invite acceptance when ``invite_token``
    is present (workspace fields are then ignored and may be omitted)."""

    tenant_name: str | None = Field(default=None, min_length=2, max_length=120)
    tenant_slug: SlugStr | None = None
    full_name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=64)
    invite_token: str | None = Field(default=None, min_length=20)


class LoginRequest(BaseModel):
    tenant_slug: str = Field(min_length=3, max_length=40)
    email: EmailStr
    password: str = Field(min_length=1, max_length=64)


class RefreshRequest(BaseModel):
    """Refresh/logout payload.

    Optional on purpose: browsers use the HttpOnly ``bms_refresh`` cookie
    instead, while API clients (CLI, e2e) pass the token in the body.
    """

    refresh_token: str | None = Field(default=None, min_length=10)


class UserOut(ORMModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    tenant_id: uuid.UUID


class TenantOut(ORMModel):
    id: uuid.UUID
    slug: str
    name: str
    tier: str
    currency: str
    locale: str
    timezone: str
    branding: dict


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds until the access token expires


class AuthResponse(BaseModel):
    user: UserOut
    tenant: TenantOut
    tokens: TokenPair


class MeOut(BaseModel):
    user: UserOut
    tenant: TenantOut
