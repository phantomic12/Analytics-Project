"""Backends package (Build Queue v2.1 Task 112)."""

from analytics_platform.backends.duckdb_connection import (
    DuckDBConnectionManager,
    QueryResult,
)
from analytics_platform.backends.duckdb_catalog import DuckDBCatalog
from analytics_platform.backends.duckdb_query_runner import DuckDBQueryRunner
from analytics_platform.backends.runtime_backend import Backend

__all__ = [
    "Backend",
    "DuckDBConnectionManager",
    "DuckDBCatalog",
    "DuckDBQueryRunner",
    "QueryResult",
]
