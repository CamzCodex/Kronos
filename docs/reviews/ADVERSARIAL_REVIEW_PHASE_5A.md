# Adversarial review — Phase 5A walk-forward protocol

Date: 2026-07-22  
Scope: `evaluation/walk-forward-engine`

## Decision

The split planner is suitable as the temporal protocol for the baseline/evaluation
runner after cross-version and package gates pass. It does not answer whether Kronos
forecasts well. Model classification remains `RESEARCH ONLY`.

## How this could produce false confidence

### A correct split over a biased dataset is still biased

Severity: critical. Monotonic timestamps do not prove point-in-time membership,
delisting coverage, calendar correctness, adjustments, licensing, or feature
availability.

Control: plans bind a dataset ID, and folds require a passed identity-matched leakage
audit. A real source adapter and approved manifest remain promotion blockers.

### Observation-count purge may be too short

Severity: critical. The engine enforces the configured count but cannot infer the
maximum target horizon, feature lookback, late availability, or overlapping-label
risk.

Control: exact excluded observations are persisted. The evaluation configuration
must derive purge/embargo from the largest relevant horizon and attach the resulting
audit. Sensitivity to larger gaps is mandatory.

### Repeated development folds expand the opportunity to tune

Severity: high. Multiple folds improve evidence breadth but also create more metrics,
hyperparameters, and opportunities for cherry-picking.

Control: target roles cannot be reused across folds; final holdout is fixed; truncated
fold plans are non-decision-grade. The runner and reports must record selection events,
multiple-comparison warnings, all folds, and parameter perturbations.

### The final holdout is declared, not physically sandboxed

Severity: critical. A developer can still read final data outside this API.

Control: every fold split hash includes the final boundary and the leakage auditor
rejects declared access/repeated evaluation. The runner still needs filesystem/API
separation and a generated event log before the holdout is considered untouched.

### Two folds can still be dominated by one regime

Severity: high. The default minimum prevents a single favorable period but does not
establish robustness.

Control: `decision_grade_protocol` is only a structural flag. Promotion criteria
still require a meaningful majority of folds, instrument/regime breadth, confidence
intervals, and a confirming final evaluation.

### Optional calibration can be misused

Severity: high. Omitting calibration while reporting token frequencies as
probabilities would overstate probabilistic quality.

Control: calibration absence is explicit in every fold and leakage spec. A report
cannot claim calibrated probabilities without a valid calibration method and
out-of-sample coverage/proper-score evidence.

### Recorded costs are not applied in this phase

Severity: high for economic claims. A canonical cost object in a fold does not mean a
return series includes spread, commission, slippage, liquidity, or impact.

Control: this phase makes no performance claim. The baseline/strategy runner must
apply and attribute each cost component and run conservative sensitivity cases.

### Audit identity still depends on declared provenance

Severity: high. The audit ID binds the supplied tables, probe frames, callable name,
and code commit. It cannot prove that the adapter omitted nothing or that runtime code
matches an allegedly clean working tree.

Control: future experiment identity must include dirty-tree state, source artifacts,
raw hashes, environment, and generated provenance. Unverified manual identity is not
decision-grade.

### Released checkpoint may overlap the proposed holdout through pretraining

Severity: high. The repository lacks the checkpoint training-data manifest.

Control: retain the provenance uncertainty in the model card and qualify any claim of
independent evaluation even when the local holdout is untouched by fork development.

## Regression evidence

Tests cover:

- exact expanding and rolling positions;
- fixed-size rolling and expanding training behavior;
- explicit optional calibration;
- purge and final embargo records;
- a fixed final holdout outside development folds;
- prevention of cross-fold target-role reuse;
- deterministic identity bound to timestamps, costs, seed, model, data, and config;
- immutable atomic plan persistence;
- timezone/order/history sufficiency failures;
- explicit non-decision-grade one-fold and truncated smoke plans;
- optional-calibration leakage audits;
- audit/spec and split identity hashes; and
- refusal of failed or mismatched audit attachments.

No real market-data plan has been created or audited.

## Checkpoint compatibility

No model, tokenizer, predictor, sampling, checkpoint, or inference code changes. The
new package is model-agnostic. Released checkpoint numerical behavior is unaffected;
the checkpoint workflow is not required by path policy for this PR.

## Security and operations

The planner reads in-memory timestamps and writes an explicit JSON plan only when
asked. It loads no checkpoint, unsafe archive, credential, external service, or
broker. Trading remains paper/simulation only.

## Promotion blockers

- Select and approve a real canonical dataset and point-in-time universe.
- Generate rather than manually author every fold's leakage provenance.
- Implement identical-information baselines and forecast/strategy metrics.
- Apply realistic costs and robustness tests.
- Enforce final-holdout isolation outside the planning object.
- Register all artifacts and dirty-tree/environment identity.

Passing Phase 5A permits baseline-runner integration only. It does not permit
fine-tuning, paper portfolio construction, or financial claims.
