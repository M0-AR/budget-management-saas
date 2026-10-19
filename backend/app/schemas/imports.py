"""Transaction CSV import schemas."""

from __future__ import annotations

from pydantic import BaseModel


class ImportRowError(BaseModel):
    row: int
    message: str


class ImportSummary(BaseModel):
    imported_expenses: int
    imported_incomes: int
    duplicates_skipped: int
    failed: int
    categories_created: int
    errors: list[ImportRowError]
