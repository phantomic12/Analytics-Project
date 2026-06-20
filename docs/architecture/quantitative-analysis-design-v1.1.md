# Quantitative-Analysis Design Review — Architecture Pack v1 → v1.1

## 0. Executive Summary

Architecture Pack v1 is strong as a software architecture foundation: it is modular, contract-first, safe around joins, cautious around leakage, and appropriately conservative about causal claims.

However, as a quantitative-analysis platform, v1 is slightly too narrow in a few places. It correctly defers broad pattern scanning and advanced ML, but it also under-specifies some foundational quantitative capabilities that should exist even in the MVP:

1. Semantic column typing.
2. Missing-data analysis.
3. Distribution profiling.
4. Correlation and association summaries.
5. Explicit model specification validation.
6. Result/experiment registry.
7. Multiple-testing structure, even if broad pattern scanning is deferred.
8. Minimal robustness and holdout strategy contracts.

The main recommendation is:

> Keep v1’s implementation scope narrow, but add v1.1 contracts for quantitative analysis now so future modules do not invent incompatible outputs later.

The MVP should still avoid becoming an automatic insight engine. But it needs enough quantitative structure to prevent weak or misleading regressions from looking authoritative.

---

# 1. Review by Quantitative-Analysis Capability

## 1.1 Schema Inference and Semantic Column Typing

### What is sufficient in v1

v1 includes:

* `ObservedSchema`
* `ExpectedSchema`
* `ColumnSchema`
* `LogicalDataType`
* `PhysicalDataType`
* `SchemaInferenceRequest`
* `SchemaValidationReport`

This is enough for basic schema inference.

### What is missing

v1 does not sufficiently distinguish between:

* Physical type: string, integer, float, date, boolean.
* Logical type: numeric, categorical, datetime.
* Semantic role: identifier, target, feature, timestamp, grouping variable, join key, leakage-risk column, post-outcome column, free text, geographic field, currency, percentage, count, ordinal category.

This matters because a column can be physically numeric but semantically dangerous.

Examples:

* `patient_id` may be numeric but should not be a continuous predictor.
* `facility_id` may be categorical but can leak site-level effects.
* `discharge_date` may be post-outcome.
* `total_paid_after_event` may leak the target.
* `year` may be ordinal or categorical depending on context.

### Should be in MVP

Yes. MVP should include **semantic column typing**, but not full automatic semantic understanding.

MVP should support:

* User-declared semantic roles.
* Heuristic semantic role suggestions.
* Confidence scores for inferred semantic roles.
* Warnings when model specs use risky semantic roles.

### Should wait until later

Later:

* Rich domain-specific ontology.
* LLM-assisted semantic typing.
* Automatic business meaning inference.
* Entity resolution.

### v1.1 change

Add `contracts/semantics.py` or add semantic typing to `contracts/schemas.py`.

Recommended v1.1 decision:

Create separate file:

`src/analytics_platform/contracts/semantics.py`

Owned types:

* `SemanticColumnType`
* `ColumnRole`
* `SemanticTypeInferenceRequest`
* `SemanticTypeInferenceReport`
* `SemanticColumnProfile`
* `ColumnRoleAssignment`
* `SemanticTypeConfidence`
* `RiskyColumnUse`

Allowed importers:

* `schema`
* `profiling`
* `joins`
* `features`
* `modeling`
* `validation`
* `reporting`
* `pipeline`

Do not let semantic typing become an AI-only feature. It should be rule-based and user-overridable in MVP.

---

## 1.2 Missing-Data Analysis

### What is sufficient in v1

v1 mentions:

* Missingness summaries in profiling.
* Missingness handling in features.
* Reporting rows before and after modeling.
* Simple missingness strategies.

This is a good start.

### What is missing

v1 does not yet require a dedicated missing-data report.

The system needs to separate:

* Missingness as data quality.
* Missingness as modeling risk.
* Missingness as possible bias.
* Missingness introduced by joins.
* Missingness introduced by feature construction.

The platform should track whether missingness is:

* Column-level.
* Row-level.
* Group-specific.
* Time-specific.
* Target-associated.
* Join-induced.
* Model-exclusion-inducing.

### Should be in MVP

