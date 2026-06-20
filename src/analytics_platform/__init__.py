"""analytics_platform package skeleton.

Contract-first analytics platform. This package is intentionally minimal at
this stage: it exists to make the package importable so that future task-based
domain modules and contract modules can be added incrementally.

No implementation behavior is provided here, and no public contracts are
exported from the top-level package. Submodules are responsible for defining
and exporting their own contracts.
"""

from __future__ import annotations

__all__: list[str] = []

__version__ = "0.0.0"