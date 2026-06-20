"""Backend-neutral execution + materialization contracts (Tasks 12-13).

Public *references* to runtime/backend-managed objects (not the objects
themselves), plus bounded materialization request/result contracts, letting
pipeline stages and downstream modules pass references around without importing
heavy compute libraries or exposing raw dataframe/relation/model objects.

Scope:

- Task 12: ``ExecutionBackend``, ``BackendId``, ``LazyFrameRef``,
  ``BackendObjectRef``.
- Task 13: ``MaterializationPolicy``, ``MaterializationRequest``,
  ``MaterializationResult``.
- Task 14: ``CollectMode``/``CollectPolicy``,
  ``PandasConversionMode``/``PandasConversionPolicy``,
  ``MemoryBudgetPolicy``, ``ExecutionLimitPolicy``.

Not implemented here: artifact persistence (Task 15; results only reference
artifacts via ``ArtifactRef``), datasets, profiling, joins, features,
modeling, validation, reporting, registry, pipeline orchestration.

Dependency-light: stdlib typing/enums, Pydantic, shared common types only.
Never imports Polars/Pandas/DuckDB/NumPy/SciPy/Statsmodels or any
implementation module; never stores raw dataframes, relations, models,
callables, sessions, connections, or backend handles.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from analytics_platform.contracts.common import (
    ArtifactRef,
    ExecutionStatus,
    RunId,
    StageId,
)

__all__ = [
    "ExecutionBackend",
    "BackendId",
    "LazyFrameRef",
    "BackendObjectRef",
    "MaterializationPolicy",
    "MaterializationRequest",
    "MaterializationResult",
    "CollectMode",
    "CollectPolicy",
    "PandasConversionMode",
    "PandasConversionPolicy",
    "MemoryBudgetPolicy",
    "ExecutionLimitPolicy",
]


# ---------------------------------------------------------------------------
# Execution backend enum
# ---------------------------------------------------------------------------
class ExecutionBackend(str, Enum):
    """Supported/planned backend categories for execution references.

    Values are stable lowercase strings so they serialize deterministically
    across JSON boundaries. Only the backend categories needed for references
    are listed here; this enum does not implement backend behavior.

    Members:

    - ``POLARS``: Polars-based local backend concept (lazy frames are the
      primary MVP execution surface).
    - ``DUCKDB``: DuckDB backend option permitted by the dependency policy.
      Backend *option* only; no DuckDB behavior is implemented in this module.
    - ``LOCAL``: A generic local/in-process backend fallback that is not tied
      to a specific dataframe library. Useful for references that do not
      require a named engine.
    """

    POLARS = "polars"
    DUCKDB = "duckdb"
    LOCAL = "local"


# ---------------------------------------------------------------------------
# Stable identifier aliases
# ---------------------------------------------------------------------------
# Lightweight validated string aliases. ``BackendId`` is a stable identifier
# for a backend/runtime context (e.g. a named execution session). It imposes
# only minimal structural constraints (non-empty, bounded length) so it does
# not overfit a particular ID-generation scheme.
_IdStr = Annotated[str, StringConstraints(min_length=1, max_length=256)]

#: Stable identifier for a backend/runtime context.
BackendId = _IdStr


# ---------------------------------------------------------------------------
# Shared base configuration
# ---------------------------------------------------------------------------
class _ExecutionContractModel(BaseModel):
    """Base configuration for execution reference contracts.

    Contracts are immutable (``frozen=True``) and reject unknown fields
    (``extra="forbid"``) so that the public surface stays explicit and stable
    for downstream consumers. Validation is strict by default and there is
    deliberately no field for raw backend objects.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", use_enum_values=False)


