"""Request context middleware (pure ASGI).

Responsibilities, in order:
1. Assign a request id (honouring an inbound ``X-Request-ID``) and echo it
   back on the response.
2. Parse the ``Authorization: Bearer`` access token, if present, into a
   verified :class:`Principal` stored on ``request.state`` (and mirrored in
   the tenant ContextVar down the call stack).
3. Emit one structured access-log line per request.

An invalid/expired token is *not* rejected here: that is the auth
dependency's job. This middleware only makes verified identity available;
endpoints decide whether it is required.
"""

from __future__ import annotations

import logging
import time
import uuid

from app.core.security import decode_token
from app.core.tenancy import (
    Principal,
    reset_current_request_id,
    reset_current_tenant,
    set_current_request_id,
    set_current_tenant,
)
from app.middleware._asgi import Receive, Scope, Send, append_header, scope_state

logger = logging.getLogger("app.access")


def parse_bearer_principal(authorization: str | None) -> Principal | None:
    """Return the verified principal for a Bearer header, or None."""
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization[7:].strip()
    try:
        payload = decode_token(token, expected_type="access")
        return Principal(
            user_id=uuid.UUID(payload["sub"]),
            tenant_id=uuid.UUID(payload["tid"]),
            role=str(payload.get("role", "member")),
        )
    except Exception:
        return None


class RequestContextMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
        request_id = headers.get("x-request-id") or uuid.uuid4().hex
        principal = parse_bearer_principal(headers.get("authorization"))

        state = scope_state(scope)
        state["request_id"] = request_id
        state["principal"] = principal

        tenant_token = set_current_tenant(principal.tenant_id if principal else None)
        request_token = set_current_request_id(request_id)

        status_holder = {"status": 500}
        started = time.perf_counter()

        async def send_wrapper(message: dict) -> None:
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
                append_header(message, b"x-request-id", request_id.encode())
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = (time.perf_counter() - started) * 1000
            tenant_label = str(principal.tenant_id) if principal else "-"
            logger.info(
                "request method=%s path=%s status=%s duration_ms=%.1f tenant=%s request_id=%s",
                scope.get("method"),
                scope.get("path"),
                status_holder["status"],
                duration_ms,
                tenant_label,
                request_id,
            )
            reset_current_request_id(request_token)
            reset_current_tenant(tenant_token)
