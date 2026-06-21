"""Reporting contracts (Build Queue v2.1 Tasks 39-40).

Public contracts for the ``reporting`` contract family declared in
``docs/contracts/contracts-index-v1.1.md``. Reporting contracts
describe the typed shapes that cross stages 4.28-4.30 of the
interface map (report bundle assembly, report rendering, visual
artifact generation). They are dependency-light: they import
``pydantic``, the standard library, and the shared ``common`` /
``datasets`` / ``features`` / ``validation`` / ``visuals``
contracts only. They never embed raw dataframes, sample values,
model objects, or backend objects.

Per the interface map:

- 4.28 (report bundle assembly): ``ReportBuildRequest`` /
  ``ReportInputBundle`` / ``ReportSection``. Missing optional
  stages are represented as skipped sections; reporting never
  recomputes analytics.
- 4.29 (report rendering): ``ReportRenderRequest`` /
  ``ReportArtifactSet`` / ``ReportClaimSummary`` /
  ``ReportWarningSummary``. Reports must include causal
  disclaimer, claim level, limitations, skipped-check
  disclosure, missingness impact, join validation status,
  leakage status, diagnostic status.
- 4.30 (visual artifact generation): ``ReportArtifactSet``
  already references ``TableArtifactRef`` / ``ChartArtifactRef``
  (see ``contracts.visuals``); deferred after profile-only MVP.

Scope:

- ``ReportFormat`` enum.
- ``ReportSectionType`` enum.
- ``ReportSection`` / ``ReportInputBundle`` models.
- ``ReportBuildRequest`` / ``ReportRenderRequest`` /
  ``ReportArtifactSet`` / ``ReportWarningSummary`` /
  ``ReportClaimSummary`` models.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from analytics_platform.contracts.common import (
    ArtifactId,
    Issue,
    ReportId,
    RunId,
    Severity,
    StageId,
    WarningRecord,
)
from analytics_platform.contracts.datasets import DatasetHandle
from analytics_platform.contracts.validation import (
    ClaimLevel,
    ModelValidationReport,
)
from analytics_platform.contracts.visuals import (
    ChartArtifactRef,
    TableArtifactRef,
)

__all__ = [
    "ReportFormat",
    "ReportSectionType",
    "ReportSection",
    "ReportInputBundle",
    "ReportBuildRequest",
    "ReportRenderRequest",
    "ReportArtifactSet",
    "ReportWarningSummary",
    "ReportClaimSummary",
]


# ---------------------------------------------------------------------------
# Shared base configuration
# ---------------------------------------------------------------------------
class _ReportingContractModel(BaseModel):
    """Base configuration for reporting contracts.

    Contracts are immutable (``frozen=True``) and reject unknown fields
    (``extra="forbid"``). They never embed raw dataframes, sample
    values, model objects, or backend objects.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", use_enum_values=False)


# Bounded ratio in [0.0, 1.0] used for percentages in summaries.
_BoundedRatio = Annotated[float, Field(ge=0.0, le=1.0)]


# ===========================================================================
# Enums
# ===========================================================================
class ReportFormat(str, Enum):
    """Catalogued report output formats.

    Values are stable lowercase strings so they serialize deterministically
    across JSON boundaries. ``HTML`` rendering is optional and not part
    of the v1.1 MVP default output.
    """

    MARKDOWN = "markdown"
    HTML = "html"
    JSON = "json"
    PDF = "pdf"


class ReportSectionType(str, Enum):
    """Catalogued report section types.

    Per the interface map, missing optional stages are represented
    as skipped sections of an appropriate type. The MVP supports
    the section types below; new section types are added in later
    tasks.
    """

    PROFILE = "profile"
    QUALITY = "quality"
    JOIN = "join"
    FEATURE = "feature"
    MODEL = "model"
    DIAGNOSTIC = "diagnostic"
    VALIDATION = "validation"
    LIMITATION = "limitation"
    SKIPPED = "skipped"
    DISCLAIMER = "disclaimer"


