from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Optional

from ..engine.base import BaseEngine
from ..exceptions import QueryError, SingleRowError
from ..response import APIResponse
from .filters import FilterMixin


@dataclass
class EmbeddedResource:
    alias: str
    table: str
    columns: list[str]
    hint: Optional[str]


def _split_top_level(s: str) -> list[str]:
    """Split a comma-separated string at depth 0 (ignores commas inside parentheses)."""
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


def _parse_select_string(
    select_str: str,
) -> tuple[list[str], list[EmbeddedResource]]:
    """
    Parse a Supabase-style select string into plain columns and embedded resources.

    Examples:
        "*"                          -> (["*"], [])
        "id, title, users(name)"     -> (["id", "title"], [EmbeddedResource(...)])
        "*, author:users!uid(name)"  -> (["*"], [EmbeddedResource(alias="author", ...)])
    """
    if select_str.strip() == "*":
        return ["*"], []

    plain_cols: list[str] = []
    embedded: list[EmbeddedResource] = []

    for part in _split_top_level(select_str):
        if "(" in part:
            m = re.match(r"^(?:(\w+):)?(\w+)(?:!(\w+))?\((.+)\)$", part.strip())
            if m:
                alias_group, table_name, hint, inner = m.groups()
                alias = alias_group if alias_group else table_name
                cols = [c.strip() for c in _split_top_level(inner)]
                embedded.append(
                    EmbeddedResource(
                        alias=alias, table=table_name, columns=cols, hint=hint
                    )
                )
        else:
            plain_cols.append(part)

    return plain_cols if plain_cols else ["*"], embedded


class SelectQueryBuilder(FilterMixin):
    def __init__(
        self,
        engine: BaseEngine,
        table: str,
        columns: str = "*",
        count: Optional[str] = None,
    ) -> None:
        self._engine = engine
        self._table = table
        plain, embedded = _parse_select_string(columns)
        self._columns = plain
        self._embedded = embedded
        self._filters: list[tuple[str, str, Any]] = []
        self._order_by: list[tuple[str, bool]] = []
        self._limit_val: Optional[int] = None
        self._offset_val: Optional[int] = None
        self._single_row = False
        self._maybe_single = False
        self._count = count

    def order(self, column: str, *, ascending: bool = True) -> SelectQueryBuilder:
        self._order_by.append((column, ascending))
        return self

    def limit(self, count: int) -> SelectQueryBuilder:
        self._limit_val = count
        return self

    def offset(self, count: int) -> SelectQueryBuilder:
        self._offset_val = count
        return self

    def range(self, start: int, end: int) -> SelectQueryBuilder:
        self._offset_val = start
        self._limit_val = end - start + 1
        return self

    def single(self) -> SelectQueryBuilder:
        self._single_row = True
        return self

    def maybe_single(self) -> SelectQueryBuilder:
        self._maybe_single = True
        return self

    def _embed_resource(
        self, rows: list[dict[str, Any]], emb: EmbeddedResource
    ) -> list[dict[str, Any]]:
        if not rows:
            return rows

        try:
            fk_col, ref_col, is_outgoing = self._engine.resolve_fk(
                self._table, emb.table, emb.hint
            )
        except Exception as exc:
            raise QueryError(f"Cannot embed '{emb.table}': {exc}") from exc

        fetch_cols = list(emb.columns)

        if is_outgoing:
            # FK on current table: many-to-one → embed as single object
            add_ref = fetch_cols != ["*"] and ref_col not in fetch_cols
            cols_to_fetch = fetch_cols + [ref_col] if add_ref else fetch_cols

            fk_values = list(
                {row[fk_col] for row in rows if row.get(fk_col) is not None}
            )
            if not fk_values:
                for row in rows:
                    row[emb.alias] = None
                return rows

            related_rows, _ = self._engine.execute_select(
                table=emb.table,
                columns=cols_to_fetch,
                filters=[(ref_col, "in", fk_values)],
                order=None,
                limit=None,
                offset=None,
                count=None,
            )

            if add_ref:
                lookup = {
                    r[ref_col]: {k: v for k, v in r.items() if k != ref_col}
                    for r in related_rows
                }
            else:
                lookup = {r[ref_col]: r for r in related_rows}

            for row in rows:
                row[emb.alias] = lookup.get(row.get(fk_col))
        else:
            # FK on related table: one-to-many → embed as list
            add_fk = fetch_cols != ["*"] and fk_col not in fetch_cols
            cols_to_fetch = fetch_cols + [fk_col] if add_fk else fetch_cols

            ref_values = list(
                {row[ref_col] for row in rows if row.get(ref_col) is not None}
            )
            if not ref_values:
                for row in rows:
                    row[emb.alias] = []
                return rows

            related_rows, _ = self._engine.execute_select(
                table=emb.table,
                columns=cols_to_fetch,
                filters=[(fk_col, "in", ref_values)],
                order=None,
                limit=None,
                offset=None,
                count=None,
            )

            grouped: dict[Any, list[dict[str, Any]]] = defaultdict(list)
            for r in related_rows:
                fk_val = r[fk_col]
                grouped[fk_val].append(
                    {k: v for k, v in r.items() if k != fk_col} if add_fk else r
                )

            for row in rows:
                row[emb.alias] = grouped.get(row.get(ref_col), [])

        return rows

    def execute(self) -> APIResponse:
        # For embedded resources, we may need extra columns in the main query
        # (the FK column for outgoing FKs, or the PK for incoming FKs).
        # Collect them so we can strip them from the final result if the user
        # didn't explicitly request them.
        extra_join_cols: set[str] = set()
        if self._embedded and self._columns != ["*"]:
            for emb in self._embedded:
                try:
                    fk_col, ref_col, is_outgoing = self._engine.resolve_fk(
                        self._table, emb.table, emb.hint
                    )
                    # outgoing FK: need fk_col on main table
                    # incoming FK: need ref_col on main table
                    join_col = fk_col if is_outgoing else ref_col
                    if join_col not in self._columns:
                        extra_join_cols.add(join_col)
                except Exception:
                    pass  # will fail with a clear message in _embed_resource

        fetch_cols = (
            self._columns + list(extra_join_cols)
            if extra_join_cols
            else self._columns
        )

        rows, count = self._engine.execute_select(
            table=self._table,
            columns=fetch_cols,
            filters=self._filters,
            order=self._order_by or None,
            limit=self._limit_val,
            offset=self._offset_val,
            count=self._count,
        )

        for emb in self._embedded:
            rows = self._embed_resource(rows, emb)

        # Strip join columns that were added internally and not requested
        if extra_join_cols:
            for row in rows:
                for col in extra_join_cols:
                    row.pop(col, None)

        if self._single_row:
            if len(rows) == 0:
                raise SingleRowError(
                    f"No rows returned from '{self._table}' for .single()"
                )
            if len(rows) > 1:
                raise SingleRowError(
                    f"Multiple rows returned from '{self._table}' for .single()"
                )
            return APIResponse(data=rows[0], count=count)  # type: ignore[arg-type]

        if self._maybe_single:
            if len(rows) == 0:
                return APIResponse(data=None, count=count)  # type: ignore[arg-type]
            if len(rows) == 1:
                return APIResponse(data=rows[0], count=count)  # type: ignore[arg-type]

        return APIResponse(data=rows, count=count)
