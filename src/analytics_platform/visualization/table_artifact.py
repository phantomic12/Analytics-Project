"""Table artifact renderer (Build Queue v2.1 Task 114)."""

from __future__ import annotations

from pathlib import Path

from analytics_platform.contracts.reporting import ReportInputBundle, TableArtifactRef, TableFormat
from analytics_platform.contracts.visuals import TableArtifactRef as LegacyTableRef


class TableArtifactRenderer:
    def render(self, bundle: ReportInputBundle, spec: LegacyTableRef, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / "table.txt"
        rows = [bundle.report_metadata, *(section.title for section in bundle.sections)]
        path.write_text("\n".join(rows))
        return path
