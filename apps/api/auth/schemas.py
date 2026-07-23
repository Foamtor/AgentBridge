"""Auth-related response schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class AuthErrorDetail(BaseModel):
    code: str = "unauthorized"
    message: str
    extra: dict[str, Any] | None = None
