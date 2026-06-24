"""DuckDB query runner (Build Queue v2.1 Task 112)."""

from __future__ import annotations

from typing import Any

from analytics_platform.backends.duckdb_connection import DuckDBConnectionManager, QueryResult


class DuckDBQueryRunner:
    def __init__(self, connection_manager: DuckDBConnectionManager) -> None:
        self._connection_manager = connection_manager

    def run_query(self, query: str) -> QueryResult:
        _validate_query(query)
        return self._connection_manager.execute(query)


def _validate_query(query: str) -> None:
    forbidden = {"DROP", "DELETE", "TRUNCATE", "ALTER", "UPDATE"}
    tokens = {token.strip("();") for token in query.upper().split()}
    if forbidden.intersection(tokens):
        raise ValueError("read-only query restriction violation")