# ---------------------------------------------------------------------------
# LazyFrameRef
# ---------------------------------------------------------------------------
class LazyFrameRef(_ExecutionContractModel):
    """A serializable reference to a lazy dataframe-like backend object.

    Carries *only* metadata and stable identifiers needed to locate a lazy
    frame within a backend runtime context. Must not contain the actual
    Polars/PyArrow/DuckDB object, a callable, a session, a connection, or any
    backend handle. Downstream stages resolve the reference through the
    backend layer, never through this contract.

    Fields:

    - ``backend``: which backend category owns the lazy frame.
    - ``backend_id``: stable identifier of the owning runtime context.
    - ``handle``: stable, backend-specific opaque handle/string identifying
      the lazy frame within ``backend_id``. Plain string only.
    - ``schema_fingerprint``: optional stable fingerprint/hash of the expected
      schema, for cheap equality/mismatch checks without materializing.
    - ``row_count_estimate``: optional non-negative estimated row count.
      Estimate only; not a guarantee. Materialization policies live in Task 13.
    - ``run_id`` / ``stage_id``: optional provenance locators.
    - ``metadata``: small bounded string-to-string metadata. No raw objects.
    """

    backend: ExecutionBackend = Field(..., description="Backend category that owns the lazy frame.")
    backend_id: BackendId = Field(
        ...,
        description="Stable identifier of the backend/runtime context owning the frame.",
    )
    handle: str = Field(
        ...,
        min_length=1,
        max_length=512,
        description=(
            "Stable, backend-specific opaque handle/string identifying the lazy frame within "
            "backend_id. Plain string only; never a raw object."
        ),
    )
    schema_fingerprint: str | None = Field(
        default=None,
        description="Optional stable fingerprint/hash of the lazy frame's expected schema.",
    )
    row_count_estimate: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative estimated row count. Estimate only; Task 13 handles materialization policies.",
    )
    run_id: RunId | None = None
    stage_id: StageId | None = None
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )


# ---------------------------------------------------------------------------
# BackendObjectRef
# ---------------------------------------------------------------------------
class BackendObjectRef(_ExecutionContractModel):
    """A generic reference to a backend-managed object.

    Fallback reference type for backend-managed objects that are not lazy
    dataframe-like frames (for which :class:`LazyFrameRef` should be used).
    Examples: intermediate relations, compiled plan handles, other
    backend-managed artifacts. Like :class:`LazyFrameRef`, it carries only
    metadata and stable identifiers, never the actual backend object,
    callable, session, connection, or handle.

    Fields:

    - ``backend``: which backend category owns the object.
    - ``backend_id``: stable identifier of the owning runtime context.
    - ``object_kind``: stable, short machine-readable kind label (e.g.
      ``"relation"``, ``"plan"``). Plain string label, not a type/callable.
    - ``handle``: stable, backend-specific opaque handle/string identifying
      the object within ``backend_id``. Plain string only.
    - ``run_id`` / ``stage_id``: optional provenance locators.
    - ``metadata``: small bounded string-to-string metadata. No raw objects.
    """

    backend: ExecutionBackend = Field(..., description="Backend category that owns the referenced object.")
    backend_id: BackendId = Field(
        ...,
        description="Stable identifier of the backend/runtime context owning the object.",
    )
    object_kind: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Stable, short machine-readable kind label for the referenced object (e.g. 'relation', 'plan'). Plain string label only.",
    )
    handle: str = Field(
        ...,
        min_length=1,
        max_length=512,
        description="Stable, backend-specific opaque handle/string identifying the object within backend_id. Plain string only; never a raw object.",
    )
    run_id: RunId | None = None
    stage_id: StageId | None = None
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )


# ===========================================================================
# Materialization contracts (Build Queue v2.1 Task 13)
# ===========================================================================
class MaterializationPolicy(str, Enum):
    """Allowed materialization intent/mode for a backend reference.

    Describes *how* a referenced backend object should be turned into a
    persisted or bounded output, not the mechanics. Bounded, serializable
    intent label only; does not implement runtime materialization.

    - ``EAGER``: materialize eagerly into a bounded in-process representation
      owned by the backend runtime. No durable artifact.
    - ``IN_MEMORY``: produce a bounded in-memory backend object reference
      resolvable later within the same runtime context. No durable artifact.
    - ``PERSISTED``: persist the output as an artifact at a stable target
      location/uri. Result references it via :class:`ArtifactRef`; no raw data.
    - ``LAZY``: keep the reference lazy/unmaterialized but record a deferred,
      bounded materialization intent. No data is copied.
    """

    EAGER = "eager"
    IN_MEMORY = "in_memory"
    PERSISTED = "persisted"
    LAZY = "lazy"


