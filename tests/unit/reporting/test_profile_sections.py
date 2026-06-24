"""Tests for the profile report sections stage (Build Queue v2.1 Task 98)."""

from __future__ import annotations

from analytics_platform.contracts.reporting import (
    ReportBuildRequest,
    ReportInputBundle,
    ReportSection,
)
from analytics_platform.profiling.summaries import compute_summaries
from analytics_platform.reporting.profile_sections import (
    build_dataset_section,
    build_profile_only_report_bundle,
    build_profile_report_build_request,
    build_profile_sections,
)


def _profile():
    return compute_summaries(
        {
            "a": [1, 2, 3, 4, 5],
            "b": ["x", "y", "x", "y", "x"],
            "c": ["x", "x", "x", "x", "x"],
        }
    )


class TestProfileSections:
    def test_build_dataset_section(self) -> None:
        section = build_dataset_section(_profile())
        assert isinstance(section, ReportSection)
        assert "Dataset:" in section.title
        assert "3 column(s)" in section.body

    def test_build_profile_sections_includes_constant_warning(self) -> None:
        sections = build_profile_sections(_profile())
        assert any("Constant" in s.title for s in sections)

    def test_build_profile_only_report_bundle(self) -> None:
        bundle = build_profile_only_report_bundle(_profile(), bundle_id="b1")
        assert isinstance(bundle, ReportInputBundle)
        assert bundle.bundle_id == "b1"
        assert len(bundle.sections) > 0

    def test_build_profile_report_build_request(self) -> None:
        request = build_profile_report_build_request(_profile(), bundle_id="b2")
        assert isinstance(request, ReportBuildRequest)
        assert request.input_bundle.bundle_id == "b2"
