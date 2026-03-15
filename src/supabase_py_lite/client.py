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

    def define_foreign_key(
        self,
        from_table: str,
        from_col: str,
        to_table: str,
        to_col: str = "id",
    ) -> None:
        """Register a FK relationship so embedded selects work.

        Args:
            from_table: Table that holds the foreign key column.
            from_col:   The foreign key column name (e.g. "user_id").
            to_table:   The referenced table (e.g. "users").
            to_col:     The referenced column, defaults to "id".

        Examples:
            # posts.user_id -> users.id  (many-to-one)
            client.define_foreign_key("posts", "user_id", "users")

            # comments.post_id -> posts.id  (one-to-many from posts' perspective)
            client.define_foreign_key("comments", "post_id", "posts")
        """
        self._engine.register_foreign_key(from_table, from_col, to_table, to_col)

    def close(self) -> None:
        self._engine.close()

    def __enter__(self) -> Client:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"<SupabaseLiteClient engine={self._engine.__class__.__name__}>"
