"""initial schema with row-level security

Revision ID: 20261018_0001
Revises:
Create Date: 2026-10-18

Creates the control plane (tenants), the tenant-owned tables (users,
categories, budgets, expenses, incomes, audit_logs), and enables *forced*
Row-Level Security on every tenant-owned table with a single isolation
policy keyed on `app.current_tenant_id`, which the application pins
per-transaction via set_config(..., is_local => true).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261018_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_OWNED_TABLES = ("users", "categories", "budgets", "expenses", "incomes", "audit_logs")

RLS_POLICY_SQL = """
CREATE POLICY {table}_tenant_isolation ON {table}
    USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
"""


def upgrade() -> None:
    # ------------------------------------------------------------ control plane
    op.create_table(
        "tenants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("tier", sa.String(length=20), nullable=False, server_default="free"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"),
        sa.Column("locale", sa.String(length=20), nullable=False, server_default="en-US"),
        sa.Column("timezone", sa.String(length=40), nullable=False, server_default="UTC"),
        sa.Column(
            "branding",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id", name="pk_tenants"),
        sa.CheckConstraint("tier IN ('free', 'pro', 'enterprise')", name="ck_tenants_tier_valid"),
        sa.CheckConstraint("status IN ('active', 'suspended')", name="ck_tenants_status_valid"),
        sa.CheckConstraint("slug ~ '^[a-z0-9][a-z0-9-]{1,38}[a-z0-9]$'", name="ck_tenants_slug_format"),
    )
    op.create_index("ix_tenants_slug", "tenants", ["slug"], unique=True)

    # ------------------------------------------------------------ tenant-owned
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("role", sa.String(length=20), nullable=False, server_default="member"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_users_tenant_id_tenants", ondelete="CASCADE"
        ),
        sa.UniqueConstraint("tenant_id", "email", name="uq_users_tenant_id_email"),
        sa.CheckConstraint("role IN ('owner', 'admin', 'member', 'viewer')", name="ck_users_role_valid"),
    )
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])

    op.create_table(
        "categories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False, server_default="expense"),
        sa.Column("color", sa.String(length=9), nullable=False, server_default="#64748b"),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id", name="pk_categories"),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_categories_tenant_id_tenants", ondelete="CASCADE"
        ),
        sa.UniqueConstraint("tenant_id", "name", "kind", name="uq_categories_tenant_id_name_kind"),
        sa.CheckConstraint("kind IN ('expense', 'income')", name="ck_categories_kind_valid"),
    )
    op.create_index("ix_categories_tenant_id", "categories", ["tenant_id"])

    op.create_table(
        "budgets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("alert_threshold_pct", sa.Integer(), nullable=False, server_default="80"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id", name="pk_budgets"),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_budgets_tenant_id_tenants", ondelete="CASCADE"
        ),
        sa.UniqueConstraint("tenant_id", "year", "month", name="uq_budgets_tenant_id_year_month"),
        sa.CheckConstraint("month BETWEEN 1 AND 12", name="ck_budgets_month_valid"),
        sa.CheckConstraint("amount >= 0", name="ck_budgets_amount_non_negative"),
        sa.CheckConstraint(
            "alert_threshold_pct BETWEEN 1 AND 100", name="ck_budgets_threshold_valid"
        ),
    )
    op.create_index("ix_budgets_tenant_id", "budgets", ["tenant_id"])

    op.create_table(
        "expenses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=True),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("happened_on", sa.Date(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id", name="pk_expenses"),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_expenses_tenant_id_tenants", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name="fk_expenses_category_id_categories",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name="fk_expenses_created_by_users", ondelete="SET NULL"
        ),
        sa.CheckConstraint("amount > 0", name="ck_expenses_amount_positive"),
    )
    op.create_index("ix_expenses_tenant_id", "expenses", ["tenant_id"])
    op.create_index(
        "ix_expenses_tenant_id_happened_on", "expenses", ["tenant_id", "happened_on"]
    )

    op.create_table(
        "incomes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=True),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("happened_on", sa.Date(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id", name="pk_incomes"),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_incomes_tenant_id_tenants", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name="fk_incomes_category_id_categories",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name="fk_incomes_created_by_users", ondelete="SET NULL"
        ),
        sa.CheckConstraint("amount > 0", name="ck_incomes_amount_positive"),
    )
    op.create_index("ix_incomes_tenant_id", "incomes", ["tenant_id"])
    op.create_index("ix_incomes_tenant_id_happened_on", "incomes", ["tenant_id", "happened_on"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=60), nullable=False),
        sa.Column("entity_type", sa.String(length=40), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=True),
        sa.Column(
            "detail",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id", name="pk_audit_logs"),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_audit_logs_tenant_id_tenants", ondelete="CASCADE"
        ),
    )
    op.create_index("ix_audit_logs_tenant_id", "audit_logs", ["tenant_id"])
    op.create_index(
        "ix_audit_logs_tenant_id_created_at", "audit_logs", ["tenant_id", "created_at"]
    )

    # ------------------------------------------------------------ row-level security
    # FORCE RLS means even the table owner (the application role) is subject
    # to the policy. Missing tenant context -> NULL comparison -> no rows on
    # read and rejected writes.
    for table in TENANT_OWNED_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(RLS_POLICY_SQL.format(table=table))


def downgrade() -> None:
    for table in reversed(TENANT_OWNED_TABLES):
        op.drop_table(table)
    op.drop_index("ix_tenants_slug", table_name="tenants")
    op.drop_table("tenants")
