"""Run manifest writer (Build Queue v2.1 Task 101).

Writes a typed run manifest for a profile-only run.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from analytics_platform.contracts.common import MetricValue
from analytics_platform.contracts.pipeline import (
    AnalysisRunResult,
    RunManifest,
    RunManifestRequest,
)


class RunManifestWriter:
    """Canonical run manifest writer."""

    def write(self, request: RunManifestRequest, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        run_id = request.run_id or "run-unknown"
        path = output_dir / f"{run_id}.json"
        manifest = RunManifest(
            manifest_id=run_id,
            run_id=run_id,
            plan=request.plan,
            artifact_ids=request.artifact_ids,
        )
        path.write_text(
            json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=True)
        )
        return path