Yes, a minimal missing-data analysis should be in MVP.

MVP should include:

* Missing count and rate by column.
* Missing count and rate by row, summarized.
* Rows dropped due to modeling missingness.
* Missingness by target availability.
* Missingness introduced by joins.
* Warning if large proportions of data are dropped before modeling.

### Should wait until later

Later:

* MCAR/MAR/MNAR formal diagnostics.
* Missingness modeling.
* Multiple imputation.
* Advanced sensitivity analysis for missing data.

### v1.1 change

Add a dedicated missingness contract, either in `contracts/profiling.py` or `contracts/quality.py`.

Recommended v1.1 decision:

Create:

`src/analytics_platform/contracts/quality.py`

Owned types:

* `DataQualityReport`
* `MissingDataReport`
* `ColumnMissingness`
* `RowMissingnessSummary`
* `MissingnessPatternSummary`
* `JoinIntroducedMissingness`
* `ModelExclusionSummary`
* `DataQualityIssue`

Allowed importers:

* `schema`
* `profiling`
* `joins`
* `features`
* `modeling`
* `validation`
* `reporting`
* `pipeline`

This makes missingness reusable across profiling, joins, features, modeling, and reporting.

---

## 1.3 Distribution Profiling

### What is sufficient in v1

v1 includes:

* `NumericProfile`
* `CategoricalProfile`
* `DatetimeProfile`
* `OutlierProfile`
* Approximate profiling mode.
* Large dataset performance constraints.

This is mostly sufficient.

### What is missing

Distribution profiling should be more explicit about what it guarantees.

MVP distribution profiles should distinguish:

* Exact vs approximate.
* Sampled vs full dataset.
* Numeric distribution.
* Categorical frequency distribution.
* Datetime range and granularity.
* Skew/outlier warnings.
* Constant and near-constant columns.
* High-cardinality categoricals.

### Should be in MVP

Yes. This is core to trustworthy profiling and modeling.

### Should wait until later

Later:

* Rich visual distributions.
* Distribution drift across datasets.
* Formal distribution fitting.
* Heavy statistical tests for normality on large data.
* Automatic transformations.

### v1.1 change

Tighten `contracts/profiling.py`.

Add or require:

* `ProfileComputationMode`
* `ProfileApproximationMethod`
* `DistributionSummary`
* `QuantileSummary`
* `FrequencySummary`
* `ConstantColumnWarning`
* `HighCardinalityWarning`

Every profile should state whether statistics are exact or approximate.

---

## 1.4 Correlation and Association Checks

### What is sufficient in v1

v1 intentionally moved broad pattern scanning out of MVP. That is wise.

### What is missing

The architecture still needs a safe place for basic association checks.

There is a difference between:

1. Broad automatic pattern discovery.
2. Basic exploratory correlation summaries used to understand data before modeling.
3. Pre-specified association tests.

v1 removed broad pattern scanning, but it should not eliminate all association structure.

Without correlation checks, OLS modeling may miss:

* Severe multicollinearity.
* Duplicate or near-duplicate predictors.
* Target leakage proxies.
* Redundant variables.
* Suspiciously perfect associations.

### Should be in MVP

Yes, but only as **diagnostic association checks**, not validated findings.

MVP should include:

* Numeric-numeric correlation matrix summary.
* Feature-target correlation warning.
* Perfect or near-perfect correlation warning.
* Categorical cardinality warning.
* Duplicate predictor warning.
* Multicollinearity input to model diagnostics.

### Should wait until later

Later:

* Broad pattern scanner.
* Automated subgroup discovery.
* Multiple families of association tests.
* Full exploratory finding generation.
* Natural-language insight generation.

### v1.1 change

Do not reintroduce full `patterns/` module yet.

Instead add:

`associations` as a diagnostic submodule or profiling extension.

Recommended structure:

`src/analytics_platform/associations/diagnostics.py`

Contracts owned by:

`contracts/associations.py`

Owned types:

* `AssociationCheckSpec`
* `AssociationCheckRequest`
* `AssociationCheckReport`
* `PairwiseAssociationSummary`
* `CorrelationMethod`
* `AssociationWarning`
* `MulticollinearityRiskSummary`

Allowed importers:

