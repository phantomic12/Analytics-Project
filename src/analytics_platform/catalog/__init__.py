"""Dataset registry and lineage catalog (Build Queue v2.1 Tasks 87-88).

This subpackage owns the canonical in-process dataset catalog and
lineage store used by the analytics platform's load, transform,
join, profile, and modeling stages. The catalog is a thin layer on
top of the contract types in ``analytics_platform.contracts``; it
never embeds raw dataframes, file bytes, or backend objects.

Per the architecture-test plan (section 5), the ``catalog`` module
is a domain module and may import from contracts, core, the
datasets runtime store (Task 85), the artifact store (Task 84),
and the approved runtime libraries. Reporting and pipeline consume
catalog state through the typed contracts; they never read the
in-process registries directly.

Scope:

- :class:`DatasetRegistry` (Task 87) — canonical in-process dataset
  registry that pairs :class:`DatasetHandle` with their
  :class:`RegisteredDatasetResult` (lineage + artifact refs).
- :class:`LineageStore` (Task 88) — append-only in-process store of
  :class:`LineageRecord` and :class:`LineageGraphSnapshot` views.
- Module-level singleton helpers (``get_dataset_registry``,
  ``reset_catalog_for_tests``) for convenience.
"""

from __future__ import annotations

from analytics_platform.catalog.dataset_registry import (
    DatasetAlreadyRegistered,
    DatasetRegistry,
    DatasetRegistryError,
    RegistrationOutcome,
    get_dataset_registry,
    register_load_result,
)
from analytics_platform.catalog.lineage_store import (
    LineageStore,
    LineageStoreError,
    get_lineage_store,
    record_lineage,
)

__all__ = [
    # Task 87 — dataset registry
    "DatasetRegistry",
    "DatasetAlreadyRegistered",
    "DatasetRegistryError",
    "RegistrationOutcome",
    "register_load_result",
    "get_dataset_registry",
    # Task 88 — lineage store
    "LineageStore",
    "LineageStoreError",
    "record_lineage",
    "get_lineage_store",
]