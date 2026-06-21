"""Compatibility adapter: Config -> Pipeline (Task 47).

The config-loading stage (4.1) returns an :class:`AnalysisPlan` that
drives every subsequent stage. This module provides the canonical
``build_plan`` adapter used by ``tests/contracts/test_compatibility_47_to_50.py``
to assert that a config-shaped input produces a valid plan.

This module is a test-only helper, not a runtime adapter. The
runtime adapter is deferred to a later implementation task.
"""

from __future__ import annotations

from analytics_platform.contracts.datasets import DatasetHandle
from analytics_platform.contracts.pipeline import (
    AnalysisPlan,
    PipelineStageName,
)


class ConfigToPipelineAdapter:
    """Adapter: a config-shaped input -> a valid ``AnalysisPlan``.

    The config-loading stage produces a plan from the resolved
    configuration. This adapter is the canonical typed shape of
    that transition. It is intentionally minimal: it accepts the
    minimum inputs needed to build a plan and lets the
    :class:`AnalysisPlan` constructor do the rest of the work.
    """

    @staticmethod
    def build_plan(
        *,
        plan_id: str,
        dataset: DatasetHandle,
        stages: tuple[PipelineStageName, ...],
    ) -> AnalysisPlan:
        """Build a minimal :class:`AnalysisPlan` from a config.

        Parameters
        ----------
        plan_id:
            Stable identifier for the plan.
        dataset:
            The single dataset the plan operates on. Multi-dataset
            plans would call :meth:`build_plan` with ``datasets``
            instead.
        stages:
            Tuple of stages the plan executes. ``>= 1`` is required.
        """
        return AnalysisPlan(
            plan_id=plan_id,
            datasets=(dataset,),
            stages=stages,
        )
