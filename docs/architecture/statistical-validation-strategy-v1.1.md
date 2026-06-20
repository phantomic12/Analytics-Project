# Statistical Validation Strategy v1.1 — Python Analytics Platform

## 0. Purpose and Scope

This document is the source of truth for **statistical safety rules** in the v1.1 MVP of the Python analytics platform.

It defines conservative claim levels, output categories, blocking and downgrade behavior, required evidence for any statistically framed output, report wording rules, and compatibility expectations for future validation, modeling, and reporting contracts.

This document is prescriptive. Future `contracts/validation.py`, `contracts/modeling.py`, `contracts/reporting.py`, leakage, join, and statistical primitive contracts must conform to it. It defines doctrine, not public data shapes.

It must be read together with `docs/architecture/architecture-pack-v1.1.md` and `docs/architecture/quantitative-analysis-design-v1.1.md`. If conflicts arise, the architecture pack v1.1 and actual repo state win, and this document wins over ad hoc statistical interpretations in downstream modules.

MVP statistical scope is narrow on purpose: OLS regression only, no broad pattern scanning, no causal inference, no automated insight generation.

---

## 1. Claim Levels

All statistically framed outputs must carry an explicit `ClaimLevel`. The MVP supports, in increasing strength:

1. `DESCRIPTIVE` — summarizes observed data without inference beyond the sample.
2. `DIAGNOSTIC` — flags potential data or model problems for human review; never a finding.
3. `ASSOCIATIONAL` — describes conditional association in the fitted sample without causal interpretation.
4. `PREDICTIVE_LIMITED` — describes in-sample or simple holdout predictive behavior without claiming generalizable performance.

Disallowed in MVP: `CAUSAL`, `EFFECT_CAUSAL`, `POLICY_ACTIONABLE`, and any claim implying intervention, counterfactual, or treatment effect.

Validation must enforce `allowed_claim_level` from the model spec, downgrade any output that exceeds it, and block any spec requesting a disallowed level.

---

## 2. Output Categories

Every statistically meaningful output must be classified into exactly one of:

* `DESCRIPTIVE` — descriptive profiles, distributions, counts, missingness summaries.
* `DIAGNOSTIC` — correlation summaries, multicollinearity warnings, residual warnings, influence warnings. Diagnostics are not findings.
* `ASSOCIATIONAL` — OLS coefficients interpreted as conditional associations, with limitations.
* `PREDICTIVE_LIMITED` — train/test metric gaps, in-sample fit, or simple holdout performance. Always paired with holdout disclosure.
* `UNSUPPORTED` — required evidence missing or assumptions violated. Must be downgraded and accompanied by a limitation statement.
* `BLOCKED` — violates a hard safety rule and must not be emitted as a result.

Rules: descriptive and diagnostic outputs must not be presented as findings; associational outputs must include effect size, uncertainty, sample size, diagnostics status, and limitations; predictive-limited outputs must state holdout configuration and whether holdout was used; unsupported outputs must not be silently promoted; blocked outputs must produce a typed block reason and must not appear as valid results.

---

## 3. No Causal Claims in MVP

Causal language is blocked entirely in v1.1 MVP across modeling, validation, associations, and reporting.

Disallowed wording, non-exhaustively: "causes", "effect of", "impact of", "leads to", "drives", "increases", "decreases" used causally; "treatment effect", "causal effect", "counterfactual", "intervention", "confounder" used as validated claims; "controlling for" interpreted as causal adjustment.

Allowed wording: "is associated with", "conditional on included covariates", "in the fitted sample", "under the model specification".

Associational OLS coefficients are conditional associations under the model spec, not causal effects. The report must include a causal disclaimer.

---

## 4. p-values Are Never Enough

A p-value alone is never sufficient evidence. Validation must reject or downgrade any result presenting p-values without effect size, uncertainty interval where available, sample size, diagnostic status, and limitations.

p-values must not be described as "significant findings" without the full evidence bundle. "Statistically significant" is discouraged and must be immediately qualified. Unadjusted p-values are not discovery guarantees. Near-threshold p-values must not be re-framed as confirmatory.