* `profiling`
* `features`
* `modeling`
* `validation`
* `reporting`
* `pipeline`

Important rule:

Association reports in MVP are diagnostic only. They do not produce validated findings.

---

## 1.5 Join Validation and Bad-Join Detection

### What is sufficient in v1

v1 is strong here.

It includes:

* `JoinSpec`
* `JoinValidationRequest`
* `JoinValidationReport`
* `JoinExecutionRequest`
* `JoinExecutionReport`
* `JoinedDatasetResult`
* Null key policy.
* Duplicate key policy.
* Cardinality classification.
* Row explosion detection.
* Blocking unsafe joins.

### What is missing

Two details should be explicit:

1. Join-induced missingness.
2. Join key semantic compatibility.

Examples:

* Joining `facility_id` to `patient_id` should be blocked even if both are strings.
* Joining keys with different semantic roles should warn or fail.
* A left join may create missing values in right-side columns that later affect modeling.

### Should be in MVP

Yes.

MVP should include:

* Key existence.
* Key physical type compatibility.
* Key semantic role compatibility if semantic roles are available.
* Duplicate key checks.
* Null key checks.
* Row count before/after.
* Unmatched row rates.
* Join-induced missingness summary.

### Should wait until later

Later:

* Fuzzy joins.
* Entity resolution.
* Probabilistic matching.
* Complex multi-hop join planning.
* Join graph optimization.

### v1.1 change

Extend `JoinValidationRequest` to optionally consume:

* `SemanticTypeInferenceReport`
* `DataQualityReport`

Extend `JoinValidationReport` with:

* `semantic_key_compatibility`
* `join_induced_missingness`
* `right_side_coverage_summary`
* `join_modeling_risk_level`

---

## 1.6 Feature Engineering With Leakage Prevention

### What is sufficient in v1

v1 includes:

* `TargetSpec`
* `FeatureSpec`
* `FeatureBuildRequest`
* `FeatureMatrixRef`
* `FeatureMatrixResult`
* `LeakageCheckRequest`
* `LeakageCheckReport`
* Split-before-preprocessing rule.
* Target leakage blocking.
* ID/high-cardinality warnings.

This is strong.

### What is missing

The architecture should distinguish:

* Feature selection.
* Feature transformation.
* Feature filtering.
* Feature encoding.
* Feature matrix materialization.
* Leakage checks before and after transformation.

It should also record transformation provenance.

Examples:

* Was a categorical variable one-hot encoded?
* Were missing values filled?
* Were rows dropped?
* Was scaling fitted only on train?
* Were high-cardinality columns excluded?
* Was a date column transformed into year/month?
* Did feature generation occur before or after split?

### Should be in MVP

Yes, minimally.

MVP should include:

* Explicit included/excluded columns.
* Basic numeric passthrough.
* Basic categorical encoding, if needed.
* Missingness handling.
* Split strategy.
* Transformation summary.
* Leakage check report.
* Feature matrix reference.

### Should wait until later

Later:

* Automated feature generation.
* Target encoding.
* Embeddings.
* Text features.
* Advanced date feature extraction.
* High-cardinality encoding.
* Feature stores.

### v1.1 change

Extend `FeatureMatrixResult` with:

* `FeatureTransformationPlan`
* `FeatureTransformationReport`
* `PreprocessingFitScope`
* `RowsExcludedReport`
* `ColumnsExcludedReport`
* `FeatureEligibilityReport`

Add explicit rule:

> Feature transformations that learn from data must be fitted only on training data and then applied to validation/test data.

---

## 1.7 Explicit Model Specifications

### What is sufficient in v1

v1 includes:

* `OLSModelSpec`
* `ModelSpec`
* `ModelFitRequest`
* explicit target and features.

This is good.

### What is missing

Model specification needs to be more explicit about:

* Unit of analysis.
* Outcome variable.
* Covariates.
* Fixed effects, deferred.
* Interaction terms, deferred.
* Weights, deferred.
* Clustered standard errors, deferred.
* Robust standard errors.
* Missingness policy.
* Train/test strategy.
* Whether model is explanatory or predictive.
* Allowed interpretation level.

OLS is not just “target plus features.” The model spec should encode interpretation intent.

