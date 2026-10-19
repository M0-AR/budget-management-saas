"""Membership management: listing, roles, removal, and email invitations.

Role-management rules (enforced here, not just in the UI):

* You can never change or remove *yourself* through this API — that keeps
  an admin from locking themselves out mid-flow.
* The workspace ``owner`` is immutable: ownership transfer is deliberately
  not exposed (it would need a two-step handshake to be safe).
* ``admin`` may manage ``member`` and ``viewer`` only; ``owner`` may also
  manage ``admin``.

Invitations are signed JWTs carrying the tenant id (so the pre-auth
acceptance flow can pin RLS context before reading the table) plus a
persisted row that carries the pending/one-time-use state. Only the hash
of the token's ``jti`` is stored, mirroring the refresh-token design.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import set_tenant_context
from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from app.core.security import TokenError, create_invite_token, decode_token, hash_jti
from app.models import Invite, User
from app.schemas.members import InviteCreate, InviteCreated, InviteOut, MemberOut
from app.services import audit

# Which roles each actor role is allowed to manage.
_MANAGED_ROLES: dict[str, tuple[str, ...]] = {
    "admin": ("member", "viewer"),
    "owner": ("admin", "member", "viewer"),
}

_NO_OWNER_CHANGES = "The workspace owner's role cannot be changed here"
_NOT_YOURSELF = "You cannot change or remove your own membership"
_OUT_OF_REACH = "Your role does not allow managing that member"


async def _get_member(session: AsyncSession, user_id: uuid.UUID) -> User:
    member = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if member is None:
        raise NotFoundError("Member not found")
    return member


def _assert_can_manage(actor: User, target: User) -> None:
    if target.id == actor.id:
        raise PermissionDeniedError(_NOT_YOURSELF)
    if target.role == "owner":
        raise PermissionDeniedError(_NO_OWNER_CHANGES)
    if target.role not in _MANAGED_ROLES.get(actor.role, ()):
        raise PermissionDeniedError(_OUT_OF_REACH)


async def list_members(session: AsyncSession) -> list[MemberOut]:
    rows = (
        (await session.execute(select(User).order_by(User.created_at, User.email))).scalars().all()
    )
    return [MemberOut.model_validate(row) for row in rows]


async def update_member_role(
    session: AsyncSession, *, actor: User, user_id: uuid.UUID, role: str
) -> MemberOut:
    member = await _get_member(session, user_id)
    _assert_can_manage(actor, member)
    if role not in _MANAGED_ROLES.get(actor.role, ()):
        raise PermissionDeniedError("Your role does not allow granting that role")
    previous = member.role
    member.role = role
    audit.record(
        session,
        tenant_id=actor.tenant_id,
        actor_user_id=actor.id,
        action="member.role_updated",
        entity_type="user",
        entity_id=member.id,
        detail={"email": member.email, "from": previous, "to": role},
    )
    return MemberOut.model_validate(member)


async def remove_member(session: AsyncSession, *, actor: User, user_id: uuid.UUID) -> None:
    member = await _get_member(session, user_id)
    _assert_can_manage(actor, member)
    email = member.email
    # Refresh tokens cascade; the removed user is signed out everywhere.
    await session.delete(member)
    audit.record(
        session,
        tenant_id=actor.tenant_id,
        actor_user_id=actor.id,
        action="member.removed",
        entity_type="user",
        entity_id=user_id,
        detail={"email": email},
    )


async def _pending_invite_for_email(session: AsyncSession, email: str) -> Invite | None:
    return (
        await session.execute(
            select(Invite).where(
                Invite.email == email,
                Invite.accepted_at.is_(None),
                Invite.expires_at > datetime.now(UTC),
            )
        )
    ).scalar_one_or_none()


async def create_invite(
    session: AsyncSession, *, actor: User, payload: InviteCreate
) -> InviteCreated:
    existing_member = (
        await session.execute(select(User).where(User.email == payload.email))
    ).scalar_one_or_none()
    if existing_member is not None:
        raise ConflictError(
            "That email already belongs to a workspace member", code="already_member"
        )
    if await _pending_invite_for_email(session, payload.email) is not None:
        raise ConflictError(
            "An invitation for that email is already pending", code="invite_pending"
        )

    invite_id = uuid.uuid4()
    jti = uuid.uuid4().hex
    token = create_invite_token(
        invite_id=invite_id, tenant_id=actor.tenant_id, role=payload.role, jti=jti
    )
    invite = Invite(
        id=invite_id,
        tenant_id=actor.tenant_id,
        email=payload.email,
        role=payload.role,
        token_hash=hash_jti(jti),
        created_by_user_id=actor.id,
        expires_at=datetime.now(UTC) + timedelta(days=get_settings().invite_token_days),
    )
    session.add(invite)
    await session.flush()
    await session.refresh(invite)

    audit.record(
        session,
        tenant_id=actor.tenant_id,
        actor_user_id=actor.id,
        action="invite.created",
        entity_type="invite",
        entity_id=invite.id,
        detail={"email": invite.email, "role": invite.role},
    )
    return InviteCreated(
        id=invite.id,
        email=invite.email,
        role=invite.role,
        expires_at=invite.expires_at,
        created_at=invite.created_at,
        token=token,
    )


async def list_invites(session: AsyncSession) -> list[InviteOut]:
    rows = (
        (
            await session.execute(
                select(Invite)
                .where(Invite.accepted_at.is_(None), Invite.expires_at > datetime.now(UTC))
                .order_by(Invite.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [InviteOut.model_validate(row) for row in rows]


async def revoke_invite(session: AsyncSession, *, actor: User, invite_id: uuid.UUID) -> None:
    invite = (
        await session.execute(select(Invite).where(Invite.id == invite_id))
    ).scalar_one_or_none()
    if invite is None:
        raise NotFoundError("Invitation not found")
    email = invite.email
    await session.execute(delete(Invite).where(Invite.id == invite_id))
    audit.record(
        session,
        tenant_id=actor.tenant_id,
        actor_user_id=actor.id,
        action="invite.revoked",
        entity_type="invite",
        entity_id=invite_id,
        detail={"email": email},
    )


class InviteClaim:
    """Validated invite handed back to the registration flow."""

    def __init__(self, invite: Invite):
        self.invite = invite

    @property
    def tenant_id(self) -> uuid.UUID:
        return self.invite.tenant_id

    @property
    def role(self) -> str:
        return self.invite.role

    @property
    def email(self) -> str:
        return self.invite.email

    async def mark_accepted(self, session: AsyncSession) -> None:
        self.invite.accepted_at = datetime.now(UTC)


async def claim_invite(session: AsyncSession, token: str, email: str) -> InviteClaim:
    """Validate an invite token for the given email; pin tenant scope.

    Called by the registration flow before any user row exists, so the
    tenant context must come from the token's own ``tid`` claim.
    """
    try:
        claims = decode_token(token, expected_type="invite")
    except TokenError as exc:
        raise ValidationError("This invite link is invalid or has expired") from exc

    tenant_id = uuid.UUID(claims["tid"])
    invite_id = uuid.UUID(claims["sub"])
    await set_tenant_context(session, tenant_id)

    invite = (
        await session.execute(
            select(Invite).where(
                Invite.id == invite_id, Invite.token_hash == hash_jti(claims["jti"])
            )
        )
    ).scalar_one_or_none()
    if invite is None or invite.accepted_at is not None:
        raise ValidationError("This invite link is invalid or has expired")
    if invite.expires_at <= datetime.now(UTC):
        raise ValidationError("This invite link is invalid or has expired")
    if invite.email.lower() != email.lower():
        raise ValidationError(
            "This invite was issued for a different email address",
            code="invite_email_mismatch",
        )
    return InviteClaim(invite)
