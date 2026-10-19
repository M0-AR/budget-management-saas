"""Central configuration.

Reads plain environment variables (no extra dependencies) with safe local
defaults, but refuses to boot with development secrets when ENVIRONMENT is
"production". See `.env.example` at the repo root.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

_DEV_JWT_SECRET = "dev-only-secret-change-me"


def _env(name: str, default: str) -> str:
    value = os.environ.get(name, "")
    return value if value.strip() else default


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:  # fail fast on misconfiguration
        raise RuntimeError(f"Environment variable {name} must be an integer, got {raw!r}") from exc


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_name: str
    environment: str
    database_url: str
    jwt_secret: str
    jwt_algorithm: str
    access_token_minutes: int
    refresh_token_days: int
    invite_token_days: int
    cors_origins: tuple[str, ...]
    rate_limit_per_minute: int
    auth_rate_limit_per_minute: int
    seed_demo: bool
    log_level: str

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    environment = _env("ENVIRONMENT", "development").lower()
    jwt_secret = _env("JWT_SECRET", _DEV_JWT_SECRET)
    if environment == "production" and jwt_secret == _DEV_JWT_SECRET:
        raise RuntimeError(
            "JWT_SECRET must be set to a strong unique value in production "
            "(generate one with: openssl rand -hex 32)"
        )

    database_url = _env(
        "DATABASE_URL",
        "postgresql+asyncpg://budget:change-me-in-production@localhost:5432/budget",
    )
    if database_url.startswith("postgresql://"):
        # Normalise plain DSNs so asyncpg is always used.
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    cors_origins = tuple(
        origin.strip()
        for origin in _env("CORS_ORIGINS", "http://localhost,http://localhost:5173").split(",")
        if origin.strip()
    )

    return Settings(
        app_name="Budget Management SaaS",
        environment=environment,
        database_url=database_url,
        jwt_secret=jwt_secret,
        jwt_algorithm="HS256",
        access_token_minutes=_env_int("ACCESS_TOKEN_MINUTES", 15),
        refresh_token_days=_env_int("REFRESH_TOKEN_DAYS", 14),
        invite_token_days=_env_int("INVITE_TOKEN_DAYS", 7),
        cors_origins=cors_origins,
        rate_limit_per_minute=_env_int("RATE_LIMIT_PER_MINUTE", 240),
        auth_rate_limit_per_minute=_env_int("AUTH_RATE_LIMIT_PER_MINUTE", 15),
        seed_demo=_env_bool("SEED_DEMO", True),
        log_level=_env("LOG_LEVEL", "info").lower(),
    )
