"""Markdown renderer (Build Queue v2.1 Task 100).

Renders a :class:`ReportInputBundle` to a Markdown string and
returns the typed :class:`ReportArtifactSet` describing the render.
"""

from __future__ import annotations

from io import StringIO

from analytics_platform.contracts.reporting import (
    ReportArtifactSet,
    ReportFormat,
    ReportRenderRequest,
)

__all__ = ["MarkdownRenderer", "render_report_to_markdown", "render_markdown_text"]


class MarkdownRenderer:
    """Canonical Markdown report renderer."""

    def render(self, request: ReportRenderRequest) -> ReportArtifactSet:
        markdown = render_markdown_text(request.input_bundle)
        return ReportArtifactSet(
            render_id=f"render-{request.input_bundle.bundle_id}",
            output_format=request.output_format or ReportFormat.MARKDOWN,
            output_uri=request.output_uri,
            sections=request.input_bundle.sections,
            run_id=request.run_id,
            stage_id=request.stage_id,
            metadata={"markdown_length": str(len(markdown))},
        )


def render_markdown_text(bundle) -> str:
    """Render a :class:`ReportInputBundle` to a Markdown string.

    Kept module-level for easy reuse and testability.
    """
    out = StringIO()
    out.write(f"# {bundle.dataset.name}\n\n")
    for section in bundle.sections:
        out.write(f"## {section.title}\n\n")
        out.write(section.body)
        out.write("\n\n")
        if section.warnings:
            out.write("Warnings:\n\n")
            for warning in section.warnings:
                out.write(f"- {warning.message}\n")
            out.write("\n")
    return out.getvalue()


def render_report_to_markdown(request: ReportRenderRequest) -> ReportArtifactSet:
    return MarkdownRenderer().render(request)
