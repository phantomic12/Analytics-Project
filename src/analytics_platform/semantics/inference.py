"""Semantic inference (Build Queue v2.1 Task 91).

This module is the canonical semantic-typing stage. It consumes an
:class:`analytics_platform.contracts.schemas.ObservedSchema` (or
anything that yields ``(column_name, logical_type)`` tuples) and
produces an
:class:`analytics_platform.contracts.semantics.SemanticTypeInferenceReport`.
The inference is *rule-based* (column-name patterns +
logical-type heuristics) so it can run with no statistics. A
later task may swap in a learned model; the public surface stays
the same.

Per the architecture-test plan (section 5), the ``semantics``
module is a domain module and may import from contracts, core,
the schema package (Task 89), and the approved runtime libraries.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Iterable

from analytics_platform.contracts.common import Issue, Severity
from analytics_platform.contracts.datasets import DatasetHandle
from analytics_platform.contracts.schemas import (
    ColumnName,
    LogicalDataType,
    ObservedSchema,
)
from analytics_platform.contracts.semantics import (
    ColumnRole,
    ColumnRoleAssignment,
    RiskyColumnUse,
    SemanticColumnProfile,
    SemanticColumnType,
    SemanticTypeConfidence,
    SemanticTypeInferenceReport,
    SemanticTypeInferenceRequest,
)
from analytics_platform.core import AnalyticsPlatformError, get_logger

__all__ = [
    "SemanticInferenceError",
    "SemanticInferencer",
    "infer_semantic_types",
    "DEFAULT_RULES",
    "SemanticInferenceRule",
]


_LOGGER = get_logger("semantics.inference")


def _make_issue(code: str, message: str, **extras: Any) -> Issue:
    """Build a typed :class:`Issue` for inference error paths."""
    return Issue(code=code, severity=Severity.ERROR, message=message, **extras)


# ---------------------------------------------------------------------------
# Rule definitions
# ---------------------------------------------------------------------------
# Each rule maps a regex pattern (case-insensitive) against the
# column name to a ``(semantic_type, role, algorithm, base_score)``
# tuple. The rule returns ``None`` when it does not match.
# ``base_score`` is multiplied by evidence (logical-type agreement,
# role overrides) at evaluation time.
class SemanticInferenceRule:
    """A single rule mapping a name pattern to a semantic type.

    Rules are intentionally simple: a compiled regex over the
    column name, an optional logical-type filter (``None`` means
    "any logical type"), and a target semantic type with a base
    confidence score. The inferencer iterates rules in declaration
    order and picks the first match per column; callers that need
    weighted ensemble logic can supply a custom rule list.
    """

    __slots__ = (
        "name",
        "pattern",
        "semantic_type",
        "logical_type_filter",
        "role",
        "algorithm",
        "base_score",
        "_compiled",
    )

    def __init__(
        self,
        name: str,
        pattern: str,
        *,
        semantic_type: SemanticColumnType,
        logical_type_filter: LogicalDataType | None = None,
        role: ColumnRole | None = None,
        algorithm: str = "name_match",
        base_score: float = 0.7,
    ) -> None:
        self.name = name
        self.pattern = pattern
        self.semantic_type = semantic_type
        self.logical_type_filter = logical_type_filter
        self.role = role
        self.algorithm = algorithm
        self.base_score = base_score
        self._compiled = re.compile(pattern, re.IGNORECASE)

    def matches(
        self,
        column_name: ColumnName,
        logical_type: LogicalDataType | None,
    ) -> bool:
        """Return True when this rule matches the given column."""
        if not self._compiled.search(column_name):
            return False
        if self.logical_type_filter is not None:
            if logical_type is None or logical_type is not self.logical_type_filter:
                return False
        return True


# Default rule set. The order matters: identifier / timestamp /
# date rules are tried first because their patterns overlap with
# measurement patterns (``"user_id"`` must match identifier
# before measurement).
DEFAULT_RULES: tuple[SemanticInferenceRule, ...] = (
    SemanticInferenceRule(
        name="id_suffix",
        pattern=r"(^|_)(id|uuid|guid|key)$",
        semantic_type=SemanticColumnType.IDENTIFIER,
        algorithm="name_match",
        base_score=0.9,
    ),
    SemanticInferenceRule(
        name="id_prefix",
        pattern=r"^(id|uuid|guid|key)_",
        semantic_type=SemanticColumnType.IDENTIFIER,
        algorithm="name_match",
        base_score=0.85,
    ),
    SemanticInferenceRule(
        name="timestamp_suffix",
        pattern=r"(^|_)(timestamp|created_at|updated_at|deleted_at|recorded_at)$",
        semantic_type=SemanticColumnType.TIMESTAMP,
        logical_type_filter=LogicalDataType.DATETIME,
        algorithm="name_match",
        base_score=0.85,
    ),
    SemanticInferenceRule(
        name="date_suffix",
        pattern=r"(^|_)(date|day|month|year)$",
        semantic_type=SemanticColumnType.DATE,
        logical_type_filter=LogicalDataType.DATE,
        algorithm="name_match",
        base_score=0.8,
    ),
    SemanticInferenceRule(
        name="bool_flag",
        pattern=r"(^|_)(is_|has_|can_|should_|will_)|(^flag$)|(^active$)|(^enabled$)",
        semantic_type=SemanticColumnType.BOOLEAN_FLAG,
        logical_type_filter=LogicalDataType.BOOLEAN,
        algorithm="name_match",
        base_score=0.8,
    ),
    SemanticInferenceRule(
        name="currency",
        pattern=r"(^|_)(price|amount|cost|revenue|salary|wage|fee|charge)$",
        semantic_type=SemanticColumnType.CURRENCY,
        logical_type_filter=LogicalDataType.FLOAT,
        algorithm="name_match",
        base_score=0.7,
    ),
    SemanticInferenceRule(
        name="geo",
        pattern=r"(^|_)(country|state|city|region|zip|postal|lat|lon|latitude|longitude)$",
        semantic_type=SemanticColumnType.GEOGRAPHIC,
        algorithm="name_match",
        base_score=0.75,
    ),
    SemanticInferenceRule(
        name="count",
        pattern=r"(^|_)(count|num|n|qty|quantity)$",
        semantic_type=SemanticColumnType.COUNT,
        logical_type_filter=LogicalDataType.INTEGER,
        algorithm="name_match",
        base_score=0.7,
    ),
    SemanticInferenceRule(
        name="measurement",
        pattern=r"(^|_)(score|rate|ratio|percent|pct|avg|mean|height|width|weight|age|temp|temperature)$",
        semantic_type=SemanticColumnType.MEASUREMENT,
        logical_type_filter=LogicalDataType.FLOAT,
        algorithm="name_match",
        base_score=0.65,
    ),
    SemanticInferenceRule(
        name="ordinal",
        pattern=r"(^|_)(rank|level|grade|tier|priority|stage|step)$",
        semantic_type=SemanticColumnType.ORDINAL,
        logical_type_filter=LogicalDataType.INTEGER,
        algorithm="name_match",
        base_score=0.6,
    ),
    SemanticInferenceRule(
        name="category",
        pattern=r"(^|_)(category|type|class|kind|group|segment|status|state|tag|label)$",
        semantic_type=SemanticColumnType.CATEGORICAL,
        logical_type_filter=LogicalDataType.STRING,
        algorithm="name_match",
        base_score=0.6,
    ),
    SemanticInferenceRule(
        name="text",
        pattern=r"(^|_)(text|comment|description|note|notes|message|body|content|summary|title|name)$",
        semantic_type=SemanticColumnType.TEXT,
        logical_type_filter=LogicalDataType.STRING,
        algorithm="name_match",
        base_score=0.6,
    ),
)


# Logical-type fallback rules. When no name rule fires, the
# inferencer falls back to a logical-type heuristic so the
# pipeline always gets *something* typed.
_LOGICAL_FALLBACK: dict[LogicalDataType, SemanticColumnType] = {
    LogicalDataType.INTEGER: SemanticColumnType.MEASUREMENT,
    LogicalDataType.FLOAT: SemanticColumnType.MEASUREMENT,
    LogicalDataType.STRING: SemanticColumnType.CATEGORICAL,
    LogicalDataType.CATEGORICAL: SemanticColumnType.CATEGORICAL,
    LogicalDataType.BOOLEAN: SemanticColumnType.BOOLEAN_FLAG,
    LogicalDataType.DATETIME: SemanticColumnType.TIMESTAMP,
    LogicalDataType.DATE: SemanticColumnType.DATE,
    LogicalDataType.TIMEDELTA: SemanticColumnType.MEASUREMENT,
}


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------
class SemanticInferenceError(AnalyticsPlatformError):
    """A typed semantic-inference failure.

    The exception carries the :class:`Issue` payload so reporting
    and registry can group on the stable issue ``code``.
    """

    def __init__(self, issue: Issue) -> None:
        super().__init__(issue.message, context=issue.context)
        self.issue = issue


# ---------------------------------------------------------------------------
# Inferencer
# ---------------------------------------------------------------------------
def _build_confidence(
    rule: SemanticInferenceRule | None,
    *,
    logical_agreement: bool,
) -> SemanticTypeConfidence:
    """Build a :class:`SemanticTypeConfidence` for a matched rule.

    The base score is boosted by ``+0.1`` when the observed
    logical type agrees with the rule's logical-type filter (the
    filter is ``None`` for name-only rules so the agreement bonus
    applies only to typed rules).
    """
    if rule is None:
        return SemanticTypeConfidence(
            score=0.0,
            algorithm="none",
            evidence_count=0,
            notes=None,
        )
    score = rule.base_score
    if rule.logical_type_filter is not None and logical_agreement:
        score = min(1.0, score + 0.1)
    return SemanticTypeConfidence(
        score=score,
        algorithm=rule.algorithm,
        evidence_count=2 if logical_agreement else 1,
        notes=None,
    )


class SemanticInferencer:
    """The canonical semantic-type inferencer.

    The inferencer walks each observed column, tries the
    configured rule list, and falls back to a logical-type
    heuristic when nothing matches. Inferences below
    ``min_confidence`` are still emitted but flagged via
    :class:`RiskyColumnUse`.

    Construction parameters:

    - ``rules``: optional iterable of :class:`SemanticInferenceRule`.
      Defaults to :data:`DEFAULT_RULES`.
    - ``min_confidence``: optional bounded score; defaults to
      ``0.5``. Inferences with a score below this threshold are
      flagged as :class:`RiskyColumnUse` warnings.
    """

    def __init__(
        self,
        *,
        rules: Iterable[SemanticInferenceRule] | None = None,
        min_confidence: float = 0.5,
    ) -> None:
        if not 0.0 <= min_confidence <= 1.0:
            raise SemanticInferenceError(
                _make_issue(
                    code="SEMANTIC_INFERENCE_BAD_MIN_CONFIDENCE",
                    message=(
                        f"min_confidence must be in [0.0, 1.0], got {min_confidence!r}"
                    ),
                )
            )
        self._rules: tuple[SemanticInferenceRule, ...] = tuple(
            rules if rules is not None else DEFAULT_RULES
        )
        self._min_confidence = min_confidence

    @property
    def min_confidence(self) -> float:
        return self._min_confidence

    @property
    def rules(self) -> tuple[SemanticInferenceRule, ...]:
        return self._rules

    def infer(
        self,
        observed: ObservedSchema | Iterable[tuple[ColumnName, LogicalDataType | None]],
        *,
        request: SemanticTypeInferenceRequest | None = None,
    ) -> SemanticTypeInferenceReport:
        """Infer semantic types for ``observed`` and return a report.

        ``request`` is optional; when provided, its
        ``role_overrides`` take precedence over inferred roles and
        its ``min_confidence`` overrides the inferencer's
        construction-time threshold (the inferencer uses ``min`` of
        the two).
        """
        min_confidence = self._min_confidence
        if request is not None:
            # The more restrictive threshold (the larger one)
            # wins so the caller can raise the bar via the request.
            min_confidence = max(min_confidence, request.min_confidence)
        rows = self._normalize(observed)
        column_profiles: list[SemanticColumnProfile] = []
        role_assignments: list[ColumnRoleAssignment] = []
        risky_uses: list[RiskyColumnUse] = []
        overrides = (
            {o.column_name: o for o in request.role_overrides}
            if request is not None
            else {}
        )
        for column_name, logical_type in rows:
            rule, agreement = self._match_rule(column_name, logical_type)
            if rule is not None:
                semantic_type = rule.semantic_type
                confidence = _build_confidence(rule, logical_agreement=agreement)
                algorithm = rule.algorithm
            else:
                semantic_type = _LOGICAL_FALLBACK.get(
                    logical_type or LogicalDataType.UNKNOWN,
                    SemanticColumnType.UNKNOWN,
                )
                confidence = SemanticTypeConfidence(
                    score=0.3,
                    algorithm="logical_fallback",
                    evidence_count=1,
                    notes=None,
                )
                algorithm = "logical_fallback"
            column_profiles.append(
                SemanticColumnProfile(
                    column_name=column_name,
                    semantic_type=semantic_type,
                    logical_type=logical_type,
                    confidence=confidence,
                    alternatives=(),
                    notes=None,
                )
            )
            # Role assignment: user override wins; otherwise use
            # the rule's role (which may be None for untyped rules).
            if column_name in overrides:
                role_assignments.append(overrides[column_name])
            elif rule is not None and rule.role is not None:
                role_assignments.append(
                    ColumnRoleAssignment(
                        column_name=column_name,
                        role=rule.role,
                        assigned_by="inference",
                        assigned_at_confidence=confidence,
                        reason=None,
                        metadata=None,
                    )
                )
            if confidence.score < min_confidence:
                risky_uses.append(
                    RiskyColumnUse(
                        column_name=column_name,
                        inferred_semantic_type=semantic_type,
                        inferred_role=None,
                        actual_use="semantic-type inference",
                        severity=Severity.WARNING,
                        code="SEMANTIC_LOW_CONFIDENCE",
                        message=(
                            f"Semantic type inference for column "
                            f"{column_name!r} produced a low-confidence score "
                            f"{confidence.score:.2f} (algorithm={algorithm})."
                        ),
                        run_id=request.run_id if request else None,
                        stage_id=request.stage_id if request else None,
                    )
                )
        # Build the report. ``dataset`` is required by the contract;
        # synthesize a minimal handle from the request when the
        # caller did not supply one (the caller can patch it later
        # via ``model_copy``).
        from analytics_platform.contracts.datasets import (
            DatasetFormat,
            DatasetMaterializationStatus,
            DatasetRef,
            DatasetRole,
            StorageBackend,
        )

        if request is not None:
            dataset = request.dataset
        else:
            dataset = DatasetHandle(
                dataset_id="unknown",
                dataset_ref=DatasetRef("ds-unknown"),
                name="unknown",
                format=DatasetFormat.UNKNOWN,
                storage_backend=StorageBackend.LOCAL_FS,
                materialization_status=DatasetMaterializationStatus.REGISTERED,
            )
        report = SemanticTypeInferenceReport(
            dataset=dataset,
            column_profiles=tuple(column_profiles),
            role_assignments=tuple(role_assignments),
            risky_uses=tuple(risky_uses),
            issues=(),
            warnings=(),
            run_id=request.run_id if request else None,
            stage_id=request.stage_id if request else None,
            metadata=None,
        )
        _LOGGER.info(
            "Inferred semantic types: columns=%d roles=%d risky=%d",
            len(column_profiles),
            len(role_assignments),
            len(risky_uses),
        )
        return report

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _match_rule(
        self,
        column_name: ColumnName,
        logical_type: LogicalDataType | None,
    ) -> tuple[SemanticInferenceRule | None, bool]:
        """Return ``(rule, logical_agreement)`` for ``column_name``.

        Walks the rule list in declaration order; the first
        matching rule wins. ``logical_agreement`` is ``True`` when
        the rule has a logical-type filter and the observed
        logical type matches.
        """
        for rule in self._rules:
            if rule.matches(column_name, logical_type):
                agreement = (
                    rule.logical_type_filter is not None
                    and logical_type is not None
                    and logical_type is rule.logical_type_filter
                )
                return rule, agreement
        return None, False

    @staticmethod
    def _normalize(
        observed: ObservedSchema | Iterable[tuple[ColumnName, LogicalDataType | None]],
    ) -> list[tuple[ColumnName, LogicalDataType | None]]:
        """Coerce ``observed`` into a list of ``(name, logical_type)`` tuples."""
        if isinstance(observed, ObservedSchema):
            return [(col.name, col.logical_type) for col in observed.columns]
        return [(ColumnName(name), logical) for name, logical in observed]


# Module-level singleton inferencer.
_INFERENCER = SemanticInferencer()


def infer_semantic_types(
    observed: ObservedSchema | Iterable[tuple[ColumnName, LogicalDataType | None]],
    *,
    request: SemanticTypeInferenceRequest | None = None,
    dataset: DatasetHandle | None = None,
) -> SemanticTypeInferenceReport:
    """Infer semantic types using the singleton inferencer.

    ``dataset`` is accepted for symmetry with the inference
    request; when ``request`` is provided the helper passes it
    through unchanged.
    """
    if request is None and dataset is not None:
        request = SemanticTypeInferenceRequest(dataset=dataset)
    return _INFERENCER.infer(observed, request=request)