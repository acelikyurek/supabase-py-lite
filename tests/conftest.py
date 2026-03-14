import pytest

from supabase_py_lite import Client, create_client


@pytest.fixture
def client() -> Client:
    """Fresh in-memory client for each test."""
    c = create_client(":memory:")
    yield c  # type: ignore[misc]
    c.close()


@pytest.fixture
def seeded_client(client: Client) -> Client:
    """Client with some test data pre-loaded."""
    users = [
        {"id": 1, "name": "Alice", "email": "alice@test.com", "age": 30},
        {"id": 2, "name": "Bob", "email": "bob@test.com", "age": 25},
        {"id": 3, "name": "Charlie", "email": "charlie@test.com", "age": 35},
    ]
    client.from_("users").insert(users).execute()
    return client
