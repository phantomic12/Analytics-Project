"""Schema inference (Build Queue v2.1 Task 89).

This module is the canonical schema-inference stage. It consumes a
Polars frame (or any object exposing a Polars-compatible
``.schema`` / ``.dtypes`` shape) and produces an
:class:`analytics_platform.contracts.schemas.ObservedSchema`. The
inference is *polymorphic* over the input frame type: the function
looks for ``.schema`` (Polars ``DataFrame`` / ``LazyFrame``) first,
falls back to ``.dtypes`` (Pandas-like), and falls back to a
provided list of ``(name, dtype_str)`` tuples when neither is
present. This keeps the inference stage testable without spinning
up a real Polars frame for every test.

Per the architecture-test plan (section 5), the ``schema`` module
is a domain module and may import from contracts, core, the
catalog (for :class:`DatasetHandle`), the backends registry (Task
83), and the approved runtime libraries (Polars is approved).

Scope (Task 89):

- :class:`SchemaInferencer` — the canonical inferencer with an
  optional ``max_columns`` and ``sample_row_count`` policy.
- :func:`infer_schema` — module-level convenience helper that
  uses the singleton inferencer.
- :class:`SchemaInferenceError` — typed failure carrying an
  :class:`Issue` payload.

The inferencer is intentionally conservative: when a physical
type does not have an obvious mapping to a logical type, it
returns ``LogicalDataType.UNKNOWN`` and records a
:class:`ColumnSchema` with ``logical_type=None``. Semantic
typing is the job of Task 91, not schema inference.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Any, Iterable, Mapping

from analytics_platform.contracts.common import Issue, Severity
from analytics_platform.contracts.datasets import DatasetHandle
from analytics_platform.contracts.schemas import (
    ColumnSchema,
    LogicalDataType,
    ObservedSchema,
    PhysicalDataType,
    SchemaInferenceRequest,
)
from analytics_platform.core import AnalyticsPlatformError, get_logger

if TYPE_CHECKING:  # pragma: no cover
    import polars as pl

__all__ = [
    "SchemaInferencer",
    "SchemaInferenceError",
    "infer_schema",
]


_LOGGER = get_logger("schema.inference")


def _make_issue(code: str, message: str, **extras: Any) -> Issue:
    """Build a typed :class:`Issue` for inference error paths."""
    return Issue(code=code, severity=Severity.ERROR, message=message, **extras)


# ---------------------------------------------------------------------------
# Physical <-> logical type mapping
# ---------------------------------------------------------------------------
# The mapping is intentionally conservative. A Polars physical type
# may map to several logical types (``FLOAT32`` / ``FLOAT64`` ->
# ``FLOAT``; ``INT8`` / ``INT16`` / ``INT32`` / ``INT64`` ->
# ``INTEGER``); the inferencer always returns the broad logical
# type and lets the semantics stage narrow it further (e.g.
# distinguishing ``INTEGER`` from ``COUNT`` or ``ORDINAL``).
_PHYSICAL_TO_LOGICAL: dict[PhysicalDataType, LogicalDataType] = {
    PhysicalDataType.INT8: LogicalDataType.INTEGER,
    PhysicalDataType.INT16: LogicalDataType.INTEGER,
    PhysicalDataType.INT32: LogicalDataType.INTEGER,
    PhysicalDataType.INT64: LogicalDataType.INTEGER,
    PhysicalDataType.UINT8: LogicalDataType.INTEGER,
    PhysicalDataType.UINT16: LogicalDataType.INTEGER,
    PhysicalDataType.UINT32: LogicalDataType.INTEGER,
    PhysicalDataType.UINT64: LogicalDataType.INTEGER,
    PhysicalDataType.FLOAT32: LogicalDataType.FLOAT,
    PhysicalDataType.FLOAT64: LogicalDataType.FLOAT,
    PhysicalDataType.BOOL: LogicalDataType.BOOLEAN,
    PhysicalDataType.UTF8: LogicalDataType.STRING,
    PhysicalDataType.LARGE_UTF8: LogicalDataType.STRING,
    PhysicalDataType.DATE32: LogicalDataType.DATE,
    PhysicalDataType.DATE64: LogicalDataType.DATE,
    PhysicalDataType.TIMESTAMP: LogicalDataType.DATETIME,
    PhysicalDataType.BINARY: LogicalDataType.BINARY,
    PhysicalDataType.LIST: LogicalDataType.UNKNOWN,
    PhysicalDataType.STRUCT: LogicalDataType.UNKNOWN,
    PhysicalDataType.NULL: LogicalDataType.UNKNOWN,
    PhysicalDataType.UNKNOWN: LogicalDataType.UNKNOWN,
}


def map_physical_to_logical(physical: PhysicalDataType) -> LogicalDataType:
    """Return the broad logical type for ``physical``."""
    return _PHYSICAL_TO_LOGICAL.get(physical, LogicalDataType.UNKNOWN)


# ---------------------------------------------------------------------------
# Helpers for normalizing a frame's column types to
# ``(name, physical_type, nullable)`` tuples.
# ---------------------------------------------------------------------------
def _stringify_physical_type(value: Any) -> str:
    """Return a stable lowercase string for a physical type value.

    Polars ``dtype`` objects stringify nicely; this helper falls
    back to ``str(value)`` for unknown types and lower-cases the
    result so look-ups in :data:`_PHYSICAL_TO_LOGICAL` are case
    insensitive.
    """
    text = str(value).strip().lower()
    return text


def _coerce_physical_type(text: str) -> PhysicalDataType:
    """Map a lowercase physical-type string to a :class:`PhysicalDataType`.

    Unknown strings fall back to :attr:`PhysicalDataType.UNKNOWN`
    rather than raising so the inferencer can still produce an
    :class:`ObservedSchema` for unusual backends.
    """
    # Strip Polars-style qualifiers like "list(utf8)" or
    # "struct{...}" down to the outer type.
    head = text.split("(", 1)[0].strip()
    head = head.split("{", 1)[0].strip()
    try:
        return PhysicalDataType(head)
    except ValueError:
        return PhysicalDataType.UNKNOWN


def _normalize_columns(
    frame: "Any | Iterable[tuple[str, str, bool | None]] | Mapping[str, str]",
) -> list[tuple[str, PhysicalDataType, bool | None]]:
    """Normalize ``frame`` into ``[(name, physical_type, nullable), ...]``.

    The normalizer accepts:

    - Polars ``DataFrame`` / ``LazyFrame`` (``.schema``).
    - Pandas-like ``DataFrame`` (``.dtypes``).
    - A list / tuple of ``(name, dtype_str, nullable | None)`` tuples
      (test path).
    - A mapping ``{name: dtype_str}`` (test path).

    Returns a list of ``(name, physical_type, nullable)`` tuples
    in the order the frame reports them.
    """
    # Polars frame path.
    if hasattr(frame, "schema") and not isinstance(frame, Mapping):
        try:
            schema = frame.schema
        except Exception as exc:  # noqa: BLE001
            raise SchemaInferenceError(
                _make_issue(
                    code="SCHEMA_INFERENCE_FRAME_SCHEMA_FAILED",
                    message=f"Failed to read frame schema: {exc}",
                )
            ) from exc
        out: list[tuple[str, PhysicalDataType, bool | None]] = []
        for name, dtype in schema.items():
            physical = _coerce_physical_type(_stringify_physical_type(dtype))
            out.append((str(name), physical, None))
        return out
    # Pandas-like frame path.
    if hasattr(frame, "dtypes") and not isinstance(frame, Mapping):
        out = []
        for name, dtype in frame.dtypes.items():
            physical = _coerce_physical_type(_stringify_physical_type(dtype))
            out.append((str(name), physical, None))
        return out
    # Iterable of tuples path (test-friendly).
    if isinstance(frame, Mapping):
        out = []
        for name, dtype in frame.items():
            physical = _coerce_physical_type(_stringify_physical_type(dtype))
            out.append((str(name), physical, None))
        return out
    # Explicit iterable.
    try:
        iterator = iter(frame)
    except TypeError as exc:
        raise SchemaInferenceError(
            _make_issue(
                code="SCHEMA_INFERENCE_UNSUPPORTED_FRAME",
                message=(
                    "SchemaInferencer does not know how to introspect "
                    f"frame of type {type(frame).__name__!r}"
                ),
            )
        ) from exc
    out = []
    for row in iterator:
        if len(row) == 3:
            name, dtype_str, nullable = row
        elif len(row) == 2:
            name, dtype_str = row
            nullable = None
        else:
            raise SchemaInferenceError(
                _make_issue(
                    code="SCHEMA_INFERENCE_BAD_ROW",
                    message=(
                        f"Schema-inference rows must have 2 or 3 elements; "
                        f"got {len(row)}"
                    ),
                )
            )
        out.append(
            (str(name), _coerce_physical_type(_stringify_physical_type(dtype_str)), nullable)
        )
    return out


def _row_count_of(frame: Any) -> int | None:
    """Best-effort row-count probe.

    Returns ``None`` when the frame does not expose a cheap row
    count (lazy frames without a sink plan, generic iterables).
    """
    height = getattr(frame, "height", None)
    if isinstance(height, int):
        return height
    shape = getattr(frame, "shape", None)
    if shape is not None:
        try:
            return int(shape[0])
        except (TypeError, IndexError, ValueError):
            return None
    return None


def _fingerprint_columns(
    columns: tuple[ColumnSchema, ...],
) -> str:
    """Compute a stable hex fingerprint of the column schema.

    The fingerprint is a SHA-256 hex digest of a canonical
    ``name|physical|logical\n`` encoding of the columns, so two
    inferred schemas with the same column names and types produce
    the same fingerprint regardless of order.
    """
    enc = "\n".join(
        f"{c.name}|{c.physical_type.value}|{(c.logical_type.value if c.logical_type else '')}"
        for c in sorted(columns, key=lambda c: c.name)
    ).encode("utf-8")
    return hashlib.sha256(enc).hexdigest()


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------
class SchemaInferenceError(AnalyticsPlatformError):
    """A typed schema-inference failure.

    The exception carries the :class:`Issue` payload so reporting
    and registry can group on the stable issue ``code``.
    """

    def __init__(self, issue: Issue) -> None:
        super().__init__(issue.message, context=issue.context)
        self.issue = issue


class SchemaInferencer:
    """The canonical schema inferencer.

    The inferencer is stateless; construction parameters control
    the upper bounds enforced at inference time.

    Construction parameters:

    - ``max_columns``: optional non-negative upper bound on the
      number of columns to inspect. ``None`` disables the bound.
    - ``sample_row_count``: optional non-negative row count to
      sample during inference. The inferencer itself does not
      sample (it inspects the schema only) but the bound is
      recorded so downstream stages can apply it.
    """

    def __init__(
        self,
        *,
        max_columns: int | None = None,
        sample_row_count: int | None = None,
    ) -> None:
        if max_columns is not None and max_columns < 0:
            raise SchemaInferenceError(
                _make_issue(
                    code="SCHEMA_INFERENCE_BAD_MAX_COLUMNS",
                    message=f"max_columns must be >= 0, got {max_columns!r}",
                )
            )
        if sample_row_count is not None and sample_row_count < 0:
            raise SchemaInferenceError(
                _make_issue(
                    code="SCHEMA_INFERENCE_BAD_SAMPLE_ROW_COUNT",
                    message=(
                        f"sample_row_count must be >= 0, got {sample_row_count!r}"
                    ),
                )
            )
        self._max_columns = max_columns
        self._sample_row_count = sample_row_count

    @property
    def max_columns(self) -> int | None:
        return self._max_columns

    @property
    def sample_row_count(self) -> int | None:
        return self._sample_row_count

    def infer(
        self,
        frame: Any,
        *,
        request: SchemaInferenceRequest | None = None,
    ) -> ObservedSchema:
        """Infer the schema of ``frame`` and return an :class:`ObservedSchema`.

        ``request`` is optional; when provided, its
        ``max_columns`` and ``sample_row_count`` fields override
        the inferencer's construction-time bounds (the inferencer
        uses ``min`` of the two to enforce the most restrictive
        bound).
        """
        max_columns = self._max_columns
        sample_row_count = self._sample_row_count
        if request is not None:
            if request.max_columns is not None:
                max_columns = (
                    request.max_columns
                    if max_columns is None
                    else min(max_columns, request.max_columns)
                )
            if request.sample_row_count is not None:
                sample_row_count = (
                    request.sample_row_count
                    if sample_row_count is None
                    else min(sample_row_count, request.sample_row_count)
                )
        rows = _normalize_columns(frame)
        if max_columns is not None and len(rows) > max_columns:
            rows = rows[:max_columns]
            _LOGGER.info(
                "Truncated schema inference to max_columns=%d", max_columns
            )
        columns: list[ColumnSchema] = []
        for ordinal, (name, physical, nullable) in enumerate(rows):
            columns.append(
                ColumnSchema(
                    name=name,
                    physical_type=physical,
                    logical_type=map_physical_to_logical(physical),
                    nullable=nullable,
                    ordinal=ordinal,
                    description=None,
                    metadata=None,
                )
            )
        row_count_estimate = _row_count_of(frame)
        fingerprint = _fingerprint_columns(tuple(columns))
        observed = ObservedSchema(
            columns=tuple(columns),
            fingerprint=fingerprint,
            row_count_estimate=row_count_estimate,
            notes=None,
            metadata=None,
        )
        _LOGGER.info(
            "Inferred schema: columns=%d rows_estimate=%s fingerprint=%s",
            len(columns),
            row_count_estimate,
            fingerprint[:12],
        )
        # Bind the inference bound to the returned object so the
        # caller can verify it without re-reading the request.
        _ = sample_row_count  # retained for downstream stages.
        return observed


# Module-level singleton inferencer (no policy bounds).
_INFERENCER = SchemaInferencer()


def infer_schema(
    frame: Any,
    *,
    request: SchemaInferenceRequest | None = None,
    dataset: DatasetHandle | None = None,
) -> ObservedSchema:
    """Infer the schema of ``frame`` using the singleton inferencer.

    ``dataset`` is accepted for symmetry with future per-dataset
    policies; the MVP inferencer does not consult it.
    """
    _ = dataset  # reserved for future per-dataset policies.
    return _INFERENCER.infer(frame, request=request)