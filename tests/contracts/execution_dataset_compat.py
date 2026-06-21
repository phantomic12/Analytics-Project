"""Compatibility adapter: Execution -> Dataset (Task 48).

Per the interface map, a :class:`MaterializationResult` from a
backend is the canonical input to the dataset registration stage
(4.3). This module is the test-only compatibility helper used by
``tests/contracts/test_compatibility_47_to_50.py`` to verify the
shape transition.
"""

from __future__ import annotations

from analytics_platform.contracts.artifacts import PersistedArtifact
from analytics_platform.contracts.execution import MaterializationPolicy


class ExecutionToDatasetAdapter:
    """Adapter: a backend materialization result -> a valid dataset
    load request / registered handle.

    This adapter is the canonical typed shape of the
    execution -> dataset boundary. It is intentionally minimal
    and only used in compatibility tests.
    """

    @staticmethod
    def extract_dataset_uri(persisted_artifact: PersistedArtifact) -> str:
        """Return the ``source_uri`` to use for a downstream
        :class:`DatasetLoadRequest`.
        """
        return persisted_artifact.location

    @staticmethod
    def default_materialization_policy() -> MaterializationPolicy:
        """Return the canonical default materialization policy used
        when bridging execution -> dataset registration.
        """
        return MaterializationPolicy.EAGER