---

## 5. Required Evidence

For any `ASSOCIATIONAL` or `PREDICTIVE_LIMITED` output, validation must require:

* Effect size for interpreted coefficients.
* Confidence interval where available, with stated coverage and method.
* Sample size used in fitting and, where relevant, testing.
* Number of features and sample-to-feature ratio.
* Diagnostic status, including assumption, data, and stability diagnostics.
* Missingness summary relevant to the modeled rows.
* Interpretation limits, including OLS assumption caveats.
* Multiple-testing context, even if no broad scan was performed.

If any required element is missing, the output must be marked `UNSUPPORTED` and downgraded, not silently emitted.

---

## 6. Semantic Column Risks

Validation must treat semantic column roles as safety-relevant. A column may be physically numeric but semantically dangerous.

Risky uses that must warn or block: identifier columns used as continuous predictors; post-outcome columns used as predictors; target-leakage proxy columns used as predictors; join key columns reused as predictors without explicit override; high-cardinality categorical columns encoded in ways that inflate dimensionality.

Validation must consume semantic typing where available and downgrade or block model specs with risky column uses. A user override may downgrade a block to a warning only if the override is explicit and recorded in lineage.

---

## 7. Missingness and Data-Quality Risk

Missingness must be treated as both data quality and modeling risk.

Required checks: column-level missing rate; row-level missingness summary; missingness by target availability; rows dropped before modeling and the proportion dropped; warning when a large proportion of rows is dropped before modeling.

Severe missingness must downgrade associational outputs to unsupported if the missingness is target-associated and unmodeled. Missingness must be reported even when rows are dropped. Imputation, if any, must be fitted only on training data and disclosed.

Formal MCAR/MAR/MNAR diagnostics are deferred, but their absence must be disclosed as a limitation.

---

## 8. Join-Induced Missingness and Bad-Join Risk

Joins are validation-sensitive operations, not simple dataframe merges.

Validation must require: join validation status before execution; row count before and after join; unmatched row rates; join-induced missingness summary for right-side columns; semantic key compatibility where semantic typing is available.

Severe join issues that must block downstream modeling: row explosion; duplicate keys producing duplicated outcomes; semantically incompatible keys, e.g. joining `facility_id` to `patient_id`; join-induced missingness in the target or in required predictors.

Less severe join issues must warn and may downgrade model outputs.

---

## 9. Leakage Blocking

Leakage checks are mandatory before modeling and are blocking by default.

Hard blocks: target column used as a predictor; post-outcome columns used as predictors; columns that are deterministic functions of the target; fitted preprocessing applied before train/test split.

Warnings: high-cardinality identifiers used as predictors; columns with suspiciously perfect target association.

A leakage block must prevent model fitting. A leakage warning must downgrade any resulting model output and must be visible in the report.

---

## 10. Invalid or Risky Model Spec Blocking

Model spec validation must run before fitting and must block or downgrade invalid specs.

Hard blocks: unsupported model family in MVP (anything other than OLS linear regression); target missing or constant; no predictors; sample size below a configured minimum; sample-to-feature ratio below a configured minimum; predictive model purpose with no holdout and no explicit override.

Downgrades: ambiguous model purpose; missingness policy conflicting with the data; spec exceeding `max_rows` or `max_features` safety limits.

Every blocked spec must produce a typed block reason.

---

## 11. OLS-Only MVP Interpretation Limits

MVP supports explicit multivariable OLS only. Interpretation limits are mandatory.

Coefficients are conditional associations under the model spec, not causal effects. OLS assumption violations must be disclosed. High multicollinearity must downgrade coefficient-level interpretation. Small sample size must downgrade interpretation and may mark outputs unsupported. High leverage or influential points must trigger warnings. Predictive performance, if reported, must be labeled predictive-limited and disclose holdout configuration.

Deferred: logistic regression, GLMs, regularized regression, tree models, classification, model comparison, automated model selection.

---

## 12. Multiple-Testing Awareness Without Broad Pattern Scanning