class MaterializationRequest(_ExecutionContractModel):
    """A bounded request to materialize an existing backend reference.

    References *exactly one* existing Task 12 execution reference: either
    :class:`LazyFrameRef` (``lazy_frame_ref``) or :class:`BackendObjectRef`
    (``backend_object_ref``). Exactly one must be provided; the other must be
    ``None``. This keeps the source explicit and prevents smuggling raw
    backend objects.

    Optional target locators apply when ``policy`` is ``PERSISTED``:
    ``target_artifact`` (an existing :class:`ArtifactRef` -- a *reference*
    only; artifact persistence itself is Task 15) and ``target_uri`` (bounded
    string/uri when ``target_artifact`` is not yet available).

    Must not carry raw dataframes, arrays, tables, backend runtime objects,
    callables, sessions, or connections.

    Fields:

    - ``policy``: materialization intent/mode.
    - ``lazy_frame_ref`` / ``backend_object_ref``: mutually exclusive source refs.
    - ``target_artifact`` / ``target_uri``: optional persisted-target refs.
    - ``run_id`` / ``stage_id``: optional provenance locators.
    - ``metadata``: small bounded string-to-string metadata. No raw objects.
    """

    policy: MaterializationPolicy = Field(..., description="Materialization intent/mode.")
    lazy_frame_ref: LazyFrameRef | None = Field(
        default=None,
        description="Existing lazy frame reference to materialize. Mutually exclusive with backend_object_ref.",
    )
    backend_object_ref: BackendObjectRef | None = Field(
        default=None,
        description="Existing generic backend object reference to materialize. Mutually exclusive with lazy_frame_ref.",
    )
    target_artifact: ArtifactRef | None = Field(
        default=None,
        description="Optional artifact target reference for PERSISTED policy. Reference only; artifact persistence itself is Task 15.",
    )
    target_uri: str | None = Field(
        default=None,
        min_length=1,
        max_length=1024,
        description="Optional bounded target uri/path for persisted materialized output.",
    )
    run_id: RunId | None = None
    stage_id: StageId | None = None
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )

    @model_validator(mode="after")
    def _exactly_one_source_ref(self) -> "MaterializationRequest":
        refs = [self.lazy_frame_ref, self.backend_object_ref]
        provided = [r for r in refs if r is not None]
        if len(provided) != 1:
            raise ValueError(
                "MaterializationRequest must reference exactly one existing backend object ref "
                "(lazy_frame_ref xor backend_object_ref)."
            )
        return self


class MaterializationResult(_ExecutionContractModel):
    """A bounded result describing what was materialized and where.

    Records the :class:`MaterializationPolicy` applied and the resulting
    reference(s). Must not embed raw data, dataframes, arrays, tables, model
    objects, or backend runtime handles. Typed references:

    - ``PERSISTED``: output referenced via ``artifact`` (an
      :class:`ArtifactRef`) and/or ``target_uri``.
    - ``EAGER``/``IN_MEMORY``/``LAZY``: bounded output referenced via
      ``result_ref`` (a :class:`BackendObjectRef`), never a raw object.

    ``rows``/``size_bytes`` are optional non-negative best-effort descriptions;
    they are *not* execution limits (Task 14) and not guarantees.

    Fields:

    - ``policy``: materialization intent/mode applied.
    - ``status``: execution status of the materialization.
    - ``artifact`` / ``target_uri``: optional persisted-target refs.
    - ``result_ref``: optional in-process/lazy materialized-output ref.
    - ``rows`` / ``size_bytes``: optional non-negative descriptions.
    - ``run_id`` / ``stage_id``: optional provenance locators.
    - ``metadata``: small bounded string-to-string metadata. No raw objects.
    """

    policy: MaterializationPolicy = Field(..., description="Materialization intent/mode that was applied.")
    status: ExecutionStatus = Field(..., description="Execution status of the materialization.")
    artifact: ArtifactRef | None = Field(
        default=None,
        description="Optional artifact reference for PERSISTED outputs.",
    )
    target_uri: str | None = Field(
        default=None,
        min_length=1,
        max_length=1024,
        description="Optional bounded target uri/path for persisted outputs.",
    )
    result_ref: BackendObjectRef | None = Field(
        default=None,
        description="Optional backend object reference for in-process/lazy materialized outputs.",
    )
    rows: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative best-effort row count description. Not a limit (Task 14).",
    )
    size_bytes: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative best-effort byte size description. Not a limit (Task 14).",
    )
    run_id: RunId | None = None
    stage_id: StageId | None = None
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )

    @model_validator(mode="after")
    def _at_least_one_target(self) -> "MaterializationResult":
        if self.artifact is None and self.target_uri is None and self.result_ref is None:
            raise ValueError(
                "MaterializationResult must reference at least one target "
                "(artifact, target_uri, or result_ref)."
            )
        return self


