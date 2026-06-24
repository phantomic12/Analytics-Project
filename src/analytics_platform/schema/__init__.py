"""Schema inference and validation (Build Queue v2.1 Tasks 89-90).

This subpackage owns the canonical schema inference and validation
stages. It consumes the contract family
(:mod:`analytics_platform.contracts.schemas`) and produces the
typed :class:`ObservedSchema` / :class:`SchemaValidationReport`
outputs that the profiling, semantics, and reporting stages read.

Per the architecture-test plan (section 5), the ``schema`` module
is a domain module and may import from contracts, core, the
catalog (for :class:`DatasetHandle`), the backends registry (Task
83), and the approved runtime libraries (Polars is approved).

Scope:

- :func:`infer_schema` (Task 89) — pure helper that infers a
  physical + logical schema from a Polars frame and returns an
  :class:`ObservedSchema`. Lives in :mod:`schema.inference`.
- :class:`SchemaInferenceError` (Task 89) — typed failure.
- :func:`validate_schema` (Task 90) — pure helper that compares
  an :class:`ObservedSchema` against an :class:`ExpectedSchema`
  and returns a :class:`SchemaValidationReport`. Lives in
  :mod:`schema.validation`.
- :class:`SchemaValidationError` (Task 90) — typed failure.
"""

from __future__ import annotations

from analytics_platform.schema.inference import (
    SchemaInferenceError,
    SchemaInferencer,
    infer_schema,
)
from analytics_platform.schema.validation import (
    SchemaValidationError,
    SchemaValidator,
    validate_schema,
)

__all__ = [
    # Task 89
    "SchemaInferencer",
    "SchemaInferenceError",
    "infer_schema",
    # Task 90
    "SchemaValidator",
    "SchemaValidationError",
    "validate_schema",
]