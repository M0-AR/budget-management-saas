"""Workspace member and invitation endpoints.

Reading the member list is available to every role (viewers included);
inviting, role changes, removals and invite revocation require admin.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_admin
from app.core.database import get_db
from app.models import User
from app.schemas.members import InviteCreate, InviteCreated, InviteOut, MemberOut, MemberRoleUpdate
from app.services import members as members_service

router = APIRouter(prefix="/members", tags=["members"])


@router.get("", response_model=list[MemberOut])
async def list_members(
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[MemberOut]:
    return await members_service.list_members(session)


# ------------------------------------------------------------- invitations
# Declared before /{user_id} so "invites" is never parsed as a user id.


@router.get("/invites", response_model=list[InviteOut])
async def list_invites(
    _: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
) -> list[InviteOut]:
    return await members_service.list_invites(session)


@router.post("/invites", response_model=InviteCreated, status_code=status.HTTP_201_CREATED)
async def create_invite(
    payload: InviteCreate,
    user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
) -> InviteCreated:
    return await members_service.create_invite(session, actor=user, payload=payload)


@router.delete("/invites/{invite_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_invite(
    invite_id: uuid.UUID,
    user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
) -> None:
    await members_service.revoke_invite(session, actor=user, invite_id=invite_id)


# ----------------------------------------------------------------- members


@router.patch("/{user_id}", response_model=MemberOut)
async def update_member_role(
    user_id: uuid.UUID,
    payload: MemberRoleUpdate,
    user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
) -> MemberOut:
    return await members_service.update_member_role(
        session, actor=user, user_id=user_id, role=payload.role
    )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    user_id: uuid.UUID,
    user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
) -> None:
    await members_service.remove_member(session, actor=user, user_id=user_id)
