"""Tests for the report bundle builder (Build Queue v2.1 Task 128)."""

from __future__ import annotations

from analytics_platform.contracts.datasets import (
    DatasetFormat,
    DatasetHandle,
    DatasetMaterializationStatus,
    DatasetRef,
    StorageBackend,
)
from analytics_platform.contracts.reporting import (
    ReportBuildRequest,
    ReportInputBundle,
    ReportSection,
    ReportSectionType,
)
from analytics_platform.reporting.report_bundle_builder import ReportBundleBuilder


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


class TestReportBundleBuilder:
    def test_build_appends_disclaimer(self) -> None:
        bundle = _bundle()
        request = ReportBuildRequest(
            report_id="r1",
            input_bundle=bundle,
        )
        result = ReportBundleBuilder().build(request)
        kinds = {section.section_type for section in result.sections}
        assert ReportSectionType.DISCLAIMER in kinds
