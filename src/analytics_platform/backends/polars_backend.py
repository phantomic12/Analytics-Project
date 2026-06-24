"""Polars backend adapter placeholder (Build Queue v2.1 Task 82)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class PolarsBackendError(Exception):
    pass


@dataclass
class PolarsBackend:
    @staticmethod
    def from_config(backend_id: Any) -> "PolarsBackend":
        raise RuntimeError("Polars backend not implemented in this build; use DuckDB backend")
