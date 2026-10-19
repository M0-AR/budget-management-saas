"""Finance services: categories, budgets, expenses, incomes.

All reads/writes are tenant-scoped twice: explicitly in every WHERE clause
via the repositories, and independently by Postgres RLS.
"""

from __future__ import annotations

import uuid
from calendar import monthrange
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ValidationError
from app.core.tenancy import require_current_tenant
from app.models import Budget, Category, Expense, Income
from app.repositories.base import TenantScopedRepository
from app.schemas.finance import (
    BudgetOut,
    BudgetUpsert,
    CategoryCreate,
    CategoryOut,
    CategoryUpdate,
    ExpenseCreate,
    ExpenseOut,
    ExpenseUpdate,
    IncomeCreate,
    IncomeOut,
    IncomeUpdate,
    TransactionPage,
)
from app.services import audit

MONEY = Decimal("0.01")


def to_money(value: float) -> Decimal:
    """Convert an API float to exact two-decimal money."""
    return Decimal(str(value)).quantize(MONEY, rounding=ROUND_HALF_UP)


def month_bounds(year: int, month: int) -> tuple[date, date]:
    return date(year, month, 1), date(year, month, monthrange(year, month)[1])


class CategoryRepository(TenantScopedRepository[Category]):
    model = Category


class BudgetRepository(TenantScopedRepository[Budget]):
    model = Budget


class ExpenseRepository(TenantScopedRepository[Expense]):
    model = Expense


class IncomeRepository(TenantScopedRepository[Income]):
    model = Income


