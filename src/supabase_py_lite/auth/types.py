"""Auth types mirroring gotrue-py / supabase-py structures."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class User:
    id: str
    email: Optional[str] = None
    phone: Optional[str] = None
    role: str = "authenticated"
    email_confirmed_at: Optional[str] = None
    phone_confirmed_at: Optional[str] = None
    confirmed_at: Optional[str] = None
    last_sign_in_at: Optional[str] = None
    app_metadata: dict[str, Any] = field(default_factory=dict)
    user_metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def __repr__(self) -> str:
        return f"<User id={self.id!r} email={self.email!r}>"


@dataclass
class Session:
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 3600
    expires_at: Optional[int] = None
    user: Optional[User] = None

    def __repr__(self) -> str:
        return f"<Session access_token={self.access_token[:8]}... user={self.user!r}>"


@dataclass
class AuthResponse:
    """Returned by sign_up, sign_in_with_password, refresh_session."""

    user: Optional[User] = None
    session: Optional[Session] = None


@dataclass
class UserResponse:
    """Returned by get_user and update_user."""

    user: Optional[User] = None
