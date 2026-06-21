"""Config loader (Build Queue v2.1 Task 80).

This module is the canonical config loader for the analytics
platform. It reads a typed config from a bounded set of supported
sources (JSON / YAML) and produces a typed
:class:`analytics_platform.contracts.pipeline.AnalysisPlan`.

The contract family defines the *shape* of an analysis plan
(see ``contracts.pipeline.AnalysisPlan``). This module implements
the runtime *loader*:

- :class:`ConfigSource` enumerates the supported source kinds.
- :class:`LoadConfigRequest` carries the input + the bounded
  options.
- :class:`LoadedConfig` is the typed output: a parsed dict
  ready to be turned into a plan.
- :func:`load_config` is the canonical entry point.
- :class:`ConfigError` is raised when the input is malformed.

The module is dependency-light: it imports the standard library
(``json`` + ``pathlib`` + ``typing``) plus the platform's
contract + core layers. Optional YAML support is gated behind a
runtime import; if PyYAML is not installed the loader returns a
clear :class:`ConfigError` rather than failing at module load.
"""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from analytics_platform.contracts.common import Issue, RunId, Severity
from analytics_platform.core import AnalyticsPlatformError, get_logger

__all__ = [
    "ConfigSource",
    "LoadConfigRequest",
    "LoadedConfig",
    "ConfigError",
    "load_config",
]


_LOGGER = get_logger("config")


class ConfigSource(str, Enum):
    """Catalogued config source kinds.

    Values are stable lowercase strings so they serialize
    deterministically across JSON boundaries. ``JSON`` is the
    canonical MVP source; ``YAML`` requires PyYAML to be installed.
    """

    JSON = "json"
    YAML = "yaml"
    DICT = "dict"


class LoadConfigRequest(BaseModel):
    """A typed config-load request.

    The request is intentionally small: a ``source`` (one of
    :class:`ConfigSource`), an optional ``path`` (for file
    sources), and an optional ``data`` (for the in-memory
    ``DICT`` source). At least one of ``path`` or ``data`` must
    be set; the constructor raises :class:`ValueError` when
    neither is provided.

    Fields:

    - ``source``: :class:`ConfigSource` describing the input kind.
    - ``path``: optional bounded absolute or relative file path.
    - ``data``: optional in-memory mapping (used when
      ``source == DICT``).
    - ``run_id`` / ``stage_id``: optional provenance locators.
    """

    source: ConfigSource = Field(..., description="ConfigSource describing the input kind.")
    path: str | None = Field(
        default=None,
        min_length=1,
        max_length=2048,
        description="Optional bounded file path (used when source is JSON or YAML).",
    )
    data: dict[str, Any] | None = Field(
        default=None,
        description="Optional in-memory mapping (used when source is DICT).",
    )
    run_id: RunId | None = None
    stage_id: str | None = None

    model_config = ConfigDict(frozen=True, extra="forbid")

    def model_post_init(self, __context: Any) -> None:
        if self.path is None and self.data is None:
            raise ValueError(
                "LoadConfigRequest requires at least one of 'path' or 'data'."
            )
        if self.path is not None and self.data is not None:
            raise ValueError(
                "LoadConfigRequest accepts at most one of 'path' or 'data'."
            )
        if self.source is ConfigSource.DICT and self.data is None:
            raise ValueError(
                "LoadConfigRequest with source=DICT requires 'data'."
            )
        if self.source in (ConfigSource.JSON, ConfigSource.YAML) and self.path is None:
            raise ValueError(
                f"LoadConfigRequest with source={self.source.value} requires 'path'."
            )


class LoadedConfig(BaseModel):
    """A typed loaded config (parsed dict ready for the plan step).

    The actual mapping is exposed via :attr:`data`. The class
    also records the canonical source kind and the originating
    path (when applicable) so the loader can produce a
    reproducible manifest.

    Fields:

    - ``data``: parsed mapping.
    - ``source``: :class:`ConfigSource` describing the input.
    - ``path``: optional bounded path the config was loaded
      from. ``None`` for in-memory ``DICT`` sources.
    - ``config_hash``: bounded short content hash computed
      from the parsed mapping (for manifest fingerprinting).
    - ``size_bytes``: optional non-negative byte count of the
      raw input. ``None`` for ``DICT`` sources.
    """

    data: dict[str, Any] = Field(..., description="Parsed mapping.")
    source: ConfigSource = Field(..., description="ConfigSource describing the input.")
    path: str | None = Field(
        default=None,
        min_length=1,
        max_length=2048,
        description="Optional bounded path the config was loaded from.",
    )
    config_hash: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Bounded short content hash for manifest fingerprinting.",
    )
    size_bytes: int | None = Field(
        default=None,
        ge=0,
        description="Optional non-negative byte count of the raw input.",
    )

    model_config = ConfigDict(frozen=True, extra="forbid")


