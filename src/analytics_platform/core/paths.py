"""Runtime metadata and artifact-path rules (Build Queue v2.1 Task 78).

This module is the canonical runtime-metadata / artifact-path
plumbing for the analytics platform:

- :class:`RuntimeContext` carries the per-run metadata that every
  stage consults to decide where to write artifacts (``run_id``,
  ``root_dir``, derived per-run subdirectory, and bounded
  ``max_artifact_bytes``).
- :class:`ArtifactPath` is the typed result of the path-resolution
  helper. The class deliberately stores ``location`` as a
  bounded string (not a real ``Path``) so it is dependency-light
  and serializable.
- :func:`resolve_artifact_path` returns the canonical artifact
  path for a given (kind, name) pair under a
  :class:`RuntimeContext`. The convention is
  ``{root_dir}/artifacts/{run_id}/{kind}/{name}``.

The module uses standard library only (``os`` + ``pathlib``); it
never imports heavy compute libraries or other domain modules.
Per the architecture-test plan (section 3.1), ``core`` may
import from ``contracts`` only.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from analytics_platform.contracts.artifacts import (
    ArtifactStorageMedium,
    ArtifactStoragePolicy,
)

__all__ = [
    "RuntimeContext",
    "ArtifactPath",
    "resolve_artifact_path",
    "validate_artifact_name",
]


# Bounded length for a URI / artifact path. Reuse the artifact
# family's bound (2048) and the dataset handle's bound (2048).
_MAX_PATH_LEN = 2048
# Bounded name: alphanumeric + dot / dash / underscore.
_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")


class RuntimeContext(BaseModel):
    """Per-run runtime metadata.

    A ``RuntimeContext`` is constructed once at the start of a run
    (or the CLI) and threaded through every stage. It is immutable
    (``frozen=True``) and rejects unknown fields
    (``extra="forbid"``) so the metadata surface stays explicit.

    Fields:

    - ``run_id``: stable run identifier.
    - ``root_dir``: absolute or relative root directory under
      which the run's artifacts live. Trailing slashes are
      tolerated and normalized.
    - ``max_artifact_bytes``: non-negative upper bound on the size
      of any single artifact produced by this run. ``0`` means
      "no bound" (used by tests).
    - ``subdir_kind_label``: optional bounded label that, when
      set, becomes the per-kind subdirectory name in
      :func:`resolve_artifact_path`. Defaults to ``"kind"``.
    """

    run_id: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Stable run identifier.",
    )
    root_dir: str = Field(
        ...,
        min_length=1,
        max_length=_MAX_PATH_LEN,
        description="Root directory under which run artifacts live.",
    )
    max_artifact_bytes: int = Field(
        default=0,
        ge=0,
        description="Non-negative upper bound on per-artifact bytes. 0 means 'no bound'.",
    )
    subdir_kind_label: str = Field(
        default="kind",
        min_length=1,
        max_length=64,
        description="Optional per-kind subdirectory label. Defaults to 'kind'.",
    )

    model_config = ConfigDict(frozen=True, extra="forbid")

    def normalized_root(self) -> str:
        """Return ``root_dir`` with trailing slashes stripped."""
        return str(Path(self.root_dir))


class ArtifactPath(BaseModel):
    """A typed, serializable artifact path.

    ``ArtifactPath`` deliberately stores ``location`` as a bounded
    string (not a real ``pathlib.Path``) so the value is
    dependency-light and serializable. The companion
    :class:`ArtifactStoragePolicy` is included for downstream
    consumers that want to know the storage intent at a glance.

    Fields:

    - ``location``: bounded URI / path of the artifact.
    - ``kind``: bounded artifact-kind label (e.g. ``"dataset"``).
    - ``run_id``: stable run identifier.
    - ``storage_policy``: :class:`ArtifactStoragePolicy` for the
      artifact (medium + retention + mutable + optional
      replication + optional compression).
    - ``relative_path``: bounded path relative to ``root_dir``.
    """

    location: str = Field(
        ...,
        min_length=1,
        max_length=_MAX_PATH_LEN,
        description="Bounded URI / path of the artifact.",
    )
    kind: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Bounded artifact-kind label.",
    )
    run_id: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Stable run identifier.",
    )
    storage_policy: ArtifactStoragePolicy = Field(
        ...,
        description="Storage policy for the artifact.",
    )
    relative_path: str = Field(
        ...,
        min_length=1,
        max_length=_MAX_PATH_LEN,
        description="Bounded path relative to root_dir.",
    )

    model_config = ConfigDict(frozen=True, extra="forbid")


def validate_artifact_name(name: str) -> None:
    """Raise :class:`ValueError` if ``name`` is not a valid artifact name.

    Valid artifact names are non-empty, bounded, and contain only
    alphanumeric characters, ``.``, ``-``, or ``_``. Path
    separators are forbidden.
    """
    if not name or len(name) > 256:
        raise ValueError(f"artifact name must be 1..256 characters; got len={len(name)}")
    if "/" in name or "\\" in name or ".." in name:
        raise ValueError(f"artifact name must not contain path separators or '..': {name!r}")
    if not _NAME_RE.match(name):
        raise ValueError(f"artifact name {name!r} must match {_NAME_RE.pattern!r}")


def resolve_artifact_path(
    ctx: RuntimeContext,
    *,
    kind: str,
    name: str,
    storage_policy: ArtifactStoragePolicy | None = None,
) -> ArtifactPath:
    """Resolve the canonical artifact path for a (kind, name) pair.

    The convention is
    ``{ctx.normalized_root()}/artifacts/{ctx.run_id}/{ctx.subdir_kind_label}/{name}``.

    The function is pure: it does not touch the filesystem. It
    returns a typed :class:`ArtifactPath` that downstream stages
    (IO, registry, reporting) consume uniformly.
    """
    validate_artifact_name(name)
    if not kind or len(kind) > 64:
        raise ValueError(f"artifact kind must be 1..64 characters; got {kind!r}")
    if storage_policy is None:
        storage_policy = ArtifactStoragePolicy(
            medium=ArtifactStorageMedium.LOCAL_FS,
        )
    relative_path = f"artifacts/{ctx.run_id}/{ctx.subdir_kind_label}/{name}"
    location = f"{ctx.normalized_root()}/{relative_path}"
    if len(location) > _MAX_PATH_LEN:
        raise ValueError(f"resolved artifact path exceeds {_MAX_PATH_LEN} characters")
    return ArtifactPath(
        location=location,
        kind=kind,
        run_id=ctx.run_id,
        storage_policy=storage_policy,
        relative_path=relative_path,
    )


# Re-export the bounded length so tests can import it without
# having to duplicate the magic number.
PATH_MAX_LEN = _MAX_PATH_LEN
