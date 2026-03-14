from __future__ import annotations

from typing import Any, Optional

from ..engine.base import BaseEngine
from ..response import APIResponse
from .select import SelectQueryBuilder


class InsertQueryBuilder:
    def __init__(
        self,
        engine: BaseEngine,
        table: str,
        data: dict[str, Any] | list[dict[str, Any]],
        upsert: bool = False,
        on_conflict: Optional[str] = None,
    ) -> None:
        self._engine = engine
        self._table = table
        self._rows = data if isinstance(data, list) else [data]
        self._upsert = upsert
        self._on_conflict = on_conflict

    def select(
        self, columns: str = "*", *, count: Optional[str] = None
    ) -> SelectQueryBuilder:
        """Chain a select after insert (insert...returning + filter)."""
        self.execute()
        return SelectQueryBuilder(self._engine, self._table, columns, count)

    def execute(self) -> APIResponse:
        rows = self._engine.execute_insert(
            table=self._table,
            rows=self._rows,
            upsert=self._upsert,
            on_conflict=self._on_conflict,
            returning=True,
        )
        return APIResponse(data=rows)
