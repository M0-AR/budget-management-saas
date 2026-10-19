"""Control-plane tables: tenants and their users.

``tenants`` is intentionally *not* under RLS: it is the control plane that
maps a login's ``tenant_slug`` to a tenant id. It holds no budgets, no
expenses, and no secrets beyond what branding needs to be public anyway.
``users`` is tenant-owned and RLS-protected like all finance tables.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, String, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantOwnedMixin, TimestampMixin

TENANT_TIERS = ("free", "pro", "enterprise")
TENANT_STATUSES = ("active", "suspended")
USER_ROLES = ("owner", "admin", "member", "viewer")


class Tenant(TimestampMixin, Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    tier: Mapped[str] = mapped_column(String(20), nullable=False, default="free", server_default="free")
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active", server_default="active"
    )
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, default="USD", server_default="USD"
    )
    locale: Mapped[str] = mapped_column(
        String(20), nullable=False, default="en-US", server_default="en-US"
    )
    timezone: Mapped[str] = mapped_column(
        String(40), nullable=False, default="UTC", server_default="UTC"
    )
    # White-label surface. Public by design (themed login page needs it).
    branding: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="'{}'::jsonb"
    )

    __table_args__ = (
        CheckConstraint(f"tier IN {TENANT_TIERS}", name="tier_valid"),
        CheckConstraint(f"status IN {TENANT_STATUSES}", name="status_valid"),
        CheckConstraint("slug ~ '^[a-z0-9][a-z0-9-]{1,38}[a-z0-9]$'", name="slug_format"),
    )


class User(TimestampMixin, TenantOwnedMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="member", server_default="member")
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True, server_default="true")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_users_tenant_id_email"),
        CheckConstraint(f"role IN {USER_ROLES}", name="role_valid"),
    )
