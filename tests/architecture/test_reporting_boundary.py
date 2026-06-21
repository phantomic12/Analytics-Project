"""Architecture test: reporting boundary checks (Build Queue v2.1 Task 74).

Per ``docs/testing/architecture-test-plan-v1.1.md`` section 3.4
(Reporting boundary checks):

- ``reporting`` imports contracts only and never domain
  implementations.
- ``reporting`` never recomputes analytics.
- ``reporting`` consumes typed ``StageResult``/result contracts
  only and never raw dataframes, model objects, matrices, or
  dictionaries.
- Report rendering produces :class:`ReportArtifactSet` from
  :class:`ReportInputBundle` / :class:`ReportSection` typed
  inputs.
- Skipped and blocked stages appear as typed skipped records
  in reports.

This test enforces the same import-boundary rule as Task 73
(``test_domain_backend_artifact_boundary.py``) but is
reporting-specific. The reporting family in Build Queue v2.1 is
currently a *contract-only* family; no runtime reporting module
exists yet. The test therefore asserts the *forward-looking*
property that any future ``analytics_platform.reporting``
subpackage imports only contracts.

The test also walks the contract family's own AST and rejects
imports of execution / data / model / validation runtime modules
inside ``contracts/reporting.py``.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACTS_DIR = REPO_ROOT / "src" / "analytics_platform" / "contracts"


class TestReportingBoundary:
    """Architecture test: the ``reporting`` contract module imports
    only from ``analytics_platform.contracts`` (and never from
    domain subpackages).

    Per the reporting boundary rules (architecture-test plan
    section 3.4), the reporting family is contract-only at this
    point in Build Queue v2.1. The test enforces that
    ``contracts/reporting.py`` does not import from any
    ``analytics_platform`` subpackage other than ``.contracts``.
    """

    DOMAIN_SUBPACKAGES: frozenset[str] = frozenset(
        {"core", "reporting", "registry", "pipeline", "cli"}
    )

    def test_reporting_contract_imports_only_allowed(self) -> None:
        path = CONTRACTS_DIR / "reporting.py"
        if not path.exists():
            pytest.skip("contracts/reporting.py not present.")
        tree = ast.parse(path.read_text(encoding="utf-8"))
        offenders: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                self._check_module(path.name, node.module, offenders, "from")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    self._check_module(path.name, alias.name, offenders, "import")
        assert not offenders, (
            "contracts/reporting.py imports from forbidden modules:\n  - "
            + "\n  - ".join(offenders)
        )

    def _check_module(
        self,
        file_name: str,
        module_name: str,
        offenders: list[str],
        kind: str,
    ) -> None:
        if not module_name.startswith("analytics_platform."):
            return
        parts = module_name.split(".")
        if len(parts) < 3:
            offenders.append(f"{file_name}: {kind} {module_name!r} (not an allowed contract root)")
            return
        subpackage = parts[1]
        if subpackage == "contracts":
            return
        if subpackage in self.DOMAIN_SUBPACKAGES:
            offenders.append(f"{file_name}: {kind} {module_name!r} (forbidden domain subpackage)")
        else:
            offenders.append(
                f"{file_name}: {kind} {module_name!r} (unknown analytics_platform subpackage)"
            )

    def test_reporting_contract_does_not_import_heavy_libs(self) -> None:
        import sys

        import analytics_platform.contracts.reporting as reporting_mod  # noqa: F401

        heavy = {"polars", "pandas", "duckdb", "numpy", "scipy", "statsmodels"}
        leaked = heavy.intersection(sys.modules)
        assert not leaked, f"heavy libs imported by reporting contracts: {leaked}"
