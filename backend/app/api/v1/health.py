"""Liveness and readiness probes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db

router = APIRouter(tags=["health"])


@router.get("/healthz", include_in_schema=False)
async def healthz() -> dict[str, str]:
    """Liveness: the process is up. No dependencies touched."""
    return {"status": "ok"}


@router.get("/readyz", include_in_schema=False)
async def readyz(session: AsyncSession = Depends(get_db)):
    """Readiness: the database answers."""
    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - exercised in chaos cases
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "detail": type(exc).__name__},
        )
    return {"status": "ok"}
