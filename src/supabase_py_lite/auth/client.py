"""In-memory auth client mirroring supabase-py's auth API."""

from __future__ import annotations

import hashlib
import time
import uuid
from typing import Any, Optional

from ..exceptions import SupabaseLiteError
from .types import AuthResponse, Session, User, UserResponse


class AuthError(SupabaseLiteError):
    """Raised when an auth operation fails."""

    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status = status

    def __repr__(self) -> str:
        return f"AuthError(message={self.message!r}, status={self.status})"


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _now_ts() -> int:
    return int(time.time())


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def _make_tokens() -> tuple[str, str]:
    return str(uuid.uuid4()), str(uuid.uuid4())


class AdminAuthClient:
    """Admin-level auth operations. Accessed via client.auth.admin."""

    def __init__(self, store: "_AuthStore") -> None:
        self._store = store

    def list_users(self) -> list[User]:
        """Return all registered users."""
        return [record["user"] for record in self._store.users.values()]

    def get_user_by_id(self, uid: str) -> UserResponse:
        """Fetch a user by their UUID."""
        record = self._store.users_by_id.get(uid)
        if record is None:
            raise AuthError(f"User not found: {uid}", status=404)
        return UserResponse(user=record["user"])

    def create_user(self, attributes: dict[str, Any]) -> UserResponse:
        """Create a user without email confirmation (admin bypass)."""
        email: Optional[str] = attributes.get("email")
        phone: Optional[str] = attributes.get("phone")
        password: Optional[str] = attributes.get("password")
        user_metadata: dict[str, Any] = attributes.get("user_metadata", {})
        app_metadata: dict[str, Any] = attributes.get("app_metadata", {})
        role: str = attributes.get("role", "authenticated")
        email_confirm: bool = attributes.get("email_confirm", True)

        if email and email in self._store.users:
            raise AuthError("User already registered", status=422)

        now = _now_iso()
        user = User(
            id=str(uuid.uuid4()),
            email=email,
            phone=phone,
            role=role,
            email_confirmed_at=now if email_confirm and email else None,
            confirmed_at=now if email_confirm and email else None,
            user_metadata=user_metadata,
            app_metadata=app_metadata,
            created_at=now,
            updated_at=now,
        )
        self._store._save_user(user, password=password)
        return UserResponse(user=user)

    def update_user_by_id(self, uid: str, attributes: dict[str, Any]) -> UserResponse:
        """Update an arbitrary user by ID."""
        record = self._store.users_by_id.get(uid)
        if record is None:
            raise AuthError(f"User not found: {uid}", status=404)

        user: User = record["user"]
        now = _now_iso()

        if "email" in attributes:
            new_email = attributes["email"]
            if new_email != user.email and new_email in self._store.users:
                raise AuthError("Email already in use", status=422)
            if user.email and user.email in self._store.users:
                del self._store.users[user.email]
            user.email = new_email
            user.email_confirmed_at = now
            user.confirmed_at = now
            if new_email:
                self._store.users[new_email] = record

        if "phone" in attributes:
            user.phone = attributes["phone"]

        if "password" in attributes:
            record["password_hash"] = _hash_password(attributes["password"])

        if "user_metadata" in attributes:
            user.user_metadata.update(attributes["user_metadata"])

        if "app_metadata" in attributes:
            user.app_metadata.update(attributes["app_metadata"])

        if "role" in attributes:
            user.role = attributes["role"]

        user.updated_at = now
        return UserResponse(user=user)

    def delete_user(self, uid: str) -> None:
        """Delete a user by ID."""
        record = self._store.users_by_id.pop(uid, None)
        if record is None:
            raise AuthError(f"User not found: {uid}", status=404)
        user = record["user"]
        if user.email and user.email in self._store.users:
            del self._store.users[user.email]
        # Revoke any sessions for this user
        tokens_to_remove = [t for t, s in self._store.sessions.items() if s.user and s.user.id == uid]
        for t in tokens_to_remove:
            del self._store.sessions[t]


class _AuthStore:
    """Shared mutable state for the auth client."""

    def __init__(self) -> None:
        # email -> {"user": User, "password_hash": str | None}
        self.users: dict[str, dict[str, Any]] = {}
        # uid -> same record
        self.users_by_id: dict[str, dict[str, Any]] = {}
        # access_token -> Session
        self.sessions: dict[str, Session] = {}
        # refresh_token -> access_token
        self.refresh_tokens: dict[str, str] = {}

    def _save_user(self, user: User, password: Optional[str] = None) -> None:
        record: dict[str, Any] = {
            "user": user,
            "password_hash": _hash_password(password) if password else None,
        }
        self.users_by_id[user.id] = record
        if user.email:
            self.users[user.email] = record

    def _create_session(self, user: User) -> Session:
        access_token, refresh_token = _make_tokens()
        now = _now_ts()
        session = Session(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=now + 3600,
            user=user,
        )
        self.sessions[access_token] = session
        self.refresh_tokens[refresh_token] = access_token
        return session


