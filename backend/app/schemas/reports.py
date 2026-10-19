"""Reporting schemas: dashboard, monthly report, trend points."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel

from app.schemas.finance import ExpenseOut

BudgetStatus = Literal["no_budget", "on_track", "warning", "over"]


class CategoryTotal(BaseModel):
    category_id: uuid.UUID | None
    name: str
    color: str
    amount: float
    share_pct: float


class MonthPoint(BaseModel):
    year: int
    month: int
    income: float
    expense: float


class MonthlyReportOut(BaseModel):
    year: int
    month: int
    income_total: float
    expense_total: float
    savings: float
    budget_amount: float
    remaining: float
    utilization_pct: float
    alert_threshold_pct: int
    status: BudgetStatus
    by_category: list[CategoryTotal]


class DashboardOut(BaseModel):
    year: int
    month: int
    budget_amount: float
    income_total: float
    expense_total: float
    remaining: float
    utilization_pct: float
    alert_threshold_pct: int
    status: BudgetStatus
    by_category: list[CategoryTotal]
    trend: list[MonthPoint]
    recent_expenses: list[ExpenseOut]
