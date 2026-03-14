"""Tests for the in-memory auth client."""

from __future__ import annotations

import pytest

from supabase_py_lite import create_client
from supabase_py_lite.auth import AuthClient, AuthError, AuthResponse, UserResponse


@pytest.fixture()
def auth() -> AuthClient:
    return create_client(":memory:").auth


# ---------------------------------------------------------------------------
# sign_up
# ---------------------------------------------------------------------------


class TestSignUp:
    def test_sign_up_returns_user_and_session(self, auth: AuthClient) -> None:
        resp = auth.sign_up({"email": "alice@example.com", "password": "hunter2"})
        assert isinstance(resp, AuthResponse)
        assert resp.user is not None
        assert resp.user.email == "alice@example.com"
        assert resp.session is not None
        assert resp.session.access_token

    def test_sign_up_sets_current_session(self, auth: AuthClient) -> None:
        auth.sign_up({"email": "alice@example.com", "password": "hunter2"})
        assert auth.get_session() is not None

    def test_sign_up_auto_confirms_email(self, auth: AuthClient) -> None:
        resp = auth.sign_up({"email": "alice@example.com", "password": "hunter2"})
        assert resp.user is not None
        assert resp.user.email_confirmed_at is not None

    def test_sign_up_stores_user_metadata(self, auth: AuthClient) -> None:
        resp = auth.sign_up({
            "email": "alice@example.com",
            "password": "hunter2",
            "options": {"data": {"name": "Alice"}},
        })
        assert resp.user is not None
        assert resp.user.user_metadata == {"name": "Alice"}

    def test_sign_up_duplicate_email_raises(self, auth: AuthClient) -> None:
        auth.sign_up({"email": "alice@example.com", "password": "hunter2"})
        with pytest.raises(AuthError, match="already registered"):
            auth.sign_up({"email": "alice@example.com", "password": "other"})

    def test_sign_up_assigns_unique_ids(self, auth: AuthClient) -> None:
        r1 = auth.sign_up({"email": "a@example.com", "password": "p"})
        auth2 = create_client(":memory:").auth
        r2 = auth2.sign_up({"email": "a@example.com", "password": "p"})
        assert r1.user is not None and r2.user is not None
        assert r1.user.id != r2.user.id


# ---------------------------------------------------------------------------
# sign_in_with_password
# ---------------------------------------------------------------------------


class TestSignInWithPassword:
    def test_sign_in_returns_auth_response(self, auth: AuthClient) -> None:
        auth.sign_up({"email": "alice@example.com", "password": "hunter2"})
        auth.sign_out()
        resp = auth.sign_in_with_password({"email": "alice@example.com", "password": "hunter2"})
        assert resp.user is not None
        assert resp.session is not None

    def test_wrong_password_raises(self, auth: AuthClient) -> None:
        auth.sign_up({"email": "alice@example.com", "password": "hunter2"})
        auth.sign_out()
        with pytest.raises(AuthError, match="Invalid login credentials"):
            auth.sign_in_with_password({"email": "alice@example.com", "password": "wrong"})

    def test_unknown_email_raises(self, auth: AuthClient) -> None:
        with pytest.raises(AuthError, match="Invalid login credentials"):
            auth.sign_in_with_password({"email": "nobody@example.com", "password": "x"})

    def test_missing_email_and_phone_raises(self, auth: AuthClient) -> None:
        with pytest.raises(AuthError, match="required"):
            auth.sign_in_with_password({"password": "x"})

    def test_sign_in_updates_last_sign_in(self, auth: AuthClient) -> None:
        auth.sign_up({"email": "alice@example.com", "password": "hunter2"})
        auth.sign_out()
        resp = auth.sign_in_with_password({"email": "alice@example.com", "password": "hunter2"})
        assert resp.user is not None
        assert resp.user.last_sign_in_at is not None


# ---------------------------------------------------------------------------
# sign_in_with_otp
# ---------------------------------------------------------------------------


