"""Tests for .or_() and .not_() filter methods."""
from __future__ import annotations

import pytest

from supabase_py_lite import Client, create_client


@pytest.fixture
def client() -> Client:
    c = create_client(":memory:")
    c.from_("users").insert(
        [
            {"id": 1, "name": "Alice", "age": 30, "active": 1},
            {"id": 2, "name": "Bob", "age": 25, "active": 1},
            {"id": 3, "name": "Charlie", "age": 35, "active": 0},
            {"id": 4, "name": "Diana", "age": 28, "active": 0},
        ]
    ).execute()
    yield c  # type: ignore[misc]
    c.close()


# ---------------------------------------------------------------------------
# .or_()
# ---------------------------------------------------------------------------


def test_or_eq(client: Client) -> None:
    resp = client.from_("users").select("name").or_("name.eq.Alice,name.eq.Bob").execute()
    names = {r["name"] for r in resp.data}
    assert names == {"Alice", "Bob"}


def test_or_mixed_ops(client: Client) -> None:
    resp = client.from_("users").select("name").or_("name.eq.Alice,age.gt.30").execute()
    names = {r["name"] for r in resp.data}
    assert names == {"Alice", "Charlie"}


def test_or_with_and(client: Client) -> None:
    # active=1 AND (name=Alice OR age>30)
    resp = (
        client.from_("users")
        .select("name")
        .eq("active", 1)
        .or_("name.eq.Alice,age.gt.30")
        .execute()
    )
    names = {r["name"] for r in resp.data}
    assert names == {"Alice"}


def test_or_in(client: Client) -> None:
    resp = client.from_("users").select("name").or_("id.in.(1,3)").execute()
    names = {r["name"] for r in resp.data}
    assert names == {"Alice", "Charlie"}


def test_or_is_null(client: Client) -> None:
    # Insert a row with null name
    client.from_("users").insert({"id": 5, "name": None, "age": 20}).execute()
    resp = (
        client.from_("users")
        .select("id")
        .or_("id.eq.1,name.is.null")
        .execute()
    )
    ids = {r["id"] for r in resp.data}
    assert ids == {1, 5}


def test_or_no_match(client: Client) -> None:
    resp = (
        client.from_("users")
        .select("name")
        .or_("name.eq.Nobody,age.eq.999")
        .execute()
    )
    assert resp.data == []


# ---------------------------------------------------------------------------
# .not_()
# ---------------------------------------------------------------------------


def test_not_eq(client: Client) -> None:
    resp = client.from_("users").select("name").not_("name", "eq", "Alice").execute()
    names = {r["name"] for r in resp.data}
    assert "Alice" not in names
    assert len(names) == 3


def test_not_gt(client: Client) -> None:
    resp = client.from_("users").select("name").not_("age", "gt", 28).execute()
    names = {r["name"] for r in resp.data}
    assert names == {"Bob", "Diana"}


def test_not_in(client: Client) -> None:
    resp = (
        client.from_("users")
        .select("name")
        .not_("id", "in", [1, 2])
        .execute()
    )
    names = {r["name"] for r in resp.data}
    assert names == {"Charlie", "Diana"}


def test_not_combined_with_eq(client: Client) -> None:
    # active=1 AND NOT name=Bob
    resp = (
        client.from_("users")
        .select("name")
        .eq("active", 1)
        .not_("name", "eq", "Bob")
        .execute()
    )
    names = {r["name"] for r in resp.data}
    assert names == {"Alice"}


# ---------------------------------------------------------------------------
# .not_() works on update and delete too
# ---------------------------------------------------------------------------


def test_not_on_delete(client: Client) -> None:
    client.from_("users").delete().not_("name", "eq", "Alice").execute()
    resp = client.from_("users").select("name").execute()
    assert resp.data == [{"name": "Alice"}]


def test_or_on_update(client: Client) -> None:
    client.from_("users").update({"active": 0}).or_("name.eq.Alice,name.eq.Bob").execute()
    resp = (
        client.from_("users")
        .select("name")
        .eq("active", 0)
        .order("name")
        .execute()
    )
    names = [r["name"] for r in resp.data]
    assert "Alice" in names and "Bob" in names
