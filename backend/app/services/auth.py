"""Authentication flows: self-serve registration, login, refresh, logout, me.

The tenant-resolution rule for login is ``tenant_slug + email + password``:
one shared identity namespace per workspace, exactly like the classic
Slack/Vercel pattern. Tokens are minted *after* the tenant is resolved and
pinned, so a token can never point at a tenant the caller did not
authenticate into.

Refresh tokens are *stateful*: every issued token has a row in
``refresh_tokens`` (keyed by the SHA-256 of its ``jti``). Refreshing rotates
the token — the presented row is marked rotated and a successor in the same
``family_id`` is issued. Replaying an already-rotated token is treated as
theft: the entire family is revoked and the request fails with 401.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import SessionLocal, set_tenant_context
from app.core.exceptions import AuthenticationError, ConflictError, ValidationError
from app.core.security import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_jti,
    hash_password,
    verify_password,
)
from app.models import Category, RefreshToken, Tenant, User
from app.schemas.auth import AuthResponse, LoginRequest, MeOut, RegisterRequest, TokenPair, UserOut
from app.services import audit
from app.services import members as members_service

DEFAULT_EXPENSE_CATEGORIES: tuple[tuple[str, str], ...] = (
    ("Housing", "#2f6df6"),
    ("Groceries", "#16a34a"),
    ("Transport", "#f59e0b"),
    ("Utilities", "#8b5cf6"),
    ("Dining out", "#ef4444"),
    ("Entertainment", "#06b6d4"),
    ("Health", "#ec4899"),
    ("Shopping", "#84cc16"),
    ("Other", "#64748b"),
)
DEFAULT_INCOME_CATEGORIES: tuple[tuple[str, str], ...] = (
    ("Salary", "#16a34a"),
    ("Freelance", "#2f6df6"),
    ("Investments", "#8b5cf6"),
    ("Other income", "#64748b"),
)

_INVALID_CREDENTIALS = "Invalid email or password for this workspace"
_SESSION_EXPIRED = "Session expired. Please sign in again."


async def _issue_session(
    session: AsyncSession,
    user: User,
    *,
    family_id: str | None = None,
    rotation_of: RefreshToken | None = None,
) -> TokenPair:
    """Mint an access/refresh pair and persist the refresh token's jti hash.

    When ``rotation_of`` is given (a refresh), the presented row is marked
    rotated and linked to the successor, keeping the same ``family_id``.
    """
    settings = get_settings()
    jti = uuid.uuid4().hex
    now = datetime.now(UTC)
    session.add(
        RefreshToken(
            tenant_id=user.tenant_id,
            user_id=user.id,
            jti_hash=hash_jti(jti),
            family_id=family_id or uuid.uuid4().hex,
            expires_at=now + timedelta(days=settings.refresh_token_days),
        )
    )
    if rotation_of is not None:
        rotation_of.rotated_at = now
        rotation_of.replaced_by = hash_jti(jti)
    return TokenPair(
        access_token=create_access_token(
            subject=user.id, tenant_id=user.tenant_id, role=user.role
        ),
        refresh_token=create_refresh_token(
            subject=user.id, tenant_id=user.tenant_id, role=user.role, jti=jti
        ),
        expires_in=settings.access_token_minutes * 60,
    )


async def _revoke_family(
    tenant_id: uuid.UUID, family_id: str, *, user_id: uuid.UUID | None = None
) -> None:
    """Revoke every live token in a family, in its own transaction.

    The caller raises ``AuthenticationError`` right after, which rolls the
    request's main transaction back — so the revocation must commit on a
    separate session to survive.
    """
    now = datetime.now(UTC)
    async with SessionLocal() as cleanup:
        async with cleanup.begin():
            await set_tenant_context(cleanup, tenant_id)
            await cleanup.execute(
                update(RefreshToken)
                .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
                .values(revoked_at=now)
            )
            audit.record(
                cleanup,
                tenant_id=tenant_id,
                actor_user_id=user_id,
                action="auth.refresh_reuse_detected",
                entity_type="session",
                entity_id=family_id,
                detail={"reason": "rotated refresh token replayed; family revoked"},
            )


async def _register_via_invite(session: AsyncSession, payload: RegisterRequest) -> AuthResponse:
    """Accept an invite: create the user inside the inviting tenant.

    The invite token pins the tenant context (RLS) *before* any tenant row
    is read, exactly like the refresh flow. No workspace is created, no
    starter categories are seeded — the new member lands in the existing
    workspace with the invited role.
    """
    claim = await members_service.claim_invite(session, payload.invite_token or "", payload.email)

    tenant = (
        await session.execute(select(Tenant).where(Tenant.id == claim.tenant_id))
    ).scalar_one()

    already_member = (
        await session.execute(select(User.id).where(User.email == payload.email))
    ).scalar_one_or_none()
    if already_member is not None:
        raise ConflictError(
            "That email is already a member of this workspace", code="already_member"
        )

    try:
        password_hash = hash_password(payload.password)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc

    user = User(
        tenant_id=claim.tenant_id,
        email=payload.email,
        password_hash=password_hash,
        full_name=payload.full_name.strip(),
        role=claim.role,
    )
    session.add(user)
    await claim.mark_accepted(session)
    await session.flush()

    audit.record(
        session,
        tenant_id=claim.tenant_id,
        actor_user_id=user.id,
        action="member.joined",
        entity_type="user",
        entity_id=user.id,
        detail={"email": user.email, "role": user.role, "via": "invite"},
    )

    tokens = await _issue_session(session, user)
    return AuthResponse(user=UserOut.model_validate(user), tenant=tenant, tokens=tokens)


async def register_tenant(session: AsyncSession, payload: RegisterRequest) -> AuthResponse:
    """Self-serve provisioning: workspace + owner + starter categories.

    With an ``invite_token`` the request instead *joins an existing
    workspace* with the invite's role — see ``_register_via_invite``.
    """
    if payload.invite_token:
        return await _register_via_invite(session, payload)

    if not payload.tenant_name or not payload.tenant_slug:
        raise ValidationError(
            "Workspace name and slug are required to create a workspace",
            code="workspace_required",
        )

    taken = (
        await session.execute(select(Tenant.id).where(Tenant.slug == payload.tenant_slug))
    ).scalar_one_or_none()
    if taken is not None:
        raise ConflictError(
            "That workspace URL is already taken. Try another slug.",
            code="slug_taken",
        )

    try:
        password_hash = hash_password(payload.password)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc

    tenant = Tenant(slug=payload.tenant_slug, name=payload.tenant_name.strip())
    session.add(tenant)
    await session.flush()  # assign tenant.id

    # The users table is under FORCE RLS: pin the new tenant before inserting.
    await set_tenant_context(session, tenant.id)

    user = User(
        tenant_id=tenant.id,
        email=payload.email,
        password_hash=password_hash,
        full_name=payload.full_name.strip(),
        role="owner",
    )
    session.add(user)

    for name, color in DEFAULT_EXPENSE_CATEGORIES:
        session.add(Category(tenant_id=tenant.id, name=name, kind="expense", color=color))
    for name, color in DEFAULT_INCOME_CATEGORIES:
        session.add(Category(tenant_id=tenant.id, name=name, kind="income", color=color))

    await session.flush()

    audit.record(
        session,
        tenant_id=tenant.id,
        actor_user_id=user.id,
        action="tenant.registered",
        entity_type="tenant",
        entity_id=tenant.id,
        detail={"slug": tenant.slug, "owner_email": user.email},
    )

    tokens = await _issue_session(session, user)
    return AuthResponse(user=UserOut.model_validate(user), tenant=tenant, tokens=tokens)


async def login(session: AsyncSession, payload: LoginRequest) -> AuthResponse:
    tenant = (
        await session.execute(select(Tenant).where(Tenant.slug == payload.tenant_slug))
    ).scalar_one_or_none()
    if tenant is None:
        raise AuthenticationError(_INVALID_CREDENTIALS)
    if tenant.status != "active":
        raise AuthenticationError("This workspace is suspended. Contact your administrator.")

    await set_tenant_context(session, tenant.id)

    user = (
        await session.execute(
            select(User).where(User.tenant_id == tenant.id, User.email == payload.email)
        )
    ).scalar_one_or_none()
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise AuthenticationError(_INVALID_CREDENTIALS)

    user.last_login_at = datetime.now(UTC)
    audit.record(
        session,
        tenant_id=tenant.id,
        actor_user_id=user.id,
        action="user.logged_in",
        entity_type="user",
        entity_id=user.id,
    )

    tokens = await _issue_session(session, user)
    return AuthResponse(user=UserOut.model_validate(user), tenant=tenant, tokens=tokens)


async def refresh(session: AsyncSession, refresh_token: str) -> TokenPair:
    try:
        claims = decode_token(refresh_token, expected_type="refresh")
    except TokenError as exc:
        raise AuthenticationError(_SESSION_EXPIRED) from exc

    tenant_id = uuid.UUID(claims["tid"])
    user_id = uuid.UUID(claims["sub"])
    now = datetime.now(UTC)

    await set_tenant_context(session, tenant_id)

    stored = (
        await session.execute(
            select(RefreshToken).where(RefreshToken.jti_hash == hash_jti(claims["jti"]))
        )
    ).scalar_one_or_none()

    if stored is None or stored.revoked_at is not None:
        raise AuthenticationError(_SESSION_EXPIRED)

    if stored.rotated_at is not None:
        # A rotated token was replayed: assume theft, kill the whole family.
        await _revoke_family(tenant_id, stored.family_id, user_id=user_id)
        raise AuthenticationError(_SESSION_EXPIRED)

    if stored.expires_at <= now:
        stored.revoked_at = now
        raise AuthenticationError(_SESSION_EXPIRED)

    user = (
        await session.execute(
            select(User).where(User.id == user_id, User.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if user is None or not user.is_active:
        raise AuthenticationError(_SESSION_EXPIRED)

    return await _issue_session(session, user, family_id=stored.family_id, rotation_of=stored)


async def logout(session: AsyncSession, refresh_token: str | None) -> None:
    """Revoke the presented refresh token's family. Idempotent, never fails."""
    if not refresh_token:
        return
    try:
        claims = decode_token(refresh_token, expected_type="refresh")
    except TokenError:
        return

    tenant_id = uuid.UUID(claims["tid"])
    await set_tenant_context(session, tenant_id)

    stored = (
        await session.execute(
            select(RefreshToken).where(RefreshToken.jti_hash == hash_jti(claims["jti"]))
        )
    ).scalar_one_or_none()
    if stored is None or stored.revoked_at is not None:
        return

    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == stored.family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
    audit.record(
        session,
        tenant_id=tenant_id,
        actor_user_id=stored.user_id,
        action="auth.logged_out",
        entity_type="user",
        entity_id=stored.user_id,
    )


async def get_me(session: AsyncSession, user_id: uuid.UUID) -> MeOut:
    user = (
        await session.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if user is None or not user.is_active:
        raise AuthenticationError("Account is no longer active")

    tenant = (await session.execute(select(Tenant).where(Tenant.id == user.tenant_id))).scalar_one()
    return MeOut(user=UserOut.model_validate(user), tenant=tenant)