### Should be in MVP

Yes, some of this belongs in MVP.

MVP should include:

* Outcome.
* Predictors.
* Unit of analysis.
* Model purpose: descriptive, associational, predictive.
* Missingness policy.
* Intercept behavior.
* Robust standard error option.
* Train/test optional split.
* Max rows/max columns safety limits.

### Should wait until later

Later:

* Fixed effects.
* Interaction terms.
* Clustered SEs.
* Survey weights.
* Panel models.
* Time-series models.
* GLMs beyond OLS.
* Formula DSL beyond simple OLS.

### v1.1 change

Extend `OLSModelSpec` with:

* `unit_of_analysis`
* `model_purpose`
* `include_intercept`
* `standard_error_type`
* `missingness_policy`
* `max_rows`
* `max_features`
* `allowed_claim_level`

Add `ModelSpecValidationReport`.

This report should be produced before fitting and should catch invalid or risky model specs.

---

## 1.8 Regression and Multivariable Modeling

### What is sufficient in v1

v1 supports OLS only. That is acceptable for the first version.

### What is missing

The phrase “multivariable models” implies multiple predictors and careful adjustment logic.

v1 should explicitly say:

* v1 supports multivariable OLS.
* v1 does not support arbitrary model families.
* v1 does not support causal adjustment claims.
* v1 does not choose covariates automatically.

### Should be in MVP

Yes:

* Multivariable OLS with explicit covariates.
* Typed coefficient table.
* Model fit statistics.
* Diagnostics.
* Interpretation limitations.

### Should wait until later

Later:

* Logistic regression.
* Poisson/negative binomial.
* Regularized regression.
* Tree models.
* Classification.
* Model comparison.
* Automated model selection.

### v1.1 change

Clarify:

> v1.1 MVP supports explicit multivariable OLS, not general automated multivariable modeling.

Add `ModelFamily` enum but allow only `OLS_LINEAR_REGRESSION` in v1.1.

---

## 1.9 Model Diagnostics

### What is sufficient in v1

v1 includes a solid minimum list:

* Rows used.
* Number of features.
* Coefficients.
* Standard errors.
* Confidence intervals.
* P-values.
* R-squared.
* Residual warnings.
* Multicollinearity warning.
* Train/test metric gap.
* Sample-size-to-feature warning.
* High-cardinality warning.
* Constant feature warning.
* Leakage warning summary.

### What is missing

The diagnostics should be separated into:

1. Fit diagnostics.
2. Assumption diagnostics.
3. Data diagnostics.
4. Stability diagnostics.
5. Interpretation limits.

Otherwise, the model diagnostics object becomes a vague bucket.

### Should be in MVP

Yes.

MVP should include:

* Coefficient table.
* Basic fit metrics.
* Residual summary.
* Multicollinearity warning.
* Influence/outlier warning, simple version.
* Sample size warning.
* Missingness warning.
* Interpretation limits.

### Should wait until later

Later:

* Formal heteroskedasticity tests.
* Full VIF table for huge models.
* Influence plots.
* Robustness grid.
* Bootstrap intervals.
* Cross-validation diagnostics.
* Calibration diagnostics for classification.

### v1.1 change

Split `ModelDiagnosticReport` into typed sections:

* `ModelFitSummary`
* `ModelAssumptionDiagnostics`
* `ModelDataDiagnostics`
* `ModelStabilityDiagnostics`
* `ModelInterpretationLimits`

This is still one public output object, but with clearer internals.

---

## 1.10 Multiple-Testing Controls

### What is sufficient in v1

v1 moved broad pattern scanning out of MVP, which reduces multiple-testing risk.

### What is missing

Even OLS can create multiple-testing risk when many coefficients are interpreted.

Also, correlation diagnostics and future pattern scans need a shared multiple-testing contract.

v1 should not wait until pattern scanning to define this.

### Should be in MVP

Minimal multiple-testing awareness should be in MVP.

MVP should include:

* Number of coefficients interpreted.
* Warning if many coefficients are being interpreted individually.
* Optional p-value adjustment for families of model coefficients.
* Clear language that unadjusted p-values are not discovery guarantees.

### Should wait until later

Later:

