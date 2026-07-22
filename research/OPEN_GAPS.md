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
- title: No source has passed the canonical benchmark evidence gate
- description: The reusable `kronos_data` contract binds canonical fields, validation, hashes, splits, adjustment declaration, code commit, and immutable manifest identity. The active source gate additionally requires confirmed rights/access, retained hashed bytes, authoritative sessions, causal adjustments, point-in-time membership, delistings, stable identifiers/currency, revision policy, and primary evidence. Qlib/Yahoo remains incomplete and reviewed alternatives require unapproved paid access.
- severity: Critical
- impact: No selected source can be ingested for a decision-grade experiment, so the benchmark cannot start honestly.
- evidence: `kronos_data/source_gate.py`, `docs/data/REFERENCE_SOURCE_ASSESSMENT.md`, primary sources linked there, `data/cards/reference_daily/DATA_CARD.md`, and the Phase 2/source-gate adversarial reviews.
- owner: Unassigned
- status: Partially resolved — requirements and candidate refusal are explicit; data acquisition remains a promotion blocker
- required work: Supply an already licensed evidence package or separately authorize paid-source evaluation; then implement the source adapter, pass this gate, and write/register the first real manifest.
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

## GAP-005 — No real source-to-result walk-forward execution

- gap_id: `GAP-005`
- title: Evaluation contracts exist but source adapters and real execution are absent
- description: PRs #16–#20 implement split/audit binding, mandatory comparators, scoring, causal costs, paired/final-isolated aggregation, audit-gated execution, immutable fold results, and byte-verified reconstruction. The active source phase refuses incomplete providers. No real source adapter, training-only scale/regime provenance, attested launcher, or physical final-data isolation exists.
- severity: Critical
- impact: The central mission question cannot be answered.
- evidence: `kronos_eval/walk_forward.py`, `baselines.py`, `metrics.py`, `costs.py`, `aggregation.py`, `runner.py`, their regression tests, protocol documents, and Phase 5A–5D adversarial reviews.
- owner: Unassigned
- status: Partially resolved — real execution remains a promotion blocker
- required work: Source-specific forecast/baseline/scale/regime adapters, attested registry launcher capture, feature-matched comparators, factor exposure source, verified real fold audits, physical final-holdout enforcement, evaluation CI smoke
- blocking decision: Model usefulness and fine-tuning gate
- related PR: `#16`, `#17`, `#18`, and this phase's pull request
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

## GAP-010 — Registry metadata and approvals are not independently attested

- gap_id: `GAP-010`
- title: Local lineage proves registered bytes but trusts launcher and reviewer declarations
- description: The Phase 7 registry verifies content hashes, deterministic experiment identity, reconstruction, immutable record/alias history, and promotion-alias policy. Git/dirty state, hardware, libraries, source semantics, and approval references are still supplied by the caller; approval authority is not signed or resolved.
- severity: High
- impact: A caller could accurately register misleading metadata or self-declare approval, producing mechanically complete but scientifically invalid evidence.
- evidence: `kronos_eval/registry.py`, `docs/reviews/ADVERSARIAL_REVIEW_PHASE_7.md`, and synthetic registry regressions.
- owner: Unassigned
- status: Open — model-promotion blocker
- required work: Capture Git/environment state in the executable launcher, bind passed audit/result artifacts automatically, resolve approval evidence to repository records, serialize concurrent writers, and define signed or repository-governed promotion authority before production use.
- blocking decision: Model promotion and production-readiness classification
- related PR: This phase's pull request
- related experiment: None
