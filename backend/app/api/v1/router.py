"""Aggregate router for /api/v1."""

from fastapi import APIRouter

from app.api.v1 import auth, finance, imports, members, reports, settings

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(finance.router)
api_router.include_router(imports.router)
api_router.include_router(members.router)
api_router.include_router(reports.router)
api_router.include_router(settings.router)
