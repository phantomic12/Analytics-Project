"""Tests for visual artifact contracts (Build Queue v2.1 Task 17).

Covers ``TableArtifactRef``, ``ChartArtifactRef``, and ``VisualArtifactSpec``:
validation, defaults, serialization round-trips, required reference fields,
rejection of missing/invalid metadata, surface guards against raw
dataframe-like fields and large inline payloads, and an import-weight guard.
These tests avoid heavy compute libraries and do not implement reporting,
registry, chart/table generation, rendering, or visual artifact persistence
runtime behavior.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from analytics_platform.contracts.artifacts import (
    ArtifactHash,
    ArtifactHashAlgorithm,
    ArtifactStorageMedium,
    ArtifactStoragePolicy,
)
from analytics_platform.contracts.visuals import (
    ChartArtifactRef,
    ChartFormat,
    TableArtifactRef,
    TableFormat,
    VisualArtifactRole,
    VisualArtifactSpec,
)

# Helpers
def _hash() -> ArtifactHash:
    return ArtifactHash(
        algorithm=ArtifactHashAlgorithm.SHA256,
        digest="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    )


def _policy(medium: ArtifactStorageMedium = ArtifactStorageMedium.LOCAL_FS) -> ArtifactStoragePolicy:
    return ArtifactStoragePolicy(medium=medium)


def _table_ref(**overrides: object) -> TableArtifactRef:
    defaults: dict[str, object] = {
        "artifact_id": "tbl-1",
        "format": TableFormat.CSV,
        "location": "file:///tmp/tbl-1.csv",
        "hash": _hash(),
        "storage_policy": _policy(),
    }
    defaults.update(overrides)
    return TableArtifactRef(**defaults)  # type: ignore[arg-type]


def _chart_ref(**overrides: object) -> ChartArtifactRef:
    defaults: dict[str, object] = {
        "artifact_id": "chart-1",
        "format": ChartFormat.PNG,
        "location": "file:///tmp/chart-1.png",
        "hash": _hash(),
        "storage_policy": _policy(),
    }
    defaults.update(overrides)
    return ChartArtifactRef(**defaults)  # type: ignore[arg-type]


# Enums
class TestEnums:
    def test_table_format_values(self) -> None:
        assert TableFormat.CSV.value == "csv"
        assert TableFormat.TSV.value == "tsv"
        assert TableFormat.JSON.value == "json"
        assert TableFormat.PARQUET.value == "parquet"
        assert TableFormat.MARKDOWN.value == "markdown"
        assert TableFormat.HTML.value == "html"

    def test_table_format_from_value(self) -> None:
        assert TableFormat("parquet") is TableFormat.PARQUET

    def test_chart_format_values(self) -> None:
        assert ChartFormat.PNG.value == "png"
        assert ChartFormat.SVG.value == "svg"
        assert ChartFormat.PDF.value == "pdf"
        assert ChartFormat.JSON.value == "json"

    def test_chart_format_from_value(self) -> None:
        assert ChartFormat("svg") is ChartFormat.SVG

    def test_role_values(self) -> None:
        assert VisualArtifactRole.SUMMARY.value == "summary"
        assert VisualArtifactRole.PROFILE.value == "profile"
        assert VisualArtifactRole.COMPARISON.value == "comparison"
        assert VisualArtifactRole.DIAGNOSTIC.value == "diagnostic"
        assert VisualArtifactRole.REPORT.value == "report"


# TableArtifactRef
class TestTableArtifactRef:
    def test_valid(self) -> None:
        r = _table_ref()
        assert r.artifact_id == "tbl-1"
        assert r.kind == "table"
        assert r.format is TableFormat.CSV
        assert r.location.startswith("file://")
        assert r.hash.algorithm is ArtifactHashAlgorithm.SHA256
        assert r.storage_policy.medium is ArtifactStorageMedium.LOCAL_FS

    def test_default_kind_is_table(self) -> None:
        assert _table_ref().kind == "table"

    def test_required_fields_present(self) -> None:
        r = _table_ref(producer="p", producer_run_id="run-1", producer_stage_id="s-1")
        for attr in ("location", "kind", "format", "hash", "storage_policy"):
            assert getattr(r, attr) is not None
        assert r.producer == "p"
        assert r.producer_run_id == "run-1"
        assert r.producer_stage_id == "s-1"

    @pytest.mark.parametrize(
        "field", ["artifact_id", "format", "location", "hash", "storage_policy"]
    )
    def test_missing_required_rejected(self, field: str) -> None:
        with pytest.raises(ValidationError):
            _table_ref(**{field: None})  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        "field,value", [("location", ""), ("rows", -1), ("columns", -1)]
    )
    def test_invalid_values_rejected(self, field: str, value: object) -> None:
        with pytest.raises(ValidationError):
            _table_ref(**{field: value})

    def test_with_descriptors(self) -> None:
        r = _table_ref(rows=100, columns=5, schema_fingerprint="fp-abc")
        assert r.rows == 100
        assert r.columns == 5
        assert r.schema_fingerprint == "fp-abc"

    def test_unknown_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _table_ref(dataframe=object())  # type: ignore[call-arg]  # noqa: NOT_USED

    def test_inline_bytes_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _table_ref(payload=b"x" * 100)  # type: ignore[call-arg]  # noqa: NOT_USED

    def test_frozen(self) -> None:
        r = _table_ref()
        with pytest.raises(ValidationError):
            r.format = TableFormat.TSV  # type: ignore[misc]

    def test_round_trip(self) -> None:
        r = _table_ref(
            producer="p", producer_run_id="run-1", producer_stage_id="s-1",
            rows=50, columns=4, schema_fingerprint="fp-1", metadata={"origin": "task-17"},
        )
        data = r.model_dump(mode="json")
        assert data["kind"] == "table"
        assert data["format"] == "csv"
        assert data["hash"]["algorithm"] == "sha256"
        assert data["storage_policy"]["medium"] == "local_fs"
        assert data["rows"] == 50
        restored = TableArtifactRef.model_validate(data)
        assert restored == r
        assert restored.format is TableFormat.CSV
        assert restored.hash.algorithm is ArtifactHashAlgorithm.SHA256
        assert restored.storage_policy.medium is ArtifactStorageMedium.LOCAL_FS


# ChartArtifactRef
class TestChartArtifactRef:
    def test_valid(self) -> None:
        r = _chart_ref()
        assert r.artifact_id == "chart-1"
        assert r.kind == "chart"
        assert r.format is ChartFormat.PNG
        assert r.location.startswith("file://")
        assert r.hash.algorithm is ArtifactHashAlgorithm.SHA256
        assert r.storage_policy.medium is ArtifactStorageMedium.LOCAL_FS

    def test_default_kind_is_chart(self) -> None:
        assert _chart_ref().kind == "chart"

    def test_required_fields_present(self) -> None:
        r = _chart_ref(producer="p", producer_run_id="run-1", producer_stage_id="s-1")
        for attr in ("location", "kind", "format", "hash", "storage_policy"):
            assert getattr(r, attr) is not None
        assert r.producer == "p"
        assert r.producer_run_id == "run-1"
        assert r.producer_stage_id == "s-1"

    @pytest.mark.parametrize(
        "field", ["artifact_id", "format", "location", "hash", "storage_policy"]
    )
    def test_missing_required_rejected(self, field: str) -> None:
        with pytest.raises(ValidationError):
            _chart_ref(**{field: None})  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        "field,value", [("location", ""), ("width_px", -1), ("height_px", -1)]
    )
    def test_invalid_values_rejected(self, field: str, value: object) -> None:
        with pytest.raises(ValidationError):
            _chart_ref(**{field: value})

    def test_with_descriptors(self) -> None:
        r = _chart_ref(mime_type="image/png", width_px=1024, height_px=768)
        assert r.mime_type == "image/png"
        assert r.width_px == 1024
        assert r.height_px == 768

    def test_unknown_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _chart_ref(image=object())  # type: ignore[call-arg]  # noqa: NOT_USED

    def test_inline_image_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _chart_ref(payload=b"\x89PNG" * 10)  # type: ignore[call-arg]  # noqa: NOT_USED

    def test_frozen(self) -> None:
        r = _chart_ref()
        with pytest.raises(ValidationError):
            r.format = ChartFormat.SVG  # type: ignore[misc]

    def test_round_trip(self) -> None:
        r = _chart_ref(
            producer="p", producer_run_id="run-1", producer_stage_id="s-1",
            mime_type="image/svg+xml", width_px=800, height_px=600,
            metadata={"origin": "task-17"},
        )
        data = r.model_dump(mode="json")
        assert data["kind"] == "chart"
        assert data["format"] == "png"
        assert data["hash"]["algorithm"] == "sha256"
        assert data["storage_policy"]["medium"] == "local_fs"
        assert data["width_px"] == 800
        restored = ChartArtifactRef.model_validate(data)
        assert restored == r
        assert restored.format is ChartFormat.PNG
        assert restored.hash.algorithm is ArtifactHashAlgorithm.SHA256
        assert restored.storage_policy.medium is ArtifactStorageMedium.LOCAL_FS


# VisualArtifactSpec
class TestVisualArtifactSpec:
    def test_valid_empty(self) -> None:
        s = VisualArtifactSpec()
        assert s.role is VisualArtifactRole.SUMMARY
        assert s.table_ref is None
        assert s.chart_ref is None
        assert s.source_artifact_ids == ()

    def test_with_table_ref(self) -> None:
        s = VisualArtifactSpec(
            role=VisualArtifactRole.SUMMARY, title="Profile summary",
            table_ref=_table_ref(), source_artifact_ids=("art-1", "art-2"),
        )
        assert s.title == "Profile summary"
        assert s.table_ref is not None
        assert s.table_ref.kind == "table"
        assert s.source_artifact_ids == ("art-1", "art-2")

    def test_with_chart_ref(self) -> None:
        s = VisualArtifactSpec(
            role=VisualArtifactRole.DIAGNOSTIC, chart_ref=_chart_ref(), report_id="report-1",
        )
        assert s.role is VisualArtifactRole.DIAGNOSTIC
        assert s.chart_ref is not None
        assert s.chart_ref.kind == "chart"
        assert s.report_id == "report-1"

    def test_unknown_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            VisualArtifactSpec(dataframe=object())  # type: ignore[call-arg]  # noqa: NOT_USED

    def test_inline_payload_rejected(self) -> None:
        with pytest.raises(ValidationError):
            VisualArtifactSpec(payload=b"x" * 100)  # type: ignore[call-arg]  # noqa: NOT_USED

    def test_frozen(self) -> None:
        s = VisualArtifactSpec()
        with pytest.raises(ValidationError):
            s.title = "changed"  # type: ignore[misc]

    def test_round_trip(self) -> None:
        s = VisualArtifactSpec(
            spec_id="spec-1", role=VisualArtifactRole.COMPARISON,
            title="Model comparison", description="ROC curves across models",
            table_ref=_table_ref(rows=10, columns=3),
            chart_ref=_chart_ref(format=ChartFormat.SVG, width_px=640, height_px=480),
            source_artifact_ids=("art-1",), producer_run_id="run-1",
            producer_stage_id="stage-visuals", report_id="report-2",
            metadata={"origin": "task-17"},
        )
        data = s.model_dump(mode="json")
        assert data["role"] == "comparison"
        assert data["table_ref"]["kind"] == "table"
        assert data["chart_ref"]["format"] == "svg"
        assert data["source_artifact_ids"] == ["art-1"]
        restored = VisualArtifactSpec.model_validate(data)
        assert restored == s
        assert restored.role is VisualArtifactRole.COMPARISON
        assert restored.table_ref is not None
        assert restored.table_ref.format is TableFormat.CSV
        assert restored.chart_ref is not None
        assert restored.chart_ref.format is ChartFormat.SVG


# Surface guards: no raw dataframe-like object fields
def test_table_artifact_ref_field_surface() -> None:
    assert set(TableArtifactRef.model_fields) == {
        "artifact_id", "kind", "format", "location", "hash", "storage_policy",
        "producer", "producer_run_id", "producer_stage_id", "rows", "columns",
        "schema_fingerprint", "created_at", "metadata",
    }


def test_chart_artifact_ref_field_surface() -> None:
    assert set(ChartArtifactRef.model_fields) == {
        "artifact_id", "kind", "format", "location", "hash", "storage_policy",
        "producer", "producer_run_id", "producer_stage_id", "mime_type",
        "width_px", "height_px", "created_at", "metadata",
    }


def test_visual_artifact_spec_field_surface() -> None:
    assert set(VisualArtifactSpec.model_fields) == {
        "spec_id", "role", "title", "description", "table_ref", "chart_ref",
        "source_artifact_ids", "producer_run_id", "producer_stage_id",
        "report_id", "created_at", "metadata",
    }


# Refs point to artifact metadata/refs, not inline payloads
def test_table_ref_uses_artifact_metadata_not_inline_payload() -> None:
    _table_ref()
    assert "body" not in TableArtifactRef.model_fields
    assert "data" not in TableArtifactRef.model_fields
    assert "rows" in TableArtifactRef.model_fields  # descriptor only, optional


def test_chart_ref_uses_artifact_metadata_not_inline_payload() -> None:
    _chart_ref()
    assert "image" not in ChartArtifactRef.model_fields
    assert "blob" not in ChartArtifactRef.model_fields
    assert "bytes" not in ChartArtifactRef.model_fields
    assert "width_px" in ChartArtifactRef.model_fields  # descriptor only, optional


def test_visual_spec_references_artifact_refs_not_payloads() -> None:
    s = VisualArtifactSpec(table_ref=_table_ref(), chart_ref=_chart_ref())
    assert "payload" not in VisualArtifactSpec.model_fields
    assert "data" not in VisualArtifactSpec.model_fields
    assert "image" not in VisualArtifactSpec.model_fields
    assert s.table_ref is not None
    assert s.chart_ref is not None


# Import-weight guard
def test_visual_contracts_do_not_import_heavy_libs() -> None:
    """The visual contracts module must not pull heavy compute libraries."""
    import sys

    import analytics_platform.contracts.visuals as visuals_mod  # noqa: F401

    heavy = {"polars", "pandas", "duckdb", "numpy", "scipy", "statsmodels", "matplotlib"}
    leaked = heavy.intersection(sys.modules)
    assert not leaked, f"heavy libs imported by visual contracts: {leaked}"