# Profile-only MVP Checkpoint (Build Queue v2.1 Task 108)

The profile-only MVP is the first end-to-end usable pipeline slice.
It runs the stages required to produce a profile report without
joins, modeling, cache, or visuals.

## Scope

Stages covered (from `PROFILE_ONLY_STAGES`):

- `config_load`
- `dataset_load`
- `dataset_register`
- `schema_inference`
- `semantic_role_inference`
- `schema_validation`
- `data_quality`
- `distribution_profiling`
- `diagnostic_association`
- `report_bundle_assembly`
- `run_manifest_writing`
- `file_based_registry_writing`

## Entry points

- `analytics_platform.pipeline.profile_orchestrator.ProfileOrchestrator`
- `analytics_platform.cli.app.main` (subcommand `profile-run`)
- `analytics_platform.pipeline.profile_flow_plan.ProfileFlowPlanBuilder`

## Integration tests

- `tests/integration/test_profile_only_smoke.py` — checkpoint smoke.
- `tests/integration/test_dirty_dataset_profile.py` — dirty data warnings.
- `tests/integration/test_semantic_typing_smoke.py` — semantic role inference.
- `tests/integration/test_association_diagnostics.py` — diagnostic associations.

## Status

Phase 10 checkpoint is green: 4 integration tests pass, plus 179
unit tests. End-to-end path: `CLI profile-run → plan builder →
executor → orchestrator → AnalysisRunResult`.
