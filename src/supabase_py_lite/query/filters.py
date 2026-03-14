from __future__ import annotations

from typing import Any, TypeVar

T = TypeVar("T", bound="FilterMixin")


class FilterMixin:
    """PostgREST-compatible filter methods."""

    _filters: list[tuple[str, str, Any]]

    def eq(self: T, column: str, value: Any) -> T:
        self._filters.append((column, "eq", value))
        return self

    def neq(self: T, column: str, value: Any) -> T:
        self._filters.append((column, "neq", value))
        return self

    def gt(self: T, column: str, value: Any) -> T:
        self._filters.append((column, "gt", value))
        return self

    def gte(self: T, column: str, value: Any) -> T:
        self._filters.append((column, "gte", value))
        return self

    def lt(self: T, column: str, value: Any) -> T:
        self._filters.append((column, "lt", value))
        return self

    def lte(self: T, column: str, value: Any) -> T:
        self._filters.append((column, "lte", value))
        return self

    def in_(self: T, column: str, values: list[Any]) -> T:
        self._filters.append((column, "in", values))
        return self

    def like(self: T, column: str, pattern: str) -> T:
        self._filters.append((column, "like", pattern))
        return self

    def ilike(self: T, column: str, pattern: str) -> T:
        self._filters.append((column, "ilike", pattern))
        return self

    def is_(self: T, column: str, value: Any) -> T:
        self._filters.append((column, "is", value))
        return self

    def contains(self: T, column: str, value: Any) -> T:
        self._filters.append((column, "contains", value))
        return self
