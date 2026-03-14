from __future__ import annotations

from typing import Any, Optional

from ..engine.base import BaseEngine
from ..exceptions import SingleRowError
from ..response import APIResponse
from .filters import FilterMixin


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
        self._columns = (
            [c.strip() for c in columns.split(",")]
            if columns != "*"
            else ["*"]
        )
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

    def execute(self) -> APIResponse:
        rows, count = self._engine.execute_select(
            table=self._table,
            columns=self._columns,
            filters=self._filters,
            order=self._order_by or None,
            limit=self._limit_val,
            offset=self._offset_val,
            count=self._count,
        )

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