* Full multiple-testing correction across pattern scan families.
* Hierarchical testing families.
* Adaptive testing.
* Research-grade confirmatory workflow.

### v1.1 change

Add `contracts/statistics.py`.

Owned types:

* `StatisticalTestResult`
* `MultipleTestingCorrectionMethod`
* `MultipleTestingCorrectionReport`
* `TestFamily`
* `PValueAdjustmentResult`
* `EffectEstimate`
* `ConfidenceInterval`

Allowed importers:

* `modeling`
* `associations`
* `validation`
* `reporting`
* `pipeline`

Reason:

These are not specific to pattern scanning. They are shared statistical primitives.

---

## 1.11 Robustness Checks

### What is sufficient in v1

v1 mentions robustness but defers complex checks.

### What is missing

There should be a minimal robustness structure, even if most checks are skipped.

Otherwise, reports may imply a model is stable when no robustness checks were run.

### Should be in MVP

Yes, but minimal.

MVP robustness should include:

* Refit after dropping rows with missingness according to configured strategy.
* Optional train/test split performance comparison.
* Sensitivity to high-leverage rows as warning only, if simple.
* Model validation report says which robustness checks were not run.

### Should wait until later

Later:

* Bootstrap.
* Cross-validation.
* Alternative model specifications.
* Subgroup robustness.
* Leave-one-group-out.
* Placebo tests.
* Negative controls.
* Sensitivity to unobserved confounding.

### v1.1 change

Add to `contracts/validation.py`:

* `RobustnessCheckSpec`
* `RobustnessCheckResult`
* `RobustnessCheckStatus`
* `SkippedRobustnessCheck`

MVP can produce skipped records for checks not implemented.

---

## 1.12 Holdout or Validation Strategies

### What is sufficient in v1

v1 allows optional train/test split and train/test metric gap.

### What is missing

The architecture should explicitly distinguish:

* Explanatory/associational OLS.
* Predictive OLS.
* No holdout required.
* Random holdout.
* Time-based holdout.
* Group-based holdout.

For associational modeling, train/test split may be less central. For predictive modeling, it is essential.

### Should be in MVP

Yes, but minimal.

MVP should support:

* No holdout, for descriptive/associational OLS.
* Random train/test split, for predictive OLS.
* Time split only if a time column is explicitly configured.

### Should wait until later

Later:

* Cross-validation.
* GroupKFold.
* Nested validation.
* Rolling windows.
* External validation datasets.

### v1.1 change

Add or tighten `SplitSpec`:

* `validation_strategy`
* `split_strategy`
* `split_column`
* `group_column`
* `test_size`
* `random_seed`
* `requires_holdout`

Add validation rule:

> If `model_purpose` is predictive, holdout is required unless explicitly overridden.

---

## 1.13 Experiment / Result Registry

### What is sufficient in v1

v1 includes:

* Run manifest.
* Artifact refs.
* Lineage.
* Analysis result.

This is good for reproducibility.

### What is missing

A run manifest alone is not enough for comparing analyses.

The platform needs a lightweight result registry concept, even if it is just file-based in MVP.

It should track:

* Run ID.
* Analysis plan hash.
* Dataset fingerprints.
* Model specs.
* Model results.
* Validation status.
* Report artifacts.
* Git commit.
* Dependency lockfile hash.

### Should be in MVP

Yes, minimally.

MVP should include a file-based run registry, not a database.

### Should wait until later

Later:

* SQLite registry.
* Searchable experiment tracking.
* MLflow integration.
* Web UI.
* Remote artifact store.

### v1.1 change

Add `contracts/registry.py`.

Owned types:

* `RunRegistryRecord`
* `ResultRegistryEntry`
* `ModelRegistryEntry`
* `DatasetRegistryEntry`
* `ArtifactRegistryEntry`
* `RegistryWriteRequest`
* `RegistryWriteResult`

Implementation module:

`src/analytics_platform/registry/file_registry.py`

Allowed importers:

* `pipeline`
* `reporting`
* `cli`

Do not make domain modules write to registry directly. Pipeline owns registry writing.

---

## 1.14 Reproducible Reporting

### What is sufficient in v1

v1 is strong here:

