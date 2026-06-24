"""Full report renderer (Build Queue v2.1 Task 129)."""

from __future__ import annotations

from datetime import datetime, timezone

from analytics_platform.contracts.reporting import (
    ReportArtifactSet,
    ReportRenderRequest,
)


class ReportRenderer:
    def render(self, request: ReportRenderRequest) -> ReportArtifactSet:
        render_id = f"render-{request.input_bundle.bundle_id}"
        return ReportArtifactSet(
            render_id=render_id,
            output_format=request.output_format,
            output_uri=request.output_uri,
            sections=request.input_bundle.sections,
            rendered_at=datetime.now(timezone.utc),
        )
