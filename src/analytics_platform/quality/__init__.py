"""Quality / missingness analysis (Build Queue v2.1 Tasks 92-93).

This subpackage owns the canonical quality and missingness
analysis stages. The stages consume the contract family's
:class:`ObservedSchema` plus any backend-friendly tabular data
(a ``{column_name: sequence}`` mapping works for Polars, Pandas,
or synthetic test data) and produce the typed
:class:`MissingDataReport` and :class:`DataQualityReport` outputs.

Per the architecture-test plan (section 5), the ``quality`` module
is a domain module and may import from contracts, core, the
schema and semantics packages, and the approved runtime libraries.

Scope:

- :func:`compute_missingness` (Task 92) — per-column + per-row
  missingness summary, plus categorical missingness patterns.
- :func:`compute_data_quality` (Task 93) — overall quality report
  that wraps the missingness report and adds high-missingness /
  constant-column / duplicate-column findings.
- :class:`MissingnessError` / :class:`DataQualityError` — typed
  failures carrying an :class:`Issue` payload.
"""

from __future__ import annotations

from analytics_platform.quality.data_quality import (
    DataQualityError,
    DataQualityReporter,
    compute_data_quality,
)
from analytics_platform.quality.missingness import (
    MissingnessError,
    MissingnessReporter,
    compute_missingness,
)

__all__ = [
    # Task 92
    "MissingnessReporter",
    "MissingnessError",
    "compute_missingness",
    # Task 93
    "DataQualityReporter",
    "DataQualityError",
    "compute_data_quality",
]