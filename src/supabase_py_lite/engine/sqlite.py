from __future__ import annotations

import json
import sqlite3
from typing import Any, Optional

from .base import BaseEngine
from ..exceptions import QueryError, TableNotFoundError

OPERATOR_MAP = {
    "eq": "=",
    "neq": "!=",
    "gt": ">",
    "gte": ">=",
    "lt": "<",
    "lte": "<=",
    "like": "LIKE",
    "ilike": "LIKE",
    "is": "IS",
}

def _infer_sqlite_type(value: Any) -> str:
    if isinstance(value, bool):
        return "INTEGER"
    if isinstance(value, int):
        return "INTEGER"
    if isinstance(value, float):
        return "REAL"
    if isinstance(value, (dict, list)):
        return "TEXT"
    return "TEXT"


class SQLiteEngine(BaseEngine):
    def __init__(self, path: str = ":memory:") -> None:
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._known_tables: dict[str, set[str]] = {}
        self._foreign_keys: dict[tuple[str, str], tuple[str, str]] = {}

    def register_foreign_key(
        self, from_table: str, from_col: str, to_table: str, to_col: str
    ) -> None:
        self._foreign_keys[(from_table, from_col)] = (to_table, to_col)

    def resolve_fk(
        self, from_table: str, to_table: str, hint: Optional[str]
    ) -> tuple[str, str, bool]:
        if hint:
            if (from_table, hint) in self._foreign_keys:
                _, ref_col = self._foreign_keys[(from_table, hint)]
                return hint, ref_col, True
            if (to_table, hint) in self._foreign_keys:
                _, ref_col = self._foreign_keys[(to_table, hint)]
                return hint, ref_col, False
            raise QueryError(
                f"No FK with hint '{hint}' found for '{from_table}' <-> '{to_table}'"
            )
        for (ft, fc), (tt, tc) in self._foreign_keys.items():
            if ft == from_table and tt == to_table:
                return fc, tc, True
        for (ft, fc), (tt, tc) in self._foreign_keys.items():
            if ft == to_table and tt == from_table:
                return fc, tc, False
        raise QueryError(
            f"No FK relationship found between '{from_table}' and '{to_table}'"
        )

    def ensure_table(self, table: str, columns: dict[str, Any]) -> None:
        if table not in self._known_tables:
            cur = self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
            )
            if cur.fetchone():
                pragma = self.conn.execute(f"PRAGMA table_info(`{table}`)").fetchall()
                self._known_tables[table] = {row["name"] for row in pragma}
            else:
                col_defs = []
                for col_name, col_value in columns.items():
                    col_type = _infer_sqlite_type(col_value)
                    if col_name == "id":
                        col_defs.append(f"`{col_name}` {col_type} PRIMARY KEY")
                    else:
                        col_defs.append(f"`{col_name}` {col_type}")
                ddl = f"CREATE TABLE `{table}` ({', '.join(col_defs)})"
                self.conn.execute(ddl)
                self.conn.commit()
                self._known_tables[table] = set(columns.keys())
                return

        existing = self._known_tables[table]
        for col_name, col_value in columns.items():
            if col_name not in existing:
                col_type = _infer_sqlite_type(col_value)
                self.conn.execute(
                    f"ALTER TABLE `{table}` ADD COLUMN `{col_name}` {col_type}"
                )
                existing.add(col_name)
        self.conn.commit()

    def _build_where(
        self, filters: list[tuple[str, str, Any]]
    ) -> tuple[str, list[Any]]:
        if not filters:
            return "", []
        clauses = []
        params: list[Any] = []
        for col, op, val in filters:
            if op == "in":
                placeholders = ", ".join("?" for _ in val)
                clauses.append(f"`{col}` IN ({placeholders})")
                params.extend(val)
            elif op == "is":
                if val is None:
                    clauses.append(f"`{col}` IS NULL")
                else:
                    clauses.append(f"`{col}` IS ?")
                    params.append(val)
            elif op == "contains":
                clauses.append(
                    f"EXISTS (SELECT 1 FROM json_each(`{col}`) WHERE json_each.value = ?)"
                )
                params.append(val)
            else:
                sql_op = OPERATOR_MAP.get(op, "=")
                clauses.append(f"`{col}` {sql_op} ?")
                params.append(val)
        return "WHERE " + " AND ".join(clauses), params

    def _serialize_value(self, val: Any) -> Any:
        if isinstance(val, (dict, list)):
            return json.dumps(val)
        return val

    def _deserialize_row(self, row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        for k, v in d.items():
            if isinstance(v, str):
                try:
                    parsed = json.loads(v)
                    if isinstance(parsed, (dict, list)):
                        d[k] = parsed
                except (json.JSONDecodeError, ValueError):
                    pass
        return d

    def execute_select(
        self,
        table: str,
        columns: list[str],
        filters: list[tuple[str, str, Any]],
        order: Optional[list[tuple[str, bool]]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        count: Optional[str] = None,
    ) -> tuple[list[dict[str, Any]], Optional[int]]:
        col_str = (
            ", ".join(f"`{c}`" for c in columns)
            if columns and columns != ["*"]
            else "*"
        )
        where_clause, params = self._build_where(filters)
        sql = f"SELECT {col_str} FROM `{table}` {where_clause}"
        if order:
            order_parts = [
                f"`{col}` {'ASC' if asc else 'DESC'}" for col, asc in order
            ]
            sql += " ORDER BY " + ", ".join(order_parts)
        if limit is not None:
            sql += f" LIMIT {limit}"
        if offset is not None:
            sql += f" OFFSET {offset}"
        try:
            rows = self.conn.execute(sql, params).fetchall()
        except sqlite3.OperationalError as e:
            if "no such table" in str(e):
                raise TableNotFoundError(f"Table '{table}' does not exist") from e
            raise QueryError(str(e)) from e
        except sqlite3.Error as e:
            raise QueryError(str(e)) from e
        result = [self._deserialize_row(r) for r in rows]
        total = None
        if count == "exact":
            count_sql = f"SELECT COUNT(*) as cnt FROM `{table}` {where_clause}"
            total = self.conn.execute(count_sql, params).fetchone()["cnt"]
        return result, total

    def execute_insert(
        self,
        table: str,
        rows: list[dict[str, Any]],
        upsert: bool = False,
        on_conflict: Optional[str] = None,
        ignore_duplicates: bool = False,
        returning: bool = True,
    ) -> list[dict[str, Any]]:
        if not rows:
            return []
        all_cols: dict[str, Any] = {}
        for row in rows:
            for k, v in row.items():
                if k not in all_cols:
                    all_cols[k] = v
        self.ensure_table(table, all_cols)
        results = []
        for row in rows:
            cols = list(row.keys())
            vals = [self._serialize_value(row[c]) for c in cols]
            placeholders = ", ".join("?" for _ in cols)
            col_names = ", ".join(f"`{c}`" for c in cols)
            if upsert:
                if ignore_duplicates:
                    sql = (
                        f"INSERT INTO `{table}` ({col_names}) VALUES ({placeholders}) "
                        f"ON CONFLICT DO NOTHING"
                    )
                else:
                    conflict_cols = [
                        c.strip() for c in (on_conflict or "id").split(",")
                    ]
                    conflict_target = ", ".join(f"`{c}`" for c in conflict_cols)
                    update_parts = ", ".join(
                        f"`{c}` = excluded.`{c}`"
                        for c in cols
                        if c not in conflict_cols
                    )
                    sql = (
                        f"INSERT INTO `{table}` ({col_names}) VALUES ({placeholders}) "
                        f"ON CONFLICT({conflict_target}) DO UPDATE SET {update_parts}"
                    )
            else:
                sql = f"INSERT INTO `{table}` ({col_names}) VALUES ({placeholders})"
            try:
                cur = self.conn.execute(sql, vals)
            except sqlite3.Error as e:
                raise QueryError(str(e)) from e
            if returning:
                inserted = self.conn.execute(
                    f"SELECT * FROM `{table}` WHERE rowid = ?", (cur.lastrowid,)
                ).fetchone()
                if inserted:
                    results.append(self._deserialize_row(inserted))
        self.conn.commit()
        return results

    def execute_update(
        self,
        table: str,
        values: dict[str, Any],
        filters: list[tuple[str, str, Any]],
        returning: bool = True,
    ) -> list[dict[str, Any]]:
        set_parts = ", ".join(f"`{k}` = ?" for k in values.keys())
        set_params = [self._serialize_value(v) for v in values.values()]
        where_clause, where_params = self._build_where(filters)
        rowids: list[int] = []
        if returning:
            select_sql = f"SELECT rowid as _rowid FROM `{table}` {where_clause}"
            before = self.conn.execute(select_sql, where_params).fetchall()
            rowids = [r["_rowid"] for r in before]
        sql = f"UPDATE `{table}` SET {set_parts} {where_clause}"
        try:
            self.conn.execute(sql, set_params + where_params)
        except sqlite3.OperationalError as e:
            if "no such table" in str(e):
                raise TableNotFoundError(f"Table '{table}' does not exist") from e
            raise QueryError(str(e)) from e
        except sqlite3.Error as e:
            raise QueryError(str(e)) from e
        self.conn.commit()
        if returning and rowids:
            placeholders = ", ".join("?" for _ in rowids)
            after = self.conn.execute(
                f"SELECT * FROM `{table}` WHERE rowid IN ({placeholders})", rowids
            ).fetchall()
            return [self._deserialize_row(r) for r in after]
        return []

    def execute_delete(
        self,
        table: str,
        filters: list[tuple[str, str, Any]],
        returning: bool = True,
    ) -> list[dict[str, Any]]:
        where_clause, params = self._build_where(filters)
        results: list[dict[str, Any]] = []
        try:
            if returning:
                select_sql = f"SELECT * FROM `{table}` {where_clause}"
                rows = self.conn.execute(select_sql, params).fetchall()
                results = [self._deserialize_row(r) for r in rows]
            sql = f"DELETE FROM `{table}` {where_clause}"
            self.conn.execute(sql, params)
        except sqlite3.OperationalError as e:
            if "no such table" in str(e):
                raise TableNotFoundError(f"Table '{table}' does not exist") from e
            raise QueryError(str(e)) from e
        except sqlite3.Error as e:
            raise QueryError(str(e)) from e
        self.conn.commit()
        return results

    def close(self) -> None:
        self.conn.close()