* Markdown report.
* Optional HTML.
* Run manifest.
* Artifact references.
* Warnings.
* Limitations.
* No recomputation in reporting.

### What is missing

Reports should include a quantitative audit section.

Required report audit elements:

* Dataset fingerprints.
* Row counts by stage.
* Rows excluded by stage.
* Join validation status.
* Missingness impact.
* Model spec.
* Feature list.
* Leakage status.
* Diagnostics status.
* Validation status.
* Claim level.
* Causal disclaimer.

### Should be in MVP

Yes.

### Should wait until later

Later:

* Rich charts.
* PDF export.
* Interactive HTML.
* Drill-down tables.
* Natural language executive summaries.

### v1.1 change

Add required `ReportSectionType` values:

* `DATASET_AUDIT`
* `SCHEMA_SUMMARY`
* `DATA_QUALITY`
* `MISSINGNESS`
* `DISTRIBUTION_PROFILE`
* `JOIN_AUDIT`
* `FEATURE_AUDIT`
* `MODEL_SPECIFICATION`
* `MODEL_RESULTS`
* `MODEL_DIAGNOSTICS`
* `VALIDATION_AND_LIMITATIONS`
* `REPRODUCIBILITY`

---

## 1.15 Warnings Against Causal Overclaims

### What is sufficient in v1

v1 is strong:

* Causal claims blocked.
* Claim levels.
* Approved/disallowed wording.
* Reporting cannot strengthen claims.

### What is missing

The causal warning should be attached to every model result and report section where coefficients are interpreted.

It should not only be a global disclaimer.

### Should be in MVP

Yes.

### Should wait until later

Later:

* Formal causal design contracts.
* Directed acyclic graph support.
* Matching.
* Difference-in-differences.
* Instrumental variables.
* Regression discontinuity.

### v1.1 change

Add to `ModelValidationReport`:

* `causal_claim_allowed: false`
* `causal_warning`
* `approved_interpretation_template`
* `disallowed_interpretation_patterns`

Add reporting rule:

> Every coefficient interpretation section must include claim level and causal limitation.

---

# 2. What Is Sufficient Overall

Architecture Pack v1 is sufficient in these areas:

1. **Software modularity**
   Modules are clear and dependency direction is disciplined.

2. **Contract-first design**
   The one-request/one-result pattern is strong.

3. **Join safety**
   Join validation is treated as a first-class risk.

4. **Leakage prevention**
   Modeling cannot consume raw datasets directly.

5. **Reproducibility**
   Run manifests, artifact references, and lineage are well placed.

6. **Causal caution**
   v1 blocks causal claims appropriately.

7. **MVP restraint**
   Deferring broad pattern scanning, classification, and advanced ML is correct.

8. **LLM usability**
   File-size rules, prompt templates, and import boundaries reduce AI coding errors.

---

# 3. What Is Missing Overall

The main missing quantitative structures are:

1. Semantic column typing.
2. Dedicated data quality and missingness contracts.
3. Diagnostic association/correlation reports.
4. Shared statistical primitive contracts.
5. Model specification validation before fitting.
6. Minimal multiple-testing awareness for coefficient interpretation.
7. Minimal robustness check structure.
8. Explicit validation strategy contract.
9. Lightweight result registry.
10. Required quantitative audit sections in reports.

These should be added as contracts in v1.1 even if not fully implemented in MVP.

---

# 4. What Should Be in MVP

The MVP should include the following quantitative capabilities:

## 4.1 Schema and Semantics

* Physical schema inference.
* Logical schema inference.
* User-declared semantic column roles.
* Heuristic semantic role suggestions.
* Semantic role warnings.

## 4.2 Data Quality

* Missingness by column.
* Missingness by row summary.
* Duplicate row summary.
* Constant and near-constant columns.
* High-cardinality columns.
* Join-induced missingness.

## 4.3 Distribution Profiling

* Numeric summaries.
* Categorical frequency summaries.
* Datetime range summaries.
* Quantiles.
* Exact vs approximate mode.
* Outlier warnings.

## 4.4 Association Diagnostics

* Correlation summaries for numeric predictors.
* Near-perfect association warnings.
* Multicollinearity risk summary.
* Diagnostic only, not findings.

