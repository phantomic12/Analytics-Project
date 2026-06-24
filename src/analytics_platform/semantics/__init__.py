"""Semantic inference package (Build Queue v2.1 Task 91).

Re-exports the canonical semantic-typing API.
"""

from __future__ import annotations

from analytics_platform.semantics.inference import (
    DEFAULT_RULES,
    SemanticInferenceError,
    SemanticInferenceRule,
    SemanticInferencer,
    infer_semantic_types,
)

__all__ = [
    "SemanticInferencer",
    "SemanticInferenceError",
    "SemanticInferenceRule",
    "infer_semantic_types",
    "DEFAULT_RULES",
]