class FinanceService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.categories = CategoryRepository(session)
        self.budgets = BudgetRepository(session)
        self.expenses = ExpenseRepository(session)
        self.incomes = IncomeRepository(session)

    # ------------------------------------------------------------------ categories

    async def list_categories(
        self, *, kind: str | None = None, include_archived: bool = False
    ) -> list[CategoryOut]:
        stmt = self.categories.base_select().order_by(Category.kind, Category.name)
        if kind is not None:
            stmt = stmt.where(Category.kind == kind)
        if not include_archived:
            stmt = stmt.where(Category.is_archived.is_(False))
        rows = (await self.session.execute(stmt)).scalars().all()
        return [CategoryOut.model_validate(row) for row in rows]

    async def create_category(
        self, payload: CategoryCreate, *, actor_user_id: uuid.UUID
    ) -> CategoryOut:
        tenant_id = require_current_tenant()
        duplicate = (
            await self.session.execute(
                select(Category.id).where(
                    Category.tenant_id == tenant_id,
                    Category.name == payload.name.strip(),
                    Category.kind == payload.kind,
                )
            )
        ).scalar_one_or_none()
        if duplicate is not None:
            raise ConflictError("A category with that name already exists", code="duplicate_category")

        category = Category(
            tenant_id=tenant_id,
            name=payload.name.strip(),
            kind=payload.kind,
            color=payload.color,
        )
        self.categories.add(category)
        await self.session.flush()
        audit.record(
            self.session,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action="category.created",
            entity_type="category",
            entity_id=category.id,
            detail={"name": category.name, "kind": category.kind},
        )
        return CategoryOut.model_validate(category)

    async def update_category(
        self, category_id: uuid.UUID, payload: CategoryUpdate, *, actor_user_id: uuid.UUID
    ) -> CategoryOut:
        category = await self.categories.get_or_404(category_id)
        changes = payload.model_dump(exclude_unset=True)
        if "name" in changes and changes["name"]:
            changes["name"] = changes["name"].strip()
        for field, value in changes.items():
            setattr(category, field, value)
        await self.session.flush()
        audit.record(
            self.session,
            tenant_id=require_current_tenant(),
            actor_user_id=actor_user_id,
            action="category.updated",
            entity_type="category",
            entity_id=category.id,
            detail=changes,
        )
        return CategoryOut.model_validate(category)

    async def delete_category(self, category_id: uuid.UUID, *, actor_user_id: uuid.UUID) -> None:
        category = await self.categories.get_or_404(category_id)
        await self.categories.delete(category)
        audit.record(
            self.session,
            tenant_id=require_current_tenant(),
            actor_user_id=actor_user_id,
            action="category.deleted",
            entity_type="category",
            entity_id=category_id,
            detail={"name": category.name},
        )

    # ------------------------------------------------------------------ budgets

    async def list_budgets(self, year: int) -> list[BudgetOut]:
        stmt = (
            self.budgets.base_select()
            .where(Budget.year == year)
            .order_by(Budget.month)
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        return [BudgetOut.model_validate(row) for row in rows]

    async def upsert_budget(self, payload: BudgetUpsert, *, actor_user_id: uuid.UUID) -> BudgetOut:
        tenant_id = require_current_tenant()
        budget = (
            await self.session.execute(
                select(Budget).where(
                    Budget.tenant_id == tenant_id,
                    Budget.year == payload.year,
                    Budget.month == payload.month,
                )
            )
        ).scalar_one_or_none()

        action = "budget.updated" if budget else "budget.created"
        if budget is None:
            budget = Budget(
                tenant_id=tenant_id,
                year=payload.year,
                month=payload.month,
                amount=to_money(payload.amount),
                alert_threshold_pct=payload.alert_threshold_pct,
            )
            self.budgets.add(budget)
        else:
            budget.amount = to_money(payload.amount)
            budget.alert_threshold_pct = payload.alert_threshold_pct

        await self.session.flush()
        audit.record(
            self.session,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action=action,
            entity_type="budget",
            entity_id=budget.id,
            detail={
                "year": payload.year,
                "month": payload.month,
                "amount": float(budget.amount),
            },
        )
        return BudgetOut.model_validate(budget)

    async def delete_budget(self, budget_id: uuid.UUID, *, actor_user_id: uuid.UUID) -> None:
        budget = await self.budgets.get_or_404(budget_id)
        await self.budgets.delete(budget)
        audit.record(
            self.session,
            tenant_id=require_current_tenant(),
            actor_user_id=actor_user_id,
            action="budget.deleted",
            entity_type="budget",
            entity_id=budget_id,
        )

    # ------------------------------------------------------------------ helpers

    async def _assert_category(self, category_id: uuid.UUID | None, *, kind: str) -> None:
        if category_id is None:
            return
        tenant_id = require_current_tenant()
        found = (
            await self.session.execute(
                select(Category.kind).where(
                    Category.id == category_id, Category.tenant_id == tenant_id
                )
            )
        ).scalar_one_or_none()
        if found is None:
            raise ValidationError("Category not found in this workspace")
        if found != kind:
            raise ValidationError(f"Category is for {found}s, not {kind}s")

    @staticmethod
    def _date_conditions(model, *, year: int | None, month: int | None) -> list:
        conditions: list = []
        if year is not None and month is not None:
            start, end = month_bounds(year, month)
            conditions.append(model.happened_on >= start)
            conditions.append(model.happened_on <= end)
        elif year is not None:
            conditions.append(model.happened_on >= date(year, 1, 1))
            conditions.append(model.happened_on <= date(year, 12, 31))
        return conditions

    async def _list_transactions(
        self,
        model,
        schema,
        *,
        year: int | None,
        month: int | None,
        category_id: uuid.UUID | None,
        query: str | None,
        page: int,
        page_size: int,
    ) -> TransactionPage:
        tenant_id = require_current_tenant()
        conditions = [model.tenant_id == tenant_id]
        conditions.extend(self._date_conditions(model, year=year, month=month))
        if category_id is not None:
            conditions.append(model.category_id == category_id)
        if query:
            conditions.append(model.note.ilike(f"%{query.strip()}%"))

        total = (
            await self.session.execute(
                select(func.count()).select_from(model).where(*conditions)
            )
        ).scalar_one()
        filtered_amount = (
            await self.session.execute(
                select(func.coalesce(func.sum(model.amount), 0)).where(*conditions)
            )
        ).scalar_one()

        rows = (
            await self.session.execute(
                select(model, Category.name, Category.color)
                .outerjoin(Category, model.category_id == Category.id)
                .where(*conditions)
                .order_by(model.happened_on.desc(), model.created_at.desc())
                .limit(page_size)
                .offset((page - 1) * page_size)
            )
        ).all()

        items = [
            schema(
                id=row.id,
                amount=float(row.amount),
                category_id=row.category_id,
                category_name=category_name,
                category_color=category_color,
                note=row.note,
                happened_on=row.happened_on,
                created_at=row.created_at,
            )
            for row, category_name, category_color in rows
        ]
        return TransactionPage(
            items=items,
            total=int(total),
            page=page,
            page_size=page_size,
            filtered_amount=float(filtered_amount),
        )

    # ------------------------------------------------------------------ expenses

    async def list_expenses(self, **kwargs) -> TransactionPage:
        return await self._list_transactions(Expense, ExpenseOut, **kwargs)

    async def get_expense(self, expense_id: uuid.UUID) -> ExpenseOut:
        expense = await self.expenses.get_or_404(expense_id)
        return await self._single_expense_out(expense)

    async def create_expense(
        self, payload: ExpenseCreate, *, actor_user_id: uuid.UUID
    ) -> ExpenseOut:
        await self._assert_category(payload.category_id, kind="expense")
        tenant_id = require_current_tenant()
        expense = Expense(
            tenant_id=tenant_id,
            category_id=payload.category_id,
            amount=to_money(payload.amount),
            note=payload.note.strip(),
            happened_on=payload.happened_on,
            created_by=actor_user_id,
        )
        self.expenses.add(expense)
        await self.session.flush()
        audit.record(
            self.session,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action="expense.created",
            entity_type="expense",
            entity_id=expense.id,
            detail={"amount": float(expense.amount), "on": payload.happened_on.isoformat()},
        )
        return await self._single_expense_out(expense)

    async def update_expense(
        self, expense_id: uuid.UUID, payload: ExpenseUpdate, *, actor_user_id: uuid.UUID
    ) -> ExpenseOut:
        expense = await self.expenses.get_or_404(expense_id)
        changes = payload.model_dump(exclude_unset=True)
        if "category_id" in changes:
            await self._assert_category(changes["category_id"], kind="expense")
        if "amount" in changes and changes["amount"] is not None:
            changes["amount"] = to_money(changes["amount"])
        if "note" in changes and changes["note"] is not None:
            changes["note"] = changes["note"].strip()
        for field, value in changes.items():
            setattr(expense, field, value)
        await self.session.flush()
        audit.record(
            self.session,
            tenant_id=require_current_tenant(),
            actor_user_id=actor_user_id,
            action="expense.updated",
            entity_type="expense",
            entity_id=expense.id,
            detail={k: (str(v) if isinstance(v, (Decimal, date)) else v) for k, v in changes.items()},
        )
        return await self._single_expense_out(expense)

    async def delete_expense(self, expense_id: uuid.UUID, *, actor_user_id: uuid.UUID) -> None:
        expense = await self.expenses.get_or_404(expense_id)
        await self.expenses.delete(expense)
        audit.record(
            self.session,
            tenant_id=require_current_tenant(),
            actor_user_id=actor_user_id,
            action="expense.deleted",
            entity_type="expense",
            entity_id=expense_id,
            detail={"amount": float(expense.amount)},
        )

    async def _single_expense_out(self, expense: Expense) -> ExpenseOut:
        category_name: str | None = None
        category_color: str | None = None
        if expense.category_id is not None:
            row = (
                await self.session.execute(
                    select(Category.name, Category.color).where(
                        Category.id == expense.category_id,
                        Category.tenant_id == expense.tenant_id,
                    )
                )
            ).one_or_none()
            if row is not None:
                category_name, category_color = row
        return ExpenseOut(
            id=expense.id,
            amount=float(expense.amount),
            category_id=expense.category_id,
            category_name=category_name,
            category_color=category_color,
            note=expense.note,
            happened_on=expense.happened_on,
            created_at=expense.created_at,
        )

    # ------------------------------------------------------------------ incomes

    async def list_incomes(self, **kwargs) -> TransactionPage:
        return await self._list_transactions(Income, IncomeOut, **kwargs)

    async def get_income(self, income_id: uuid.UUID) -> IncomeOut:
        income = await self.incomes.get_or_404(income_id)
        return await self._single_income_out(income)

    async def create_income(self, payload: IncomeCreate, *, actor_user_id: uuid.UUID) -> IncomeOut:
        await self._assert_category(payload.category_id, kind="income")
        tenant_id = require_current_tenant()
        income = Income(
            tenant_id=tenant_id,
            category_id=payload.category_id,
            amount=to_money(payload.amount),
            note=payload.note.strip(),
            happened_on=payload.happened_on,
            created_by=actor_user_id,
        )
        self.incomes.add(income)
        await self.session.flush()
        audit.record(
            self.session,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action="income.created",
            entity_type="income",
            entity_id=income.id,
            detail={"amount": float(income.amount), "on": payload.happened_on.isoformat()},
        )
        return await self._single_income_out(income)

    async def update_income(
        self, income_id: uuid.UUID, payload: IncomeUpdate, *, actor_user_id: uuid.UUID
    ) -> IncomeOut:
        income = await self.incomes.get_or_404(income_id)
        changes = payload.model_dump(exclude_unset=True)
        if "category_id" in changes:
            await self._assert_category(changes["category_id"], kind="income")
        if "amount" in changes and changes["amount"] is not None:
            changes["amount"] = to_money(changes["amount"])
        if "note" in changes and changes["note"] is not None:
            changes["note"] = changes["note"].strip()
        for field, value in changes.items():
            setattr(income, field, value)
        await self.session.flush()
        audit.record(
            self.session,
            tenant_id=require_current_tenant(),
            actor_user_id=actor_user_id,
            action="income.updated",
            entity_type="income",
            entity_id=income.id,
            detail={k: (str(v) if isinstance(v, (Decimal, date)) else v) for k, v in changes.items()},
        )
        return await self._single_income_out(income)

    async def delete_income(self, income_id: uuid.UUID, *, actor_user_id: uuid.UUID) -> None:
        income = await self.incomes.get_or_404(income_id)
        await self.incomes.delete(income)
        audit.record(
            self.session,
            tenant_id=require_current_tenant(),
            actor_user_id=actor_user_id,
            action="income.deleted",
            entity_type="income",
            entity_id=income_id,
            detail={"amount": float(income.amount)},
        )

    async def _single_income_out(self, income: Income) -> IncomeOut:
        category_name: str | None = None
        category_color: str | None = None
        if income.category_id is not None:
            row = (
                await self.session.execute(
                    select(Category.name, Category.color).where(
                        Category.id == income.category_id,
                        Category.tenant_id == income.tenant_id,
                    )
                )
            ).one_or_none()
            if row is not None:
                category_name, category_color = row
        return IncomeOut(
            id=income.id,
            amount=float(income.amount),
            category_id=income.category_id,
            category_name=category_name,
            category_color=category_color,
            note=income.note,
            happened_on=income.happened_on,
            created_at=income.created_at,
        )
