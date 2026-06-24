"""Visualization renderer facade (Build Queue v2.1 Task 114)."""

from __future__ import annotations

from pathlib import Path

from analytics_platform.contracts.reporting import ReportInputBundle
from analytics_platform.contracts.visuals import VisualArtifactRef, VisualArtifactSpec
from analytics_platform.visualization.spec_compiler import SpecCompiler


class VisualizationRenderer:
    def __init__(self, compiler: SpecCompiler | None = None) -> None:
        self._compiler = compiler or SpecCompiler()

    def render(self, bundle: ReportInputBundle, specs: list[VisualArtifactSpec]) -> list[VisualArtifactRef]:
        return list(self._compiler.compile(bundle, specs))