# ===========================================================================
# ReportSection / ReportInputBundle
# ===========================================================================
class ReportSection(_ReportingContractModel):
    """A single typed report section.

    A report section is the atomic unit of a report bundle. It pairs
    a :class:`ReportSectionType` with the bounded content (a
    free-form text body plus optional typed artifact refs) and the
    typed warnings. Per the interface map, the section type matches
    the kind of analytics that produced the section; the body is
    bounded prose produced by reporting, not raw analytics.

    Fields:

    - ``section_id``: stable identifier.
    - ``section_type``: :class:`ReportSectionType`.
    - ``title``: bounded human-readable title.
    - ``body``: bounded human-readable body.
    - ``table_refs``: optional tuple of :class:`TableArtifactRef`.
    - ``chart_refs``: optional tuple of :class:`ChartArtifactRef`.
    - ``warnings``: tuple of :class:`WarningRecord`.
    - ``claim_level``: optional :class:`ClaimLevel` for the
      claim this section makes (typically ``EXPLANATORY`` for
      modeling sections).
    - ``evidence_grade``: optional :class:`Severity`-like
      enum... (we use the ``Issue`` family) - actually we use
      ``Severity``.
    - ``notes``: optional bounded human-readable note.
    """

    section_id: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Stable identifier.",
    )
    section_type: ReportSectionType = Field(
        ..., description="ReportSectionType."
    )
    title: str = Field(
        ...,
        min_length=1,
        max_length=512,
        description="Bounded human-readable title.",
    )
    body: str = Field(
        ...,
        min_length=1,
        max_length=65536,
        description="Bounded human-readable body (prose produced by reporting).",
    )
    table_refs: tuple[TableArtifactRef, ...] = Field(
        default=(),
        description="Optional tuple of TableArtifactRef.",
    )
    chart_refs: tuple[ChartArtifactRef, ...] = Field(
        default=(),
        description="Optional tuple of ChartArtifactRef.",
    )
    warnings: tuple[WarningRecord, ...] = Field(
        default=(),
        description="Tuple of WarningRecord raised during section assembly (immutable).",
    )
    claim_level: ClaimLevel | None = Field(
        default=None,
        description="Optional ClaimLevel for the claim this section makes.",
    )
    severity: Severity | None = Field(
        default=None,
        description="Optional severity for the claim this section makes.",
    )
    notes: str | None = Field(
        default=None,
        max_length=4096,
        description="Optional bounded human-readable note.",
    )

    @model_validator(mode="after")
    def _table_refs_unique(self) -> "ReportSection":
        seen: set[str] = set()
        for ref in self.table_refs:
            if ref.artifact_id in seen:
                raise ValueError(
                    f"ReportSection has duplicate table_ref artifact_id: {ref.artifact_id!r}."
                )
            seen.add(ref.artifact_id)
        return self

    @model_validator(mode="after")
    def _chart_refs_unique(self) -> "ReportSection":
        seen: set[str] = set()
        for ref in self.chart_refs:
            if ref.artifact_id in seen:
                raise ValueError(
                    f"ReportSection has duplicate chart_ref artifact_id: {ref.artifact_id!r}."
                )
            seen.add(ref.artifact_id)
        return self


class ReportInputBundle(_ReportingContractModel):
    """The typed input bundle for report rendering (stage 4.28).

    Per the interface map, ``ReportInputBundle`` aggregates the
    typed result objects from the analytics stages. Reporting
    consumes contracts only and never recomputes analytics.

    Fields:

    - ``bundle_id``: stable identifier.
    - ``dataset``: :class:`DatasetHandle` for the dataset the
      report describes.
    - ``validation_report``: optional :class:`ModelValidationReport`.
    - ``model_id``: optional :data:`ArtifactId` referencing a
      model artifact (when validation_report is set, this is
      redundant but allowed).
    - ``sections``: tuple of :class:`ReportSection` (immutable;
      may be empty).
    - ``issues`` / ``warnings``: common typed collections.
    - ``created_at``: optional timezone-aware timestamp.
    - ``run_id`` / ``stage_id``: optional provenance locators.
    - ``metadata``: small bounded string-to-string metadata.
    """

    bundle_id: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Stable identifier.",
    )
    dataset: DatasetHandle = Field(
        ...,
        description="DatasetHandle for the dataset the report describes.",
    )
    validation_report: ModelValidationReport | None = Field(
        default=None,
        description="Optional ModelValidationReport.",
    )
    model_id: ArtifactId | None = Field(
        default=None,
        description="Optional ArtifactId referencing a model artifact.",
    )
    sections: tuple[ReportSection, ...] = Field(
        default=(),
        description="Tuple of ReportSection (immutable).",
    )
    issues: tuple[Issue, ...] = Field(
        default=(),
        description="Tuple of common Issue raised during bundle assembly (immutable).",
    )
    warnings: tuple[WarningRecord, ...] = Field(
        default=(),
        description="Tuple of common WarningRecord raised during bundle assembly (immutable).",
    )
    created_at: datetime | None = Field(
        default=None,
        description="Optional timezone-aware timestamp of bundle creation.",
    )
    run_id: RunId | None = None
    stage_id: StageId | None = None
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )

    @model_validator(mode="after")
    def _section_ids_unique(self) -> "ReportInputBundle":
        seen: set[str] = set()
        for section in self.sections:
            if section.section_id in seen:
                raise ValueError(
                    f"ReportInputBundle has duplicate section_id: {section.section_id!r}."
                )
            seen.add(section.section_id)
        return self

    @model_validator(mode="after")
    def _created_at_is_timezone_aware(self) -> "ReportInputBundle":
        if self.created_at is not None and self.created_at.tzinfo is None:
            object.__setattr__(
                self,
                "created_at",
                self.created_at.replace(tzinfo=timezone.utc),
            )
        return self


