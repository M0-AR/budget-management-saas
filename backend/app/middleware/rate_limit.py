"""Per-tenant rate limiting middleware.

Keys on the tenant id when a verifiable access token is present, otherwise
on the client IP. Responses advertise their budget via ``X-RateLimit-*``
headers and a 429 carries ``Retry-After`` (RFC 9110).

Credential endpoints (login/register/refresh/logout) get a *separate,
stricter* budget keyed by client IP — the standard brute-force /
credential-stuffing defense (OWASP recommends stricter limits for
authentication endpoints than for the general API surface).

Health probes and CORS preflights are exempt.
"""

from __future__ import annotations

import json

from app.core.rate_limit import SlidingWindowLimiter
from app.middleware._asgi import Receive, Scope, Send, append_header, scope_state, send_json
from app.middleware.request_context import parse_bearer_principal

_EXEMPT_PATHS = {"/healthz", "/readyz", "/docs", "/openapi.json", "/redoc"}

_AUTH_PATHS = {
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/auth/refresh",
    "/api/v1/auth/logout",
}


class RateLimitMiddleware:
    def __init__(
        self,
        app,
        *,
        limiter: SlidingWindowLimiter,
        auth_limiter: SlidingWindowLimiter | None = None,
    ):
        self.app = app
        self.limiter = limiter
        self.auth_limiter = auth_limiter

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method") == "OPTIONS":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path in _EXEMPT_PATHS or path.startswith("/docs/"):
            await self.app(scope, receive, send)
            return

        client = scope.get("client")
        client_ip = client[0] if client else "unknown"

        if self.auth_limiter is not None and path in _AUTH_PATHS:
            limiter = self.auth_limiter
            key = f"auth:{client_ip}"
        else:
            limiter = self.limiter
            headers = {
                k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])
            }
            principal = parse_bearer_principal(headers.get("authorization"))
            if principal is not None:
                key = f"tenant:{principal.tenant_id}"
            else:
                key = f"ip:{client_ip}"

        allowed, remaining, retry_after = limiter.allow(key)
        limit = str(limiter.limit)

        if not allowed:
            body = json.dumps(
                {
                    "detail": "Too many requests. Please slow down and retry shortly.",
                    "code": "rate_limited",
                }
            ).encode()
            await send_json(
                send,
                status=429,
                headers=[
                    (b"retry-after", str(retry_after).encode()),
                    (b"x-ratelimit-limit", limit.encode()),
                    (b"x-ratelimit-remaining", b"0"),
                ],
                body=body,
            )
            return

        async def send_wrapper(message: dict) -> None:
            if message["type"] == "http.response.start":
                append_header(message, b"x-ratelimit-limit", limit.encode())
                append_header(message, b"x-ratelimit-remaining", str(remaining).encode())
            await send(message)

        await self.app(scope, receive, send_wrapper)
