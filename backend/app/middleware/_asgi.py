"""Shared helpers for pure-ASGI middleware."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

Message = dict[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
Scope = dict[str, Any]


def scope_state(scope: Scope) -> dict[str, Any]:
    """Return the mutable per-request state dict (Starlette's Request.state)."""
    if scope["type"] == "http" and "state" not in scope:
        scope["state"] = {}
    return scope.get("state", {})


def append_header(message: Message, name: bytes, value: bytes) -> None:
    headers = message.setdefault("headers", [])
    headers.append((name, value))


async def send_json(
    send: Send,
    *,
    status: int,
    headers: list[tuple[bytes, bytes]] | None = None,
    body: bytes = b"",
) -> None:
    header_list = [(b"content-type", b"application/json")]
    header_list.extend(headers or [])
    header_list.append((b"content-length", str(len(body)).encode()))
    await send({"type": "http.response.start", "status": status, "headers": header_list})
    await send({"type": "http.response.body", "body": body})
