"""Workspace settings: public branding + tenant configuration."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models import Tenant
from app.schemas.settings import PublicBrandingOut, SettingsUpdate, TenantSettingsOut
from app.services import audit

_BRANDING_KEYS = ("display_name", "accent_color", "logo_url")


async def get_tenant(session: AsyncSession, tenant_id: uuid.UUID) -> Tenant:
    tenant = (
        await session.execute(select(Tenant).where(Tenant.id == tenant_id))
    ).scalar_one_or_none()
    if tenant is None:
        raise NotFoundError("Workspace not found")
    return tenant


async def public_branding(session: AsyncSession, slug: str) -> PublicBrandingOut:
    """Unauthenticated: only safe-to-expose branding fields."""
    tenant = (
        await session.execute(select(Tenant).where(Tenant.slug == slug))
    ).scalar_one_or_none()
    if tenant is None or tenant.status != "active":
        raise NotFoundError("Workspace not found")

    branding = tenant.branding or {}
    return PublicBrandingOut(
        slug=tenant.slug,
        display_name=branding.get("display_name") or tenant.name,
        accent_color=branding.get("accent_color"),
        logo_url=branding.get("logo_url"),
        currency=tenant.currency,
        locale=tenant.locale,
    )


def _view(tenant: Tenant, role: str) -> TenantSettingsOut:
    branding = tenant.branding or {}
    return TenantSettingsOut(
        slug=tenant.slug,
        name=tenant.name,
        display_name=branding.get("display_name") or tenant.name,
        accent_color=branding.get("accent_color"),
        logo_url=branding.get("logo_url"),
        currency=tenant.currency,
        locale=tenant.locale,
        timezone=tenant.timezone,
        tier=tenant.tier,
        role=role,
    )


async def get_settings(session: AsyncSession, tenant_id: uuid.UUID, role: str) -> TenantSettingsOut:
    tenant = await get_tenant(session, tenant_id)
    return _view(tenant, role)


async def update_settings(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    role: str,
    actor_user_id: uuid.UUID,
    payload: SettingsUpdate,
) -> TenantSettingsOut:
    tenant = await get_tenant(session, tenant_id)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return _view(tenant, role)

    branding = dict(tenant.branding or {})
    branding_changed = False
    for key in _BRANDING_KEYS:
        if key in changes:
            value = changes.pop(key)
            if value is None:
                branding.pop(key, None)
            else:
                branding[key] = value
            branding_changed = True
    if branding_changed:
        tenant.branding = branding

    for field in ("currency", "locale", "timezone"):
        if field in changes:
            value = changes.pop(field)
            if value is not None:
                setattr(tenant, field, value)

    audit.record(
        session,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action="tenant.settings_updated",
        entity_type="tenant",
        entity_id=tenant.id,
        detail=payload.model_dump(exclude_unset=True, mode="json"),
    )

    await session.flush()
    return _view(tenant, role)