class ConfigError(AnalyticsPlatformError):
    """A typed config-load failure.

    The exception carries the :class:`Issue` payload so reporting
    and registry can group on the stable issue ``code``.
    """

    def __init__(self, issue: Issue) -> None:
        super().__init__(issue.message, context=issue.context)
        self.issue = issue


def _make_issue(code: str, message: str, **extras: Any) -> Issue:
    return Issue(code=code, severity=Severity.ERROR, message=message, **extras)


def _config_hash(data: dict[str, Any]) -> str:
    """Return a stable short hash for a parsed mapping.

    The hash is the first 16 hex chars of ``sha256`` of the
    canonical JSON encoding. It is *not* a security hash — it is
    a manifest fingerprint that lets downstream stages detect
    config changes cheaply.
    """
    import hashlib

    canonical = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _load_json(path: Path) -> tuple[dict[str, Any], int]:
    raw = path.read_text(encoding="utf-8")
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ConfigError(
            _make_issue(
                code="CONFIG_NOT_MAPPING",
                message=(
                    f"JSON config at {path} is not a mapping (got "
                    f"{type(parsed).__name__})"
                ),
            )
        )
    return parsed, len(raw.encode("utf-8"))


def _load_yaml(path: Path) -> tuple[dict[str, Any], int]:
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError as exc:  # pragma: no cover - rare
        raise ConfigError(
            _make_issue(
                code="YAML_NOT_INSTALLED",
                message=(
                    f"YAML config at {path} requested but PyYAML is not "
                    f"installed: {exc}"
                ),
            )
        ) from exc
    raw = path.read_text(encoding="utf-8")
    parsed = yaml.safe_load(raw)
    if not isinstance(parsed, dict):
        raise ConfigError(
            _make_issue(
                code="CONFIG_NOT_MAPPING",
                message=(
                    f"YAML config at {path} is not a mapping (got "
                    f"{type(parsed).__name__})"
                ),
            )
        )
    return parsed, len(raw.encode("utf-8"))


def load_config(request: LoadConfigRequest) -> LoadedConfig:
    """Load a typed config from a :class:`LoadConfigRequest`.

    Returns a :class:`LoadedConfig` whose ``data`` is a flat
    mapping. The downstream plan-construction step is responsible
    for turning the mapping into a typed
    :class:`analytics_platform.contracts.pipeline.AnalysisPlan`.
    """
    if request.source is ConfigSource.DICT:
        assert request.data is not None
        return LoadedConfig(
            data=request.data,
            source=request.source,
            path=None,
            config_hash=_config_hash(request.data),
            size_bytes=None,
        )

    assert request.path is not None
    path = Path(request.path)
    if not path.exists():
        raise ConfigError(
            _make_issue(
                code="CONFIG_FILE_NOT_FOUND",
                message=f"Config file not found: {path}",
            )
        )
    try:
        if request.source is ConfigSource.JSON:
            data, size_bytes = _load_json(path)
        elif request.source is ConfigSource.YAML:
            data, size_bytes = _load_yaml(path)
        else:  # pragma: no cover - defensive
            raise ConfigError(
                _make_issue(
                    code="CONFIG_UNSUPPORTED_SOURCE",
                    message=f"Unsupported config source: {request.source.value!r}",
                )
            )
    except ConfigError:
        raise
    except json.JSONDecodeError as exc:
        raise ConfigError(
            _make_issue(
                code="CONFIG_JSON_DECODE_ERROR",
                message=f"JSON decode error in {path}: {exc}",
            )
        ) from exc
    except OSError as exc:
        raise ConfigError(
            _make_issue(
                code="CONFIG_IO_ERROR",
                message=f"OS error reading {path}: {exc}",
            )
        ) from exc

    _LOGGER.info(
        "Loaded config: source=%s path=%s size_bytes=%s config_hash=%s",
        request.source.value,
        request.path,
        size_bytes,
        _config_hash(data),
    )
    return LoadedConfig(
        data=data,
        source=request.source,
        path=request.path,
        config_hash=_config_hash(data),
        size_bytes=size_bytes,
    )
