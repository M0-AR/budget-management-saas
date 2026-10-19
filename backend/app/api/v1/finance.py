"""Finance endpoints: categories, budgets, expenses, incomes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Pagination, get_current_user, require_writer
from app.core.database import get_db
from app.models import User
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
from app.services.finance import FinanceService
from app.services.reports import ReportService

router = APIRouter(tags=["finance"])


def _service(session: AsyncSession) -> FinanceService:
    return FinanceService(session)


# ---------------------------------------------------------------- categories


@router.get("/categories", response_model=list[CategoryOut])
async def list_categories(
    kind: str | None = Query(default=None, pattern="^(expense|income)$"),
    include_archived: bool = Query(default=False),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[CategoryOut]:
    return await _service(session).list_categories(kind=kind, include_archived=include_archived)


@router.post("/categories", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
async def create_category(
    payload: CategoryCreate,
    user: User = Depends(require_writer),
    session: AsyncSession = Depends(get_db),
) -> CategoryOut:
    return await _service(session).create_category(payload, actor_user_id=user.id)


@router.put("/categories/{category_id}", response_model=CategoryOut)
async def update_category(
    category_id: uuid.UUID,
    payload: CategoryUpdate,
    user: User = Depends(require_writer),
    session: AsyncSession = Depends(get_db),
) -> CategoryOut:
    return await _service(session).update_category(category_id, payload, actor_user_id=user.id)


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: uuid.UUID,
    user: User = Depends(require_writer),
    session: AsyncSession = Depends(get_db),
) -> None:
    await _service(session).delete_category(category_id, actor_user_id=user.id)


# ---------------------------------------------------------------- budgets


@router.get("/budgets", response_model=list[BudgetOut])
async def list_budgets(
    year: int = Query(ge=2000, le=2100),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[BudgetOut]:
    return await _service(session).list_budgets(year)


@router.put("/budgets", response_model=BudgetOut)
async def upsert_budget(
    payload: BudgetUpsert,
    user: User = Depends(require_writer),
    session: AsyncSession = Depends(get_db),
) -> BudgetOut:
    return await _service(session).upsert_budget(payload, actor_user_id=user.id)


@router.delete("/budgets/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_budget(
    budget_id: uuid.UUID,
    user: User = Depends(require_writer),
    session: AsyncSession = Depends(get_db),
) -> None:
    await _service(session).delete_budget(budget_id, actor_user_id=user.id)


# ---------------------------------------------------------------- expenses


@router.get("/expenses", response_model=TransactionPage)
async def list_expenses(
    year: int | None = Query(default=None, ge=2000, le=2100),
    month: int | None = Query(default=None, ge=1, le=12),
    category_id: uuid.UUID | None = Query(default=None),
    q: str | None = Query(default=None, max_length=120),
    pagination: Pagination = Depends(),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> TransactionPage:
    return await _service(session).list_expenses(
        year=year,
        month=month,
        category_id=category_id,
        query=q,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get("/expenses/{expense_id}", response_model=ExpenseOut)
async def get_expense(
    expense_id: uuid.UUID,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ExpenseOut:
    return await _service(session).get_expense(expense_id)


@router.post("/expenses", response_model=ExpenseOut, status_code=status.HTTP_201_CREATED)
async def create_expense(
    payload: ExpenseCreate,
    user: User = Depends(require_writer),
    session: AsyncSession = Depends(get_db),
) -> ExpenseOut:
    return await _service(session).create_expense(payload, actor_user_id=user.id)


@router.put("/expenses/{expense_id}", response_model=ExpenseOut)
async def update_expense(
    expense_id: uuid.UUID,
    payload: ExpenseUpdate,
    user: User = Depends(require_writer),
    session: AsyncSession = Depends(get_db),
) -> ExpenseOut:
    return await _service(session).update_expense(expense_id, payload, actor_user_id=user.id)


@router.delete("/expenses/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_expense(
    expense_id: uuid.UUID,
    user: User = Depends(require_writer),
    session: AsyncSession = Depends(get_db),
) -> None:
    await _service(session).delete_expense(expense_id, actor_user_id=user.id)


# ---------------------------------------------------------------- incomes


@router.get("/incomes", response_model=TransactionPage)
async def list_incomes(
    year: int | None = Query(default=None, ge=2000, le=2100),
    month: int | None = Query(default=None, ge=1, le=12),
    category_id: uuid.UUID | None = Query(default=None),
    q: str | None = Query(default=None, max_length=120),
    pagination: Pagination = Depends(),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> TransactionPage:
    return await _service(session).list_incomes(
        year=year,
        month=month,
        category_id=category_id,
        query=q,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get("/incomes/{income_id}", response_model=IncomeOut)
async def get_income(
    income_id: uuid.UUID,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> IncomeOut:
    return await _service(session).get_income(income_id)


@router.post("/incomes", response_model=IncomeOut, status_code=status.HTTP_201_CREATED)
async def create_income(
    payload: IncomeCreate,
    user: User = Depends(require_writer),
    session: AsyncSession = Depends(get_db),
) -> IncomeOut:
    return await _service(session).create_income(payload, actor_user_id=user.id)


@router.put("/incomes/{income_id}", response_model=IncomeOut)
async def update_income(
    income_id: uuid.UUID,
    payload: IncomeUpdate,
    user: User = Depends(require_writer),
    session: AsyncSession = Depends(get_db),
) -> IncomeOut:
    return await _service(session).update_income(income_id, payload, actor_user_id=user.id)


@router.delete("/incomes/{income_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_income(
    income_id: uuid.UUID,
    user: User = Depends(require_writer),
    session: AsyncSession = Depends(get_db),
) -> None:
    await _service(session).delete_income(income_id, actor_user_id=user.id)


# ---------------------------------------------------------------- csv export


@router.get("/exports/transactions.csv", include_in_schema=False)
async def export_transactions_csv(
    year: int = Query(ge=2000, le=2100),
    month: int = Query(ge=1, le=12),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> PlainTextResponse:
    csv_body = await ReportService(session).export_csv(year, month)
    filename = f"transactions-{year}-{month:02d}.csv"
    return PlainTextResponse(
        csv_body,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