Broad pattern scanning is out of MVP, but multiple-testing risk still exists within OLS and within diagnostic association checks.

Required behavior: report the number of coefficients interpreted; warn when many coefficients are interpreted individually; optionally support p-value adjustment within a declared family of model coefficients; state explicitly that unadjusted p-values are not discovery guarantees; diagnostic association summaries must not be treated as a testing family producing findings.

Deferred: full multiple-testing correction across pattern scan families, hierarchical testing, adaptive testing.

---

## 13. Diagnostic Associations Are Diagnostics Only

Association checks in MVP are diagnostic only and do not produce validated findings.

Permitted diagnostic association outputs: numeric-numeric correlation summaries; feature-target correlation warnings; perfect or near-perfect correlation warnings; multicollinearity risk summaries fed into model diagnostics.

Diagnostic associations must be labeled `DIAGNOSTIC`, must not appear in the report as findings, and suspiciously perfect associations must trigger leakage re-checks, not conclusions.

Deferred: broad pattern scanner, automated subgroup discovery, natural-language insight generation.

---

## 14. Robustness and Holdout Expectations

Robustness in MVP is minimal but explicit.

Required robustness structure: refit after dropping rows with missingness according to the configured strategy, if applicable; optional train/test split performance comparison for predictive-limited outputs; sensitivity to high-leverage rows as warning only, if simple.

Required holdout behavior: associational OLS may omit holdout; predictive OLS requires holdout unless explicitly overridden; time split only if a time column is explicitly configured.

Skipped-check disclosure: the validation report must list which robustness checks were not run; reports must not imply stability when no robustness checks were performed; skipped checks must be emitted as typed skipped records, not omitted silently.

Deferred: bootstrap, cross-validation, alternative model specs, subgroup robustness, leave-one-group-out, placebo tests, negative controls, sensitivity to unobserved confounding.

---

## 15. Report Wording Rules and Disallowed Overclaims

Reports must follow conservative wording.

Allowed: "is associated with", "conditional on included covariates", "in the fitted sample", "under the specified model"; "descriptive summary", "diagnostic warning", "not a validated finding"; "predictive-limited result with holdout configuration X".

Disallowed: "causes", "effect of", "impact of", "drives", "leads to"; "significant finding" without effect size, uncertainty, sample size, diagnostics, and limitations; "validated causal effect"; "robust" when robustness checks were skipped; "generalizes" or "will generalize".

Required report elements: causal disclaimer; claim level; limitations section; skipped-check disclosure; missingness impact; join validation status; leakage status; diagnostic status.

Reporting must not recompute analytics, must not strengthen claim language, and must not hide warnings.

---

## 16. Warning, Downgrade, and Block Behavior

Validation must apply severity-graded behavior.

`WARN`: visible in report, does not change claim level. Used for minor data-quality or diagnostic concerns.

`DOWNGRADE`: reduces claim level, e.g. associational to unsupported, or predictive-limited to unsupported. Used when evidence is incomplete or assumptions are violated.

`BLOCK`: prevents the output from being emitted as a valid result. Used for causal claim requests in MVP, leakage violations, invalid model specs, unsafe joins, unsupported model families, and predictive purpose without holdout and without explicit override.

Every block must produce a typed block reason. Every downgrade must be recorded and visible in the report. Every warning must be visible in the report and preserved in lineage. Severe issues must never be silently promoted to findings.

---

## 17. Compatibility With Future Contracts

This document defines doctrine, not public data shapes. Future contracts must conform to it.

* `contracts/validation.py` must encode claim levels, output categories, and block reasons consistent with this document.
* `contracts/modeling.py` must encode `allowed_claim_level` and model spec validation consistent with this document.
* `contracts/reporting.py` must enforce wording rules and required report elements consistent with this document.
* Leakage and join contracts must enforce blocking behavior consistent with this document.
* Statistical primitive contracts must support effect sizes, confidence intervals, and multiple-testing awareness consistent with this document.

This document must not prematurely define public data shapes; it must constrain them.