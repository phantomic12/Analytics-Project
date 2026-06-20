"""Visual artifact contracts (Build Queue v2.1 Task 17).

Public, dependency-light contracts describing *references* and *specifications*
for future table and chart artifacts. Only standard-library types, Pydantic
primitives, common IDs (Task 11), and artifact persistence contracts (Task 15)
are used. No Polars, Pandas, DuckDB, NumPy, SciPy, Statsmodels, Matplotlib, or
any implementation module is imported, and no raw dataframes, tables, model
objects, backend handles, raw chart images, binary blobs, or large inline
payloads are stored.

Scope:

- ``TableArtifactRef``: typed serializable reference to a persisted table artifact.
- ``ChartArtifactRef``: typed serializable reference to a persisted chart artifact.
- ``VisualArtifactSpec``: typed serializable specification/metadata for a
  visual artifact request or produced visual.

Not implemented here: reporting contracts, registry behavior, chart/table
generation, rendering, Matplotlib usage, visual artifact persistence runtime
behavior, or dataset/lineage/schema/modeling/validation/pipeline contracts.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from analytics_platform.contracts.artifacts import (
    ArtifactHash,
    ArtifactStoragePolicy,
)
from analytics_platform.contracts.common import (
    ArtifactId,
    ReportId,
    RunId,
    StageId,
)

__all__ = [
    "TableFormat",
    "ChartFormat",
    "VisualArtifactRole",
    "TableArtifactRef",
    "ChartArtifactRef",
    "VisualArtifactSpec",
]


# ---------------------------------------------------------------------------
# Shared base configuration
# ---------------------------------------------------------------------------
class _VisualContractModel(BaseModel):
    """Base configuration for visual artifact contracts.

    Immutable (``frozen=True``) and explicit (``extra="forbid"``). There is
    deliberately no field for raw dataframes, tables, model objects, backend
    runtime handles, raw chart images, binary blobs, callables, sessions,
    connections, or large inline payloads.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", use_enum_values=False)


# ===========================================================================
# Stable labels
# ===========================================================================
class TableFormat(str, Enum):
    """Stable format labels for persisted table artifacts.

    Values are stable lowercase strings so they serialize deterministically
    across JSON boundaries. These are *format labels* only; they do not
    implement table generation or rendering.

    - ``CSV``: comma-separated values.
    - ``TSV``: tab-separated values.
    - ``JSON``: JSON array-of-objects or column/row structure.
    - ``PARQUET``: Parquet-encoded table artifact.
    - ``MARKDOWN``: Markdown table text artifact.
    - ``HTML``: HTML table fragment artifact.
    """

    CSV = "csv"
    TSV = "tsv"
    JSON = "json"
    PARQUET = "parquet"
    MARKDOWN = "markdown"
    HTML = "html"


class ChartFormat(str, Enum):
    """Stable format labels for persisted chart/visual artifacts.

    Values are stable lowercase strings. These are *format labels* only; they
    do not implement chart generation, Matplotlib usage, or rendering.

    - ``PNG``: raster PNG image artifact.
    - ``SVG``: vector SVG image artifact.
    - ``PDF``: PDF chart artifact.
    - ``JSON``: JSON-encoded chart spec/trace artifact (no inline dataframes).
    """

    PNG = "png"
    SVG = "svg"
    PDF = "pdf"
    JSON = "json"


class VisualArtifactRole(str, Enum):
    """Role/purpose label for a visual artifact at the contract level.

    Values are stable lowercase strings. The role is an advisory label only;
    it does not implement reporting layout, registry behavior, or rendering.

    - ``SUMMARY``: summary table/chart for a stage or run.
    - ``PROFILE``: dataset profile visual (e.g. distribution chart).
    - ``COMPARISON``: comparison visual across groups/models/datasets.
    - ``DIAGNOSTIC``: diagnostic visual (e.g. residuals, calibration).
    - ``REPORT``: visual intended for an assembled report.
    """

    SUMMARY = "summary"
    PROFILE = "profile"
    COMPARISON = "comparison"
    DIAGNOSTIC = "diagnostic"
    REPORT = "report"


