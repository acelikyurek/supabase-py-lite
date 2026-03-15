from __future__ import annotations

from typing import Any, TypeVar

T = TypeVar("T", bound="FilterMixin")


def _split_comma(s: str) -> list[str]:
    """Split by comma, respecting parentheses."""
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for char in s:
        if char == "(":
            depth += 1
            current.append(char)
        elif char == ")":
            depth -= 1
            current.append(char)
        elif char == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    if current:
        parts.append("".join(current).strip())
    return [p for p in parts if p]


def _coerce(val: str) -> Any:
    """Try to coerce a string to int or float; return as string otherwise."""
    try:
        return int(val)
    except ValueError:
        pass
    try:
        return float(val)
    except ValueError:
        pass
    return val


def _parse_or_string(filter_str: str) -> list[tuple[str, str, Any]]:
    """
    Parse a PostgREST filter string into a list of (col, op, val) tuples.

    Examples:
        "name.eq.Alice,age.gt.30"   -> [("name", "eq", "Alice"), ("age", "gt", 30)]
        "id.in.(1,2,3)"             -> [("id", "in", [1, 2, 3])]
        "deleted_at.is.null"        -> [("deleted_at", "is", None)]
    """
    result: list[tuple[str, str, Any]] = []
    for part in _split_comma(filter_str):
        chunks = part.split(".", 2)
        if len(chunks) < 3:
            continue
        col, op, val_str = chunks
        val: Any
        if op == "in" and val_str.startswith("(") and val_str.endswith(")"):
            val = [_coerce(v.strip()) for v in val_str[1:-1].split(",")]
        elif op == "is":
            val = None if val_str.lower() == "null" else val_str
        else:
            val = _coerce(val_str)
        result.append((col, op, val))
    return result


class FilterMixin:
    """PostgREST-compatible filter methods."""

    _filters: list[Any]

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

    def or_(self: T, filters: str) -> T:
        """Add an OR group using PostgREST filter string syntax.

        Args:
            filters: Comma-separated filter expressions, e.g. "name.eq.Alice,age.gt.30"

        Example:
            .or_("name.eq.Alice,age.gt.30")
            # WHERE (name = 'Alice' OR age > 30)
        """
        self._filters.append(("__or__", _parse_or_string(filters)))
        return self

    def not_(self: T, column: str, op: str, value: Any) -> T:
        """Negate a single filter condition.

        Args:
            column: Column name.
            op:     Operator string, e.g. "eq", "gt", "in".
            value:  Value to compare against.

        Example:
            .not_("name", "eq", "Alice")
            # WHERE NOT (name = 'Alice')
        """
        self._filters.append(("__not__", column, op, value))
        return self