class AuthClient:
    """
    In-memory auth client with the same API as supabase-py's ``client.auth``.

    Supports:
    - sign_up / sign_in_with_password / sign_in_with_otp
    - sign_out
    - get_user / get_session
    - update_user / set_session / refresh_session
    - reset_password_for_email (no-op simulation)
    - admin operations via .admin
    """

    def __init__(self) -> None:
        self._store = _AuthStore()
        self._current_session: Optional[Session] = None
        self.admin = AdminAuthClient(self._store)

    # ------------------------------------------------------------------
    # Registration / sign-in
    # ------------------------------------------------------------------

    def sign_up(self, credentials: dict[str, Any]) -> AuthResponse:
        """
        Create a new user account.

        Args:
            credentials: dict with ``email`` and ``password`` (and optionally
                         ``phone``, ``options.data`` for user_metadata).

        Returns:
            AuthResponse with ``user`` and ``session``.

        Raises:
            AuthError: if the email is already registered.
        """
        email: Optional[str] = credentials.get("email")
        phone: Optional[str] = credentials.get("phone")
        password: Optional[str] = credentials.get("password")
        options: dict[str, Any] = credentials.get("options", {})
        user_metadata: dict[str, Any] = options.get("data", {})

        if email and email in self._store.users:
            raise AuthError("User already registered", status=422)

        now = _now_iso()
        user = User(
            id=str(uuid.uuid4()),
            email=email,
            phone=phone,
            # simulate auto-confirm for test environments
            email_confirmed_at=now if email else None,
            confirmed_at=now if email else None,
            user_metadata=user_metadata,
            created_at=now,
            updated_at=now,
        )
        self._store._save_user(user, password=password)
        session = self._store._create_session(user)
        self._current_session = session
        return AuthResponse(user=user, session=session)

    def sign_in_with_password(self, credentials: dict[str, Any]) -> AuthResponse:
        """
        Sign in with email+password or phone+password.

        Args:
            credentials: dict with (``email`` or ``phone``) and ``password``.

        Returns:
            AuthResponse with ``user`` and ``session``.

        Raises:
            AuthError: on invalid credentials.
        """
        email: Optional[str] = credentials.get("email")
        phone: Optional[str] = credentials.get("phone")
        password: str = credentials.get("password", "")

        key = email or phone
        if not key:
            raise AuthError("Email or phone is required", status=400)

        record = self._store.users.get(key) if email else None
        if record is None and phone:
            # scan for phone match
            record = next(
                (r for r in self._store.users_by_id.values() if r["user"].phone == phone),
                None,
            )

        if record is None:
            raise AuthError("Invalid login credentials", status=400)

        if record["password_hash"] != _hash_password(password):
            raise AuthError("Invalid login credentials", status=400)

        user: User = record["user"]
        now = _now_iso()
        user.last_sign_in_at = now
        user.updated_at = now

        session = self._store._create_session(user)
        self._current_session = session
        return AuthResponse(user=user, session=session)

    def sign_in_with_otp(self, credentials: dict[str, Any]) -> AuthResponse:
        """
        Sign in / sign up via magic link or phone OTP (simulated).

        In this lite implementation the OTP is accepted immediately without
        any verification step — suitable for test doubles.

        Args:
            credentials: dict with ``email`` or ``phone``, and optionally
                         ``options.data`` for user_metadata.

        Returns:
            AuthResponse with ``user`` and ``session``.
        """
        email: Optional[str] = credentials.get("email")
        phone: Optional[str] = credentials.get("phone")
        options: dict[str, Any] = credentials.get("options", {})
        user_metadata: dict[str, Any] = options.get("data", {})

        key = email or phone
        if not key:
            raise AuthError("Email or phone is required", status=400)

        record = self._store.users.get(key) if email else None
        if record is None and phone:
            record = next(
                (r for r in self._store.users_by_id.values() if r["user"].phone == phone),
                None,
            )

        now = _now_iso()
        if record is None:
            user = User(
                id=str(uuid.uuid4()),
                email=email,
                phone=phone,
                email_confirmed_at=now if email else None,
                phone_confirmed_at=now if phone else None,
                confirmed_at=now,
                user_metadata=user_metadata,
                created_at=now,
                updated_at=now,
            )
            self._store._save_user(user, password=None)
        else:
            user = record["user"]

        user.last_sign_in_at = now
        user.updated_at = now
        session = self._store._create_session(user)
        self._current_session = session
        return AuthResponse(user=user, session=session)

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def sign_out(self) -> None:
        """
        Clear the current session.

        Tokens remain valid in the store so ``get_user(jwt=...)`` and
        ``set_session`` still work after sign-out, mirroring the fact that
        in real Supabase the server-side session can be reused until it
        expires or is explicitly revoked.
        """
        self._current_session = None

    def get_session(self) -> Optional[Session]:
        """Return the currently active session, or ``None`` if not signed in."""
        return self._current_session

    def set_session(self, access_token: str, refresh_token: str) -> AuthResponse:
        """
        Manually set the active session from existing tokens.

        Raises:
            AuthError: if the access_token is not recognised.
        """
        session = self._store.sessions.get(access_token)
        if session is None:
            raise AuthError("Invalid access token", status=400)
        self._current_session = session
        return AuthResponse(user=session.user, session=session)

    def refresh_session(self, refresh_token: Optional[str] = None) -> AuthResponse:
        """
        Exchange a refresh token for a new access token.

        Args:
            refresh_token: the refresh token to exchange.  If omitted the
                           current session's refresh token is used.

        Returns:
            AuthResponse with a new Session.

        Raises:
            AuthError: if the refresh token is invalid or there is no current session.
        """
        rt = refresh_token
        if rt is None:
            if self._current_session is None:
                raise AuthError("No active session", status=400)
            rt = self._current_session.refresh_token

        old_access = self._store.refresh_tokens.get(rt)
        if old_access is None:
            raise AuthError("Invalid refresh token", status=400)

        old_session = self._store.sessions.pop(old_access, None)
        self._store.refresh_tokens.pop(rt, None)

        user = old_session.user if old_session else None
        if user is None:
            raise AuthError("User not found for refresh token", status=400)

        session = self._store._create_session(user)
        self._current_session = session
        return AuthResponse(user=user, session=session)

    # ------------------------------------------------------------------
    # User retrieval / update
    # ------------------------------------------------------------------

    def get_user(self, jwt: Optional[str] = None) -> UserResponse:
        """
        Return the user associated with the given JWT (access token), or the
        current session's user if ``jwt`` is omitted.

        Raises:
            AuthError: if not signed in / token is invalid.
        """
        if jwt is not None:
            session = self._store.sessions.get(jwt)
            if session is None:
                raise AuthError("Invalid JWT", status=401)
            return UserResponse(user=session.user)

        if self._current_session is None:
            raise AuthError("Not authenticated", status=401)
        return UserResponse(user=self._current_session.user)

    def update_user(self, attributes: dict[str, Any]) -> UserResponse:
        """
        Update the current user's attributes.

        Args:
            attributes: dict with any of ``email``, ``phone``, ``password``,
                        ``data`` (merges into ``user_metadata``).

        Returns:
            UserResponse with the updated User.

        Raises:
            AuthError: if not signed in.
        """
        if self._current_session is None or self._current_session.user is None:
            raise AuthError("Not authenticated", status=401)

        user = self._current_session.user
        record = self._store.users_by_id.get(user.id)
        if record is None:
            raise AuthError("User record not found", status=404)

        now = _now_iso()

        if "email" in attributes:
            new_email = attributes["email"]
            if new_email != user.email and new_email in self._store.users:
                raise AuthError("Email already in use", status=422)
            if user.email and user.email in self._store.users:
                del self._store.users[user.email]
            user.email = new_email
            user.email_confirmed_at = now
            user.confirmed_at = now
            if new_email:
                self._store.users[new_email] = record

        if "phone" in attributes:
            user.phone = attributes["phone"]

        if "password" in attributes:
            record["password_hash"] = _hash_password(attributes["password"])

        if "data" in attributes:
            user.user_metadata.update(attributes["data"])

        user.updated_at = now
        return UserResponse(user=user)

    # ------------------------------------------------------------------
    # Password reset (simulation)
    # ------------------------------------------------------------------

    def reset_password_for_email(self, email: str, options: Optional[dict[str, Any]] = None) -> None:  # noqa: ARG002
        """
        Simulate sending a password-reset email.

        In this lite implementation the call always succeeds silently — no
        email is actually sent.  Use ``admin.update_user_by_id`` to directly
        set a new password in tests.
        """
        # no-op for testing; real implementation would send an email
        return None
