"""Tenant-owned finance tables: categories, budgets, expenses, incomes.

Money is stored as ``NUMERIC(14, 2)`` and handled as :class:`decimal.Decimal`
server-side. It is only converted to float at the API-schema boundary.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantOwnedMixin, TimestampMixin

CATEGORY_KINDS = ("expense", "income")


class Category(TimestampMixin, TenantOwnedMixin, Base):
    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    kind: Mapped[str] = mapped_column(String(10), nullable=False, default="expense")
    color: Mapped[str] = mapped_column(String(9), nullable=False, default="#64748b")
    is_archived: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="false")

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", "kind", name="uq_categories_tenant_id_name_kind"),
        CheckConstraint(f"kind IN {CATEGORY_KINDS}", name="kind_valid"),
    )


class Budget(TimestampMixin, TenantOwnedMixin, Base):
    __tablename__ = "budgets"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    alert_threshold_pct: Mapped[int] = mapped_column(
        Integer, nullable=False, default=80, server_default="80"
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "year", "month", name="uq_budgets_tenant_id_year_month"),
        CheckConstraint("month BETWEEN 1 AND 12", name="month_valid"),
        CheckConstraint("amount >= 0", name="amount_non_negative"),
        CheckConstraint("alert_threshold_pct BETWEEN 1 AND 100", name="threshold_valid"),
    )


class Expense(TimestampMixin, TenantOwnedMixin, Base):
    __tablename__ = "expenses"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    happened_on: Mapped[date] = mapped_column(Date, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        Index("ix_expenses_tenant_id_happened_on", "tenant_id", "happened_on"),
    )


class Income(TimestampMixin, TenantOwnedMixin, Base):
    __tablename__ = "incomes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    happened_on: Mapped[date] = mapped_column(Date, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        Index("ix_incomes_tenant_id_happened_on", "tenant_id", "happened_on"),
    )
