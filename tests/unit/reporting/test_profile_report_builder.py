"""Tests for the profile report builder (Build Queue v2.1 Task 99)."""

from __future__ import annotations

from analytics_platform.contracts.reporting import ReportBuildRequest
from analytics_platform.profiling.summaries import compute_summaries
from analytics_platform.reporting.profile_report_builder import (
    ProfileReportBuilder,
    build_profile_report,
)


def _profile():
    return compute_summaries({"a": [1, 2, 3, 4, 5]})


class TestProfileReportBuilder:
    def test_build_request_class(self) -> None:
        request = ProfileReportBuilder().build_request(_profile(), bundle_id="x1")
        assert isinstance(request, ReportBuildRequest)
        assert request.input_bundle.bundle_id == "x1"

    def test_module_helper(self) -> None:
        request = build_profile_report(_profile(), bundle_id="x2")
        assert request.input_bundle.bundle_id == "x2"
