import pytest

from supabase_py_lite import Client, create_client
from supabase_py_lite.exceptions import SingleRowError


class TestClient:
    def test_create_in_memory(self):
        client = create_client(":memory:")
        assert repr(client) == "<SupabaseLiteClient engine=SQLiteEngine>"
        client.close()

    def test_context_manager(self):
        with create_client(":memory:") as client:
            client.from_("t").insert({"id": 1}).execute()

    def test_table_alias(self):
        with create_client(":memory:") as client:
            client.table("t").insert({"id": 1}).execute()
            res = client.table("t").select("*").execute()
            assert len(res.data) == 1


class TestInsert:
    def test_insert_single(self, client: Client):
        res = client.from_("users").insert({"id": 1, "name": "Alice"}).execute()
        assert len(res.data) == 1
        assert res.data[0]["name"] == "Alice"

    def test_insert_multiple(self, client: Client):
        rows = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
        res = client.from_("users").insert(rows).execute()
        assert len(res.data) == 2

    def test_auto_create_table(self, client: Client):
        res = client.from_("new_table").insert({"id": 1, "col": "val"}).execute()
        assert res.data[0]["col"] == "val"

    def test_auto_add_column(self, client: Client):
        client.from_("t").insert({"id": 1, "a": "x"}).execute()
        client.from_("t").insert({"id": 2, "a": "y", "b": "z"}).execute()
        res = client.from_("t").select("*").eq("id", 2).execute()
        assert res.data[0]["b"] == "z"


class TestSelect:
    def test_select_all(self, seeded_client: Client):
        res = seeded_client.from_("users").select("*").execute()
        assert len(res.data) == 3

    def test_select_columns(self, seeded_client: Client):
        res = seeded_client.from_("users").select("id, name").execute()
        assert "email" not in res.data[0]
        assert "name" in res.data[0]

    def test_select_with_count(self, seeded_client: Client):
        res = seeded_client.from_("users").select("*", count="exact").execute()
        assert res.count == 3

    def test_single(self, seeded_client: Client):
        res = (
            seeded_client.from_("users")
            .select("*")
            .eq("id", 1)
            .single()
            .execute()
        )
        assert res.data["name"] == "Alice"

    def test_single_raises_on_empty(self, seeded_client: Client):
        with pytest.raises(SingleRowError):
            seeded_client.from_("users").select("*").eq("id", 999).single().execute()

    def test_maybe_single_returns_none(self, seeded_client: Client):
        res = (
            seeded_client.from_("users")
            .select("*")
            .eq("id", 999)
            .maybe_single()
            .execute()
        )
        assert res.data is None

    def test_maybe_single_returns_row(self, seeded_client: Client):
        res = (
            seeded_client.from_("users")
            .select("*")
            .eq("id", 1)
            .maybe_single()
            .execute()
        )
        assert res.data["name"] == "Alice"


class TestFilters:
    def test_eq(self, seeded_client: Client):
        res = seeded_client.from_("users").select("*").eq("name", "Alice").execute()
        assert len(res.data) == 1

    def test_neq(self, seeded_client: Client):
        res = seeded_client.from_("users").select("*").neq("name", "Alice").execute()
        assert len(res.data) == 2

    def test_gt(self, seeded_client: Client):
        res = seeded_client.from_("users").select("*").gt("age", 28).execute()
        assert all(r["age"] > 28 for r in res.data)

    def test_gte(self, seeded_client: Client):
        res = seeded_client.from_("users").select("*").gte("age", 30).execute()
        assert all(r["age"] >= 30 for r in res.data)

    def test_lt(self, seeded_client: Client):
        res = seeded_client.from_("users").select("*").lt("age", 30).execute()
        assert all(r["age"] < 30 for r in res.data)

    def test_lte(self, seeded_client: Client):
        res = seeded_client.from_("users").select("*").lte("age", 30).execute()
        assert all(r["age"] <= 30 for r in res.data)

    def test_in(self, seeded_client: Client):
        res = (
            seeded_client.from_("users")
            .select("*")
            .in_("name", ["Alice", "Bob"])
            .execute()
        )
        assert len(res.data) == 2

    def test_like(self, seeded_client: Client):
        res = seeded_client.from_("users").select("*").like("name", "A%").execute()
        assert len(res.data) == 1

    def test_is_null(self, client: Client):
        client.from_("t").insert({"id": 1, "val": "x"}).execute()
        client.from_("t").insert({"id": 2, "val": None}).execute()
        res = client.from_("t").select("*").is_("val", None).execute()
        assert len(res.data) == 1
        assert res.data[0]["id"] == 2

    def test_chained_filters(self, seeded_client: Client):
        res = (
            seeded_client.from_("users")
            .select("*")
            .gte("age", 25)
            .lte("age", 30)
            .execute()
        )
        assert len(res.data) == 2


