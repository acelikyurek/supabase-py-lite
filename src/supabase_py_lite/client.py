from __future__ import annotations

from .auth.client import AuthClient
from .engine.sqlite import SQLiteEngine
from .query.builder import TableQueryBuilder


class Client:
    """Lightweight Supabase-compatible client backed by SQLite."""

    def __init__(self, db_path: str = ":memory:") -> None:
        self._engine = SQLiteEngine(db_path)
        self.auth = AuthClient()

    def from_(self, table: str) -> TableQueryBuilder:
        """Start building a query on the given table. Mirrors supabase-py's .from_()."""
        return TableQueryBuilder(self._engine, table)

    def table(self, table: str) -> TableQueryBuilder:
        """Alias for from_()."""
        return self.from_(table)

    def close(self) -> None:
        self._engine.close()

    def __enter__(self) -> Client:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"<SupabaseLiteClient engine={self._engine.__class__.__name__}>"