class ReportBuildRequest(_ReportingContractModel):
    """A typed request to assemble a report bundle (stage 4.28 input).

    Fields:

    - ``report_id``: :data:`ReportId` for the report.
    - ``input_bundle``: :class:`ReportInputBundle`.
    - ``include_disclaimer_section``: when ``True`` (default), the
      bundle includes a ``DISCLAIMER`` section with the causal
      disclaimer, claim level, and limitations.
    - ``include_limitation_section``: when ``True`` (default),
      the bundle includes a ``LIMITATION`` section with
      skipped-check disclosure, missingness impact, join
      validation status, leakage status, and diagnostic status.
    - ``target_audience``: optional bounded audience label
      (``"internal"`` / ``"external"`` / etc.).
    - ``run_id`` / ``stage_id``: optional provenance locators.
    - ``metadata``: small bounded string-to-string metadata.
    """

    report_id: ReportId = Field(..., description="ReportId for the report.")
    input_bundle: ReportInputBundle = Field(
        ...,
        description="InputBundle to assemble the report from.",
    )
    include_disclaimer_section: bool = Field(
        default=True,
        description="When True (default), the bundle includes a DISCLAIMER section.",
    )
    include_limitation_section: bool = Field(
        default=True,
        description="When True (default), the bundle includes a LIMITATION section.",
    )
    target_audience: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        description="Optional bounded audience label.",
    )
    run_id: RunId | None = None
    stage_id: StageId | None = None
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )


class ReportRenderRequest(_ReportingContractModel):
    """A typed request to render a report bundle (stage 4.29 input).

    Fields:

    - ``input_bundle``: :class:`ReportInputBundle`.
    - ``output_format``: :class:`ReportFormat` (defaults to
      ``MARKDOWN``).
    - ``output_uri``: optional bounded uri/path of the rendered
      output.
    - ``run_id`` / ``stage_id``: optional provenance locators.
    - ``metadata``: small bounded string-to-string metadata.
    """

    input_bundle: ReportInputBundle = Field(
        ...,
        description="InputBundle to render.",
    )
    output_format: ReportFormat = Field(
        default=ReportFormat.MARKDOWN,
        description="ReportFormat. Defaults to MARKDOWN.",
    )
    output_uri: str | None = Field(
        default=None,
        min_length=1,
        max_length=2048,
        description="Optional bounded uri/path of the rendered output.",
    )
    run_id: RunId | None = None
    stage_id: StageId | None = None
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )


class ReportClaimSummary(_ReportingContractModel):
    """A typed per-claim summary in a rendered report.

    A claim summary records the typed claim level, evidence
    grade, the bounded approved wording, and the per-section
    counts. Per the interface map, the report must include the
    claim level, limitations, and the causal disclaimer.

    Fields:

    - ``claim_level``: :class:`ClaimLevel` actually emitted.
    - ``approved_wording_count``: optional non-negative count of
      validated / approved-wording claim sections.
    - ``rejected_claim_count``: optional non-negative count of
      rejected claim sections.
    - ``causal_warning_count``: optional non-negative count of
      causal warnings emitted.
    - ``notes``: optional bounded human-readable note.
    """

    claim_level: ClaimLevel = Field(
        ...,
        description="ClaimLevel actually emitted.",
    )
    approved_wording_count: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative count of approved-wording claim sections.",
    )
    rejected_claim_count: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative count of rejected claim sections.",
    )
    causal_warning_count: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative count of causal warnings emitted.",
    )
    notes: str | None = Field(
        default=None,
        max_length=1024,
        description="Optional bounded human-readable note.",
    )


class ReportWarningSummary(_ReportingContractModel):
    """A typed per-warning summary in a rendered report.

    Per the interface map, the report must include skipped-check
    disclosure, missingness impact, join validation status,
    leakage status, and diagnostic status. This summary records
    those counts so consumers can verify disclosure completeness.

    Fields:

    - ``total_warning_count``: optional non-negative count of
      warnings emitted across all sections.
    - ``skipped_check_count``: optional non-negative count of
      skipped checks.
    - ``missingness_impact_count``: optional non-negative count
      of sections reporting missingness impact.
    - ``join_validation_status_count``: optional non-negative
      count of sections reporting join validation status.
    - ``leakage_status_count``: optional non-negative count of
      sections reporting leakage status.
    - ``diagnostic_status_count``: optional non-negative count
      of sections reporting diagnostic status.
    - ``notes``: optional bounded human-readable note.
    """

    total_warning_count: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative count of warnings emitted across all sections.",
    )
    skipped_check_count: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative count of skipped checks.",
    )
    missingness_impact_count: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative count of sections reporting missingness impact.",
    )
    join_validation_status_count: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative count of sections reporting join validation status.",
    )
    leakage_status_count: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative count of sections reporting leakage status.",
    )
    diagnostic_status_count: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative count of sections reporting diagnostic status.",
    )
    notes: str | None = Field(
        default=None,
        max_length=1024,
        description="Optional bounded human-readable note.",
    )