# ===========================================================================
# TableArtifactRef
# ===========================================================================
class TableArtifactRef(_VisualContractModel):
    """Typed serializable reference to a persisted table artifact.

    A durable reference to a persisted table artifact (e.g. a CSV/Parquet
    summary table written by IO). It carries a stable location/URI, a stable
    ``kind`` label (defaulting to ``"table"``), a typed content hash, a storage
    policy inherited from Task 15, and small bounded table-shape descriptors
    (``rows`` / ``columns``). It deliberately does not embed the table body,
    raw dataframe, arrays, model objects, backend handles, or large inline
    payloads.

    Fields:

    - ``artifact_id``: stable artifact identifier.
    - ``kind``: stable artifact type/kind label; defaults to ``"table"``.
    - ``format``: stable table format label (e.g. ``"csv"``, ``"parquet"``).
    - ``location``: stable path or URI-like location of the table artifact.
    - ``hash``: typed content-hash representation.
    - ``storage_policy``: storage/retention policy for the artifact.
    - ``producer``: optional short stable producer label (e.g. stage name).
    - ``producer_run_id`` / ``producer_stage_id``: optional provenance locators.
    - ``rows`` / ``columns``: optional non-negative best-effort shape descriptors.
    - ``schema_fingerprint``: optional stable fingerprint of the table schema.
    - ``created_at``: optional ISO-8601 creation timestamp.
    - ``metadata``: small bounded string-to-string metadata. No raw objects.
    """

    artifact_id: ArtifactId = Field(..., description="Stable artifact identifier.")
    kind: str = Field(
        default="table",
        min_length=1,
        max_length=128,
        description="Stable artifact type/kind label; defaults to 'table'.",
    )
    format: TableFormat = Field(
        ...,
        description="Stable table format label (e.g. 'csv', 'parquet').",
    )
    location: str = Field(
        ...,
        min_length=1,
        max_length=2048,
        description="Stable path or URI-like location of the table artifact (no raw payload).",
    )
    hash: ArtifactHash = Field(..., description="Typed content-hash representation.")
    storage_policy: ArtifactStoragePolicy = Field(
        ...,
        description="Storage/retention policy for the table artifact.",
    )
    producer: str | None = Field(
        default=None,
        min_length=1,
        max_length=256,
        description="Optional short stable producer label (e.g. stage name).",
    )
    producer_run_id: RunId | None = Field(
        default=None,
        description="Optional run that produced the table artifact.",
    )
    producer_stage_id: StageId | None = Field(
        default=None,
        description="Optional stage that produced the table artifact.",
    )
    rows: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative best-effort row count descriptor.",
    )
    columns: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative best-effort column count descriptor.",
    )
    schema_fingerprint: str | None = Field(
        default=None,
        min_length=1,
        max_length=512,
        description="Optional stable fingerprint of the table schema.",
    )
    created_at: datetime | None = Field(
        default=None,
        description="Optional ISO-8601 creation timestamp.",
    )
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )


# ===========================================================================
# ChartArtifactRef
# ===========================================================================
class ChartArtifactRef(_VisualContractModel):
    """Typed serializable reference to a persisted chart/visual artifact.

    A durable reference to a persisted chart/visual artifact (e.g. a PNG/SVG
    chart written by a future chart stage). It carries a stable location/URI,
    a stable ``kind`` label (defaulting to ``"chart"``), a typed content hash,
    a storage policy inherited from Task 15, an optional format-specific
    ``mime_type`` hint, and optional dimension descriptors. It deliberately
    does not embed raw chart images, binary blobs, dataframe handles, model
    objects, backend handles, or large inline payloads.

    Fields:

    - ``artifact_id``: stable artifact identifier.
    - ``kind``: stable artifact type/kind label; defaults to ``"chart"``.
    - ``format``: stable chart format label (e.g. ``"png"``, ``"svg"``).
    - ``location``: stable path or URI-like location of the chart artifact.
    - ``hash``: typed content-hash representation.
    - ``storage_policy``: storage/retention policy for the artifact.
    - ``producer``: optional short stable producer label (e.g. stage name).
    - ``producer_run_id`` / ``producer_stage_id``: optional provenance locators.
    - ``mime_type``: optional stable MIME-type hint for the chart artifact.
    - ``width_px`` / ``height_px``: optional non-negative dimension descriptors.
    - ``created_at``: optional ISO-8601 creation timestamp.
    - ``metadata``: small bounded string-to-string metadata. No raw objects.
    """

    artifact_id: ArtifactId = Field(..., description="Stable artifact identifier.")
    kind: str = Field(
        default="chart",
        min_length=1,
        max_length=128,
        description="Stable artifact type/kind label; defaults to 'chart'.",
    )
    format: ChartFormat = Field(
        ...,
        description="Stable chart format label (e.g. 'png', 'svg').",
    )
    location: str = Field(
        ...,
        min_length=1,
        max_length=2048,
        description="Stable path or URI-like location of the chart artifact (no raw payload).",
    )
    hash: ArtifactHash = Field(..., description="Typed content-hash representation.")
    storage_policy: ArtifactStoragePolicy = Field(
        ...,
        description="Storage/retention policy for the chart artifact.",
    )
    producer: str | None = Field(
        default=None,
        min_length=1,
        max_length=256,
        description="Optional short stable producer label (e.g. stage name).",
    )
    producer_run_id: RunId | None = Field(
        default=None,
        description="Optional run that produced the chart artifact.",
    )
    producer_stage_id: StageId | None = Field(
        default=None,
        description="Optional stage that produced the chart artifact.",
    )
    mime_type: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        description="Optional stable MIME-type hint for the chart artifact.",
    )
    width_px: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative chart width in pixels.",
    )
    height_px: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative chart height in pixels.",
    )
    created_at: datetime | None = Field(
        default=None,
        description="Optional ISO-8601 creation timestamp.",
    )
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )


