"""supabase-lite: In-memory Supabase client for testing."""

from .auth import AuthClient, AuthError, AuthResponse, Session, User, UserResponse
from .client import Client
from .response import APIResponse

__version__ = "0.1.0"


def create_client(db_path: str = ":memory:") -> Client:
    """Create a new supabase-lite client.

    Args:
        db_path: SQLite database path. Use ":memory:" for in-memory (default),
                 or a file path for persistence.

    Returns:
        A Client instance with the same query API as supabase-py.

    Examples:
        >>> from supabase_lite import create_client
        >>> client = create_client(":memory:")
        >>> client.from_("users").insert({"id": 1, "name": "Alice"}).execute()
        >>> client.auth.sign_up({"email": "alice@example.com", "password": "secret"})
    """
    return Client(db_path)


__all__ = [
    "create_client",
    "Client",
    "APIResponse",
    "AuthClient",
    "AuthError",
    "AuthResponse",
    "Session",
    "User",
    "UserResponse",
    "__version__",
]
