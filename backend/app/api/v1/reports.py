"""Reporting endpoints: dashboard, monthly report."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import User
from app.schemas.reports import DashboardOut, MonthlyReportOut
from app.services.reports import ReportService

router = APIRouter(prefix="/reports", tags=["reports"])


def _current_month() -> tuple[int, int]:
    now = datetime.now(UTC)
    return now.year, now.month


@router.get("/dashboard", response_model=DashboardOut)
async def dashboard(
    year: int | None = Query(default=None, ge=2000, le=2100),
    month: int | None = Query(default=None, ge=1, le=12),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> DashboardOut:
    default_year, default_month = _current_month()
    return await ReportService(session).dashboard(year or default_year, month or default_month)


@router.get("/monthly", response_model=MonthlyReportOut)
async def monthly(
    year: int | None = Query(default=None, ge=2000, le=2100),
    month: int | None = Query(default=None, ge=1, le=12),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> MonthlyReportOut:
    default_year, default_month = _current_month()
    return await ReportService(session).monthly(year or default_year, month or default_month)
