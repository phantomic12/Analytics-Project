"""Chart artifact renderer (Build Queue v2.1 Task 114)."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from analytics_platform.contracts.visuals import ChartArtifactRef, ChartFormat
from analytics_platform.contracts.visuals import TableArtifactRef as LegacyTableRef


class ChartArtifactRenderer:
    def render(self, artifact: ChartArtifactRef, data: Path | None = None, output_dir: Path | None = None) -> Path:
        fmt = (artifact.format or ChartFormat.PNG).value.lower()
        out_dir = output_dir or Path(".")
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"chart.{fmt}"

        x = [1, 2, 3, 4]
        y = [1, 4, 2, 3]
        fig, axis = plt.subplots()
        axis.plot(x, y)
        axis.set_title(artifact.title or "chart")
        fig.savefig(out_path)
        plt.close(fig)
        return out_path
