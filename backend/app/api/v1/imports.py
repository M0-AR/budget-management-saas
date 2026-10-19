"""Bulk transaction import endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_writer
from app.core.database import get_db
from app.models import User
from app.schemas.imports import ImportSummary
from app.services.importer import ImportService

router = APIRouter(tags=["imports"])


@router.post("/imports/transactions", response_model=ImportSummary)
async def import_transactions(
    file: UploadFile = File(...),
    kind: str = Query(default="expense", pattern="^(expense|income)$"),
    skip_duplicates: bool = Query(default=True),
    user: User = Depends(require_writer),
    session: AsyncSession = Depends(get_db),
) -> ImportSummary:
    """Import expenses (or incomes with ``kind=income``) from a CSV file.

    Expected columns: ``date`` and ``amount`` (required), plus optional
    ``note``, ``category`` and ``type``. Aliases such as ``happened_on``,
    ``description`` or ``memo`` are accepted. Rows with an explicit
    ``type`` of ``expense``/``income`` override the ``kind`` parameter.
    """
    content = await file.read()
    return await ImportService(session).import_csv(
        content,
        fallback_kind=kind,
        skip_duplicates=skip_duplicates,
        actor_user_id=user.id,
    )