# ===========================================================================
# Execution limit contracts (Build Queue v2.1 Task 14)
# ===========================================================================
# Public, serializable limit *policies* only. They declare how future
# backends/profiling/features/modeling code must express memory, collect, and
# Pandas conversion limits. They do NOT implement runtime enforcement,
# backends, materialization, profiling, features, or modeling behavior.
#
# Defaults are intentionally restrictive: unbounded collect/materialization is
# not representable, and Pandas conversion is forbidden unless explicitly
# bounded (Pandas is permitted later only as a private bounded modeling
# adapter). Memory budgets must be explicit and serializable.
class CollectMode(str, Enum):
    """Whether and how backend lazy data may be collected/materialized.

    Values are stable lowercase strings. There is intentionally no
    ``UNBOUNDED`` member: unbounded collect is not representable by this
    contract. To allow collect, use ``BOUNDED`` and supply explicit limits.

    - ``FORBIDDEN``: collect/materialization is disallowed (default).
    - ``BOUNDED``: collect is allowed only under explicit, required limits
      (``max_rows`` required; ``max_bytes`` optional).
    """

    FORBIDDEN = "forbidden"
    BOUNDED = "bounded"


class CollectPolicy(_ExecutionContractModel):
    """Controls whether and how backend lazy data may be collected/materialized.

    Default behavior disallows collect (``mode=FORBIDDEN``). When collect is
    allowed (``mode=BOUNDED``), ``max_rows`` is required so that collect is
    always explicitly bounded. ``max_bytes`` is an optional additional bound.
    Unbounded collect is not representable and is rejected at construction.

    Must not carry raw dataframes, backend objects, callables, or sessions.

    Fields:

    - ``mode``: collect mode (FORBIDDEN by default).
    - ``max_rows``: required non-negative row bound when ``mode=BOUNDED``.
    - ``max_bytes``: optional non-negative byte bound.
    - ``metadata``: small bounded string-to-string metadata. No raw objects.
    """

    mode: CollectMode = Field(default=CollectMode.FORBIDDEN, description="Collect mode; FORBIDDEN by default.")
    max_rows: int | None = Field(
        default=None,
        ge=0,
        description="Non-negative row bound; required when mode=BOUNDED.",
    )
    max_bytes: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative byte bound on collected data.",
    )
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )

    @model_validator(mode="after")
    def _bounded_requires_explicit_row_limit(self) -> "CollectPolicy":
        if self.mode is CollectMode.BOUNDED and self.max_rows is None:
            raise ValueError(
                "CollectPolicy(mode=bounded) requires an explicit max_rows limit; "
                "unbounded collect is not permitted."
            )
        return self


