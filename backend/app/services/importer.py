"""Bulk transaction import from CSV.

Designed to round-trip the CSV produced by ``ReportService.export_csv``
(``date,type,category,note,amount``) while also accepting the column names
and date formats found in common bank exports. Valid rows import even when
other rows fail; per-row failures are reported back with line numbers.
"""

from __future__ import annotations

import csv
import io
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.core.tenancy import require_current_tenant
from app.models import Category, Expense, Income
from app.schemas.imports import ImportRowError, ImportSummary
from app.services import audit
from app.services.finance import to_money

MAX_FILE_BYTES = 1_048_576
MAX_ROWS = 1000
MAX_ERRORS_REPORTED = 20
DEFAULT_CATEGORY_COLOR = "#64748b"

HEADER_ALIASES: dict[str, tuple[str, ...]] = {
    "date": ("date", "happened_on", "transaction_date", "posted"),
    "amount": ("amount", "value", "total"),
    "note": ("note", "description", "memo", "details"),
    "category": ("category", "category_name"),
    "type": ("type", "kind"),
}

DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y")
KINDS = ("expense", "income")
UNCATEGORIZED = {"", "uncategorized", "uncategorised", "-"}


@dataclass
class _Row:
    line: int
    kind: str
    happened_on: date
    amount: Decimal
    note: str
    category_name: str | None


def _normalise_header(header: str) -> str:
    return header.strip().lower().replace(" ", "_")


def _clean_text(raw: str | None) -> str:
    """Trim, and undo the apostrophe guard added by CSV export."""
    value = (raw or "").strip()
    if value[:1] == "'" and value[1:2] in ("=", "+", "-", "@"):
        return value[1:]
    return value


def _parse_date(raw: str) -> date:
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"unrecognised date {raw!r} (expected YYYY-MM-DD)")


def _parse_amount(raw: str) -> Decimal:
    cleaned = raw.replace("$", "").replace(",", "").replace(" ", "")
    try:
        amount = Decimal(cleaned)
    except InvalidOperation:
        raise ValueError(f"unrecognised amount {raw!r}") from None
    if not amount.is_finite() or amount <= 0:
        raise ValueError(f"amount must be a positive number, got {raw!r}")
    if amount > Decimal(10**12):
        raise ValueError("amount is too large")
    return to_money(amount)