# ===========================================================================
# VisualArtifactSpec
# ===========================================================================
class VisualArtifactSpec(_VisualContractModel):
    """Typed serializable specification for a visual artifact request/output.

    Describes a visual artifact *request* or a *produced visual* at the
    contract level: what kind of visual is wanted/produced, which persisted
    artifact references back it, and small bounded descriptors. It is a
    *specification* only; it does not embed tables, chart images, binary
    blobs, dataframe handles, model objects, backend handles, or large inline
    payloads, and it does not implement rendering or Matplotlib behavior.

    Exactly one of ``table_ref`` / ``chart_ref`` SHOULD be set per spec. The
    contract does not add a cross-field validator to keep the model
    dependency-light and to allow future paired table+chart combinations once
    reporting contracts stabilize.

    Fields:

    - ``spec_id``: optional stable identifier for this visual spec.
    - ``role``: advisory role/purpose label for the visual artifact.
    - ``title``: optional short human-readable title for the visual.
    - ``description``: optional short human-readable description.
    - ``table_ref``: optional reference to a persisted table artifact.
    - ``chart_ref``: optional reference to a persisted chart/visual artifact.
    - ``source_artifact_ids``: stable IDs of source persisted artifacts.
    - ``producer_run_id`` / ``producer_stage_id``: optional provenance locators.
    - ``report_id``: optional report this spec is intended for.
    - ``created_at``: optional ISO-8601 creation timestamp.
    - ``metadata``: small bounded string-to-string metadata. No raw objects.
    """

    spec_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=256,
        description="Optional stable identifier for this visual spec.",
    )
    role: VisualArtifactRole = Field(
        default=VisualArtifactRole.SUMMARY,
        description="Advisory role/purpose label for the visual artifact.",
    )
    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=512,
        description="Optional short human-readable title for the visual.",
    )
    description: str | None = Field(
        default=None,
        min_length=1,
        max_length=4096,
        description="Optional short human-readable description.",
    )
    table_ref: TableArtifactRef | None = Field(
        default=None,
        description="Optional reference to a persisted table artifact.",
    )
    chart_ref: ChartArtifactRef | None = Field(
        default=None,
        description="Optional reference to a persisted chart/visual artifact.",
    )
    source_artifact_ids: tuple[ArtifactId, ...] = Field(
        default=(),
        description="Stable IDs of source persisted artifacts (immutable).",
    )
    producer_run_id: RunId | None = Field(
        default=None,
        description="Optional run that produced the visual spec.",
    )
    producer_stage_id: StageId | None = Field(
        default=None,
        description="Optional stage that produced the visual spec.",
    )
    report_id: ReportId | None = Field(
        default=None,
        description="Optional report this spec is intended for.",
    )
    created_at: datetime | None = Field(
        default=None,
        description="Optional ISO-8601 creation timestamp.",
    )
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )