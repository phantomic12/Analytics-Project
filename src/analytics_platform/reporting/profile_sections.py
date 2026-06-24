"""Profile report sections (Build Queue v2.1 Task 98).

Builds :class:`ReportSection` instances from a
:class:`DatasetProfile` and assembles a :class:`ReportInputBundle`
for the profile-only MVP report.
"""

from __future__ import annotations

from analytics_platform.contracts.common import WarningRecord
from analytics_platform.contracts.datasets import DatasetHandle
from analytics_platform.contracts.profiling import DatasetProfile
from analytics_platform.contracts.reporting import (
    ReportBuildRequest,
    ReportInputBundle,
    ReportSection,
    ReportSectionType,
)

__all__ = [
    "build_dataset_section",
    "build_schema_section",
    "build_profile_sections",
    "build_profile_only_report_bundle",
    "build_profile_report_build_request",
]


def _warning_record_from_warnings(
    warnings: tuple, *, run_id: str | None, stage_id: str | None
) -> tuple[WarningRecord, ...]:
    out: list[WarningRecord] = []
    for w in warnings:
        if isinstance(w, WarningRecord):
            out.append(w)
        else:
            message = getattr(w, "message", None) or str(w)
            code = getattr(w, "code", None) or "PROFILE_WARNING"
            out.append(
                WarningRecord(
                    code=code,
                    message=message,
                    run_id=run_id,
                    stage_id=stage_id,
                )
            )
    return tuple(out)


def build_dataset_section(profile: DatasetProfile) -> ReportSection:
    return ReportSection(
        section_id=f"dataset-{profile.dataset.dataset_id}",
        section_type=ReportSectionType.PROFILE,
        title=f"Dataset: {profile.dataset.name}",
        body=(
            f"Profiled dataset {profile.dataset.name} "
            f"with {len(profile.column_profiles)} column(s)."
        ),
    )


def build_schema_section(profile: DatasetProfile) -> ReportSection:
    return ReportSection(
        section_id="schema-section",
        section_type=ReportSectionType.PROFILE,
        title="Schema",
        body="Schema information is recorded in the dataset profile.",
    )


def build_profile_sections(
    profile: DatasetProfile,
    *,
    run_id: str | None = None,
    stage_id: str | None = None,
) -> tuple[ReportSection, ...]:
    sections: list[ReportSection] = [
        build_dataset_section(profile),
        build_schema_section(profile),
    ]
    if profile.constant_column_warnings:
        warnings = _warning_record_from_warnings(
            profile.constant_column_warnings,
            run_id=run_id,
            stage_id=stage_id,
        )
        sections.append(
            ReportSection(
                section_id="constant-column-warnings",
                section_type=ReportSectionType.PROFILE,
                title="Constant column warnings",
                body=(
                    f"{len(profile.constant_column_warnings)} constant column(s) detected."
                ),
                warnings=warnings,
            )
        )
    if profile.high_cardinality_warnings:
        warnings = _warning_record_from_warnings(
            profile.high_cardinality_warnings,
            run_id=run_id,
            stage_id=stage_id,
        )
        sections.append(
            ReportSection(
                section_id="high-cardinality-warnings",
                section_type=ReportSectionType.PROFILE,
                title="High cardinality warnings",
                body=(
                    f"{len(profile.high_cardinality_warnings)} high-cardinality column(s) detected."
                ),
                warnings=warnings,
            )
        )
    return tuple(sections)


def build_profile_only_report_bundle(
    profile: DatasetProfile,
    *,
    bundle_id: str,
    run_id: str | None = None,
    stage_id: str | None = None,
) -> ReportInputBundle:
    handle: DatasetHandle = profile.dataset
    return ReportInputBundle(
        bundle_id=bundle_id,
        dataset=handle,
        sections=build_profile_sections(profile, run_id=run_id, stage_id=stage_id),
        run_id=run_id,
        stage_id=stage_id,
    )


def build_profile_report_build_request(
    profile: DatasetProfile,
    *,
    bundle_id: str,
    run_id: str | None = None,
    stage_id: str | None = None,
) -> ReportBuildRequest:
    bundle = build_profile_only_report_bundle(
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
