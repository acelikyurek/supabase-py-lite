from __future__ import annotations

from typing import Any

from ..engine.base import BaseEngine
from ..response import APIResponse
from .filters import FilterMixin


class UpdateQueryBuilder(FilterMixin):
    def __init__(self, engine: BaseEngine, table: str, values: dict[str, Any]) -> None:
        self._engine = engine
        self._table = table
        self._values = values
        self._filters: list[tuple[str, str, Any]] = []

    def execute(self) -> APIResponse:
        rows = self._engine.execute_update(
            table=self._table,
            values=self._values,
            filters=self._filters,
            returning=True,
        )
        return APIResponse(data=rows)
