from __future__ import annotations

from typing import Any, Optional

from ..engine.base import BaseEngine
from .delete import DeleteQueryBuilder
from .insert import InsertQueryBuilder, ReturnMethod
from .select import SelectQueryBuilder
from .update import UpdateQueryBuilder


class TableQueryBuilder:
    """Entry point returned by client.from_("table_name")."""

    def __init__(self, engine: BaseEngine, table: str) -> None:
        self._engine = engine
        self._table = table

    def select(
        self, columns: str = "*", *, count: Optional[str] = None
    ) -> SelectQueryBuilder:
        return SelectQueryBuilder(self._engine, self._table, columns, count)

    def insert(
        self,
        data: dict[str, Any] | list[dict[str, Any]],
        *,
        returning: ReturnMethod = "representation",
        count: Optional[str] = None,
    ) -> InsertQueryBuilder:
        return InsertQueryBuilder(
            self._engine, self._table, data, returning=returning, count=count
        )

    def upsert(
        self,
        data: dict[str, Any] | list[dict[str, Any]],
        *,
        on_conflict: str = "id",
        ignore_duplicates: bool = False,
        returning: ReturnMethod = "representation",
        count: Optional[str] = None,
    ) -> InsertQueryBuilder:
        return InsertQueryBuilder(
            self._engine,
            self._table,
            data,
            upsert=True,
            on_conflict=on_conflict,
            ignore_duplicates=ignore_duplicates,
            returning=returning,
            count=count,
        )

    def update(self, values: dict[str, Any]) -> UpdateQueryBuilder:
        return UpdateQueryBuilder(self._engine, self._table, values)

    def delete(self) -> DeleteQueryBuilder:
        return DeleteQueryBuilder(self._engine, self._table)
