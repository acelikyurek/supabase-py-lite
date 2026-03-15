"""Tests for foreign key support and embedded select queries."""
from __future__ import annotations

import pytest

from supabase_py_lite import Client, QueryError, create_client


@pytest.fixture
def fk_client() -> Client:
    c = create_client(":memory:")

    # Seed users
    c.from_("users").insert(
        [
            {"id": 1, "name": "Alice", "email": "alice@test.com"},
            {"id": 2, "name": "Bob", "email": "bob@test.com"},
        ]
    ).execute()

    # Seed posts (posts.user_id -> users.id)
    c.from_("posts").insert(
        [
            {"id": 1, "title": "Hello World", "user_id": 1},
            {"id": 2, "title": "Second Post", "user_id": 1},
            {"id": 3, "title": "Bob's Post", "user_id": 2},
        ]
    ).execute()

    # Seed comments (comments.post_id -> posts.id)
    c.from_("comments").insert(
        [
            {"id": 1, "body": "Great post!", "post_id": 1},
            {"id": 2, "body": "Thanks!", "post_id": 1},
            {"id": 3, "body": "Nice!", "post_id": 2},
        ]
    ).execute()

    # Register FK relationships
    c.define_foreign_key("posts", "user_id", "users")
    c.define_foreign_key("comments", "post_id", "posts")

    yield c  # type: ignore[misc]
    c.close()


# ---------------------------------------------------------------------------
# Many-to-one (outgoing FK): posts -> users
# ---------------------------------------------------------------------------


def test_many_to_one_basic(fk_client: Client) -> None:
    resp = fk_client.from_("posts").select("id, title, users(name)").execute()
    assert resp.data is not None
    rows = resp.data
    assert len(rows) == 3
    # user_id not selected → not in result; identify rows by embedded user name
    alice_posts = [r for r in rows if r["users"] and r["users"]["name"] == "Alice"]
    assert len(alice_posts) == 2
    bob_post = next(r for r in rows if r["users"] and r["users"]["name"] == "Bob")
    assert bob_post["title"] == "Bob's Post"
    # join column should not leak into result
    assert "user_id" not in rows[0]


def test_many_to_one_multiple_columns(fk_client: Client) -> None:
    resp = fk_client.from_("posts").select("id, users(name, email)").execute()
    rows = resp.data
    assert rows[0]["users"] == {"name": "Alice", "email": "alice@test.com"}


def test_many_to_one_wildcard_main(fk_client: Client) -> None:
    resp = fk_client.from_("posts").select("*, users(name)").execute()
    rows = resp.data
    assert all("users" in r for r in rows)
    assert all("id" in r and "title" in r and "user_id" in r for r in rows)


def test_many_to_one_null_fk(fk_client: Client) -> None:
    fk_client.from_("posts").insert({"id": 99, "title": "No author", "user_id": None}).execute()
    resp = fk_client.from_("posts").select("id, users(name)").eq("id", 99).execute()
    assert resp.data[0]["users"] is None


# ---------------------------------------------------------------------------
# Alias syntax: author:users(name)
# ---------------------------------------------------------------------------


def test_alias_syntax(fk_client: Client) -> None:
    resp = fk_client.from_("posts").select("id, author:users(name)").execute()
    rows = resp.data
    assert "author" in rows[0]
    assert "users" not in rows[0]
    assert rows[0]["author"] == {"name": "Alice"}


# ---------------------------------------------------------------------------
# Hint syntax: users!user_id(name)
# ---------------------------------------------------------------------------


def test_hint_syntax(fk_client: Client) -> None:
    resp = fk_client.from_("posts").select("id, users!user_id(name)").execute()
    rows = resp.data
    assert rows[0]["users"] == {"name": "Alice"}


# ---------------------------------------------------------------------------
# One-to-many (incoming FK): posts <- comments
# ---------------------------------------------------------------------------


def test_one_to_many_basic(fk_client: Client) -> None:
    resp = fk_client.from_("posts").select("id, title, comments(body)").execute()
    rows = resp.data
    post1 = next(r for r in rows if r["id"] == 1)
    assert len(post1["comments"]) == 2
    bodies = {c["body"] for c in post1["comments"]}
    assert bodies == {"Great post!", "Thanks!"}

    post2 = next(r for r in rows if r["id"] == 2)
    assert len(post2["comments"]) == 1
    assert post2["comments"][0]["body"] == "Nice!"

    post3 = next(r for r in rows if r["id"] == 3)
    assert post3["comments"] == []


def test_one_to_many_wildcard_embedded(fk_client: Client) -> None:
    resp = fk_client.from_("posts").select("id, comments(*)").execute()
    rows = resp.data
    post1 = next(r for r in rows if r["id"] == 1)
    assert len(post1["comments"]) == 2
    # post_id should be included since we requested *
    assert all("post_id" in c for c in post1["comments"])


# ---------------------------------------------------------------------------
# Reverse direction: querying comments embeds posts (many-to-one via comments.post_id)
# ---------------------------------------------------------------------------


def test_embed_from_child_side(fk_client: Client) -> None:
    resp = fk_client.from_("comments").select("id, body, posts(title)").execute()
    rows = resp.data
    assert rows[0]["posts"] == {"title": "Hello World"}


# ---------------------------------------------------------------------------
# Combined: users -> posts -> comments (two separate embeds)
# ---------------------------------------------------------------------------


def test_two_embedded_resources(fk_client: Client) -> None:
    # posts embeds both users and comments
    resp = (
        fk_client.from_("posts")
        .select("id, users(name), comments(body)")
        .execute()
    )
    rows = resp.data
    post1 = next(r for r in rows if r["id"] == 1)
    assert post1["users"] == {"name": "Alice"}
    assert len(post1["comments"]) == 2


# ---------------------------------------------------------------------------
# Error: no FK defined between tables
# ---------------------------------------------------------------------------


def test_missing_fk_raises(fk_client: Client) -> None:
    with pytest.raises(QueryError, match="No FK relationship"):
        fk_client.from_("posts").select("id, comments_unknown(body)").execute()


# ---------------------------------------------------------------------------
# define_foreign_key is idempotent (re-registering overwrites)
# ---------------------------------------------------------------------------


def test_redefine_fk(fk_client: Client) -> None:
    fk_client.define_foreign_key("posts", "user_id", "users", "id")
    resp = fk_client.from_("posts").select("id, users(name)").eq("id", 1).single().execute()
    assert resp.data["users"] == {"name": "Alice"}
