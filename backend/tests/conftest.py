"""Shared test fixtures.

Unit tests run anywhere. DB-backed contract tests skip themselves when no
database is reachable, so `pytest` is always safe to run.
"""

from __future__ import annotations

import os

os.environ.setdefault("SEED_DEMO", "false")

# The test suite exercises many register/login/refresh calls from one client
# key. Raise the credential-endpoint budget so the brute-force limiter does
# not trip the suite; its behaviour is unit-tested in test_security_unit.py.
os.environ["AUTH_RATE_LIMIT_PER_MINUTE"] = "100000"

import pytest
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.main import app  # noqa: E402


def sync_dsn() -> str:
    return get_settings().database_url.replace("postgresql+asyncpg://", "postgresql://")


async def db_is_reachable() -> bool:
    import asyncpg

    try:
        connection = await asyncpg.connect(dsn=sync_dsn(), timeout=3)
        await connection.close()
        return True
    except Exception:
        return False


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as http:
        yield http


@pytest_asyncio.fixture
async def db_client(client: AsyncClient) -> AsyncClient:
    if not await db_is_reachable():
        pytest.skip("database not reachable; skipping DB-backed contract tests")
    yield client
