"""Shared FastAPI dependencies: identity, RBAC, pagination."""

from __future__ import annotations

import uuid
from collections.abc import Callable

from fastapi import Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AuthenticationError, PermissionDeniedError
from app.core.tenancy import Principal
from app.models import User

WRITE_ROLES = ("owner", "admin", "member")
ADMIN_ROLES = ("owner", "admin")


def get_principal(request: Request) -> Principal:
    principal: Principal | None = getattr(request.state, "principal", None)
    if principal is None:
        raise AuthenticationError("Sign in to continue")
    return principal


async def get_current_user(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_db),
) -> User:
    user = (
        await session.execute(
            select(User).where(User.id == principal.user_id, User.tenant_id == principal.tenant_id)
        )
    ).scalar_one_or_none()
    if user is None or not user.is_active:
        raise AuthenticationError("Account is no longer active")
    return user


def require_roles(*roles: str) -> Callable[[User], User]:
    async def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise PermissionDeniedError("Your role does not allow this action")
        return user

    return dependency


require_writer = require_roles(*WRITE_ROLES)
require_admin = require_roles(*ADMIN_ROLES)


class Pagination:
    def __init__(
        self,
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=50, ge=1, le=100),
    ):
        self.page = page
        self.page_size = page_size


def user_id_of(user: User) -> uuid.UUID:
    return user.id
