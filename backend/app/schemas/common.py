"""Shared schema primitives."""

from __future__ import annotations

import re
from typing import Annotated, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

T = TypeVar("T")

# Lenient-but-safe email shape check (deliberately no extra dependency).
EMAIL_PATTERN = r"^[^@\s]{1,128}@[^@\s]{1,120}\.[A-Za-z]{2,24}$"
EMAIL_REGEX = re.compile(EMAIL_PATTERN)

SLUG_PATTERN = r"^[a-z0-9](?:[a-z0-9-]{1,38})[a-z0-9]$"  # 3-40 chars, no edge hyphens
HEX_COLOR_PATTERN = r"^#[0-9a-fA-F]{6}$"

EmailStr = Annotated[
    str,
    StringConstraints(strip_whitespace=True, to_lower=True, min_length=5, max_length=255, pattern=EMAIL_PATTERN),
]
SlugStr = Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True, pattern=SLUG_PATTERN)]
HexColor = Annotated[str, StringConstraints(pattern=HEX_COLOR_PATTERN)]


class ORMModel(BaseModel):
    """Base for response models built from SQLAlchemy objects."""

    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