class ReportArtifactSet(_ReportingContractModel):
    """The typed output of report rendering (stage 4.29 / 4.30).

    Per the interface map, a ``ReportArtifactSet`` is the typed
    bundle of section / table / chart artifacts produced by report
    rendering. The set references artifacts by
    :class:`TableArtifactRef` / :class:`ChartArtifactRef`; it does
    not embed raw dataframes or sample values.

    Fields:

    - ``render_id``: stable identifier.
    - ``output_format``: :class:`ReportFormat` that was rendered.
    - ``output_uri``: optional bounded uri/path of the rendered
      output.
    - ``sections``: tuple of :class:`ReportSection` (immutable).
    - ``table_refs``: tuple of :class:`TableArtifactRef`.
    - ``chart_refs``: tuple of :class:`ChartArtifactRef`.
    - ``claim_summary``: optional :class:`ReportClaimSummary`.
    - ``warning_summary``: optional :class:`ReportWarningSummary`.
    - ``issues`` / ``warnings``: common typed collections.
    - ``rendered_at``: optional timezone-aware timestamp.
    - ``run_id`` / ``stage_id``: optional provenance locators.
    - ``metadata``: small bounded string-to-string metadata.
    """

    render_id: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Stable identifier.",
    )
    output_format: ReportFormat = Field(
        ...,
        description="ReportFormat that was rendered.",
    )
    output_uri: str | None = Field(
        default=None,
        min_length=1,
        max_length=2048,
        description="Optional bounded uri/path of the rendered output.",
    )
    sections: tuple[ReportSection, ...] = Field(
        default=(),
        description="Tuple of ReportSection (immutable).",
    )
    table_refs: tuple[TableArtifactRef, ...] = Field(
        default=(),
        description="Tuple of TableArtifactRef (immutable).",
    )
    chart_refs: tuple[ChartArtifactRef, ...] = Field(
        default=(),
        description="Tuple of ChartArtifactRef (immutable).",
    )
    claim_summary: ReportClaimSummary | None = Field(
        default=None,
        description="Optional ReportClaimSummary.",
    )
    warning_summary: ReportWarningSummary | None = Field(
        default=None,
        description="Optional ReportWarningSummary.",
    )
    issues: tuple[Issue, ...] = Field(
        default=(),
        description="Tuple of common Issue raised during rendering (immutable).",
    )
    warnings: tuple[WarningRecord, ...] = Field(
        default=(),
        description="Tuple of common WarningRecord raised during rendering (immutable).",
    )
    rendered_at: datetime | None = Field(
        default=None,
        description="Optional timezone-aware timestamp of rendering.",
    )
    run_id: RunId | None = None
    stage_id: StageId | None = None
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Small bounded string-to-string metadata. No raw objects.",
    )

    @model_validator(mode="after")
    def _section_ids_unique(self) -> "ReportArtifactSet":
        seen: set[str] = set()
        for section in self.sections:
            if section.section_id in seen:
                raise ValueError(
                    f"ReportArtifactSet has duplicate section_id: {section.section_id!r}."
                )
            seen.add(section.section_id)
        return self

    @model_validator(mode="after")
    def _artifact_ids_unique(self) -> "ReportArtifactSet":
        seen_table: set[str] = set()
        for ref in self.table_refs:
            if ref.artifact_id in seen_table:
                raise ValueError(
                    f"ReportArtifactSet has duplicate table_ref artifact_id: {ref.artifact_id!r}."
                )
            seen_table.add(ref.artifact_id)
        seen_chart: set[str] = set()
        for ref in self.chart_refs:
            if ref.artifact_id in seen_chart:
                raise ValueError(
                    f"ReportArtifactSet has duplicate chart_ref artifact_id: {ref.artifact_id!r}."
                )
            seen_chart.add(ref.artifact_id)
        return self

    @model_validator(mode="after")
    def _rendered_at_is_timezone_aware(self) -> "ReportArtifactSet":
        if self.rendered_at is not None and self.rendered_at.tzinfo is None:
            object.__setattr__(
                self,
                "rendered_at",
                self.rendered_at.replace(tzinfo=timezone.utc),
            )
        return self
