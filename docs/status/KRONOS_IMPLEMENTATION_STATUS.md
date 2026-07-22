# Kronos implementation status

Status date: 2026-07-22  
Evidence baseline: `master` at `7f99e93962f1a4baee617874605871433578731e` plus the data-acquisition closeout phase
Operating mode: research and paper simulation only; no broker execution

## Executive status

Kronos has a materially stronger engineering foundation than the upstream demo, but it does not yet contain the real evidence required to determine whether the model adds economically useful information. Storage, sampling, packaging, selected model primitives, pinned-checkpoint numerical regression, canonical data and leakage contracts, typed probabilistic forecasts, walk-forward planning, eleven mandatory baselines, scoring/cost/aggregation, the audit-gated runner, byte-verified experiment lineage, a fail-closed reference-source evidence gate, required quality/security CI, and a local-only Web UI boundary are implemented. No reviewed provider has complete licensing, snapshot, calendar, adjustment, point-in-time universe, and delisting evidence, so real source adapters, audits, and the zero-shot benchmark remain blocked.

Current implementation classification: **ENGINEERING HARDENED / RESEARCH NOT VALIDATED**.

## Reconciled repository state

- Default branch: `master`.
- Current master SHA at acquisition phase start: `7f99e93962f1a4baee617874605871433578731e`.
- Most recent merge at phase start: PR #24, local-only Web UI trust boundary.
- PR #24 removed 29 generated path-disclosing demo results and passed quality/security #7, offline #121, and package #106.
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
| Leakage and causality auditor with deliberate contamination fixtures | `kronos_data/leakage.py`; `data/leakage-auditor` | Complete as a reusable gate; not yet bound to a real experiment |
| Typed raw-path forecast API, explicit randomness, candle validity and repair accounting | PR #15; `model/forecast.py` | Complete for the covered API; pinned released-checkpoint regression passed |
| Expanding/rolling fold planning, fixed holdout, purge/embargo records and audit binding | PR #16; `kronos_eval/walk_forward.py` | Complete as a reusable protocol; not an evaluation runner or real-data result |
| Eleven required identical-information baseline forecasts with frozen hashed controls | PR #17; `kronos_eval/baselines.py` | Complete as reference comparators; not a market-performance result |
| Point/direction/ranking/probabilistic scoring, causal paper-cost ledgers and final-isolated paired fold aggregation | PR #18; `kronos_eval/metrics.py`; `costs.py`; `aggregation.py` | Complete as calculation contracts; not run on real forecasts |
| Passed-audit-only complete comparator execution, test/final boundary enforcement, truth matching and immutable fold results | PR #19; `kronos_eval/runner.py` | Merged; no real inputs or result |
| Byte-verified content-addressed experiment records, reconstruction, immutable alias history and promotion policy | PR #20; `kronos_eval/registry.py` | Merged; no real experiment registered |
| Fail-closed source licensing/access/snapshot/calendar/adjustment/universe/delisting/reproducibility gate | PR #21 plus gate v1.1 entitlement binding; `kronos_data/source_gate.py` | Paid access now requires a retained contract SHA-256; no source approved |
| Pinned Ruff/Mypy/dependency/secret/archive/leakage/evaluation merge controls | PR #23; `.github/workflows/quality-security.yml` | Active on branch pushes; branch-protection settings remain unverified |
| Local-only Web UI trust boundary, strict input refusal, and route regressions | PR #24; `webui/security.py`; `tests/webui/test_security.py`; Web UI adversarial review | Merged for deliberate single-user loopback use; every remote deployment remains blocked |
| Conditional provider acquisition decision and signed-contract checklist | Acquisition decision and adversarial review | Preferred technical product selected; standard purchase rejected; no source acquired or approved |

## Branch reconciliation

### Current development branches

- `docs/data-acquisition-closeout` — provider contract/acquisition decision and final status reconciliation.

The next source-adapter branch remains blocked pending a signed durable-retention licence and a trial export that passes the source gate.

### Retained historical branches

