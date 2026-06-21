"""Tests for reporting contracts (Build Queue v2.1 Tasks 39-40)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from analytics_platform.contracts.artifacts import (
    ArtifactHash,
    ArtifactHashAlgorithm,
    ArtifactRetention,
    ArtifactStorageMedium,
    ArtifactStoragePolicy,
)
from analytics_platform.contracts.common import (
    Issue,
    ReportId,
    Severity,
    WarningRecord,
)
from analytics_platform.contracts.datasets import DatasetHandle
from analytics_platform.contracts.reporting import (
    ReportArtifactSet,
    ReportBuildRequest,
    ReportClaimSummary,
    ReportFormat,
    ReportInputBundle,
    ReportRenderRequest,
    ReportSection,
    ReportSectionType,
    ReportWarningSummary,
)
from analytics_platform.contracts.validation import ClaimLevel
from analytics_platform.contracts.visuals import (
    ChartArtifactRef,
    ChartFormat,
    TableArtifactRef,
    TableFormat,
)


def _handle() -> DatasetHandle:
    return DatasetHandle(dataset_id="d1", dataset_ref="ds-v1", name="orders")


def _bundle() -> ReportInputBundle:
    return ReportInputBundle(
        bundle_id="b1",
        dataset=_handle(),
    )


def _section(
    section_id: str = "s1",
    section_type: ReportSectionType = ReportSectionType.PROFILE,
) -> ReportSection:
    return ReportSection(
        section_id=section_id,
        section_type=section_type,
        title="title",
        body="body",
    )


def _storage_policy() -> ArtifactStoragePolicy:
    return ArtifactStoragePolicy(
        medium=ArtifactStorageMedium.LOCAL_FS,
        retention=ArtifactRetention.PERSISTENT,
    )


def _hash() -> ArtifactHash:
    return ArtifactHash(
        algorithm=ArtifactHashAlgorithm.SHA256,
        digest="abc123",
    )


def _table_ref(artifact_id: str = "a1") -> TableArtifactRef:
    return TableArtifactRef(
        artifact_id=artifact_id,
        format=TableFormat.CSV,
        location="/data/x.csv",
        hash=_hash(),
        storage_policy=_storage_policy(),
    )


def _chart_ref(artifact_id: str = "a2") -> ChartArtifactRef:
    return ChartArtifactRef(
        artifact_id=artifact_id,
        format=ChartFormat.PNG,
        location="/data/x.png",
        hash=_hash(),
        storage_policy=_storage_policy(),
    )


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class TestEnums:
    def test_report_format(self) -> None:
        assert ReportFormat.MARKDOWN.value == "markdown"
        assert ReportFormat.HTML.value == "html"
        assert ReportFormat.PDF.value == "pdf"
        assert ReportFormat.JSON.value == "json"

    def test_section_types(self) -> None:
        assert ReportSectionType.PROFILE.value == "profile"
        assert ReportSectionType.MODEL.value == "model"
        assert ReportSectionType.DIAGNOSTIC.value == "diagnostic"
        assert ReportSectionType.VALIDATION.value == "validation"
        assert ReportSectionType.LIMITATION.value == "limitation"
        assert ReportSectionType.SKIPPED.value == "skipped"
        assert ReportSectionType.DISCLAIMER.value == "disclaimer"


# ---------------------------------------------------------------------------
# ReportSection
# ---------------------------------------------------------------------------
class TestReportSection:
    def test_basic(self) -> None:
        s = _section()
        assert s.body == "body"
        assert s.table_refs == ()
        assert s.chart_refs == ()

    def test_with_artifact_refs(self) -> None:
        s = ReportSection(
            section_id="s1",
            section_type=ReportSectionType.PROFILE,
            title="title",
            body="body",
            table_refs=(_table_ref("a1"),),
            chart_refs=(_chart_ref("a2"),),
            claim_level=ClaimLevel.EXPLANATORY,
            severity=Severity.WARNING,
        )
        assert len(s.table_refs) == 1

    def test_empty_body_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ReportSection(
                section_id="s1",
                section_type=ReportSectionType.PROFILE,
                title="t",
                body="",
            )

    def test_duplicate_table_refs_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ReportSection(
                section_id="s1",
                section_type=ReportSectionType.PROFILE,
                title="t",
                body="b",
                table_refs=(_table_ref("a1"), _table_ref("a1")),
            )

    def test_duplicate_chart_refs_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ReportSection(
                section_id="s1",
                section_type=ReportSectionType.PROFILE,
                title="t",
                body="b",
                chart_refs=(_chart_ref("a1"), _chart_ref("a1")),
            )

    def test_round_trip(self) -> None:
        s = _section()
        assert ReportSection.model_validate(s.model_dump(mode="json")) == s


# ---------------------------------------------------------------------------
# ReportInputBundle
# ---------------------------------------------------------------------------
class TestReportInputBundle:
    def test_basic(self) -> None:
        b = _bundle()
        assert b.sections == ()

    def test_with_sections(self) -> None:
        b = ReportInputBundle(
            bundle_id="b1",
            dataset=_handle(),
            sections=(_section("s1"), _section("s2")),
        )
        assert len(b.sections) == 2

    def test_duplicate_section_ids_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ReportInputBundle(
                bundle_id="b1",
                dataset=_handle(),
                sections=(_section("s1"), _section("s1")),
            )

    def test_naive_created_at_normalized(self) -> None:
        b = ReportInputBundle(
            bundle_id="b1",
            dataset=_handle(),
            created_at=datetime(2026, 6, 20, 18, 0, 0),
        )
        assert b.created_at is not None
        assert b.created_at.tzinfo is timezone.utc

    def test_with_issues_and_warnings(self) -> None:
        b = ReportInputBundle(
            bundle_id="b1",
            dataset=_handle(),
            issues=(Issue(code="I", severity=Severity.WARNING, message="m"),),
            warnings=(WarningRecord(code="W", message="m"),),
        )
        assert len(b.issues) == 1


# ---------------------------------------------------------------------------
# ReportBuildRequest
# ---------------------------------------------------------------------------
class TestReportBuildRequest:
    def test_basic(self) -> None:
        r = ReportBuildRequest(
            report_id=ReportId("rep-1"),
            input_bundle=_bundle(),
        )
        assert r.include_disclaimer_section is True
        assert r.include_limitation_section is True

    def test_disclaimers_off(self) -> None:
        r = ReportBuildRequest(
            report_id=ReportId("rep-1"),
            input_bundle=_bundle(),
            include_disclaimer_section=False,
            include_limitation_section=False,
        )
        assert r.include_disclaimer_section is False


# ---------------------------------------------------------------------------
# ReportRenderRequest
# ---------------------------------------------------------------------------
class TestReportRenderRequest:
    def test_defaults(self) -> None:
        r = ReportRenderRequest(input_bundle=_bundle())
        assert r.output_format is ReportFormat.MARKDOWN

    def test_with_format(self) -> None:
        r = ReportRenderRequest(
            input_bundle=_bundle(),
            output_format=ReportFormat.HTML,
            output_uri="s3://bucket/report.html",
        )
        assert r.output_format is ReportFormat.HTML


# ---------------------------------------------------------------------------
# ReportClaimSummary / ReportWarningSummary
# ---------------------------------------------------------------------------
class TestSummaries:
    def test_claim_summary(self) -> None:
        s = ReportClaimSummary(claim_level=ClaimLevel.EXPLANATORY)
        assert s.causal_warning_count is None

    def test_warning_summary(self) -> None:
        s = ReportWarningSummary(total_warning_count=10)
        assert s.skipped_check_count is None

    def test_negative_counts_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ReportClaimSummary(
                claim_level=ClaimLevel.EXPLANATORY,
                causal_warning_count=-1,
            )


# ---------------------------------------------------------------------------
# ReportArtifactSet
# ---------------------------------------------------------------------------
class TestReportArtifactSet:
    def test_basic(self) -> None:
        r = ReportArtifactSet(
            render_id="r1",
            output_format=ReportFormat.MARKDOWN,
        )
        assert r.sections == ()

    def test_with_sections_and_refs(self) -> None:
        r = ReportArtifactSet(
            render_id="r1",
            output_format=ReportFormat.MARKDOWN,
            sections=(_section("s1"),),
            table_refs=(_table_ref("a1"),),
            claim_summary=ReportClaimSummary(
                claim_level=ClaimLevel.EXPLANATORY
            ),
            warning_summary=ReportWarningSummary(total_warning_count=0),
        )
        assert len(r.sections) == 1
        assert r.claim_summary is not None

    def test_duplicate_section_ids_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ReportArtifactSet(
                render_id="r1",
                output_format=ReportFormat.MARKDOWN,
                sections=(_section("s1"), _section("s1")),
            )

    def test_duplicate_table_ref_ids_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ReportArtifactSet(
                render_id="r1",
                output_format=ReportFormat.MARKDOWN,
                table_refs=(_table_ref("a1"), _table_ref("a1")),
            )

    def test_duplicate_chart_ref_ids_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ReportArtifactSet(
                render_id="r1",
                output_format=ReportFormat.MARKDOWN,
                chart_refs=(_chart_ref("a1"), _chart_ref("a1")),
            )

    def test_naive_rendered_at_normalized(self) -> None:
        r = ReportArtifactSet(
            render_id="r1",
            output_format=ReportFormat.MARKDOWN,
            rendered_at=datetime(2026, 6, 20, 18, 0, 0),
        )
        assert r.rendered_at is not None
        assert r.rendered_at.tzinfo is timezone.utc

    def test_round_trip(self) -> None:
        r = ReportArtifactSet(
            render_id="r1",
            output_format=ReportFormat.MARKDOWN,
        )
        assert ReportArtifactSet.model_validate(
            r.model_dump(mode="json")
        ) == r


def test_reporting_contracts_do_not_import_heavy_libs() -> None:
    import sys

    import analytics_platform.contracts.reporting as reporting_mod  # noqa: F401

    heavy = {"polars", "pandas", "duckdb", "numpy", "scipy", "statsmodels"}
    leaked = heavy.intersection(sys.modules)
    assert not leaked, f"heavy libs imported by reporting contracts: {leaked}"
