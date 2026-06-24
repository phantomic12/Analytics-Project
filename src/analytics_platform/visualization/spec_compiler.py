"""Visualization spec compiler (Build Queue v2.1 Task 114)."""

from __future__ import annotations

from typing import Sequence

from analytics_platform.contracts.reporting import (
    ReportInputBundle,
    TableArtifactRef,
    TableFormat,
)
from analytics_platform.contracts.visuals import (
    ChartArtifactRef,
    ChartFormat,
    VisualArtifactRef,
    VisualArtifactSpec,
    VisualArtifactRole,
)
from analytics_platform.visualization.table_artifact import TableArtifactRenderer
from analytics_platform.visualization.chart_artifact import ChartArtifactRenderer


class SpecCompiler:
    def __init__(self) -> None:
        self._table_renderer = TableArtifactRenderer()
        self._chart_renderer = ChartArtifactRenderer()

    def compile(self, bundle: ReportInputBundle, specs: Sequence[VisualArtifactSpec]) -> Sequence[VisualArtifactRef]:
        compiled: list[VisualArtifactRef] = []
        for spec in specs:
            source = spec.source_artifact or bundle.artifacts[0] if bundle.artifacts else TableArtifactRef(table_format=TableFormat.PLAINTEXT, table_uri="missing")
            role = spec.role or VisualArtifactRole.DASHBOARD
            if role is VisualArtifactRole.DASHBOARD:
                ref = self._table_renderer.render(bundle, source, Path("."))
            elif role is VisualArtifactRole.SUPPLEMENTARY:
                ref = self._chart_renderer.render(spec.to_chart() if hasattr(spec, 'to_chart') else spec, output_dir=Path("."))
                ref = TableArtifactRef(table_format=TableFormat.PLAINTEXT, table_uri=str(ref))
            else:
                ref = self._table_renderer.render(bundle, source, Path("."))
            compiled.append(VisualArtifactRef(visual_id=spec.role.value, source_artifact=source, derived_artifact=ref))
        return compiled