## 4.5 Joins

* Join key existence.
* Join key type compatibility.
* Join key semantic compatibility.
* Null key checks.
* Duplicate key checks.
* Row explosion detection.
* Unmatched row rates.
* Join-induced missingness.

## 4.6 Features

* Explicit target.
* Explicit feature list.
* Explicit exclusions.
* Basic missingness handling.
* Basic encoding.
* Split strategy.
* Transformation report.
* Leakage report.

## 4.7 Modeling

* Explicit multivariable OLS.
* Model spec validation.
* Coefficient table.
* Fit metrics.
* Diagnostics.
* Associational interpretation only.

## 4.8 Validation

* Leakage gate.
* Join quality gate.
* Model spec gate.
* Sample size and feature count gate.
* Causal overclaim gate.
* Minimal multiple-testing warning for many coefficients.
* Minimal robustness status.

## 4.9 Reporting

* Dataset audit.
* Schema summary.
* Missingness section.
* Join audit.
* Feature audit.
* Model specification.
* Model results.
* Diagnostics.
* Validation and limitations.
* Reproducibility metadata.

## 4.10 Registry

* File-based result registry entry per run.

---

# 5. What Should Wait Until Later

Move these out of MVP:

1. Broad automatic pattern scanning.
2. Validated exploratory finding generation.
3. Logistic regression.
4. Classification metrics.
5. Scikit-learn model training.
6. Cross-validation.
7. Bootstrap robustness.
8. Advanced imputation.
9. Fixed effects.
10. Clustered standard errors.
11. Interaction terms.
12. Automated feature generation.
13. Target encoding.
14. Text features.
15. Entity resolution.
16. Fuzzy joins.
17. Causal inference.
18. Natural-language insight generation.
19. Dashboard UI.
20. PDF reports.
21. Database-backed registry.
22. Cloud execution.

---

# 6. Architecture Pack v1.1 Changes

## 6.1 Add New Contract Files

Add:

```text
src/analytics_platform/contracts/semantics.py
src/analytics_platform/contracts/quality.py
src/analytics_platform/contracts/associations.py
src/analytics_platform/contracts/statistics.py
src/analytics_platform/contracts/registry.py
```

These files should be contracts-only.

---

## 6.2 Add New Implementation Modules

Add to MVP:

```text
src/analytics_platform/associations/
  __init__.py
  diagnostics.py

src/analytics_platform/registry/
  __init__.py
  file_registry.py
```

Do not add full `patterns/` yet.

---

## 6.3 Update Existing Contract Files

### Update `contracts/schemas.py`

Add links to semantic typing:

* `semantic_report_ref`
* `logical_type_confidence`
* `type_inference_mode`

### Update `contracts/profiling.py`

Add:

* exact vs approximate mode
* quantile summaries
* distribution summaries
* high-cardinality warnings
* constant column warnings

### Update `contracts/joins.py`

Add:

* semantic key compatibility
* join-induced missingness
* join modeling risk level

### Update `contracts/features.py`

Add:

* `FeatureTransformationPlan`
* `FeatureTransformationReport`
* `FeatureEligibilityReport`
* `RowsExcludedReport`
* `ColumnsExcludedReport`

### Update `contracts/modeling.py`

Add:

* `ModelSpecValidationReport`
* `unit_of_analysis`
* `model_purpose`
* `standard_error_type`
* `allowed_claim_level`
* `max_rows`
* `max_features`

### Update `contracts/validation.py`

Add:

* `RobustnessCheckSpec`
* `RobustnessCheckResult`
* `ValidationStrategy`
* `CausalWarning`
* stronger claim-level controls

### Update `contracts/reporting.py`

Add required report section types.

### Update `contracts/pipeline.py`

Add registry outputs:

* `RunRegistryRecord`
* registry write status reference

---

# 7. Revised v1.1 Pipeline

The v1.1 MVP pipeline should be:

