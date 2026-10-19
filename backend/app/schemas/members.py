"""Workspace member and invitation schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import EmailStr, ORMModel

# Roles that can be granted through member management. "owner" is excluded:
# ownership is fixed at workspace creation (no silent transfers).
AssignableRole = Literal["admin", "member", "viewer"]


class MemberOut(ORMModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    created_at: datetime


class MemberRoleUpdate(BaseModel):
    role: AssignableRole


class InviteCreate(BaseModel):
    email: EmailStr
    role: AssignableRole = "member"


class InviteOut(ORMModel):
    id: uuid.UUID
    email: str
    role: str
    expires_at: datetime
    created_at: datetime


class InviteCreated(InviteOut):
    """Creation response: the only time the plaintext token is exposed."""

    token: str = Field(min_length=20)
