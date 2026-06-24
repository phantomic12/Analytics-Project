"""Tests for config loader (Build Queue v2.1 Task 80)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from analytics_platform.config import (
    ConfigError,
    ConfigSource,
    LoadConfigRequest,
    LoadedConfig,
    load_config,
)


# ---------------------------------------------------------------------------
# LoadConfigRequest validation
# ---------------------------------------------------------------------------
class TestLoadConfigRequest:
    def test_json_with_path(self) -> None:
        r = LoadConfigRequest(
            source=ConfigSource.JSON, path="/tmp/cfg.json"
        )
        assert r.path == "/tmp/cfg.json"

    def test_yaml_with_path(self) -> None:
        r = LoadConfigRequest(
            source=ConfigSource.YAML, path="/tmp/cfg.yaml"
        )
        assert r.path == "/tmp/cfg.yaml"

    def test_dict_with_data(self) -> None:
        r = LoadConfigRequest(
            source=ConfigSource.DICT, data={"k": "v"}
        )
        assert r.data == {"k": "v"}

    def test_both_path_and_data_rejected(self) -> None:
        with pytest.raises(ValueError):
            LoadConfigRequest(
                source=ConfigSource.JSON,
                path="/tmp/cfg.json",
                data={"k": "v"},
            )

    def test_neither_path_nor_data_rejected(self) -> None:
        with pytest.raises(ValueError):
            LoadConfigRequest(source=ConfigSource.JSON)

    def test_dict_without_data_rejected(self) -> None:
        with pytest.raises(ValueError):
            LoadConfigRequest(source=ConfigSource.DICT)

    def test_json_without_path_rejected(self) -> None:
        with pytest.raises(ValueError):
            LoadConfigRequest(source=ConfigSource.JSON)

    def test_frozen(self) -> None:
        r = LoadConfigRequest(
            source=ConfigSource.DICT, data={"k": "v"}
        )
        with pytest.raises(ValidationError):
            r.source = ConfigSource.JSON  # type: ignore[misc]

    def test_unknown_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            LoadConfigRequest(
                source=ConfigSource.DICT,
                data={"k": "v"},
                extra="x",  # type: ignore[call-arg]
            )


# ---------------------------------------------------------------------------
# load_config
# ---------------------------------------------------------------------------
class TestLoadConfig:
    def test_dict_source(self) -> None:
        r = LoadConfigRequest(
            source=ConfigSource.DICT, data={"a": 1, "b": "x"}
        )
        loaded = load_config(r)
        assert isinstance(loaded, LoadedConfig)
        assert loaded.data == {"a": 1, "b": "x"}
        assert loaded.source is ConfigSource.DICT
        assert loaded.path is None
        assert loaded.size_bytes is None
        assert len(loaded.config_hash) == 16

    def test_json_source(self, tmp_path: Path) -> None:
        path = tmp_path / "cfg.json"
        path.write_text(json.dumps({"a": 1, "b": [1, 2, 3]}), encoding="utf-8")
        r = LoadConfigRequest(source=ConfigSource.JSON, path=str(path))
        loaded = load_config(r)
        assert loaded.data == {"a": 1, "b": [1, 2, 3]}
        assert loaded.path == str(path)
        assert loaded.size_bytes is not None
        assert loaded.size_bytes > 0

    def test_json_not_mapping_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "cfg.json"
        path.write_text("[1, 2, 3]", encoding="utf-8")
        r = LoadConfigRequest(source=ConfigSource.JSON, path=str(path))
        with pytest.raises(ConfigError) as ei:
            load_config(r)
        assert ei.value.issue.code == "CONFIG_NOT_MAPPING"

    def test_json_decode_error(self, tmp_path: Path) -> None:
        path = tmp_path / "cfg.json"
        path.write_text("{not valid json}", encoding="utf-8")
        r = LoadConfigRequest(source=ConfigSource.JSON, path=str(path))
        with pytest.raises(ConfigError) as ei:
            load_config(r)
        assert ei.value.issue.code == "CONFIG_JSON_DECODE_ERROR"

    def test_file_not_found(self) -> None:
        r = LoadConfigRequest(
            source=ConfigSource.JSON, path="/nonexistent/cfg.json"
        )
        with pytest.raises(ConfigError) as ei:
            load_config(r)
        assert ei.value.issue.code == "CONFIG_FILE_NOT_FOUND"

    def test_yaml_source(self, tmp_path: Path, monkeypatch) -> None:
        # The YAML loader requires PyYAML. The test injects a
        # tiny in-process stub if PyYAML is not installed.
        path = tmp_path / "cfg.yaml"
        path.write_text("a: 1\nb: hello\n", encoding="utf-8")

        class _StubYAML:
            @staticmethod
            def safe_load(text: str) -> dict[str, object]:
                parsed: dict[str, object] = {}
                for line in text.splitlines():
                    if ":" in line:
                        k, v = line.split(":", 1)
                        parsed[k.strip()] = v.strip()
                return parsed

        import sys
        import types

        yaml_stub = types.ModuleType("yaml")
        yaml_stub.safe_load = _StubYAML.safe_load  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "yaml", yaml_stub)
        # Force a fresh import path for the loader.
        r = LoadConfigRequest(source=ConfigSource.YAML, path=str(path))
        loaded = load_config(r)
        assert loaded.data == {"a": "1", "b": "hello"}

    def test_config_hash_changes_with_data(self) -> None:
        r1 = LoadConfigRequest(
            source=ConfigSource.DICT, data={"a": 1}
        )
        r2 = LoadConfigRequest(
            source=ConfigSource.DICT, data={"a": 2}
        )
        assert load_config(r1).config_hash != load_config(r2).config_hash

    def test_config_hash_stable_for_same_data(self) -> None:
        r1 = LoadConfigRequest(
            source=ConfigSource.DICT, data={"a": 1, "b": 2}
        )
        r2 = LoadConfigRequest(
            source=ConfigSource.DICT, data={"b": 2, "a": 1}  # diff order
        )
        # Hash is order-insensitive (sort_keys=True).
        assert load_config(r1).config_hash == load_config(r2).config_hash