1. Load config.
2. Load datasets.
3. Register datasets.
4. Infer physical/logical schema.
5. Infer or accept semantic column roles.
6. Validate schema.
7. Produce data quality report.
8. Profile distributions.
9. Run diagnostic association checks.
10. Validate joins, if configured.
11. Execute safe joins, if configured.
12. Re-run schema/profile/quality checks on joined dataset.
13. Build feature matrix.
14. Run leakage checks.
15. Validate model specification.
16. Fit OLS.
17. Run model diagnostics.
18. Validate model interpretation and claim level.
19. Build report bundle.
20. Render report.
21. Write run manifest.
22. Write file-based registry record.
23. Return `AnalysisRunResult`.

---

# 8. Revised Dependency Rules for v1.1

## 8.1 New Contract Import Permissions

### `contracts/semantics.py`

Allowed importers:

* `schema`
* `profiling`
* `joins`
* `features`
* `modeling`
* `validation`
* `reporting`
* `pipeline`

### `contracts/quality.py`

Allowed importers:

* `schema`
* `profiling`
* `joins`
* `features`
* `modeling`
* `validation`
* `reporting`
* `pipeline`

### `contracts/associations.py`

Allowed importers:

* `associations`
* `features`
* `modeling`
* `validation`
* `reporting`
* `pipeline`

### `contracts/statistics.py`

Allowed importers:

* `associations`
* `modeling`
* `validation`
* `reporting`
* `pipeline`

### `contracts/registry.py`

Allowed importers:

* `registry`
* `pipeline`
* `cli`
* `reporting`, read-only references only

## 8.2 New Forbidden Imports

* `associations` must not import `modeling`.
* `modeling` must not import `associations`.
* `registry` must not import domain implementation modules.
* Domain modules must not write directly to registry.
* `reporting` must not import `registry.file_registry`.
* `validation` must not call modeling implementation.

Pipeline remains the only orchestrator.

---

# 9. New Minimum Contract Tests for v1.1

Add contract tests for:

1. `SchemaInferenceReport` → `SemanticTypeInferenceReport`
2. `DatasetProfile` → `DataQualityReport`
3. `DatasetProfile` → `AssociationCheckReport`
4. `JoinValidationReport` includes join-induced missingness.
5. `FeatureMatrixResult` includes transformation report and rows excluded.
6. `LeakageCheckReport` blocks target leakage.
7. `ModelSpecValidationReport` blocks invalid model specs.
8. `ModelResult` uses shared statistical primitives.
9. `ModelValidationReport` blocks causal claim level.
10. `ReportBuildRequest` accepts quantitative audit sections.
11. `RunManifest` and `RunRegistryRecord` can both reference the same run.
12. `AnalysisRunResult` can include skipped optional stages and registry write status.

---

# 10. Revised MVP Integration Tests for v1.1

Add these to the v1 integration test set:

## 10.1 Semantic Typing Smoke Test

Input:

* Dataset with ID, date, numeric, categorical, and target-like columns.

Expected:

* Semantic roles are assigned or suggested.
* ID-like column is flagged if used as predictor.

## 10.2 Missingness Modeling Impact Test

Input:

* Dataset with missing values in model features.

Expected:

* Missingness report is produced.
* Rows dropped before modeling are counted.
* Report warns if drop rate exceeds threshold.

## 10.3 Association Diagnostics Test

Input:

* Dataset with two near-duplicate predictors.

Expected:

* Association diagnostics warn about high predictor correlation.
* Modeling diagnostics include multicollinearity warning.

## 10.4 Model Spec Validation Test

Input:

* OLS config with categorical target or no predictors.

Expected:

* Model spec validation blocks fitting.

## 10.5 Registry Smoke Test

Input:

* Profile-only config.

Expected:

* Run manifest is written.
* Registry record is written.
* Registry record references report artifacts and config hash.

---

# 11. Final Recommendation

Architecture Pack v1 is a good software architecture but needs v1.1 quantitative structure before implementation.

The right balance is:

* Do not expand MVP into broad pattern discovery.
* Do not add advanced ML yet.
* Do not add causal methods yet.
* Do add semantic typing, data quality, association diagnostics, shared statistical primitives, model spec validation, minimal robustness structure, and a file-based result registry.

The safest v1.1 architecture is:

> A contract-first, OLS-first, join-safe, leakage-safe, semantically aware, reproducible analysis pipeline that produces cautious reports and refuses to overclaim.

That gives the platform a strong quantitative foundation without becoming too broad for the first version.
