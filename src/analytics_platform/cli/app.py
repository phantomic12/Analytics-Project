"""CLI app (Build Queue v2.1 Tasks 106-107).

Thin CLI exposing ``validate-config`` and ``profile-run`` commands.
The CLI consumes the orchestrator / planner only; it never calls
domain modules directly.
"""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from analytics_platform.contracts.common import RunId
from analytics_platform.contracts.datasets import (
    DatasetFormat,
    DatasetHandle,
    DatasetMaterializationStatus,
    DatasetRef,
    StorageBackend,
)
from analytics_platform.contracts.pipeline import AnalysisPlan
from analytics_platform.pipeline.profile_orchestrator import ProfileOrchestrator
from analytics_platform.pipeline.profile_flow_plan import ProfileFlowPlanBuilder


def _synthetic_handle(dataset_id: str) -> DatasetHandle:
    return DatasetHandle(
        dataset_id=dataset_id,
        dataset_ref=DatasetRef(f"ds-{dataset_id}"),
        name=dataset_id,
        format=DatasetFormat.CSV,
        storage_backend=StorageBackend.LOCAL_FS,
        materialization_status=DatasetMaterializationStatus.REGISTERED,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="analytics-platform")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate-config", help="Validate an analysis plan id (no execution).")
    validate.add_argument("--plan-id", required=True)

    run = sub.add_parser("profile-run", help="Run the profile-only pipeline.")
    run.add_argument("--plan-id", required=True)
    run.add_argument("--run-id", default=None)
    return parser


def _cmd_validate_config(plan_id: str) -> int:
    builder = ProfileFlowPlanBuilder()
    plan = builder.build(plan_id=plan_id, datasets=[_synthetic_handle(plan_id)])
    print(f"plan-ok plan_id={plan.plan_id} stages={len(plan.stages)}")
    return 0


def _cmd_profile_run(plan_id: str, run_id: str | None) -> int:
    builder = ProfileFlowPlanBuilder()
    plan = builder.build(plan_id=plan_id, datasets=[_synthetic_handle(plan_id)])
    result = ProfileOrchestrator().run(plan, run_id=run_id)
    rid = run_id or result.run_id
    print(f"run-ok run_id={rid} status={result.status} stages={len(plan.stages)}")
    return 0 if result.status.value == "succeeded" else 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "validate-config":
        return _cmd_validate_config(args.plan_id)
    if args.command == "profile-run":
        return _cmd_profile_run(args.plan_id, args.run_id)
    return 2


if __name__ == "__main__":
    sys.exit(main())
