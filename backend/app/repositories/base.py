"""Tenant-safe repository primitives.

Every query issued through a repository *explicitly* filters on the tenant
id pinned for the request — RLS in the database is the second, independent
line of defence. Services compose extra filters on top.
"""

from __future__ import annotations

import uuid
from typing import Generic, TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.tenancy import require_current_tenant
from app.models.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class TenantScopedRepository(Generic[ModelT]):
    model: type[ModelT]

    def __init__(self, session: AsyncSession):
        self.session = session

    def base_select(self) -> Select:
        """A SELECT pre-filtered to the current tenant."""
        return select(self.model).where(self.model.tenant_id == require_current_tenant())

    async def get(self, entity_id: uuid.UUID) -> ModelT | None:
        stmt = self.base_select().where(self.model.id == entity_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_or_404(self, entity_id: uuid.UUID) -> ModelT:
        obj = await self.get(entity_id)
        if obj is None:
            raise NotFoundError(f"{self.model.__name__} not found")
        return obj

    async def count(self, *where_clauses) -> int:
        stmt = select(func.count()).select_from(self.model).where(
            self.model.tenant_id == require_current_tenant(), *where_clauses
        )
        return int((await self.session.execute(stmt)).scalar_one())

    def add(self, obj: ModelT) -> ModelT:
        self.session.add(obj)
        return obj

    async def delete(self, obj: ModelT) -> None:
        await self.session.delete(obj)
