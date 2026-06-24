"""Tests for the markdown renderer (Build Queue v2.1 Task 100)."""

from __future__ import annotations

from analytics_platform.contracts.reporting import ReportFormat, ReportRenderRequest
from analytics_platform.profiling.summaries import compute_summaries
from analytics_platform.reporting.markdown_renderer import (
    MarkdownRenderer,
    render_markdown_text,
    render_report_to_markdown,
)
from analytics_platform.reporting.profile_sections import build_profile_only_report_bundle


def _profile():
    return compute_summaries({"a": [1, 2, 3, 4, 5]})


def _bundle():
    return build_profile_only_report_bundle(_profile(), bundle_id="b1")


class TestMarkdownRenderer:
    def test_render_text_contains_title(self) -> None:
        bundle = _bundle()
        text = render_markdown_text(bundle)
        assert bundle.dataset.name in text
        assert "## " in text

    def test_class_render(self) -> None:
        bundle = _bundle()
        request = ReportRenderRequest(
            input_bundle=bundle,
            output_format=ReportFormat.MARKDOWN,
        )
        artifact_set = MarkdownRenderer().render(request)
        assert artifact_set.output_format is ReportFormat.MARKDOWN
        assert artifact_set.metadata is not None
        assert "markdown_length" in artifact_set.metadata

    def test_module_helper(self) -> None:
        bundle = _bundle()
        request = ReportRenderRequest(input_bundle=bundle)
        artifact_set = render_report_to_markdown(request)
        assert artifact_set.render_id == "render-b1"
