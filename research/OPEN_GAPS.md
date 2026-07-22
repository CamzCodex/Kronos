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

## GAP-004 — Mean-only forecast API

- gap_id: `GAP-004`
- title: Raw probabilistic forecast paths and validity accounting absent
- description: The predictor averages sampled paths and lacks typed provenance, quantiles, tail statistics, explicit generators, raw/projected distinction, and repair reporting.
- severity: High
- impact: Calibration cannot be evaluated and invalid generated candles may be hidden or discarded inconsistently.
- evidence: `model/kronos.py` predictor interface at the evidence baseline.
- owner: Unassigned
- status: Open
- required work: `inference/probabilistic-forecast-api`
- blocking decision: Probabilistic benchmark
- related PR: None
- related experiment: None

## GAP-005 — No walk-forward and baseline engine

- gap_id: `GAP-005`
- title: Comparable out-of-sample evaluation absent
- description: Expanding/rolling folds, purge/embargo, mandatory baselines, calibration metrics, costs, robustness, and final holdout are not implemented.
- severity: Critical
- impact: The central mission question cannot be answered.
- evidence: Repository inventory and `HARDENING_ROADMAP.md` Phase 5 remains open.
- owner: Unassigned
- status: Open — promotion blocker
- required work: Walk-forward engine, baseline suite, evaluation CI smoke
- blocking decision: Model usefulness and fine-tuning gate
- related PR: None
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