class PandasConversionMode(str, Enum):
    """Whether and how conversion to Pandas is permitted.

    There is intentionally no ``UNBOUNDED`` member. Pandas is allowed later
    only as a private bounded modeling adapter, so conversion must be explicit
    and bounded when allowed.

    - ``FORBIDDEN``: Pandas conversion is disallowed (default).
    - ``BOUNDED``: conversion is allowed only under explicit, required limits
      (``max_rows`` required; ``max_bytes``/``max_columns`` optional).
    """

    FORBIDDEN = "forbidden"
    BOUNDED = "bounded"


class PandasConversionPolicy(_ExecutionContractModel):
    """Controls whether conversion to Pandas is allowed and under what bounds.

    Default behavior forbids Pandas conversion. When allowed
    (``mode=BOUNDED``), ``max_rows`` is required so conversion is always
    explicitly bounded. Optional ``max_bytes`` and ``max_columns`` further
    bound the materialized representation. Unbounded conversion is not
    representable.

    This policy declares intent only; it does not implement conversion and
    does not import Pandas.

    Fields:

    - ``mode``: conversion mode; FORBIDDEN by default.
    - ``max_rows``: required non-negative row bound when ``mode=BOUNDED``.
    - ``max_bytes``: optional non-negative byte bound.
    - ``max_columns``: optional non-negative column bound.
    - ``metadata``: small bounded string-to-string metadata. No raw objects.
    """

    mode: PandasConversionMode = Field(
        default=PandasConversionMode.FORBIDDEN,
        description="Pandas conversion mode; FORBIDDEN by default.",
    )
    max_rows: int | None = Field(
        default=None,
        ge=0,
        description="Non-negative row bound; required when mode=BOUNDED.",
    )
    max_bytes: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative byte bound on converted data.",
    )
    max_columns: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative column bound on converted data.",
    )
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )

    @model_validator(mode="after")
    def _bounded_requires_explicit_row_limit(self) -> "PandasConversionPolicy":
        if self.mode is PandasConversionMode.BOUNDED and self.max_rows is None:
            raise ValueError(
                "PandasConversionPolicy(mode=bounded) requires an explicit max_rows limit; "
                "unbounded Pandas conversion is not permitted."
            )
        return self


class MemoryBudgetPolicy(_ExecutionContractModel):
    """Explicit, serializable memory budget representation.

    A memory budget is an explicit byte limit (``max_bytes``, required and
    non-negative) with an optional stable ``scope`` label (e.g. ``"stage"``,
    ``"run"``). This is a contract only: it declares the budget and does not
    implement runtime measurement or enforcement.

    Fields:

    - ``max_bytes``: required non-negative memory budget in bytes.
    - ``scope``: optional short stable scope label.
    - ``metadata``: small bounded string-to-string metadata. No raw objects.
    """

    max_bytes: int = Field(
        ...,
        ge=0,
        description="Explicit non-negative memory budget in bytes. Required.",
    )
    scope: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        description="Optional short stable scope label for the budget.",
    )
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )


class ExecutionLimitPolicy(_ExecutionContractModel):
    """Top-level execution limit policy grouping collect, Pandas, and memory limits.

    Bundles the three limit policies into one serializable contract so that
    downstream stages pass a single explicit limit policy. Defaults are
    restrictive: ``collect`` defaults to forbidden, ``pandas_conversion``
    defaults to forbidden, and ``memory_budget`` is required (no implicit
    unbounded budget).

    Does not implement runtime enforcement, backends, profiling, features,
    modeling, or materialization behavior.

    Fields:

    - ``collect``: collect/materialization limit policy (forbidden by default).
    - ``pandas_conversion``: Pandas conversion limit policy (forbidden by default).
    - ``memory_budget``: explicit memory budget (required).
    - ``metadata``: small bounded string-to-string metadata. No raw objects.
    """

    collect: CollectPolicy = Field(
        default_factory=CollectPolicy,
        description="Collect/materialization limit policy; forbidden by default.",
    )
    pandas_conversion: PandasConversionPolicy = Field(
        default_factory=PandasConversionPolicy,
        description="Pandas conversion limit policy; forbidden by default.",
    )
    memory_budget: MemoryBudgetPolicy = Field(
        ...,
        description="Explicit memory budget; required (no implicit unbounded budget).",
    )
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )
