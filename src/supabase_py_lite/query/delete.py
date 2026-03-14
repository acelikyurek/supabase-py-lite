from __future__ import annotations

from typing import Any

from ..engine.base import BaseEngine
from ..response import APIResponse
from .filters import FilterMixin


class DeleteQueryBuilder(FilterMixin):
    def __init__(self, engine: BaseEngine, table: str) -> None:
        self._engine = engine
        self._table = table
        self._filters: list[tuple[str, str, Any]] = []

    def execute(self) -> APIResponse:
        rows = self._engine.execute_delete(
            table=self._table,
            filters=self._filters,
            returning=True,
        )
        return APIResponse(data=rows)
