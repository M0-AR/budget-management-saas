"""Reporting services: dashboard, monthly report, CSV export.

Compute-heavy reads are pushed into SQL aggregates (SUM, GROUP BY,
date_trunc) so report cost stays flat as a tenant's history grows.
"""

from __future__ import annotations

import csv
import io
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenancy import require_current_tenant
from app.models import Budget, Category, Expense, Income
from app.schemas.finance import ExpenseOut
from app.schemas.reports import (
    BudgetStatus,
    CategoryTotal,
    DashboardOut,
    MonthPoint,
    MonthlyReportOut,
)
from app.services.finance import month_bounds


def _status(budget_amount: Decimal, expense_total: Decimal, threshold_pct: int) -> BudgetStatus:
    if budget_amount <= 0:
        return "no_budget"
    utilization = expense_total / budget_amount * 100
    if utilization >= 100:
        return "over"
    if utilization >= threshold_pct:
        return "warning"
    return "on_track"


def _utilization(budget_amount: Decimal, expense_total: Decimal) -> float:
    if budget_amount <= 0:
        return 0.0
    return round(float(expense_total / budget_amount * 100), 1)


def _shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1


class ReportService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _month_totals(self, model, year: int, month: int) -> Decimal:
        start, end = month_bounds(year, month)
        stmt = select(func.coalesce(func.sum(model.amount), 0)).where(
            model.tenant_id == require_current_tenant(),
            model.happened_on >= start,
            model.happened_on <= end,
        )
        return (await self.session.execute(stmt)).scalar_one()

    async def _budget_for(self, year: int, month: int) -> Budget | None:
        stmt = select(Budget).where(
            Budget.tenant_id == require_current_tenant(),
            Budget.year == year,
            Budget.month == month,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def _by_category(self, year: int, month: int, expense_total: Decimal) -> list[CategoryTotal]:
        start, end = month_bounds(year, month)
        stmt = (
            select(
                Category.id,
                Category.name,
                Category.color,
                func.sum(Expense.amount).label("total"),
            )
            .select_from(Expense)
            .outerjoin(Category, Expense.category_id == Category.id)
            .where(
                Expense.tenant_id == require_current_tenant(),
                Expense.happened_on >= start,
                Expense.happened_on <= end,
            )
            .group_by(Category.id, Category.name, Category.color)
            .order_by(func.sum(Expense.amount).desc())
        )
        rows = (await self.session.execute(stmt)).all()

        total_float = float(expense_total)
        result: list[CategoryTotal] = []
        for category_id, name, color, amount in rows:
            amount_float = float(amount)
            result.append(
                CategoryTotal(
                    category_id=category_id,
                    name=name or "Uncategorized",
                    color=color or "#94a3b8",
                    amount=amount_float,
                    share_pct=round(amount_float / total_float * 100, 1) if total_float > 0 else 0.0,
                )
            )
        return result

    async def _trend(self, year: int, month: int, months: int = 6) -> list[MonthPoint]:
        first_year, first_month = _shift_month(year, month, -(months - 1))
        range_start, _ = month_bounds(first_year, first_month)
        _, range_end = month_bounds(year, month)

        async def grouped(model) -> dict[tuple[int, int], Decimal]:
            stmt = (
                select(
                    func.date_trunc("month", model.happened_on).label("bucket"),
                    func.sum(model.amount),
                )
                .where(
                    model.tenant_id == require_current_tenant(),
                    model.happened_on >= range_start,
                    model.happened_on <= range_end,
                )
                .group_by("bucket")
            )
            rows = (await self.session.execute(stmt)).all()
            return {
                (bucket.year, bucket.month): amount
                for bucket, amount in rows
                if bucket is not None
            }

        expense_map = await grouped(Expense)
        income_map = await grouped(Income)

        points: list[MonthPoint] = []
        for offset in range(months):
            y, m = _shift_month(first_year, first_month, offset)
            points.append(
                MonthPoint(
                    year=y,
                    month=m,
                    income=float(income_map.get((y, m), 0)),
                    expense=float(expense_map.get((y, m), 0)),
                )
            )
        return points

    async def dashboard(self, year: int, month: int) -> DashboardOut:
        budget = await self._budget_for(year, month)
        budget_amount = budget.amount if budget else Decimal("0")
        threshold = budget.alert_threshold_pct if budget else 80

        expense_total = await self._month_totals(Expense, year, month)
        income_total = await self._month_totals(Income, year, month)

        start, end = month_bounds(year, month)
        recent_rows = (
            await self.session.execute(
                select(Expense, Category.name, Category.color)
                .outerjoin(Category, Expense.category_id == Category.id)
                .where(
                    Expense.tenant_id == require_current_tenant(),
                    Expense.happened_on >= start,
                    Expense.happened_on <= end,
                )
                .order_by(Expense.happened_on.desc(), Expense.created_at.desc())
                .limit(5)
            )
        ).all()

        return DashboardOut(
            year=year,
            month=month,
            budget_amount=float(budget_amount),
            income_total=float(income_total),
            expense_total=float(expense_total),
            remaining=float(budget_amount - expense_total),
            utilization_pct=_utilization(budget_amount, expense_total),
            alert_threshold_pct=threshold,
            status=_status(budget_amount, expense_total, threshold),
            by_category=await self._by_category(year, month, expense_total),
            trend=await self._trend(year, month),
            recent_expenses=[
                ExpenseOut(
                    id=row.id,
                    amount=float(row.amount),
                    category_id=row.category_id,
                    category_name=name,
                    category_color=color,
                    note=row.note,
                    happened_on=row.happened_on,
                    created_at=row.created_at,
                )
                for row, name, color in recent_rows
            ],
        )

    async def monthly(self, year: int, month: int) -> MonthlyReportOut:
        budget = await self._budget_for(year, month)
        budget_amount = budget.amount if budget else Decimal("0")
        threshold = budget.alert_threshold_pct if budget else 80

        expense_total = await self._month_totals(Expense, year, month)
        income_total = await self._month_totals(Income, year, month)

        return MonthlyReportOut(
            year=year,
            month=month,
            income_total=float(income_total),
            expense_total=float(expense_total),
            savings=float(income_total - expense_total),
            budget_amount=float(budget_amount),
            remaining=float(budget_amount - expense_total),
            utilization_pct=_utilization(budget_amount, expense_total),
            alert_threshold_pct=threshold,
            status=_status(budget_amount, expense_total, threshold),
            by_category=await self._by_category(year, month, expense_total),
        )

    async def export_csv(self, year: int, month: int) -> str:
        """Transactions for the month as CSV (spreadsheet-injection safe)."""
        start, end = month_bounds(year, month)
        tenant_id = require_current_tenant()

        def safe(value: str) -> str:
            # Neutralise spreadsheet formula injection.
            return f"'{value}" if value[:1] in ("=", "+", "-", "@") else value

        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["date", "type", "category", "note", "amount"])

        expense_rows = (
            await self.session.execute(
                select(Expense.happened_on, Category.name, Expense.note, Expense.amount)
                .outerjoin(Category, Expense.category_id == Category.id)
                .where(
                    Expense.tenant_id == tenant_id,
                    Expense.happened_on >= start,
                    Expense.happened_on <= end,
                )
            )
        ).all()
        income_rows = (
            await self.session.execute(
                select(Income.happened_on, Category.name, Income.note, Income.amount)
                .outerjoin(Category, Income.category_id == Category.id)
                .where(
                    Income.tenant_id == tenant_id,
                    Income.happened_on >= start,
                    Income.happened_on <= end,
                )
            )
        ).all()

        combined = sorted(
            [(row[0], "income", row[1], row[2], row[3]) for row in income_rows]
            + [(row[0], "expense", row[1], row[2], row[3]) for row in expense_rows],
            key=lambda item: (item[0], item[1]),
        )
        for happened_on, kind, category, note, amount in combined:
            writer.writerow(
                [happened_on.isoformat(), kind, safe(category or "Uncategorized"), safe(note or ""), f"{amount:.2f}"]
            )

        return buffer.getvalue()