class ImportService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def import_csv(
        self,
        content: bytes,
        *,
        fallback_kind: str,
        skip_duplicates: bool,
        actor_user_id: uuid.UUID,
    ) -> ImportSummary:
        reader = self._build_reader(content)
        columns = self._resolve_columns(reader.fieldnames or [])
        parsed, errors, failed = self._parse_rows(reader, columns, fallback_kind)

        categories_created = await self._ensure_categories(parsed, actor_user_id=actor_user_id)
        imported_expenses, imported_incomes, duplicates = await self._insert(
            parsed, skip_duplicates=skip_duplicates, actor_user_id=actor_user_id
        )
        await self.session.flush()

        summary = ImportSummary(
            imported_expenses=imported_expenses,
            imported_incomes=imported_incomes,
            duplicates_skipped=duplicates,
            failed=failed,
            categories_created=categories_created,
            errors=errors,
        )
        audit.record(
            self.session,
            tenant_id=require_current_tenant(),
            actor_user_id=actor_user_id,
            action="transactions.imported",
            entity_type="import",
            entity_id=uuid.uuid4(),
            detail=summary.model_dump(exclude={"errors"}),
        )
        return summary

    # ------------------------------------------------------------------ parsing

    def _build_reader(self, content: bytes) -> csv.DictReader:
        if len(content) > MAX_FILE_BYTES:
            raise ValidationError(
                f"File is too large — the limit is {MAX_FILE_BYTES // 1024} KB",
                code="import_file_too_large",
            )
        text = content.decode("utf-8-sig", errors="replace")
        try:
            dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(io.StringIO(text), dialect=dialect)
        if not reader.fieldnames:
            raise ValidationError("The file is empty or not a CSV", code="import_empty_file")
        return reader

    @staticmethod
    def _resolve_columns(fieldnames: list[str]) -> dict[str, str]:
        by_normalised = {_normalise_header(name): name for name in fieldnames if name}
        columns: dict[str, str] = {}
        for field, aliases in HEADER_ALIASES.items():
            for alias in aliases:
                if alias in by_normalised:
                    columns[field] = by_normalised[alias]
                    break
        missing = [field for field in ("date", "amount") if field not in columns]
        if missing:
            raise ValidationError(
                "CSV must include 'date' and 'amount' columns (optionally 'note', 'category', 'type')",
                code="import_missing_columns",
            )
        return columns

    def _parse_rows(
        self, reader: csv.DictReader, columns: dict[str, str], fallback_kind: str
    ) -> tuple[list[_Row], list[ImportRowError], int]:
        parsed: list[_Row] = []
        errors: list[ImportRowError] = []
        failed = 0
        data_rows = 0

        def fail(line: int, message: str) -> None:
            nonlocal failed
            failed += 1
            if len(errors) < MAX_ERRORS_REPORTED:
                errors.append(ImportRowError(row=line, message=message))

        for raw in reader:
            if not any((value or "").strip() for value in raw.values()):
                continue
            data_rows += 1
            if data_rows > MAX_ROWS:
                raise ValidationError(
                    f"Too many rows — the limit is {MAX_ROWS} per import",
                    code="import_too_many_rows",
                )
            line = reader.line_num
            row = {field: (raw.get(header) or "") for field, header in columns.items()}

            kind = fallback_kind
            if "type" in row and row["type"].strip():
                candidate = row["type"].strip().lower()
                if candidate in KINDS:
                    kind = candidate
                else:
                    fail(line, f"unsupported type {row['type'].strip()!r} (use 'expense' or 'income')")
                    continue

            try:
                happened_on = _parse_date(row["date"].strip())
            except ValueError as exc:
                fail(line, str(exc))
                continue

            try:
                amount = _parse_amount(row["amount"].strip())
            except ValueError as exc:
                fail(line, str(exc))
                continue

            note = _clean_text(row.get("note"))
            if len(note) > 500:
                fail(line, "note is longer than 500 characters")
                continue

            category_name = _clean_text(row.get("category"))
            if category_name.lower() in UNCATEGORIZED:
                category_name = ""
            if len(category_name) > 80:
                fail(line, "category name is longer than 80 characters")
                continue

            parsed.append(
                _Row(
                    line=line,
                    kind=kind,
                    happened_on=happened_on,
                    amount=amount,
                    note=note,
                    category_name=category_name or None,
                )
            )

        return parsed, errors, failed

    # ------------------------------------------------------------------ categories

    async def _ensure_categories(self, rows: list[_Row], *, actor_user_id: uuid.UUID) -> int:
        wanted = {(row.category_name.lower(), row.kind) for row in rows if row.category_name}
        if not wanted:
            return 0

        tenant_id = require_current_tenant()
        existing = (
            await self.session.execute(
                select(Category.name, Category.kind).where(Category.tenant_id == tenant_id)
            )
        ).all()
        known = {(name.lower(), kind) for name, kind in existing}

        created = 0
        for name_lower, kind in sorted(wanted):
            if (name_lower, kind) in known:
                continue
            original = next(
                row.category_name
                for row in rows
                if row.kind == kind and row.category_name and row.category_name.lower() == name_lower
            )
            category = Category(
                tenant_id=tenant_id,
                name=original,
                kind=kind,
                color=DEFAULT_CATEGORY_COLOR,
            )
            self.session.add(category)
            await self.session.flush()
            known.add((name_lower, kind))
            created += 1
            audit.record(
                self.session,
                tenant_id=tenant_id,
                actor_user_id=actor_user_id,
                action="category.created",
                entity_type="category",
                entity_id=category.id,
                detail={"name": original, "kind": kind, "source": "csv_import"},
            )
        return created

    # ------------------------------------------------------------------ insertion

    async def _insert(
        self, rows: list[_Row], *, skip_duplicates: bool, actor_user_id: uuid.UUID
    ) -> tuple[int, int, int]:
        if not rows:
            return 0, 0, 0

        tenant_id = require_current_tenant()
        category_ids = await self._category_ids(rows)
        existing = await self._existing_keys(rows) if skip_duplicates else set()

        imported_expenses = 0
        imported_incomes = 0
        duplicates = 0
        for row in rows:
            key = (row.kind, row.happened_on, row.amount, row.note)
            if skip_duplicates and key in existing:
                duplicates += 1
                continue
            category_id = category_ids.get((row.category_name or "").lower(), {}).get(row.kind)
            payload = dict(
                tenant_id=tenant_id,
                category_id=category_id,
                amount=row.amount,
                note=row.note,
                happened_on=row.happened_on,
                created_by=actor_user_id,
            )
            if row.kind == "expense":
                self.session.add(Expense(**payload))
                imported_expenses += 1
            else:
                self.session.add(Income(**payload))
                imported_incomes += 1
        return imported_expenses, imported_incomes, duplicates

    async def _category_ids(self, rows: list[_Row]) -> dict[tuple[str, str], uuid.UUID]:
        tenant_id = require_current_tenant()
        result = (
            await self.session.execute(
                select(Category.id, Category.name, Category.kind).where(
                    Category.tenant_id == tenant_id
                )
            )
        ).all()
        resolved: dict[tuple[str, str], uuid.UUID] = {}
        for category_id, name, kind in result:
            resolved[(name.lower(), kind)] = category_id
        mapping: dict[str, dict[str, uuid.UUID]] = {}
        for row in rows:
            if not row.category_name:
                continue
            key = (row.category_name.lower(), row.kind)
            if key in resolved:
                mapping.setdefault(row.category_name.lower(), {})[row.kind] = resolved[key]
        return mapping

    async def _existing_keys(
        self, rows: list[_Row]
    ) -> set[tuple[str, date, Decimal, str]]:
        tenant_id = require_current_tenant()
        keys: set[tuple[str, date, Decimal, str]] = set()
        for kind, model in (("expense", Expense), ("income", Income)):
            dates = [row.happened_on for row in rows if row.kind == kind]
            if not dates:
                continue
            result = (
                await self.session.execute(
                    select(model.happened_on, model.amount, model.note).where(
                        model.tenant_id == tenant_id,
                        model.happened_on >= min(dates),
                        model.happened_on <= max(dates),
                    )
                )
            ).all()
            keys.update(
                (kind, happened_on, amount, note) for happened_on, amount, note in result
            )
        return keys
