"""Application factory and wiring.

Middleware execution order (outermost → innermost):
    CORS → RateLimit → SecurityHeaders → RequestContext → routes
CORS is outermost so even a 429 carries CORS headers; RequestContext is
innermost so it always cleans up its ContextVars.
"""

from __future__ import annotations

import logging
import logging.config
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.health import router as health_router
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.exceptions import DomainError, domain_error_handler
from app.core.rate_limit import SlidingWindowLimiter
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.request_context import RequestContextMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware

logger = logging.getLogger("app")


def _configure_logging(level: str) -> None:
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "plain": {
                    "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
                    "datefmt": "%Y-%m-%dT%H:%M:%S%z",
                }
            },
            "handlers": {
                "console": {"class": "logging.StreamHandler", "formatter": "plain"}
            },
            "root": {"handlers": ["console"], "level": level.upper()},
            "loggers": {
                "uvicorn.access": {"level": "WARNING"},
                "sqlalchemy.engine": {"level": "WARNING"},
            },
        }
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    _configure_logging(settings.log_level)
    logger.info(
        "startup environment=%s seed_demo=%s", settings.environment, settings.seed_demo
    )

    if settings.seed_demo:
        try:
            from scripts.seed_demo import seed_if_empty

            await seed_if_empty()
        except Exception:  # never block boot on demo data
            logger.exception("demo seed skipped due to an error")

    yield
    logger.info("shutdown")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
        openapi_url=None if settings.is_production else "/openapi.json",
        lifespan=lifespan,
    )

    limiter = SlidingWindowLimiter(settings.rate_limit_per_minute)
    auth_limiter = SlidingWindowLimiter(settings.auth_rate_limit_per_minute)

    # Added last = runs first.
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RateLimitMiddleware, limiter=limiter, auth_limiter=auth_limiter)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID", "X-RateLimit-Limit", "X-RateLimit-Remaining", "Retry-After"],
        max_age=600,
    )

    app.add_exception_handler(DomainError, domain_error_handler)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "detail": "The request payload is invalid.",
                "code": "validation_error",
                "errors": [
                    {"loc": list(err.get("loc", [])), "msg": err.get("msg", "")}
                    for err in exc.errors()
                ],
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "Something went wrong on our side.", "code": "internal_error"},
        )

    app.include_router(health_router)
    app.include_router(api_router)
    return app


app = create_app()
