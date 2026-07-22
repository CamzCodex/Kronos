# Kronos implementation status

Status date: 2026-07-22  
Evidence baseline: `master` at `577af114c2fdae7fde5dfc4f89475ebcda06e074`
Operating mode: research and paper simulation only; no broker execution

## Executive status

Kronos has a materially stronger engineering foundation than the upstream demo, but it does not yet contain the research system required to determine whether the model adds economically useful information. Storage, sampling, packaging, selected model primitives, pinned-checkpoint numerical regression, and the reusable canonical data contract are hardened. A real approved dataset, causal auditor, probabilistic forecast contract, walk-forward engine, baseline suite, executable experiment registry, and zero-shot benchmark are not implemented.

Current implementation classification: **ENGINEERING HARDENED / RESEARCH NOT VALIDATED**.

## Reconciled repository state

- Default branch: `master`.
- Current master SHA at this phase's start: `577af114c2fdae7fde5dfc4f89475ebcda06e074`.
- Open pull requests at this phase's start: none after PR #12 merged.
- Most recent merge at this phase's start: PR #12, Phase 0 status and research-governance reconciliation.
- The mission's previously expected SHA, `af9c4bb0d1c6d4883e1d9ea28a83632c1c6eb978`, was correct before PR #11.
- The repository has no release tag or declared production deployment.

## Completed capabilities

| Capability | Evidence | Status |
|---|---|---|
| Core correctness and causal CSV normalization regression | PR #4; commit history ending at `ef9867d` | Complete for covered paths |
| Python 3.10/3.12 offline unit workflow | `.github/workflows/offline-tests.yml` | Active |
| Pinned released-checkpoint numerical regression | `tests/test_kronos_regression.py`; PR #4 CI | Active, path-filtered |
| Installable package, sdist, wheel, clean external import | PR #5; `.github/workflows/package-smoke.yml` | Active |
| Validated, non-mutating top-k/top-p sampling | PR #7; `model/sampling.py` | Complete for covered API |
| Versioned checksummed data-only `.kronos.zip` format | PR #8; `finetune/data_io.py` | Complete for portable snapshots |
| Safe Qlib preprocessing, training, inference and signal persistence | PRs #9 and #10 | Complete for covered I/O paths |
| Memory-bounded multi-frame archive writing and pre-replacement validation | PR #11; `finetune/archive_writer.py` | Complete for format v1 |
| Canonical bar schema, structured validation, deterministic dataset manifests and data-card templates | `kronos_data/`; `data/canonical-market-contract` | Complete as a reusable contract; not yet bound to a real source |

## Branch reconciliation

### Current development branches

`data/canonical-market-contract` is the active focused branch for this phase. Its capabilities are not treated as merged until its required CI gates pass.

### Retained historical branches

- `hardening/phase-1-correctness`
- `hardening/phase-2-packaging`
- `hardening/phase-3-sampling-api`
- `hardening/phase-4-safe-data-io`
- `hardening/phase-4b-wire-safe-data`
- `hardening/phase-4c-safe-backtest`
- `hardening/phase-4d-stream-archives`
- `docs/phase-0-reconciliation`
- `import/upstream-pr-247-offline-tests`
- `import/upstream-pr-262-sampling`
- `import/upstream-pr-263-csv-leakage`

These branches are historical evidence; their merged state does not imply that every upstream change was adopted unchanged.

### Superseded or closed probe branches

- `import/upstream-pr-244-core-fixes`: PR #3 closed; relevant fixes were selectively integrated with attribution in PR #4.
- `integration/pr244-plus-pr262`: PR #6 conflict probe closed; superseded by the focused compatibility module in PR #7.

Branch deletion is not required for correctness and is deferred until repository retention policy is defined.

## Known failures and blockers

1. **Critical — split contamination:** `finetune/config.py` overlaps training and validation from 2022-09-01 through 2022-12-31, and validation and test from 2024-04-01 through 2024-06-30. The overlap exceeds the declared 90-row lookback accommodation. Current demo fine-tuning and backtesting cannot support an untouched out-of-sample claim.
2. **Critical — no reusable leakage auditor:** only selected normalization behavior has a regression test. Split, label-window, feature-availability, corporate-action, universe, and final-holdout causality are unproven.
3. **High — no approved real dataset:** the canonical contract now exists on this phase branch, but no selected provider, authoritative calendar, point-in-time universe, licensed raw snapshot, or immutable benchmark manifest exists.
4. **High — inference averages paths:** the public predictor does not expose typed raw sample paths, quantiles, calibration data, repair accounting, or explicit generator provenance.
5. **High — no walk-forward evidence engine:** expanding/rolling folds, purging/embargo, mandatory baselines, probabilistic metrics, conservative costs, and final holdout do not exist.
6. **High — no evidence-grade benchmark:** no repository artifact demonstrates incremental forecasting or economic value over a naive baseline.
7. **Medium — incomplete CI controls:** Ruff is configured but not a required workflow; static type checks, dependency vulnerability scanning, secret scanning, explicit leakage smoke, and evaluation smoke are absent.
8. **Medium — training runner limitations:** current training scripts assume DDP-oriented execution and do not provide the required single-process CPU/GPU debug, resume, immutable lineage, and promotion controls.
9. **Medium — checkpoint history uncertainty:** regression tests pin exact Hugging Face revisions, but the relationship between released checkpoint training data/preprocessing and later normalization fixes is undocumented.

## Current CI state

- PR #11 offline tests: success on Python 3.10 and 3.12.
- PR #11 package smoke: success on Python 3.10 and 3.12, including editable, sdist, wheel, and clean import paths.
- PR #12 offline and package smoke: success on Python 3.10 and 3.12.
- PR #4 released-checkpoint regression: success at the pinned model and tokenizer revisions.
- No failing required check was observed during reconciliation.
- Absence of a workflow is not treated as a passing control.

## Immediate critical path

1. Select the reference source and bind its authoritative calendar, point-in-time universe, raw hashes, and licensing to the canonical contract.
2. Implement the leakage and causality auditor, including contaminated fixtures and a hard invalidation result.
3. Replace the mean-only forecast return with a typed probabilistic result while preserving the current compatibility wrapper.
4. Build the walk-forward and baseline engine only after the data and causality contracts are executable.
5. Run the released-checkpoint zero-shot benchmark before any serious fine-tuning or paper-portfolio promotion.

## Next three planned PRs

1. `data/leakage-auditor` — split/feature/label/holdout/universe/corporate-action checks, contaminated fixtures, CI gate.
2. `inference/probabilistic-forecast-api` — requests/results, raw and validated paths, quantiles, seeded generation, validity accounting, compatibility wrapper.
3. `evaluation/walk-forward-engine` — expanding/rolling folds, fixed holdout, purging/embargo, immutable fold records.

## Merge policy

No research or paper-trading promotion is allowed while a critical gap in `research/OPEN_GAPS.md` is open. Passing software tests is necessary but not evidence of market usefulness.
