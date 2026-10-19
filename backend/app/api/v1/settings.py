"""Workspace settings and public branding endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_admin
from app.core.database import get_db
from app.models import User
from app.schemas.settings import PublicBrandingOut, SettingsUpdate, TenantSettingsOut
from app.services import tenants as tenant_service

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/public/{slug}", response_model=PublicBrandingOut)
async def public_branding(slug: str, session: AsyncSession = Depends(get_db)) -> PublicBrandingOut:
    """Unauthenticated: themes the login page for a workspace slug."""
    return await tenant_service.public_branding(session, slug)


@router.get("", response_model=TenantSettingsOut)
async def get_settings(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)
) -> TenantSettingsOut:
    return await tenant_service.get_settings(session, user.tenant_id, user.role)


@router.put("", response_model=TenantSettingsOut)
async def update_settings(
    payload: SettingsUpdate,
    user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
) -> TenantSettingsOut:
    return await tenant_service.update_settings(
        session,
        tenant_id=user.tenant_id,
        role=user.role,
        actor_user_id=user.id,
        payload=payload,
    )
