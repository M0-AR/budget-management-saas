"""Unit tests: password hashing and JWT handling. No database needed."""

from __future__ import annotations

import time
import uuid

import jwt
import pytest

from app.core.config import get_settings
from app.core.security import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    validate_password_length,
    verify_password,
)


def test_password_hash_round_trip() -> None:
    hashed = hash_password("Correct-Horse-9!")
    assert hashed != "Correct-Horse-9!"
    assert hashed.startswith("$2")
    assert verify_password("Correct-Horse-9!", hashed)
    assert not verify_password("wrong-password", hashed)


def test_password_hash_is_salted() -> None:
    assert hash_password("same-password") != hash_password("same-password")


def test_password_length_limit_is_enforced() -> None:
    with pytest.raises(ValueError):
        validate_password_length("x" * 73)
    with pytest.raises(ValueError):
        hash_password("x" * 73)
    validate_password_length("x" * 72)


def test_access_token_round_trip() -> None:
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    token = create_access_token(subject=user_id, tenant_id=tenant_id, role="owner")
    claims = decode_token(token, expected_type="access")
    assert claims["sub"] == str(user_id)
    assert claims["tid"] == str(tenant_id)
    assert claims["role"] == "owner"


def test_refresh_token_cannot_be_used_as_access_token() -> None:
    token = create_refresh_token(subject=uuid.uuid4(), tenant_id=uuid.uuid4(), role="member")
    with pytest.raises(TokenError):
        decode_token(token, expected_type="access")
    claims = decode_token(token, expected_type="refresh")
    assert claims["typ"] == "refresh"


def test_tampered_token_is_rejected() -> None:
    token = create_access_token(subject=uuid.uuid4(), tenant_id=uuid.uuid4(), role="member")
    header, payload, signature = token.split(".")
    tampered = f"{header}.{payload}.{signature[:-4]}AAAA"
    with pytest.raises(TokenError):
        decode_token(tampered, expected_type="access")


def test_expired_token_is_rejected() -> None:
    settings = get_settings()
    import datetime as dt

    now = dt.datetime.now(dt.UTC)
    expired = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "tid": str(uuid.uuid4()),
            "role": "owner",
            "typ": "access",
            "iat": int(now.timestamp()) - 3600,
            "exp": int(now.timestamp()) - 1800,
            "jti": uuid.uuid4().hex,
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(TokenError):
        decode_token(expired, expected_type="access")


def test_token_with_garbage_is_rejected() -> None:
    with pytest.raises(TokenError):
        decode_token("not-a-jwt", expected_type="access")


def test_sliding_window_limiter_behaviour() -> None:
    from app.core.rate_limit import SlidingWindowLimiter

    limiter = SlidingWindowLimiter(limit=3, window_seconds=60)
    assert limiter.allow("tenant:a")[0] is True
    assert limiter.allow("tenant:a")[0] is True
    allowed, remaining, _ = limiter.allow("tenant:a")
    assert allowed is True and remaining == 0
    allowed, remaining, retry_after = limiter.allow("tenant:a")
    assert allowed is False and remaining == 0 and retry_after >= 1
    # A different key is unaffected.
    assert limiter.allow("tenant:b")[0] is True


async def test_auth_endpoints_use_a_stricter_ip_limiter() -> None:
    """Credential endpoints get their own, smaller per-IP budget."""
    from app.core.rate_limit import SlidingWindowLimiter
    from app.middleware.rate_limit import RateLimitMiddleware

    async def ok_app(scope, receive, send) -> None:  # pragma: no cover - trivial
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"{}"})

    middleware = RateLimitMiddleware(
        ok_app,
        limiter=SlidingWindowLimiter(limit=1000, window_seconds=60),
        auth_limiter=SlidingWindowLimiter(limit=2, window_seconds=60),
    )
    sent: list[dict] = []

    async def send(message: dict) -> None:
        sent.append(message)

    async def receive() -> dict:
        return {"type": "http.request", "body": b"", "more_body": False}

    auth_scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/auth/login",
        "headers": [],
        "client": ("203.0.113.9", 12345),
    }

    for _ in range(2):
        await middleware(auth_scope, receive, send)
    assert all(m.get("status") != 429 for m in sent if m["type"] == "http.response.start")

    await middleware(auth_scope, receive, send)
    statuses = [m.get("status") for m in sent if m["type"] == "http.response.start"]
    assert statuses[-1] == 429

    # The general API limiter is untouched by the auth budget.
    general_scope = {**auth_scope, "path": "/api/v1/expenses"}
    await middleware(general_scope, receive, send)
    statuses = [m.get("status") for m in sent if m["type"] == "http.response.start"]
    assert statuses[-1] == 200


def test_password_verification_never_raises_on_garbage_hash() -> None:
    assert verify_password("whatever", "not-a-bcrypt-hash") is False


def test_token_contains_no_password_material() -> None:
    token = create_access_token(subject=uuid.uuid4(), tenant_id=uuid.uuid4(), role="owner")
    claims = decode_token(token, expected_type="access")
    assert set(claims) == {"sub", "tid", "role", "typ", "iat", "exp", "jti"}


def test_time_budget_of_crypto_helpers() -> None:
    # Sanity: hashing + verification must stay fast enough for the hot login path.
    started = time.perf_counter()
    hashed = hash_password("Benchmark-123!")
    verify_password("Benchmark-123!", hashed)
    elapsed = time.perf_counter() - started
    assert elapsed < 2.0
