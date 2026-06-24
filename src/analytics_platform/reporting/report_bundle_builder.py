"""Full report bundle builder (Build Queue v2.1 Task 128)."""

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


def _default_dataset() -> DatasetHandle:
    return DatasetHandle(
        dataset_id="ds-default",
        dataset_ref=DatasetRef("ds-default"),
        name="ds-default",
        format=DatasetFormat.CSV,
        storage_backend=StorageBackend.LOCAL_FS,
        materialization_status=DatasetMaterializationStatus.REGISTERED,
    )


class ReportBundleBuilder:
    def build(self, request: ReportBuildRequest) -> ReportInputBundle:
        sections: list[ReportSection] = list(request.input_bundle.sections)
        if request.include_disclaimer_section:
            sections.append(
                ReportSection(
                    section_id="disclaimer",
                    section_type=ReportSectionType.DISCLAIMER,
                    title="Causal disclaimer",
                    body="Causal language is not supported.",
                )
            )
        if request.include_limitation_section:
            sections.append(
                ReportSection(
                    section_id="limitation",
                    section_type=ReportSectionType.LIMITATION,
                    title="Limitations",
                    body="See input bundle warnings.",
                )
            )
        return ReportInputBundle(
            bundle_id=str(request.input_bundle.bundle_id),
            dataset=_default_dataset(),
            sections=tuple(sections),
        )