class TestSignInWithOTP:
    def test_otp_creates_user_on_first_call(self, auth: AuthClient) -> None:
        resp = auth.sign_in_with_otp({"email": "new@example.com"})
        assert resp.user is not None
        assert resp.user.email == "new@example.com"

    def test_otp_reuses_existing_user(self, auth: AuthClient) -> None:
        r1 = auth.sign_up({"email": "alice@example.com", "password": "p"})
        auth.sign_out()
        r2 = auth.sign_in_with_otp({"email": "alice@example.com"})
        assert r1.user is not None and r2.user is not None
        assert r1.user.id == r2.user.id

    def test_otp_missing_credentials_raises(self, auth: AuthClient) -> None:
        with pytest.raises(AuthError, match="required"):
            auth.sign_in_with_otp({})


# ---------------------------------------------------------------------------
# sign_out / get_session
# ---------------------------------------------------------------------------


class TestSignOut:
    def test_sign_out_clears_session(self, auth: AuthClient) -> None:
        auth.sign_up({"email": "alice@example.com", "password": "p"})
        auth.sign_out()
        assert auth.get_session() is None

    def test_sign_out_twice_is_safe(self, auth: AuthClient) -> None:
        auth.sign_up({"email": "alice@example.com", "password": "p"})
        auth.sign_out()
        auth.sign_out()  # should not raise


# ---------------------------------------------------------------------------
# get_user
# ---------------------------------------------------------------------------


class TestGetUser:
    def test_get_user_when_signed_in(self, auth: AuthClient) -> None:
        auth.sign_up({"email": "alice@example.com", "password": "p"})
        resp = auth.get_user()
        assert isinstance(resp, UserResponse)
        assert resp.user is not None
        assert resp.user.email == "alice@example.com"

    def test_get_user_when_not_signed_in_raises(self, auth: AuthClient) -> None:
        with pytest.raises(AuthError, match="Not authenticated"):
            auth.get_user()

    def test_get_user_with_valid_jwt(self, auth: AuthClient) -> None:
        resp = auth.sign_up({"email": "alice@example.com", "password": "p"})
        assert resp.session is not None
        token = resp.session.access_token
        auth.sign_out()
        user_resp = auth.get_user(jwt=token)
        assert user_resp.user is not None
        assert user_resp.user.email == "alice@example.com"

    def test_get_user_with_invalid_jwt_raises(self, auth: AuthClient) -> None:
        with pytest.raises(AuthError, match="Invalid JWT"):
            auth.get_user(jwt="not-a-real-token")


# ---------------------------------------------------------------------------
# set_session / refresh_session
# ---------------------------------------------------------------------------


class TestSessionManagement:
    def test_set_session_restores_session(self, auth: AuthClient) -> None:
        resp = auth.sign_up({"email": "alice@example.com", "password": "p"})
        assert resp.session is not None
        access = resp.session.access_token
        refresh = resp.session.refresh_token
        auth.sign_out()
        auth.set_session(access, refresh)
        assert auth.get_session() is not None

    def test_set_session_invalid_token_raises(self, auth: AuthClient) -> None:
        with pytest.raises(AuthError, match="Invalid access token"):
            auth.set_session("bad", "token")

    def test_refresh_session_returns_new_tokens(self, auth: AuthClient) -> None:
        auth.sign_up({"email": "alice@example.com", "password": "p"})
        old_session = auth.get_session()
        assert old_session is not None
        resp = auth.refresh_session()
        new_session = resp.session
        assert new_session is not None
        assert new_session.access_token != old_session.access_token
        assert new_session.refresh_token != old_session.refresh_token

    def test_refresh_session_with_explicit_token(self, auth: AuthClient) -> None:
        resp = auth.sign_up({"email": "alice@example.com", "password": "p"})
        assert resp.session is not None
        rt = resp.session.refresh_token
        new_resp = auth.refresh_session(refresh_token=rt)
        assert new_resp.user is not None
        assert new_resp.user.email == "alice@example.com"

    def test_refresh_session_invalid_token_raises(self, auth: AuthClient) -> None:
        with pytest.raises(AuthError, match="Invalid refresh token"):
            auth.refresh_session(refresh_token="bad-token")

    def test_refresh_session_no_session_raises(self, auth: AuthClient) -> None:
        with pytest.raises(AuthError, match="No active session"):
            auth.refresh_session()


