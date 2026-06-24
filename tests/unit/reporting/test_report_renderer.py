"""Tests for the report renderer (Build Queue v2.1 Task 129)."""

from __future__ import annotations

from analytics_platform.contracts.datasets import (
    DatasetFormat,
    DatasetHandle,
    DatasetMaterializationStatus,
    DatasetRef,
    StorageBackend,
)
from analytics_platform.contracts.reporting import (
    ReportFormat,
    ReportInputBundle,
    ReportRenderRequest,
    ReportSection,
    ReportSectionType,
)
from analytics_platform.reporting.report_renderer import ReportRenderer


def _bundle() -> ReportInputBundle:
    handle = DatasetHandle(
        dataset_id="ds1",
        dataset_ref=DatasetRef("ds1"),
        name="ds1",
        format=DatasetFormat.CSV,
        storage_backend=StorageBackend.LOCAL_FS,
        materialization_status=DatasetMaterializationStatus.REGISTERED,
    )
    return ReportInputBundle(
        bundle_id="b1",
        dataset=handle,
        sections=(
            ReportSection(
                section_id="profile",
                section_type=ReportSectionType.PROFILE,
                title="Profile",
                body="results",
            ),
        ),
    )


class TestReportRenderer:
    def test_render_returns_artifact_set(self) -> None:
        bundle = _bundle()
        request = ReportRenderRequest(
            input_bundle=bundle,
            output_format=ReportFormat.MARKDOWN,
        )
        artifact_set = ReportRenderer().render(request)
        assert artifact_set.output_format is ReportFormat.MARKDOWN
        assert len(artifact_set.sections) == 1
