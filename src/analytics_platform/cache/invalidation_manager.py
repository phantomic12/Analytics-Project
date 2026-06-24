"""Cache invalidation manager (Build Queue v2.1 Task 113)."""

from __future__ import annotations

from typing import Sequence

from analytics_platform.cache.fingerprint_cache import FingerprintCache
from analytics_platform.contracts.cache import CacheFingerprint, CacheKey


class InvalidationManager:
    def __init__(self, cache: FingerprintCache) -> None:
        self._cache = cache

    def invalidate(self, keys: Sequence[CacheKey]) -> tuple[CacheFingerprint, ...]:
        result: list[CacheFingerprint] = []
        for key in keys:
            for fingerprint in key.fingerprints:
                self._cache.invalidate(fingerprint.hash.digest)
            if key.fingerprints:
                result.append(key.fingerprints[0])
        return tuple(result)
