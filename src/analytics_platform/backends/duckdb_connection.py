"""DuckDB connection manager (Build Queue v2.1 Task 112)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from analytics_platform.contracts.datasets import DatasetFormat, DatasetHandle


class QueryResult:
    def __init__(self, columns: tuple[str, ...] = (), rows: tuple[tuple[Any, ...], ...] = (), row_count: int = 0, query: str = "") -> None:
        self.columns = columns
        self.rows = rows
        self.row_count = row_count
        self.query = query


class DuckDBConnectionManager:
    def __init__(self, database: str | Path = ":memory:") -> None:
        import duckdb
        self._conn = duckdb.connect(database=database)

    def load_dataset(self, handle: DatasetHandle, path: Path | None = None) -> None:
        import duckdb
        uri = str(path) if path is not None else handle.dataset_ref.uri
        fmt = (handle.format or DatasetFormat.CSV).value.lower()
        table_name = handle.dataset_id
        query = f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM read_{fmt}_auto('{uri}')"
        self._conn.execute(query)

    def execute(self, query: str) -> QueryResult:
        import duckdb
        cur = self._conn.execute(query)
        rows = cur.fetchall()
        cols = cur.description if cur.description else ()
        return QueryResult(
            columns=tuple(col[0] for col in cols),
            rows=tuple(tuple(r) for r in rows),
            row_count=len(rows),
        )

    def close(self) -> None:
        self._conn.close()
