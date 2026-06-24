"""DuckDB catalog (Build Queue v2.1 Task 112)."""

from __future__ import annotations

from typing import Sequence

from analytics_platform.backends.duckdb_connection import DuckDBConnectionManager


class DuckDBCatalog:
    def __init__(self, connection_manager: DuckDBConnectionManager) -> None:
        self._connection_manager = connection_manager

    def list_tables(self) -> tuple[str, ...]:
        rows = self._connection_manager.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
        ).rows
        return tuple(r[0] for r in rows)

    def table_exists(self, table_name: str) -> bool:
        result = self._connection_manager.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = ?",
        )
        return bool(result.rows and result.rows[0][0] > 0)
