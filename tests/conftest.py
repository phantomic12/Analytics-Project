"""Minimal pytest configuration for the analytics-platform test suite.

The project uses a ``src`` layout. The package is not editable-installed yet
(``[tool.uv] package = false`` in ``pyproject.toml``) and there is no
``pythonpath`` entry under ``[tool.pytest.ini_options]``, so pytest needs
``src`` on ``sys.path`` for future tests to ``import analytics_platform``.

That packaging configuration lives in ``pyproject.toml``, which is outside the
allowed file scope for Build Queue v2.1 Task 10. To keep test discovery working
without touching ``pyproject.toml``, we add the ``src`` directory to
``sys.path`` here. This is intentionally minimal; once editable installs or a
``pythonpath`` setting are enabled, this block can be removed.

Heavy-library test isolation:

Tests that import heavy libraries at module load time
(``tests/test_polars_backend.py`` for Task 82, future
``tests/test_duckdb_backend.py`` for Task 112) leave those
libraries in ``sys.modules`` after they run. That pollutes
``sys.modules`` for downstream "do not import heavy libs"
guard tests, which then flake. The pragmatic fix for the v1.1
MVP is to run heavy-library tests in a fresh subprocess; that
is configured via the ``[tool.pytest.ini_options]`` addopts
entry ``--forked`` once ``pytest-forked`` is added to the dev
group. Until then, the guard tests can be excluded with
``uv run pytest tests/ --ignore=tests/test_polars_backend.py``
when developing locally.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

# Test-only compatibility adapters live in tests/contracts/ as
# standalone modules (e.g. ``config_pipeline_compat`` for Task 47).
# Add the tests/contracts/ directory to sys.path so the adapters
# can be imported by name in compatibility tests.
_TESTS_CONTRACTS_DIR = Path(__file__).resolve().parent / "contracts"
if str(_TESTS_CONTRACTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_CONTRACTS_DIR))
