# Build Queue v2.1 — Roadmap Checklist

This document is the human-readable roadmap for the **`Build Queue v2.1 — Contract-First Analytics Platform`** task table.
It mirrors the 141-task table forwarded by Sean Dery on 2026-06-20 and regroups the tasks into phases for easier tracking.

**Source of truth**: the Build Queue v2.1 table in the email titled `Task Table for Data Analytics` (in this fork's `docs/roadmap/`).
**Project repo**: https://github.com/seandery1-beep/Analytics-Project
**Working fork**: https://github.com/phantomic12/Analytics-Project

**Status legend**:

- `[x]` — done in upstream main as of 2026-06-20
- `[ ]` — not yet done
- `[~]` — in progress in this fork (added by a PR)

**Totals**: 141 tasks · **17 done** · **124 remaining**

---

## Phase 0 — Foundation & Docs

- [x] **#1** Project base scaffold _(effort: High)_
  - Goal: Create baseline project files without implementation logic
  - Files: `pyproject.toml; .gitignore; README.md`
  - Commit: `Initialize project base scaffold`
- [x] **#2** Dependency manifest and lock policy _(effort: Max)_
  - Goal: Declare MVP runtime/dev dependencies before implementation depends on them
  - Files: `pyproject.toml; uv.lock; docs/architecture/dependency-policy-v1.1.md`
  - Commit: `Define project dependencies and lock policy`
- [x] **#3** Architecture docs v1.1 _(effort: Max)_
  - Goal: Add source-of-truth architecture docs
  - Files: `docs/architecture/architecture-pack-v1.1.md; docs/architecture/quantitative-analysis-design-v1.1.md`
  - Commit: `Add architecture pack v1.1 docs`
- [x] **#4** Dependency and file-size docs _(effort: Max)_
  - Goal: Define import and modularity rules
  - Files: `docs/architecture/dependency-rules-v1.1.md; docs/architecture/file-size-rules-v1.1.md`
  - Commit: `Add dependency and file-size rules`
- [x] **#5** Statistical validation docs _(effort: Max)_
  - Goal: Define statistical safety rules
  - Files: `docs/architecture/statistical-validation-strategy-v1.1.md`
  - Commit: `Add statistical validation strategy`
- [x] **#6** Interface and contract index docs _(effort: Max)_
  - Goal: Define stage input/output map
  - Files: `docs/contracts/interface-map-v1.1.md; docs/contracts/contracts-index-v1.1.md`
  - Commit: `Add contract interface map`
- [x] **#7** Testing strategy docs _(effort: Max)_
  - Goal: Define contract, integration, architecture, and performance tests
  - Files: `docs/testing/contract-test-plan-v1.1.md; docs/testing/integration-test-plan-v1.1.md; docs/testing/architecture-test-plan-v1.1.md`
  - Commit: `Add testing strategy docs`
- [x] **#8** Performance smoke test plan _(effort: Max)_
  - Goal: Define large-dataset and memory-safety expectations
  - Files: `docs/testing/performance-smoke-test-plan-v1.1.md`
  - Commit: `Add performance smoke test plan`
- [x] **#9** LLM prompt guardrails _(effort: High)_
  - Goal: Create reusable GLM/Cline guardrail docs
  - Files: `docs/prompts/stable-cached-context.md; docs/prompts/implementation-guardrails.md; docs/prompts/contract-build-template.md`
  - Commit: `Add GLM prompt guardrails`
- [x] **#10** Package skeleton _(effort: High)_
  - Goal: Create source/test package layout
  - Files: `src/analytics_platform/__init__.py; src/analytics_platform/contracts/__init__.py; tests/conftest.py`
  - Commit: `Create package skeleton`

## Phase 1 — Public Contracts

- [x] **#11** Common contracts _(effort: Max)_
  - Goal: Define universal IDs, status, issues, warnings, metrics, and artifacts
  - Files: `src/analytics_platform/contracts/common.py; tests/contracts/test_common_contracts.py`
  - Commit: `Add common shared contracts`
- [x] **#12** Execution reference contracts _(effort: Max)_
  - Goal: Define backend-neutral execution references
  - Files: `src/analytics_platform/contracts/execution.py; tests/contracts/test_execution_reference_contracts.py`
  - Commit: `Add execution reference contracts`
- [x] **#13** Materialization contracts _(effort: Max)_
  - Goal: Define backend-neutral materialization requests/results
  - Files: `src/analytics_platform/contracts/execution.py; tests/contracts/test_materialization_contracts.py`
  - Commit: `Add materialization contracts`
- [x] **#14** Execution limit contracts _(effort: Max)_
  - Goal: Define memory, collect, and conversion policies
  - Files: `src/analytics_platform/contracts/execution.py; tests/contracts/test_execution_limit_contracts.py`
  - Commit: `Add execution limit contracts`
- [x] **#15** Artifact persistence contracts _(effort: Max)_
  - Goal: Define durable artifact references and storage policy
  - Files: `src/analytics_platform/contracts/artifacts.py; docs/contracts/artifact-contracts.md; tests/contracts/test_artifact_contracts.py`
  - Commit: `Add artifact persistence contracts`
- [x] **#16** Cache invalidation contracts _(effort: Max)_
  - Goal: Define cache keys, fingerprints, and stale artifact policy
  - Files: `src/analytics_platform/contracts/cache.py; docs/contracts/cache-contracts.md; tests/contracts/test_cache_contracts.py`
  - Commit: `Add cache invalidation contracts`
- [x] **#17** Visual artifact contracts _(effort: High)_
  - Goal: Define table/chart artifact references
  - Files: `src/analytics_platform/contracts/visuals.py; docs/contracts/visual-artifact-contracts.md; tests/contracts/test_visual_contracts.py`
  - Commit: `Add visual artifact contracts`
- [ ] **#18** Dataset identity and handle contracts _(effort: Max)_
  - Goal: Define stable dataset references without dataframes
  - Files: `src/analytics_platform/contracts/datasets.py; tests/contracts/test_dataset_handle_contracts.py`
  - Commit: `Add dataset handle contracts`
- [ ] **#19** Dataset load and ingestion contracts _(effort: Max)_
  - Goal: Define dataset load request/result contracts
  - Files: `src/analytics_platform/contracts/datasets.py; tests/contracts/test_dataset_load_contracts.py`
  - Commit: `Add dataset load contracts`
- [ ] **#20** Dataset fingerprint contracts _(effort: Max)_
  - Goal: Define content/source fingerprint contracts
  - Files: `src/analytics_platform/contracts/datasets.py; tests/contracts/test_dataset_fingerprint_contracts.py`
  - Commit: `Add dataset fingerprint contracts`
- [ ] **#21** Lineage contracts _(effort: Max)_
  - Goal: Define lineage records and transformation references
  - Files: `src/analytics_platform/contracts/lineage.py; tests/contracts/test_lineage_contracts.py`
  - Commit: `Add lineage contracts`
- [ ] **#22** Schema contracts _(effort: Max)_
  - Goal: Define schema inference and validation interfaces
  - Files: `src/analytics_platform/contracts/schemas.py; tests/contracts/test_schema_contracts.py`
  - Commit: `Add schema contracts`
- [ ] **#23** Semantic contracts _(effort: Max)_
  - Goal: Define semantic column typing interfaces
  - Files: `src/analytics_platform/contracts/semantics.py; tests/contracts/test_semantic_contracts.py`
  - Commit: `Add semantic typing contracts`
- [ ] **#24** Quality contracts _(effort: Max)_
  - Goal: Define data quality and missingness outputs
  - Files: `src/analytics_platform/contracts/quality.py; tests/contracts/test_quality_contracts.py`
  - Commit: `Add data quality contracts`
- [ ] **#25** Profiling contracts _(effort: Max)_
  - Goal: Define profiles and distribution summaries
  - Files: `src/analytics_platform/contracts/profiling.py; tests/contracts/test_profiling_contracts.py`
  - Commit: `Add profiling contracts`
- [ ] **#26** Association diagnostic contracts _(effort: Max)_
  - Goal: Define diagnostic association reports
  - Files: `src/analytics_platform/contracts/associations.py; tests/contracts/test_association_contracts.py`
  - Commit: `Add association diagnostic contracts`
- [ ] **#27** Join contracts _(effort: Max)_
  - Goal: Define join validation and execution contracts
  - Files: `src/analytics_platform/contracts/joins.py; tests/contracts/test_join_contracts.py`
  - Commit: `Add join contracts`
- [ ] **#28** Target and feature spec contracts _(effort: Max)_
  - Goal: Define explicit target/features/exclusions
  - Files: `src/analytics_platform/contracts/features.py; tests/contracts/test_target_feature_spec_contracts.py`
  - Commit: `Add target and feature spec contracts`
- [ ] **#29** Feature transformation contracts _(effort: Max)_
  - Goal: Define transformation plans and reports
  - Files: `src/analytics_platform/contracts/features.py; tests/contracts/test_feature_transformation_contracts.py`
  - Commit: `Add feature transformation contracts`
- [ ] **#30** Feature matrix reference contracts _(effort: Max)_
  - Goal: Define model-ready matrix references
  - Files: `src/analytics_platform/contracts/features.py; tests/contracts/test_feature_matrix_contracts.py`
  - Commit: `Add feature matrix contracts`
- [ ] **#31** Leakage contracts _(effort: Max)_
  - Goal: Define leakage request/report/risk contracts
  - Files: `src/analytics_platform/contracts/features.py; tests/contracts/test_leakage_contracts.py`
  - Commit: `Add leakage contracts`
- [ ] **#32** Statistics contracts _(effort: Max)_
  - Goal: Define shared statistical primitives
  - Files: `src/analytics_platform/contracts/statistics.py; tests/contracts/test_statistics_contracts.py`
  - Commit: `Add statistical primitive contracts`
- [ ] **#33** Model spec contracts _(effort: Max)_
  - Goal: Define OLS model specification and spec validation output
  - Files: `src/analytics_platform/contracts/modeling.py; tests/contracts/test_model_spec_contracts.py`
  - Commit: `Add model spec contracts`
- [ ] **#34** Model result contracts _(effort: Max)_
  - Goal: Define fitted model result shape
  - Files: `src/analytics_platform/contracts/modeling.py; tests/contracts/test_model_result_contracts.py`
  - Commit: `Add model result contracts`
- [ ] **#35** Model diagnostics contracts _(effort: Max)_
  - Goal: Define diagnostic section types
  - Files: `src/analytics_platform/contracts/modeling.py; tests/contracts/test_model_diagnostics_contracts.py`
  - Commit: `Add model diagnostics contracts`
- [ ] **#36** Claim-level contracts _(effort: Max)_
  - Goal: Define evidence grades and causal warning contracts
  - Files: `src/analytics_platform/contracts/validation.py; tests/contracts/test_claim_level_contracts.py`
  - Commit: `Add claim level contracts`
- [ ] **#37** Model validation contracts _(effort: Max)_
  - Goal: Define model validation request/report contracts
  - Files: `src/analytics_platform/contracts/validation.py; tests/contracts/test_model_validation_contracts.py`
  - Commit: `Add model validation contracts`
- [ ] **#38** Robustness contracts _(effort: Max)_
  - Goal: Define robustness and skipped-check contracts
  - Files: `src/analytics_platform/contracts/validation.py; tests/contracts/test_robustness_contracts.py`
  - Commit: `Add robustness contracts`
- [ ] **#39** Report section contracts _(effort: Max)_
  - Goal: Define report specs, section types, and section objects
  - Files: `src/analytics_platform/contracts/reporting.py; tests/contracts/test_report_section_contracts.py`
  - Commit: `Add report section contracts`
- [ ] **#40** Report bundle and artifact contracts _(effort: Max)_
  - Goal: Define report bundles and generated artifact sets
  - Files: `src/analytics_platform/contracts/reporting.py; tests/contracts/test_report_bundle_contracts.py`
  - Commit: `Add report bundle contracts`
- [ ] **#41** Registry contracts _(effort: Max)_
  - Goal: Define result registry and experiment history interfaces
  - Files: `src/analytics_platform/contracts/registry.py; tests/contracts/test_registry_contracts.py`
  - Commit: `Add registry contracts`
- [ ] **#42** Pipeline stage contracts _(effort: Max)_
  - Goal: Define pipeline stage names and stage result rules
  - Files: `src/analytics_platform/contracts/pipeline.py; tests/contracts/test_pipeline_stage_contracts.py`
  - Commit: `Add pipeline stage contracts`
- [ ] **#43** Analysis plan contracts _(effort: Max)_
  - Goal: Define top-level analysis plan contract
  - Files: `src/analytics_platform/contracts/pipeline.py; tests/contracts/test_analysis_plan_contracts.py`
  - Commit: `Add analysis plan contracts`
- [ ] **#44** Run manifest contracts _(effort: Max)_
  - Goal: Define reproducibility manifest contracts
  - Files: `src/analytics_platform/contracts/pipeline.py; tests/contracts/test_run_manifest_contracts.py`
  - Commit: `Add run manifest contracts`
- [ ] **#45** Analysis run result contracts _(effort: Max)_
  - Goal: Define top-level pipeline run result
  - Files: `src/analytics_platform/contracts/pipeline.py; tests/contracts/test_analysis_run_result_contracts.py`
  - Commit: `Add analysis run result contracts`
- [ ] **#46** Contract index exports _(effort: High)_
  - Goal: Stabilize contract package exports
  - Files: `src/analytics_platform/contracts/__init__.py; tests/contracts/test_contract_exports.py`
  - Commit: `Stabilize contract exports`

## Phase 2 — Compatibility Tests

- [ ] **#47** Config-to-pipeline compatibility _(effort: Max)_
  - Goal: Prove config shape feeds pipeline contract
  - Files: `tests/contracts/test_config_to_pipeline_contract.py; tests/fixtures/configs/profile_only.yaml`
  - Commit: `Add config to pipeline contract test`
- [ ] **#48** Execution-to-dataset compatibility _(effort: Max)_
  - Goal: Prove backend refs can support dataset handles
  - Files: `tests/contracts/test_execution_to_dataset_contract.py`
  - Commit: `Add execution dataset compatibility test`
- [ ] **#49** Execution-limits-to-backend compatibility _(effort: Max)_
  - Goal: Prove backend requests include execution limits
  - Files: `tests/contracts/test_execution_limits_to_backend_contract.py`
  - Commit: `Add execution limits backend compatibility test`
- [ ] **#50** Artifact-to-cache compatibility _(effort: Max)_
  - Goal: Prove artifacts can participate in cache keys
  - Files: `tests/contracts/test_artifact_to_cache_contract.py`
  - Commit: `Add artifact cache compatibility test`
- [ ] **#51** Cache-to-pipeline compatibility _(effort: Max)_
  - Goal: Prove pipeline can record cache decisions
  - Files: `tests/contracts/test_cache_to_pipeline_contract.py`
  - Commit: `Add cache pipeline compatibility test`
- [ ] **#52** Visual-to-reporting compatibility _(effort: High)_
  - Goal: Prove report sections can reference visual artifacts
  - Files: `tests/contracts/test_visual_to_reporting_contract.py`
  - Commit: `Add visual reporting compatibility test`
- [ ] **#53** IO-to-catalog compatibility _(effort: Max)_
  - Goal: Prove loaded datasets register cleanly
  - Files: `tests/contracts/test_io_to_catalog_contract.py`
  - Commit: `Add IO to catalog compatibility test`
- [ ] **#54** Catalog-to-schema compatibility _(effort: Max)_
  - Goal: Prove dataset handles feed schema inference
  - Files: `tests/contracts/test_catalog_to_schema_contract.py`
  - Commit: `Add catalog to schema compatibility test`
- [ ] **#55** Schema-to-semantics compatibility _(effort: Max)_
  - Goal: Prove schema feeds semantic typing
  - Files: `tests/contracts/test_schema_to_semantics_contract.py`
  - Commit: `Add schema to semantics compatibility test`
- [ ] **#56** Schema/semantics-to-quality compatibility _(effort: Max)_
  - Goal: Prove quality reports consume schema and roles
  - Files: `tests/contracts/test_schema_semantics_to_quality_contract.py`
  - Commit: `Add schema semantics quality compatibility test`
- [ ] **#57** Quality-to-profiling compatibility _(effort: Max)_
  - Goal: Prove profiling can include quality refs
  - Files: `tests/contracts/test_quality_to_profiling_contract.py`
  - Commit: `Add quality to profiling compatibility test`
- [ ] **#58** Profile-to-association compatibility _(effort: Max)_
  - Goal: Prove association diagnostics consume profiles
  - Files: `tests/contracts/test_profile_to_association_contract.py`
  - Commit: `Add profile to association compatibility test`
- [ ] **#59** Schema/profile/quality-to-join compatibility _(effort: Max)_
  - Goal: Prove join validation consumes upstream evidence
  - Files: `tests/contracts/test_schema_profile_quality_to_join_contract.py`
  - Commit: `Add join input compatibility test`
- [ ] **#60** Join validation-to-execution compatibility _(effort: Max)_
  - Goal: Prove execution requires approved validation
  - Files: `tests/contracts/test_join_validation_to_execution_contract.py`
  - Commit: `Add join validation execution compatibility test`
- [ ] **#61** Feature transform-to-matrix compatibility _(effort: Max)_
  - Goal: Prove transformation plans feed matrix refs
  - Files: `tests/contracts/test_feature_transform_to_matrix_contract.py`
  - Commit: `Add feature transform matrix compatibility test`
- [ ] **#62** Dataset-to-feature compatibility _(effort: Max)_
  - Goal: Prove raw or joined handles can feed feature build
  - Files: `tests/contracts/test_dataset_to_feature_contract.py`
  - Commit: `Add dataset feature compatibility test`
- [ ] **#63** Feature-to-leakage compatibility _(effort: Max)_
  - Goal: Prove feature matrix feeds leakage checks
  - Files: `tests/contracts/test_feature_to_leakage_contract.py`
  - Commit: `Add feature leakage compatibility test`
- [ ] **#64** Model spec-to-data adapter compatibility _(effort: Max)_
  - Goal: Prove validated specs can feed bounded data conversion
  - Files: `tests/contracts/test_model_spec_to_data_adapter_contract.py`
  - Commit: `Add model spec data adapter compatibility test`
- [ ] **#65** Feature/leakage-to-modeling compatibility _(effort: Max)_
  - Goal: Prove modeling consumes feature and leakage outputs
  - Files: `tests/contracts/test_feature_leakage_to_modeling_contract.py`
  - Commit: `Add feature leakage modeling compatibility test`
- [ ] **#66** Modeling-to-diagnostics compatibility _(effort: Max)_
  - Goal: Prove diagnostics consume model results
  - Files: `tests/contracts/test_modeling_to_diagnostics_contract.py`
  - Commit: `Add modeling diagnostics compatibility test`
- [ ] **#67** Modeling-to-validation compatibility _(effort: Max)_
  - Goal: Prove model evidence feeds validation
  - Files: `tests/contracts/test_modeling_to_validation_contract.py`
  - Commit: `Add modeling validation compatibility test`
- [ ] **#68** Results-to-reporting compatibility _(effort: Max)_
  - Goal: Prove reports consume all typed results
  - Files: `tests/contracts/test_results_to_reporting_contract.py`
  - Commit: `Add results reporting compatibility test`
- [ ] **#69** Manifest-to-registry compatibility _(effort: Max)_
  - Goal: Prove registry can consume manifest and artifact outputs
  - Files: `tests/contracts/test_manifest_to_registry_contract.py`
  - Commit: `Add manifest registry compatibility test`
- [ ] **#70** Reporting-to-pipeline compatibility _(effort: Max)_
  - Goal: Prove pipeline can include report artifacts
  - Files: `tests/contracts/test_reporting_to_pipeline_contract.py`
  - Commit: `Add reporting pipeline compatibility test`
- [ ] **#71** Pipeline-to-CLI compatibility _(effort: Max)_
  - Goal: Prove CLI can display run results
  - Files: `tests/contracts/test_pipeline_to_cli_contract.py`
  - Commit: `Add pipeline CLI compatibility test`

## Phase 3 — Architecture Tests

- [ ] **#72** Import boundary tests _(effort: Max)_
  - Goal: Prevent circular dependencies
  - Files: `tests/architecture/test_import_boundaries.py; tests/architecture/test_contracts_do_not_import_implementations.py`
  - Commit: `Add import boundary architecture tests`
- [ ] **#73** Domain/backend/artifact architecture tests _(effort: Max)_
  - Goal: Prevent hidden orchestration and backend leakage
  - Files: `tests/architecture/test_domain_backend_boundaries.py; tests/architecture/test_artifact_registry_boundaries.py`
  - Commit: `Add backend artifact architecture tests`
- [ ] **#74** Reporting architecture tests _(effort: Max)_
  - Goal: Ensure reporting consumes contracts only
  - Files: `tests/architecture/test_reporting_does_not_import_domain_implementations.py; tests/architecture/test_domain_modules_do_not_import_pipeline.py`
  - Commit: `Add reporting architecture tests`
- [ ] **#75** File-size architecture test _(effort: High)_
  - Goal: Enforce modularity limits
  - Files: `tests/architecture/test_file_size_limits.py`
  - Commit: `Add file size architecture test`
- [ ] **#76** Required modules architecture test _(effort: High)_
  - Goal: Ensure planned modules/contracts exist
  - Files: `tests/architecture/test_required_modules_present.py`
  - Commit: `Add required modules architecture test`

## Phase 4 — Core Infrastructure

- [ ] **#77** Core errors and logging _(effort: High)_
  - Goal: Add minimal shared infrastructure
  - Files: `src/analytics_platform/core/errors.py; src/analytics_platform/core/logging.py; tests/unit/core/test_errors_logging.py`
  - Commit: `Add core errors and logging`
- [ ] **#78** Runtime and artifact paths _(effort: Max)_
  - Goal: Add runtime metadata and artifact path rules
  - Files: `src/analytics_platform/core/runtime.py; src/analytics_platform/core/artifact_paths.py; tests/unit/core/test_runtime_artifact_paths.py`
  - Commit: `Add runtime and artifact path helpers`
- [ ] **#79** Execution limits policy _(effort: Max)_
  - Goal: Implement row, column, collect, Pandas-conversion, and artifact-size limits
  - Files: `src/analytics_platform/core/execution_limits.py; tests/unit/core/test_execution_limits.py`
  - Commit: `Add execution limits policy`

## Phase 5 — Config, IO & Backend

- [ ] **#80** Config loader _(effort: Max)_
  - Goal: Load config into typed AnalysisPlan
  - Files: `src/analytics_platform/core/config.py; tests/unit/core/test_config.py`
  - Commit: `Add typed config loader`
- [ ] **#81** IO format detection _(effort: High)_
  - Goal: Detect supported local dataset formats
  - Files: `src/analytics_platform/io/format_detection.py; tests/unit/io/test_format_detection.py`
  - Commit: `Add dataset format detection`
- [ ] **#82** Polars backend adapter _(effort: Max)_
  - Goal: Make Polars the first concrete lazy backend
  - Files: `src/analytics_platform/backends/polars_backend.py; src/analytics_platform/backends/__init__.py; tests/unit/backends/test_polars_backend.py`
  - Commit: `Add Polars execution backend`
- [ ] **#83** Backend registry and selection _(effort: Max)_
  - Goal: Resolve backends without circular imports
  - Files: `src/analytics_platform/backends/registry.py; tests/unit/backends/test_backend_registry.py`
  - Commit: `Add backend registry`
- [ ] **#84** Parquet artifact store _(effort: Max)_
  - Goal: Persist intermediate datasets and selected outputs as Parquet artifacts
  - Files: `src/analytics_platform/artifacts/parquet_store.py; src/analytics_platform/artifacts/__init__.py; tests/unit/artifacts/test_parquet_store.py`
  - Commit: `Add Parquet artifact store`
- [ ] **#85** Runtime dataset store _(effort: Max)_
  - Goal: Store private lazy/dataframe objects behind handles
  - Files: `src/analytics_platform/catalog/runtime_store.py; tests/unit/catalog/test_runtime_store.py`
  - Commit: `Add runtime dataset store`
- [ ] **#86** Local dataset readers _(effort: Max)_
  - Goal: Load CSV/Parquet into backend refs and ingestion reports
  - Files: `src/analytics_platform/io/readers.py; tests/unit/io/test_readers.py`
  - Commit: `Add local dataset readers`

## Phase 6 — Dataset Registry & Lineage

- [ ] **#87** Dataset registry _(effort: Max)_
  - Goal: Register loaded and derived datasets
  - Files: `src/analytics_platform/catalog/dataset_registry.py; tests/unit/catalog/test_dataset_registry.py`
  - Commit: `Add dataset registry`
- [ ] **#88** Lineage store _(effort: High)_
  - Goal: Store lineage records
  - Files: `src/analytics_platform/catalog/lineage_store.py; tests/unit/catalog/test_lineage_store.py`
  - Commit: `Add lineage store`

## Phase 7 — Schema, Semantics, Quality

- [ ] **#89** Schema inference _(effort: Max)_
  - Goal: Infer physical/logical schemas
  - Files: `src/analytics_platform/schema/inference.py; tests/unit/schema/test_inference.py`
  - Commit: `Add schema inference`
- [ ] **#90** Schema validation _(effort: Max)_
  - Goal: Validate expected vs observed schema
  - Files: `src/analytics_platform/schema/validation.py; tests/unit/schema/test_validation.py`
  - Commit: `Add schema validation`
- [ ] **#91** Semantic inference _(effort: Max)_
  - Goal: Infer or apply semantic column roles
  - Files: `src/analytics_platform/semantics/inference.py; tests/unit/semantics/test_inference.py`
  - Commit: `Add semantic role inference`
- [ ] **#92** Missingness analysis _(effort: Max)_
  - Goal: Produce missing-data report
  - Files: `src/analytics_platform/quality/missingness.py; tests/unit/quality/test_missingness.py`
  - Commit: `Add missing data analysis`
- [ ] **#93** Data quality summary _(effort: Max)_
  - Goal: Produce general data quality report
  - Files: `src/analytics_platform/quality/data_quality.py; tests/unit/quality/test_data_quality.py`
  - Commit: `Add data quality reporting`

## Phase 8 — Profiling

- [ ] **#94** Profiling summaries _(effort: Max)_
  - Goal: Implement numeric/categorical/datetime summaries
  - Files: `src/analytics_platform/profiling/summaries.py; tests/unit/profiling/test_summaries.py`
  - Commit: `Add profiling summary helpers`
- [ ] **#95** Lazy profiling plan _(effort: Max)_
  - Goal: Ensure profiling can run exact or approximate safely
  - Files: `src/analytics_platform/profiling/lazy_profile_plan.py; tests/unit/profiling/test_lazy_profile_plan.py`
  - Commit: `Add lazy profiling safeguards`
- [ ] **#96** Dataset profiler _(effort: Max)_
  - Goal: Produce DatasetProfile
  - Files: `src/analytics_platform/profiling/profiler.py; tests/unit/profiling/test_profiler.py`
  - Commit: `Add dataset profiler`
- [ ] **#97** Association diagnostics _(effort: Max)_
  - Goal: Add diagnostic correlations and warnings
  - Files: `src/analytics_platform/associations/diagnostics.py; tests/unit/associations/test_diagnostics.py`
  - Commit: `Add association diagnostics`
- [ ] **#98** Profile report sections _(effort: Max)_
  - Goal: Build dataset/schema/quality/profile report sections
  - Files: `src/analytics_platform/reporting/profile_sections.py; tests/unit/reporting/test_profile_sections.py`
  - Commit: `Add profile report sections`
- [ ] **#99** Minimal profile report bundle _(effort: Max)_
  - Goal: Assemble profile-only report bundle
  - Files: `src/analytics_platform/reporting/profile_report_builder.py; tests/unit/reporting/test_profile_report_builder.py`
  - Commit: `Add profile-only report builder`
- [ ] **#100** Minimal Markdown renderer _(effort: High)_
  - Goal: Render profile-only Markdown report
  - Files: `src/analytics_platform/reporting/markdown_renderer.py; tests/unit/reporting/test_profile_markdown_renderer.py`
  - Commit: `Add profile-only Markdown renderer`

## Phase 9 — Manifest, Registry & CLI

- [ ] **#101** Run manifest writer _(effort: Max)_
  - Goal: Write reproducibility manifest for profile-only runs
  - Files: `src/analytics_platform/pipeline/run_manifest.py; tests/unit/pipeline/test_run_manifest.py`
  - Commit: `Add run manifest writer`
- [ ] **#102** File registry writer _(effort: High)_
  - Goal: Write minimal file-based run/result registry record
  - Files: `src/analytics_platform/registry/file_registry.py; tests/unit/registry/test_file_registry.py`
  - Commit: `Add file-based run registry`
- [ ] **#103** Profile flow plan builder _(effort: Max)_
  - Goal: Build typed plan for profile-only pipeline stages
  - Files: `src/analytics_platform/pipeline/profile_flow_plan.py; tests/unit/pipeline/test_profile_flow_plan.py`
  - Commit: `Add profile flow plan builder`
- [ ] **#104** Profile flow executor _(effort: Max)_
  - Goal: Execute profile-only stages from the plan
  - Files: `src/analytics_platform/pipeline/profile_flow_executor.py; tests/unit/pipeline/test_profile_flow_executor.py`
  - Commit: `Add profile flow executor`
- [ ] **#105** Profile-only orchestrator _(effort: Max)_
  - Goal: Return AnalysisRunResult for profile-only runs
  - Files: `src/analytics_platform/pipeline/profile_orchestrator.py; tests/unit/pipeline/test_profile_orchestrator.py`
  - Commit: `Add profile-only orchestrator`
- [ ] **#106** CLI validate-config command _(effort: High)_
  - Goal: Add thin config validation CLI
  - Files: `src/analytics_platform/cli/app.py; tests/unit/cli/test_validate_config.py`
  - Commit: `Add CLI config validation command`
- [ ] **#107** CLI profile-run command _(effort: High)_
  - Goal: Add thin profile-only run command
  - Files: `src/analytics_platform/cli/app.py; tests/unit/cli/test_profile_run_command.py`
  - Commit: `Add CLI profile run command`

## Phase 10 — Profile-only MVP Checkpoint

- [ ] **#108** Profile-only MVP checkpoint _(effort: Max)_
  - Goal: Verify usable profile-only MVP before joins/modeling/cache/charts/history
  - Files: `docs/testing/profile-only-mvp-checkpoint.md; tests/integration/test_profile_only_smoke.py`
  - Commit: `Add profile-only MVP checkpoint`
- [ ] **#109** Dirty dataset profile integration _(effort: Max)_
  - Goal: Verify data quality warnings in profile-only path
  - Files: `tests/integration/test_dirty_dataset_profile.py; tests/fixtures/configs/dirty_profile.yaml; tests/fixtures/datasets/small_dirty.csv`
  - Commit: `Add dirty dataset profile integration test`
- [ ] **#110** Semantic typing integration _(effort: Max)_
  - Goal: Verify semantic role inference in profile-only path
  - Files: `tests/integration/test_semantic_typing_smoke.py; tests/fixtures/datasets/semantic_columns.csv`
  - Commit: `Add semantic typing integration test`
- [ ] **#111** Association diagnostics integration _(effort: Max)_
  - Goal: Verify diagnostic association output before modeling
  - Files: `tests/integration/test_association_diagnostics.py; tests/fixtures/datasets/association_diagnostics.csv`
  - Commit: `Add association diagnostics integration test`

## Phase 11 — DuckDB Backend, Cache & Visuals

- [ ] **#112** DuckDB backend boundary _(effort: Max)_
  - Goal: Add DuckDB backend compatibility after Polars profile MVP works
  - Files: `src/analytics_platform/backends/duckdb_backend.py; tests/unit/backends/test_duckdb_backend.py`
  - Commit: `Add DuckDB backend boundary`
- [ ] **#113** Cache manager _(effort: Max)_
  - Goal: Implement file-based cache status and reuse/recompute decisions
  - Files: `src/analytics_platform/artifacts/cache_manager.py; tests/unit/artifacts/test_cache_manager.py`
  - Commit: `Add artifact cache manager`
- [ ] **#114** Table artifact generation _(effort: High)_
  - Goal: Generate summary tables as report artifacts
  - Files: `src/analytics_platform/reporting/artifact_tables.py; tests/unit/reporting/test_artifact_tables.py`
  - Commit: `Add report table artifacts`
- [ ] **#115** Chart artifact generation _(effort: High)_
  - Goal: Generate basic diagnostic/profile charts as artifacts
  - Files: `src/analytics_platform/reporting/artifact_charts.py; tests/unit/reporting/test_artifact_charts.py`
  - Commit: `Add report chart artifacts`

## Phase 12 — Safe Joins

- [ ] **#116** Join validator _(effort: Max)_
  - Goal: Validate join safety before execution
  - Files: `src/analytics_platform/joins/validator.py; tests/unit/joins/test_validator.py`
  - Commit: `Add join validation`
- [ ] **#117** Join executor _(effort: Max)_
  - Goal: Execute approved joins and lineage
  - Files: `src/analytics_platform/joins/executor.py; tests/unit/joins/test_executor.py`
  - Commit: `Add approved join execution`
- [ ] **#118** Join report sections _(effort: Max)_
  - Goal: Build join audit report sections
  - Files: `src/analytics_platform/reporting/join_sections.py; tests/unit/reporting/test_join_sections.py`
  - Commit: `Add join report sections`
- [ ] **#119** Join flow plan builder _(effort: Max)_
  - Goal: Build typed join stage plan
  - Files: `src/analytics_platform/pipeline/join_flow_plan.py; tests/unit/pipeline/test_join_flow_plan.py`
  - Commit: `Add join flow plan builder`
- [ ] **#120** Join flow executor _(effort: Max)_
  - Goal: Execute join stage plan without becoming orchestrator god object
  - Files: `src/analytics_platform/pipeline/join_flow_executor.py; tests/unit/pipeline/test_join_flow_executor.py`
  - Commit: `Add join flow executor`
- [ ] **#121** Safe/unsafe join integration _(effort: Max)_
  - Goal: Verify safe join passes and unsafe join blocks
  - Files: `tests/integration/test_safe_join.py; tests/integration/test_unsafe_join_blocked.py; fixtures`
  - Commit: `Add join integration tests`

## Phase 13 — Feature Matrix & Leakage

- [ ] **#122** Feature spec resolver _(effort: Max)_
  - Goal: Resolve explicit target/features/exclusions before transformation
  - Files: `src/analytics_platform/features/spec_resolver.py; tests/unit/features/test_spec_resolver.py`
  - Commit: `Add feature spec resolver`
- [ ] **#123** Feature split planner _(effort: Max)_
  - Goal: Define train/test or no-holdout split safely
  - Files: `src/analytics_platform/features/split_planner.py; tests/unit/features/test_split_planner.py`
  - Commit: `Add feature split planner`
- [ ] **#124** Feature transformation planner _(effort: Max)_
  - Goal: Plan missingness, encoding, scaling, and fit scope
  - Files: `src/analytics_platform/features/transformation_planner.py; tests/unit/features/test_transformation_planner.py`
  - Commit: `Add feature transformation planner`
- [ ] **#125** Feature matrix builder _(effort: Max)_
  - Goal: Materialize or reference model-ready matrices
  - Files: `src/analytics_platform/features/builder.py; tests/unit/features/test_builder.py`
  - Commit: `Add feature matrix builder`
- [ ] **#126** Leakage checks _(effort: Max)_
  - Goal: Block target and obvious leakage
  - Files: `src/analytics_platform/features/leakage_checks.py; tests/unit/features/test_leakage_checks.py`
  - Commit: `Add leakage checks`

## Phase 14 — OLS Modeling

- [ ] **#127** Model spec validation _(effort: Max)_
  - Goal: Validate OLS specs before data prep/fitting
  - Files: `src/analytics_platform/modeling/spec_validation.py; tests/unit/modeling/test_spec_validation.py`
  - Commit: `Add OLS model spec validation`
- [ ] **#128** Statsmodels data adapter _(effort: Max)_
  - Goal: Convert bounded feature refs into Statsmodels-ready private data
  - Files: `src/analytics_platform/modeling/data_adapter.py; tests/unit/modeling/test_data_adapter.py`
  - Commit: `Add modeling data adapter`
- [ ] **#129** OLS fit core _(effort: Max)_
  - Goal: Fit explicit multivariable OLS
  - Files: `src/analytics_platform/modeling/ols.py; tests/unit/modeling/test_ols_fit.py`
  - Commit: `Add OLS fit core`
- [ ] **#130** OLS result extraction _(effort: Max)_
  - Goal: Extract coefficients, intervals, p-values, and metrics into typed result
  - Files: `src/analytics_platform/modeling/result_extraction.py; tests/unit/modeling/test_result_extraction.py`
  - Commit: `Add OLS result extraction`
- [ ] **#131** Model fit metrics _(effort: Max)_
  - Goal: Compute fit and train/test metrics for OLS
  - Files: `src/analytics_platform/modeling/metrics.py; tests/unit/modeling/test_metrics.py`
  - Commit: `Add OLS fit metrics`
- [ ] **#132** Multicollinearity diagnostics _(effort: Max)_
  - Goal: Add predictor association and multicollinearity warnings
  - Files: `src/analytics_platform/modeling/multicollinearity.py; tests/unit/modeling/test_multicollinearity.py`
  - Commit: `Add multicollinearity diagnostics`
- [ ] **#133** Residual and assumption diagnostics _(effort: Max)_
  - Goal: Add residual, outlier, and assumption warning summaries
  - Files: `src/analytics_platform/modeling/assumption_diagnostics.py; tests/unit/modeling/test_assumption_diagnostics.py`
  - Commit: `Add OLS assumption diagnostics`
- [ ] **#134** Model diagnostic assembler _(effort: Max)_
  - Goal: Assemble full ModelDiagnosticReport
  - Files: `src/analytics_platform/modeling/diagnostics.py; tests/unit/modeling/test_diagnostics.py`
  - Commit: `Add OLS diagnostic report assembler`
- [ ] **#135** Multiple-testing implementation _(effort: Max)_
  - Goal: Implement p-value correction methods
  - Files: `src/analytics_platform/validation/multiple_testing.py; tests/unit/validation/test_multiple_testing.py`
  - Commit: `Add multiple testing correction`
- [ ] **#136** Claim rules _(effort: Max)_
  - Goal: Enforce claim levels and causal blocking
  - Files: `src/analytics_platform/validation/claim_rules.py; tests/unit/validation/test_claim_rules.py`
  - Commit: `Add claim rule validation`
- [ ] **#137** Robustness status _(effort: Max)_
  - Goal: Track minimal robustness and skipped checks
  - Files: `src/analytics_platform/validation/robustness.py; tests/unit/validation/test_robustness.py`
  - Commit: `Add robustness status handling`
- [ ] **#138** Model validation gates _(effort: Max)_
  - Goal: Validate model interpretation and claim level
  - Files: `src/analytics_platform/validation/model_validation.py; tests/unit/validation/test_model_validation.py`
  - Commit: `Add model validation gates`

## Phase 15 — Full Reporting

- [ ] **#139** Model report sections _(effort: Max)_
  - Goal: Build model, diagnostic, validation, and limitation sections
  - Files: `src/analytics_platform/reporting/model_sections.py; tests/unit/reporting/test_model_sections.py`
  - Commit: `Add model report sections`
- [ ] **#140** Full report bundle assembler _(effort: Max)_
  - Goal: Assemble profile, join, model, visual, and skipped sections
  - Files: `src/analytics_platform/reporting/report_builder.py; tests/unit/reporting/test_report_builder.py`
  - Commit: `Add full report bundle assembler`
- [ ] **#141** Full Markdown renderer _(effort: )_
  - Goal: Render full Markdown report with table/chart refs

---

## Build-ordering notes

- Tasks execute in numerical order; each task's upstream dependencies are listed in the source table.
- All contract tasks (#11–#46) must land before any implementation that consumes those contracts.
- **Profile-only MVP checkpoint is Task #108**. Joins, feature matrices, modeling, DuckDB, charts, and history CLI are gated behind that checkpoint.
- Final full-Markdown renderer is Task #141.

## How to update this file

When you land a task in a PR:

1. Open this file in the fork.
2. Flip `[ ]` → `[x]` for the completed task(s).
3. Commit the checkbox change in the same PR (or in a follow-up doc-only PR).

Keep this doc in lock-step with the Build Queue v2.1 source-of-truth table.