- `hardening/phase-1-correctness`
- `hardening/phase-2-packaging`
- `hardening/phase-3-sampling-api`
- `hardening/phase-4-safe-data-io`
- `hardening/phase-4b-wire-safe-data`
- `hardening/phase-4c-safe-backtest`
- `hardening/phase-4d-stream-archives`
- `docs/phase-0-reconciliation`
- `data/canonical-market-contract`
- `data/leakage-auditor`
- `inference/probabilistic-forecast-api`
- `evaluation/walk-forward-engine`
- `evaluation/baseline-suite`
- `evaluation/metrics-and-costs`
- `evaluation/audit-gated-runner`
- `registry/experiment-and-model-lineage`
- `data/reference-source-gate`
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
2. **Critical — no real dataset has passed the leakage auditor:** the reusable gate and identity-bound fold attachment exist, but no selected source has generated complete provenance or a passing real audit.
3. **Critical — no approved real dataset:** Norgate US Stocks Platinum is conditionally preferred, but its standard terms conflict with durable lineage and its public documentation does not establish every historical availability timestamp. No contract, payment, retained raw snapshot, authoritative calendar, point-in-time universe, or immutable benchmark manifest exists.
4. **High — probabilistic interface not yet empirically calibrated:** PR #15 exposes typed raw samples, quantiles, return distributions, explicit randomness, and repair accounting while retaining legacy wrappers. No walk-forward evidence establishes calibration.
5. **High — no real walk-forward execution:** PRs #16–#20 provide split, baseline, scoring, cost, aggregation, audit-gated execution, immutable fold results, and byte-verified local lineage. Source adapters, training-only scale/regime provenance, attested launcher capture, factor exposure, physical final isolation, and real runs remain absent.
6. **High — no evidence-grade benchmark:** no repository artifact demonstrates incremental forecasting or economic value over a naive baseline.
7. **Medium — incomplete CI enforcement/scope:** PR #23 provides green Ruff, maintained-surface Mypy, dependency, full-history secret, archive, leakage, and evaluation workflows. Branch-protection/GitHub-native settings are unverified, and legacy executables remain outside staged static analysis.
8. **High — Web UI remote deployment remains prohibited:** local file, browser, validation, launcher, and error defaults are hardened, but authentication, TLS, rate limiting, multi-user isolation, workload quotas, production serving, and immutable interactive checkpoint revisions are absent.
9. **Medium — training runner limitations:** current training scripts assume DDP-oriented execution and do not provide the required single-process CPU/GPU debug, resume, immutable lineage, and promotion controls.
10. **Medium — checkpoint history uncertainty:** regression tests pin exact Hugging Face revisions, but the relationship between released checkpoint training data/preprocessing and later normalization fixes is undocumented.

## Current CI state

- PR #11 offline tests: success on Python 3.10 and 3.12.
- PR #11 package smoke: success on Python 3.10 and 3.12, including editable, sdist, wheel, and clean import paths.
- PR #12 offline and package smoke: success on Python 3.10 and 3.12.
- PR #13 offline and package smoke: success on Python 3.10 and 3.12.
- PR #14 offline and package smoke: success on Python 3.10 and 3.12.
- PR #15 offline and package smoke: success on Python 3.10 and 3.12; pinned released-checkpoint regression success.
- PR #16 offline and package smoke: success on Python 3.10 and 3.12.
- PR #17 offline and package smoke: success on Python 3.10 and 3.12.
- PR #18 offline and package smoke: success on Python 3.10 and 3.12.
- PR #19 offline run #107 and package smoke run #92: success on Python 3.10 and 3.12.
- PR #20 offline run #110 and package smoke run #95: success on Python 3.10 and 3.12.
- PR #21 offline run #112 and package smoke run #97: success on Python 3.10 and 3.12.
- PR #23 quality/security run #4: Ruff/Mypy, two dependency audits, integrity smoke, and full-history Gitleaks success.
- PR #23 offline run #119 and package smoke run #104: success on Python 3.10 and 3.12.
- PR #23 released-checkpoint run #8: success at the pinned revisions.
- PR #24 quality/security run #7: Ruff/Mypy, two dependency audits, integrity smoke (including 37 Web UI cases), and full-history Gitleaks success.
- PR #24 offline run #121 and package run #106: success on Python 3.10 and 3.12.
- Acquisition phase local evidence: 19 isolated source-gate regressions, Ruff, maintained-surface Mypy, compilation, and patch hygiene passed; full GitHub matrices remain required.
- PR #4 released-checkpoint regression: success at the pinned model and tokenizer revisions.
- No failing required check was observed during reconciliation.
- Absence of a workflow is not treated as a passing control.

## Immediate critical path

1. Obtain a signed Norgate amendment satisfying the acquisition checklist, or an equivalent provider contract; do not purchase standard access.
2. Acquire a bounded trial snapshot on a controlled Windows host, hash it before parsing, and pass every source-gate field, including availability timing.
3. Implement the selected source adapter and bind its calendar, point-in-time universe, raw hashes, licensing, and causal scale/regime generation to the canonical contract.
4. Generate, bind, and register real leakage-audit and forecast evidence for every development fold.
5. Add final-holdout isolation, run it once after development decisions freeze, and publish the zero-shot report before fine-tuning or paper-portfolio promotion.

## Next three planned PRs

1. `data/reference-dataset-adapter` — selected approved source, authoritative calendar/universe, raw hashes, data card, causal scale/regime provenance, and real audits.
2. `evaluation/reference-submission-adapters` — causal scale/regime generation, released-checkpoint and baseline submissions, and automatic registry capture.
3. `evaluation/reference-zero-shot-benchmark` — all registered folds, fixed final holdout, immutable report pack, and decision.

## Merge policy

No research or paper-trading promotion is allowed while a critical gap in `research/OPEN_GAPS.md` is open. Passing software tests is necessary but not evidence of market usefulness.
