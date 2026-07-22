# Kronos open gaps

Status date: 2026-07-22

## GAP-001 — Overlapping demo dataset splits

- gap_id: `GAP-001`
- title: Overlapping Qlib train, validation, and test ranges
- description: Default configuration shares observations across train/validation and validation/test for periods materially longer than the declared lookback accommodation.
- severity: Critical
- impact: Invalidates model-selection, calibration, test, and final-holdout independence claims.
- evidence: `finetune/config.py` lines defining 2011-01-01–2022-12-31 training, 2022-09-01–2024-06-30 validation, and 2024-04-01–2025-06-05 test.
- owner: Unassigned
- status: Open — promotion blocker
- required work: Define non-overlapping target intervals, explicit context-only buffers, purge/embargo rules, and regression tests.
- blocking decision: Fine-tuning, benchmark promotion, and paper-portfolio work
- related PR: None
- related experiment: None

## GAP-002 — No approved canonical benchmark dataset

- gap_id: `GAP-002`
- title: Canonical bars, validation reports, and deterministic manifests absent
- description: The reusable `kronos_data` contract now binds canonical fields, structured validation, content/configuration hashes, splits, adjustment declaration, code commit, and immutable manifest identity. No real provider adapter, authoritative calendar, point-in-time universe, or approved dataset manifest exists yet.
- severity: High
- impact: A selected source still cannot be used for evidence-grade experiments until it is ingested and bound to the contract.
- evidence: `kronos_data/`, `data/cards/reference_daily/DATA_CARD.md`, and the Phase 2 adversarial review.
- owner: Unassigned
- status: Partially resolved — real dataset remains a promotion blocker
- required work: Select source/licence; implement adapter; supply authoritative calendar and universe history; write and register the first immutable manifest.
- blocking decision: Any evidence-grade experiment
- related PR: None
- related experiment: None

## GAP-003 — No leakage and causality auditor

- gap_id: `GAP-003`
- title: Reusable causal audit absent
- description: A reusable auditor now tests normalization perturbation, split/label boundaries, feature availability, adjustment effective time, point-in-time membership, selection isolation, and final-holdout use. No real dataset or evaluation fold has yet generated and passed the required provenance.
- severity: Critical
- impact: False positive research results could pass existing tests.
- evidence: `kronos_data/leakage.py`, contaminated fixtures in `tests/test_leakage_auditor.py`, and the Phase 3 adversarial review.
- owner: Unassigned
- status: Partially resolved — real audits remain a promotion blocker
- required work: Generate source provenance; attach one audit per walk-forward fold and final holdout; block experiment registration on failure.
- blocking decision: Evaluation validity
- related PR: None
- related experiment: None

## GAP-004 — Probabilistic forecast calibration and integration

- gap_id: `GAP-004`
- title: Typed raw paths exist but calibration and evaluation integration are absent
- description: PR #15 adds raw samples, typed provenance, quantiles, return distributions, isolated generators, raw/projected distinction, and repair reporting while retaining the legacy mean-only wrapper. No out-of-sample run has established calibration, invalid-path behavior, or incremental information.
- severity: High
- impact: Calibration cannot be evaluated and invalid generated candles may be hidden or discarded inconsistently.
- evidence: `model/forecast.py`, `docs/inference/PROBABILISTIC_FORECAST_API.md`, and the Phase 4 adversarial review.
- owner: Unassigned
- status: Partially resolved — evaluation integration and empirical calibration remain blockers
- required work: Bind verified registry provenance; evaluate calibration and repair sensitivity on every walk-forward fold.
- blocking decision: Probabilistic benchmark
- related PR: `#15`
- related experiment: None

## GAP-005 — No complete walk-forward evaluation runner

- gap_id: `GAP-005`
- title: Split and baseline protocols exist but comparable out-of-sample execution is absent
- description: PRs #16 and #17 implement deterministic split/audit binding and all eleven required frozen comparators. The active phase adds normalized forecast metrics, causal paper-return cost ledgers, cost sensitivity, paired fold bootstrap summaries, and separation of final-holdout scores. Audit-gated forecast execution, training-only scale/regime provenance, immutable run artifacts, and physical final-data access enforcement remain absent.
- severity: Critical
- impact: The central mission question cannot be answered.
- evidence: `kronos_eval/walk_forward.py`, `baselines.py`, `metrics.py`, `costs.py`, `aggregation.py`, their regression tests, protocol documents, and Phase 5A/5B/5C adversarial reviews.
- owner: Unassigned
- status: Partially resolved — evaluation runner remains a promotion blocker
- required work: Audit-gated runner and immutable results, feature-matched comparators, training-only scale/regime provenance, factor exposure source, verified real fold audits, physical final-holdout enforcement, evaluation CI smoke
- blocking decision: Model usefulness and fine-tuning gate
- related PR: `#16`, `#17`, and this phase's pull request
- related experiment: None

## GAP-006 — No zero-shot reference benchmark

- gap_id: `GAP-006`
- title: Released checkpoint has not been benchmarked against required baselines
- description: No immutable reports, metrics, figures, dataset card, cost assumptions, or leakage audit exist for a reference universe.
- severity: Critical
- impact: No go/no-go decision for fine-tuning or paper portfolio is defensible.
- evidence: `research/EXPERIMENT_REGISTER.jsonl` records zero evidence-grade experiments.
- owner: Unassigned
- status: Open — promotion blocker
- required work: Select reproducible licensed data, run zero-shot folds, publish complete report pack
- blocking decision: Fine-tuning and paper-trading vertical slice
- related PR: None
- related experiment: None

## GAP-007 — CI control gaps

- gap_id: `GAP-007`
- title: Required lint, type, security, leakage, and evaluation gates absent
- description: Existing workflows cover offline tests, packaging, and path-filtered checkpoint regression only.
- severity: Medium
- impact: Important classes of defects can merge without an automated gate.
- evidence: `.github/workflows/` contains three workflows at reconciliation.
- owner: Unassigned
- status: Open
- required work: Add focused Ruff, typing, dependency, secret, leakage, and evaluation-smoke workflows without broad formatting churn.
- blocking decision: Production-readiness classification
- related PR: None
- related experiment: None

## GAP-008 — Released-checkpoint preprocessing provenance

- gap_id: `GAP-008`
- title: Relationship between checkpoint training and later normalization fixes unknown
- description: Exact checkpoint revisions are pinned, but training-data and preprocessing manifests are not available in this fork.
- severity: High
- impact: Pretraining overlap and preprocessing mismatch can confound benchmark interpretation.
- evidence: `tests/test_kronos_regression.py` pins revisions; no corresponding training manifest is present.
- owner: Unassigned
- status: Open
- required work: Trace upstream primary documentation and record known/unknown provenance in the model card.
- blocking decision: Strength of benchmark independence claim
- related PR: None
- related experiment: None

## GAP-009 — Packaging license metadata deprecation

- gap_id: `GAP-009`
- title: Setuptools license table and classifier emit deprecation warnings
- description: Local sdist/wheel builds report that the TOML license table and MIT classifier should migrate to an SPDX license expression before the stated 2027-02-18 enforcement date.
- severity: Low
- impact: No current build failure, but a future setuptools release can stop accepting the existing metadata.
- evidence: Local Phase 4 package build output from current `pyproject.toml`; package smoke remains green.
- owner: Unassigned
- status: Open — non-blocking
- required work: Make a focused packaging-metadata PR, verify published metadata, sdist, wheel, and supported Python imports.
- blocking decision: None for research evaluation; blocks future packaging-readiness claim after the enforcement date.
- related PR: None
- related experiment: None
