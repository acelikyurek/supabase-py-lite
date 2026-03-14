from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class APIResponse:
    """Mirrors the Supabase APIResponse interface."""

    data: list[dict[str, Any]] = field(default_factory=list)
    count: Optional[int] = None
    error: Optional[APIError] = None


@dataclass
class APIError:
    message: str
    code: Optional[str] = None
    details: Optional[str] = None
    hint: Optional[str] = None
