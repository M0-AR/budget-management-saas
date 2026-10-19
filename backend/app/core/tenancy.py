"""Tenant context primitives.

The verified principal is attached to ``request.state`` by the request
context middleware (``app/middleware/request_context.py``) and mirrored in
a ``ContextVar`` so that repositories deep in the call stack can assert
that a tenant is pinned before touching tenant-owned tables.
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Principal:
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    role: str


class TenantContextMissing(RuntimeError):
    """Raised when tenant-owned data is accessed without a tenant pinned."""


_current_tenant_id: ContextVar[uuid.UUID | None] = ContextVar("current_tenant_id", default=None)
_current_request_id: ContextVar[str | None] = ContextVar("current_request_id", default=None)


def set_current_tenant(tenant_id: uuid.UUID | None) -> object:
    return _current_tenant_id.set(tenant_id)


def reset_current_tenant(token: object) -> None:
    _current_tenant_id.reset(token)  # type: ignore[arg-type]


def current_tenant_id() -> uuid.UUID | None:
    return _current_tenant_id.get()


def require_current_tenant() -> uuid.UUID:
    tenant_id = _current_tenant_id.get()
    if tenant_id is None:
        raise TenantContextMissing(
            "No tenant context is pinned for this request; refusing to touch "
            "tenant-owned data."
        )
    return tenant_id


def set_current_request_id(request_id: str | None) -> object:
    return _current_request_id.set(request_id)


def reset_current_request_id(token: object) -> None:
    _current_request_id.reset(token)  # type: ignore[arg-type]


def current_request_id() -> str | None:
    return _current_request_id.get()
