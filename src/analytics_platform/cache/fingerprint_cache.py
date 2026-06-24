"""Fingerprint cache (Build Queue v2.1 Task 113)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from analytics_platform.contracts.artifacts import ArtifactHash, ArtifactHashAlgorithm
from analytics_platform.contracts.cache import CacheFingerprint, CacheStatus


def _hash(value: str) -> ArtifactHash:
    return ArtifactHash(algorithm=ArtifactHashAlgorithm.SHA256, digest=value)


class FingerprintCache:
    def __init__(self, cache_dir: Path) -> None:
        self._cache_dir = cache_dir
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def _key_path(self, key_hex: str) -> Path:
        return self._cache_dir / key_hex[:2] / f"{key_hex}.json"

    def _content_fingerprint(self, payload: Any) -> str:
        raw = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()

    def put(self, key: str, payload: Any, kind: str = "input") -> CacheFingerprint:
        key_fp = hashlib.sha256(key.encode()).hexdigest()
        content_fp = self._content_fingerprint(payload)
        path = self._key_path(key_fp)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"payload": payload, "content_fp": content_fp}))
        return CacheFingerprint(kind=kind, hash=_hash(content_fp), label=key[:64])

    def get(self, key: str) -> tuple[CacheStatus, Any | None]:
        key_fp = hashlib.sha256(key.encode()).hexdigest()
        path = self._key_path(key_fp)
        if not path.exists():
            return CacheStatus.MISS, None
        record = json.loads(path.read_text())
        return CacheStatus.HIT, record.get("payload")

    def invalidate(self, key: str) -> None:
        key_fp = hashlib.sha256(key.encode()).hexdigest()
        path = self._key_path(key_fp)
        if path.exists():
            path.unlink()
