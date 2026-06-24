"""Tests for the fingerprint cache (Build Queue v2.1 Task 113)."""

from __future__ import annotations

from pathlib import Path

import pytest

from analytics_platform.contracts.cache import CacheStatus
from analytics_platform.cache.fingerprint_cache import FingerprintCache


class TestFingerprintCache:
    def test_put_and_get(self, tmp_path: Path) -> None:
        cache = FingerprintCache(tmp_path)
        fingerprint = cache.put("k1", {"a": 1})
        assert fingerprint.kind == "input"
        status, value = cache.get("k1")
        assert status is CacheStatus.HIT
        assert value == {"a": 1}

    def test_invalidate(self, tmp_path: Path) -> None:
        cache = FingerprintCache(tmp_path)
        cache.put("k1", {"a": 1})
        cache.invalidate("k1")
        status, value = cache.get("k1")
        assert status is CacheStatus.MISS
        assert value is None