class TestOrder:
    def test_order_asc(self, seeded_client: Client):
        res = (
            seeded_client.from_("users")
            .select("*")
            .order("age", ascending=True)
            .execute()
        )
        ages = [r["age"] for r in res.data]
        assert ages == sorted(ages)

    def test_order_desc(self, seeded_client: Client):
        res = (
            seeded_client.from_("users")
            .select("*")
            .order("age", ascending=False)
            .execute()
        )
        ages = [r["age"] for r in res.data]
        assert ages == sorted(ages, reverse=True)


class TestLimitOffset:
    def test_limit(self, seeded_client: Client):
        res = seeded_client.from_("users").select("*").limit(2).execute()
        assert len(res.data) == 2

    def test_offset(self, seeded_client: Client):
        res = (
            seeded_client.from_("users")
            .select("*")
            .order("id")
            .offset(1)
            .limit(2)
            .execute()
        )
        assert res.data[0]["id"] == 2

    def test_range(self, seeded_client: Client):
        res = (
            seeded_client.from_("users")
            .select("*")
            .order("id")
            .range(0, 1)
            .execute()
        )
        assert len(res.data) == 2
        assert res.data[0]["id"] == 1
        assert res.data[1]["id"] == 2


class TestUpdate:
    def test_update_single(self, seeded_client: Client):
        seeded_client.from_("users").update({"name": "Alicia"}).eq("id", 1).execute()
        res = seeded_client.from_("users").select("*").eq("id", 1).execute()
        assert res.data[0]["name"] == "Alicia"

    def test_update_returns_rows(self, seeded_client: Client):
        res = (
            seeded_client.from_("users").update({"age": 99}).eq("id", 1).execute()
        )
        assert res.data[0]["age"] == 99

    def test_update_multiple(self, seeded_client: Client):
        res = (
            seeded_client.from_("users")
            .update({"age": 50})
            .gt("age", 28)
            .execute()
        )
        assert len(res.data) == 2
        assert all(r["age"] == 50 for r in res.data)


class TestDelete:
    def test_delete_single(self, seeded_client: Client):
        res = seeded_client.from_("users").delete().eq("id", 1).execute()
        assert len(res.data) == 1
        remaining = seeded_client.from_("users").select("*").execute()
        assert len(remaining.data) == 2

    def test_delete_returns_deleted(self, seeded_client: Client):
        res = seeded_client.from_("users").delete().eq("name", "Bob").execute()
        assert res.data[0]["name"] == "Bob"

    def test_delete_with_filter(self, seeded_client: Client):
        seeded_client.from_("users").delete().lt("age", 30).execute()
        remaining = seeded_client.from_("users").select("*").execute()
        assert len(remaining.data) == 2
        assert all(r["age"] >= 30 for r in remaining.data)


class TestUpsert:
    def test_upsert_insert(self, client: Client):
        client.from_("users").insert({"id": 1, "name": "Alice"}).execute()
        client.from_("users").upsert({"id": 2, "name": "Bob"}).execute()
        res = client.from_("users").select("*").execute()
        assert len(res.data) == 2

    def test_upsert_update(self, client: Client):
        client.from_("users").insert({"id": 1, "name": "Alice"}).execute()
        client.from_("users").upsert({"id": 1, "name": "Alicia"}).execute()
        res = client.from_("users").select("*").eq("id", 1).execute()
        assert res.data[0]["name"] == "Alicia"


class TestJSON:
    def test_json_column(self, client: Client):
        client.from_("t").insert(
            {"id": 1, "meta": {"key": "value", "num": 42}}
        ).execute()
        res = client.from_("t").select("*").eq("id", 1).execute()
        assert res.data[0]["meta"] == {"key": "value", "num": 42}

    def test_json_array(self, client: Client):
        client.from_("t").insert({"id": 1, "tags": ["a", "b", "c"]}).execute()
        res = client.from_("t").select("*").eq("id", 1).execute()
        assert res.data[0]["tags"] == ["a", "b", "c"]
