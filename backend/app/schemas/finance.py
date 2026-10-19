"""Finance domain schemas: categories, budgets, expenses, incomes."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel

CategoryKind = Literal["expense", "income"]

AMOUNT_FIELD = Field(gt=0, le=10**12, description="Positive amount, max 1e12")
NOTE_FIELD = Field(default="", max_length=500)


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    kind: CategoryKind = "expense"
    color: str = Field(default="#64748b", pattern=r"^#[0-9a-fA-F]{6}$")


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    is_archived: bool | None = None


class CategoryOut(ORMModel):
    id: uuid.UUID
    name: str
    kind: str
    color: str
    is_archived: bool


class BudgetUpsert(BaseModel):
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)
    amount: float = Field(ge=0, le=10**12)
    alert_threshold_pct: int = Field(default=80, ge=1, le=100)


class BudgetOut(ORMModel):
    id: uuid.UUID
    year: int
    month: int
    amount: float
    alert_threshold_pct: int


class ExpenseCreate(BaseModel):
    amount: float = AMOUNT_FIELD
    category_id: uuid.UUID | None = None
    note: str = NOTE_FIELD
    happened_on: date


class ExpenseUpdate(BaseModel):
    amount: float | None = Field(default=None, gt=0, le=10**12)
    category_id: uuid.UUID | None = None
    note: str | None = Field(default=None, max_length=500)
    happened_on: date | None = None


class ExpenseOut(ORMModel):
    id: uuid.UUID
    amount: float
    category_id: uuid.UUID | None
    category_name: str | None = None
    category_color: str | None = None
    note: str
    happened_on: date
    created_at: datetime


class TransactionPage(BaseModel):
    items: list[ExpenseOut]
    total: int
    page: int
    page_size: int
    filtered_amount: float


class IncomeCreate(BaseModel):
    amount: float = AMOUNT_FIELD
    category_id: uuid.UUID | None = None
    note: str = NOTE_FIELD
    happened_on: date


class IncomeUpdate(BaseModel):
    amount: float | None = Field(default=None, gt=0, le=10**12)
    category_id: uuid.UUID | None = None
    note: str | None = Field(default=None, max_length=500)
    happened_on: date | None = None


class IncomeOut(ORMModel):
    id: uuid.UUID
    amount: float
    category_id: uuid.UUID | None
    category_name: str | None = None
    category_color: str | None = None
    note: str
    happened_on: date
    created_at: datetime
