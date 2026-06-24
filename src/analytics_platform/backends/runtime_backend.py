"""Runtime backend (Build Queue v2.1 Task 112)."""

from __future__ import annotations

from typing import Protocol

from analytics_platform.contracts.datasets import DatasetHandle, DatasetRef


class Backend(Protocol):
    def load(self, handle: DatasetHandle, path: str | None = None) -> None:
        ...

    def execute(self, query: str) -> object:
        ...

    def close(self) -> None:
        ...
