"""Architecture test: domain / backend / artifact boundary checks (Task 73).

Per ``docs/testing/architecture-test-plan-v1.1.md`` section 3.5
(Domain/pipeline boundary checks) and section 3.2 (Contracts do
not import implementations):

- Pipeline is the only cross-module orchestrator.
- Domain modules do not call each other directly.
- Domain modules do not import ``contracts/pipeline.py``.
- Pipeline calls domain modules through their documented
  request/result contracts.
- Registry writing is owned by pipeline; domain modules do not
  write directly.

This is a *documentation-level* test for Build Queue v2.1: at the
current point in the Build Queue, no domain modules exist yet
(pipeline / core / reporting / cli modules are deferred to later
PRs). The test therefore asserts the *forward-looking* property
that no module under the contracts subpackage imports from any
non-contracts analytics_platform subpackage. As domain modules
land, this test will need to be paired with a runtime boundary
test that walks the import graph across all packages.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src" / "analytics_platform"


class TestDomainBackendArtifactBoundary:
    """Architecture test: contract modules import only from
    ``analytics_platform.contracts`` and never from any other
    ``analytics_platform`` subpackage.

    The ``reporting`` / ``registry`` / ``pipeline`` / ``cli`` /
    ``core`` subpackages are domain implementations. Per the
    contract-first discipline, contract modules may not depend on
    them; this test enforces that rule statically by walking the
    AST of every contract module.
    """

    # Subpackages of ``analytics_platform`` that are domain
    # implementations. Contract modules may not import from any of
    # these. Add new domain subpackages to this set as they land.
    DOMAIN_SUBPACKAGES: frozenset[str] = frozenset(
        {"core", "reporting", "registry", "pipeline", "cli"}
    )

    def test_contracts_do_not_import_domain_subpackages(self) -> None:
        contracts_dir = SRC_DIR / "contracts"
        if not contracts_dir.exists():
            pytest.skip("contracts/ directory not present.")
        offenders: list[str] = []
        for path in sorted(contracts_dir.glob("*.py")):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError as exc:  # pragma: no cover - rare
                offenders.append(f"{path.name}: parse error {exc}")
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    self._check_module(path.name, node.module, offenders, "from")
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        self._check_module(path.name, alias.name, offenders, "import")
        assert not offenders, (
            "Contract modules import from domain subpackages:\n  - " + "\n  - ".join(offenders)
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
            # ``analytics_platform.contracts`` is the only allowed
            # in-package import target. ``analytics_platform`` alone
            # is not a valid module import.
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


class TestHeavyLibraryBoundaries:
    """Architecture test: no analytics_platform module transitively
    imports heavy compute libraries at import time.

    Per the architecture-test plan section 3.1, the contract-first
    discipline forbids heavy runtime libraries
    (``polars`` / ``pandas`` / ``duckdb`` / ``numpy`` / ``scipy`` /
    ``statsmodels`` / ``matplotlib``) from being imported at module
    load time. Importing any contract module must not transitively
    load these libraries.
    """

    def test_contracts_subpackage_is_dependency_light(self) -> None:
        # Force the subpackage to be imported so all module-level
        # imports have already run by the time we check sys.modules.
        importlib_contracts = __import__("importlib")
        importlib_contracts.import_module("analytics_platform.contracts")

        heavy = {"polars", "pandas", "duckdb", "numpy", "scipy", "statsmodels"}
        leaked = heavy.intersection(sys.modules)
        assert not leaked, (
            f"contracts subpackage transitively imports heavy lib(s): "
            f"{leaked}. contract modules may import only pydantic, the "
            f"standard library, and other contracts (see "
            f"dependency-rules-v1.1.md)."
        )