# ---------------------------------------------------------------------------
# update_user
# ---------------------------------------------------------------------------


class TestUpdateUser:
    def test_update_email(self, auth: AuthClient) -> None:
        auth.sign_up({"email": "alice@example.com", "password": "p"})
        resp = auth.update_user({"email": "new@example.com"})
        assert resp.user is not None
        assert resp.user.email == "new@example.com"

    def test_update_password_allows_new_sign_in(self, auth: AuthClient) -> None:
        auth.sign_up({"email": "alice@example.com", "password": "old"})
        auth.update_user({"password": "new"})
        auth.sign_out()
        resp = auth.sign_in_with_password({"email": "alice@example.com", "password": "new"})
        assert resp.user is not None

    def test_update_user_metadata(self, auth: AuthClient) -> None:
        auth.sign_up({"email": "alice@example.com", "password": "p"})
        resp = auth.update_user({"data": {"role": "admin"}})
        assert resp.user is not None
        assert resp.user.user_metadata["role"] == "admin"

    def test_update_user_not_signed_in_raises(self, auth: AuthClient) -> None:
        with pytest.raises(AuthError, match="Not authenticated"):
            auth.update_user({"email": "x@example.com"})


# ---------------------------------------------------------------------------
# reset_password_for_email
# ---------------------------------------------------------------------------


class TestResetPassword:
    def test_reset_password_does_not_raise(self, auth: AuthClient) -> None:
        auth.sign_up({"email": "alice@example.com", "password": "p"})
        # Should succeed silently
        auth.reset_password_for_email("alice@example.com")


# ---------------------------------------------------------------------------
# Admin operations
# ---------------------------------------------------------------------------


class TestAdminAuth:
    def test_admin_list_users_empty(self, auth: AuthClient) -> None:
        assert auth.admin.list_users() == []

    def test_admin_list_users(self, auth: AuthClient) -> None:
        auth.sign_up({"email": "a@example.com", "password": "p"})
        auth.admin.create_user({"email": "b@example.com", "password": "p"})
        users = auth.admin.list_users()
        emails = {u.email for u in users}
        assert "a@example.com" in emails
        assert "b@example.com" in emails

    def test_admin_create_user(self, auth: AuthClient) -> None:
        resp = auth.admin.create_user({"email": "admin@example.com", "password": "secret"})
        assert resp.user is not None
        assert resp.user.email == "admin@example.com"
        assert resp.user.email_confirmed_at is not None

    def test_admin_create_duplicate_raises(self, auth: AuthClient) -> None:
        auth.admin.create_user({"email": "x@example.com", "password": "p"})
        with pytest.raises(AuthError, match="already registered"):
            auth.admin.create_user({"email": "x@example.com", "password": "p"})

    def test_admin_get_user_by_id(self, auth: AuthClient) -> None:
        resp = auth.admin.create_user({"email": "x@example.com"})
        assert resp.user is not None
        uid = resp.user.id
        user_resp = auth.admin.get_user_by_id(uid)
        assert user_resp.user is not None
        assert user_resp.user.id == uid

    def test_admin_get_user_by_id_not_found(self, auth: AuthClient) -> None:
        with pytest.raises(AuthError, match="not found"):
            auth.admin.get_user_by_id("00000000-0000-0000-0000-000000000000")

    def test_admin_update_user_by_id(self, auth: AuthClient) -> None:
        resp = auth.admin.create_user({"email": "x@example.com"})
        assert resp.user is not None
        uid = resp.user.id
        updated = auth.admin.update_user_by_id(uid, {"email": "y@example.com"})
        assert updated.user is not None
        assert updated.user.email == "y@example.com"

    def test_admin_delete_user(self, auth: AuthClient) -> None:
        resp = auth.admin.create_user({"email": "x@example.com"})
        assert resp.user is not None
        uid = resp.user.id
        auth.admin.delete_user(uid)
        with pytest.raises(AuthError, match="not found"):
            auth.admin.get_user_by_id(uid)

    def test_admin_delete_nonexistent_raises(self, auth: AuthClient) -> None:
        with pytest.raises(AuthError, match="not found"):
            auth.admin.delete_user("00000000-0000-0000-0000-000000000000")
