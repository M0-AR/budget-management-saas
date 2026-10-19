"""Workspace settings and public branding schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import HexColor


class PublicBrandingOut(BaseModel):
    """Served to unauthenticated browsers so the login page can be themed."""

    slug: str
    display_name: str
    accent_color: str | None
    logo_url: str | None
    currency: str
    locale: str


class TenantSettingsOut(BaseModel):
    slug: str
    name: str
    display_name: str
    accent_color: str | None
    logo_url: str | None
    currency: str
    locale: str
    timezone: str
    tier: str
    role: str  # the requesting user's role, so the UI can gate editing


class SettingsUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=60)
    accent_color: HexColor | None = None
    logo_url: str | None = Field(default=None, max_length=500)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    locale: str | None = Field(default=None, min_length=2, max_length=20)
    timezone: str | None = Field(default=None, min_length=1, max_length=40)

    @field_validator("logo_url")
    @classmethod
    def _validate_logo_url(cls, value: str | None) -> str | None:
        if value and not value.startswith(("https://", "http://")):
            raise ValueError("logo_url must be an http(s) URL")
        return value

    @field_validator("currency")
    @classmethod
    def _validate_currency(cls, value: str | None) -> str | None:
        if value is not None:
            value = value.upper()
            if not value.isalpha():
                raise ValueError("currency must be a 3-letter ISO code")
        return value
