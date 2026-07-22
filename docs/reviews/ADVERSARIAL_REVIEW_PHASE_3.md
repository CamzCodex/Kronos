# Adversarial review — Phase 3 leakage and causality auditor

Date: 2026-07-22  
Scope: `data/leakage-auditor`

## Decision

The auditor is suitable as a mandatory invalidation gate after required CI passes. It catches deliberately contaminated fixtures across normalization, splits, labels, features, adjustments, universes, model selection, and the final holdout. No real dataset has passed it; therefore no existing experiment is newly validated.

## False-confidence risks and controls

### Provenance inputs can be false or incomplete

Severity: critical. The auditor can verify declared timestamps and relationships but cannot independently prove that an adapter emitted every source event or feature.

Control: every sample requires point-in-time universe evidence and provenance for every declared expected feature. Corporate-action coverage requires an explicit completeness declaration. Source-adapter reconciliation and raw hashes remain mandatory.

### A normalization probe covers only the callable supplied

Severity: high. A causal probe can pass while another unregistered normalization path remains leaky.

Control: the audit accepts multiple required probes and fails when none are supplied. Each ingestion/training/inference normalizer must register its own probe before the evaluation engine can treat the audit as complete.

### Event logs cannot prove that hidden holdout access did not occur

Severity: critical. A developer could read final-holdout data outside the declared selection-event log.

Control: the auditor rejects declared selection access, post-freeze selection, repeated final evaluation, wrong-split final evaluation, and post-final tuning. The evaluation engine must additionally enforce filesystem/API separation and generate events itself rather than trusting manual logs.

### “Corporate-action provenance complete” is self-declared

Severity: high. A true flag does not prove that the provider exposed every action or the correct knowledge timestamp.

Control: action rows are checked for known/effective time and adjusted-feature time, but provider documentation and source reconciliation remain required in the data card.

### Point-in-time membership may still omit unknown delistings

Severity: critical. A dataset can claim `includes_delisted=True` while the upstream universe is already survivor-filtered.

Control: the auditor requires source declaration, stable IDs, delisting inclusion, causal membership time, and membership evidence for every sample. External universe-source validation remains a benchmark gate.

## What contaminated fixtures prove

Tests deliberately introduce and detect:

- future-sensitive normalization;
- overlapping target splits;
- labels crossing a split boundary;
- late feature availability and rolling windows extending into the future;
- future-known and future-effective corporate-action adjustments;
- a survivor-only universe policy;
- hyperparameter search on the final holdout and selection after final evaluation;
- missing normalization probes;
- incomplete per-sample feature provenance.

These tests establish auditor behavior, not the causal validity of any market dataset.

## Residual limitations

- One audit specification represents one ordered train/validation/calibration/test/final protocol. A walk-forward engine should attach an audit per fold and a separate final-holdout audit.
- The auditor validates timestamps, declared completeness, and event relationships; it does not sandbox code or monitor arbitrary file reads.
- Correct embargo duration remains an evaluation-design decision supplied to the auditor.
- It does not determine whether a feature is economically meaningful, statistically robust, or licensed.
- It does not select a universe, provider, adjustment method, baseline, or cost model.

## Checkpoint compatibility

No model, tokenizer, inference, or checkpoint-sensitive structure changes. Released checkpoint numerical behavior is unaffected.

## Promotion blockers

- Bind the first real canonical dataset and point-in-time source artifacts.
- Generate, rather than manually author, feature, membership, action, and selection provenance.
- Run and persist an audit for every walk-forward fold and the final holdout.
- Ensure a failed audit prevents experiment registration and report promotion.

Passing this phase permits evaluation-engine integration only. It does not permit fine-tuning, paper portfolio construction, or financial claims.
