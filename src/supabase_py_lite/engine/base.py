from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional


class BaseEngine(ABC):
    """Abstract interface for database backends."""

    @abstractmethod
    def execute_select(
        self,
        table: str,
        columns: list[str],
        filters: list[tuple[str, str, Any]],
        order: Optional[list[tuple[str, bool]]],
        limit: Optional[int],
        offset: Optional[int],
        count: Optional[str],
    ) -> tuple[list[dict[str, Any]], Optional[int]]:
        ...

    @abstractmethod
    def execute_insert(
        self,
        table: str,
        rows: list[dict[str, Any]],
        upsert: bool,
        on_conflict: Optional[str],
        returning: bool,
    ) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    def execute_update(
        self,
        table: str,
        values: dict[str, Any],
        filters: list[tuple[str, str, Any]],
        returning: bool,
    ) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    def execute_delete(
        self,
        table: str,
        filters: list[tuple[str, str, Any]],
        returning: bool,
    ) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    def ensure_table(self, table: str, columns: dict[str, Any]) -> None:
        ...

    @abstractmethod
    def close(self) -> None:
        ...

    @abstractmethod
    def register_foreign_key(
        self, from_table: str, from_col: str, to_table: str, to_col: str
    ) -> None:
        """Register a foreign key relationship: from_table.from_col -> to_table.to_col."""
        ...

    @abstractmethod
    def resolve_fk(
        self, from_table: str, to_table: str, hint: Optional[str]
    ) -> tuple[str, str, bool]:
        """
        Resolve the FK relationship between two tables.

        Returns (fk_col, ref_col, is_outgoing) where:
        - is_outgoing=True: fk_col is on from_table, ref_col is on to_table (many-to-one)
        - is_outgoing=False: fk_col is on to_table, ref_col is on from_table (one-to-many)
        """
        ...
