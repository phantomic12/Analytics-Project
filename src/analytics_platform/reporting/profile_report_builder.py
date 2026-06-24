"""Profile report builder (Build Queue v2.1 Task 99).

Assembles a profile-only :class:`ReportInputBundle` and the
corresponding :class:`ReportBuildRequest` from a
:class:`DatasetProfile`.
"""

from __future__ import annotations

from analytics_platform.contracts.profiling import DatasetProfile
from analytics_platform.contracts.reporting import (
    ReportBuildRequest,
    ReportInputBundle,
)
from analytics_platform.reporting.profile_sections import (
    build_profile_only_report_bundle,
    build_profile_sections,
)

__all__ = ["ProfileReportBuilder", "build_profile_report"]


class ProfileReportBuilder:
    """Canonical profile-only report builder."""

    def build_bundle(
        self,
        profile: DatasetProfile,
        *,
        bundle_id: str,
        run_id: str | None = None,
        stage_id: str | None = None,
    ) -> ReportInputBundle:
        return build_profile_only_report_bundle(
            profile,
            bundle_id=bundle_id,
            run_id=run_id,
            stage_id=stage_id,
        )

    def build_request(
        self,
        profile: DatasetProfile,
        *,
        bundle_id: str,
        run_id: str | None = None,
        stage_id: str | None = None,
    ) -> ReportBuildRequest:
        bundle = self.build_bundle(
            profile,
            bundle_id=bundle_id,
            run_id=run_id,
            stage_id=stage_id,
        )
        return ReportBuildRequest(
            report_id=f"report-{bundle_id}",
            input_bundle=bundle,
            run_id=run_id,
            stage_id=stage_id,
        )


def build_profile_report(
    profile: DatasetProfile,
    *,
    bundle_id: str,
    run_id: str | None = None,
    stage_id: str | None = None,
) -> ReportBuildRequest:
    return ProfileReportBuilder().build_request(
        profile,
        bundle_id=bundle_id,
        run_id=run_id,
        stage_id=stage_id,
    )
