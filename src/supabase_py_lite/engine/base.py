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
