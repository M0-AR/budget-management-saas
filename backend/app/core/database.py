"""Async database engine, session factory, and the request-scoped session.

Every request gets exactly one transaction. When the request is
authenticated, the tenant context is pinned inside that transaction with
``SET LOCAL``-style semantics (``set_config(..., is_local => true)``), which
is what makes Postgres RLS safe to combine with connection pooling: the
setting evaporates when the transaction ends and can never leak to the next
request that reuses the pooled connection.

See docs/MULTI-TENANCY.md for the full design.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=1800,
    echo=False,
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


async def set_tenant_context(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    """Pin the tenant for the remainder of the *current transaction*.

    ``set_config(name, value, true)`` is the function form of ``SET LOCAL``
    and is our tenant switchboard: RLS policies read
    ``current_setting('app.current_tenant_id')``.
    """
    await session.execute(
        text("SELECT set_config('app.current_tenant_id', :tid, true)"),
        {"tid": str(tenant_id)},
    )


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one transaction per request, tenant pinned."""
    async with SessionLocal() as session:
        async with session.begin():
            principal = getattr(request.state, "principal", None)
            if principal is not None:
                await set_tenant_context(session, principal.tenant_id)
            yield session
