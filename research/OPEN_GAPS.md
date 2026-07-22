# Kronos open gaps

Status date: 2026-07-22

## GAP-001 — Overlapping demo dataset splits (resolved)

- gap_id: `GAP-001`
- title: Overlapping Qlib train, validation, and test ranges
- description: The old defaults overlapped. The defaults now use disjoint target ranges (train through 2022-12-31, validation from 2023-01-01 through 2024-06-30, and test from 2024-07-01), validate ordering/containment at construction, and reject mutations that reintroduce overlap. Context is no longer justified by overlapping target membership.
- severity: Resolved critical defect; remaining source/final-isolation gaps are tracked separately
- impact: The bundled demonstration configuration no longer creates direct target-date overlap. This does not make its unapproved source or test/backtest reuse decision-grade.
- evidence: `finetune/config.py`, `tests/test_finetune_config.py`, and the local-runtime adversarial review.
- owner: Resolved by local-runtime readiness phase
- status: Resolved for bundled defaults
- required work: Approved source adapters must still implement explicit context-only buffers, purge/embargo, and physical final isolation under GAP-002/GAP-005.
- blocking decision: None independently; GAP-002/GAP-005/GAP-006 remain blockers
- related PR: Local-runtime readiness PR
- related experiment: None

## GAP-002 — No approved canonical benchmark dataset

- gap_id: `GAP-002`
- title: No source has passed the canonical benchmark evidence gate
- description: The reusable `kronos_data` contract binds canonical fields, validation, hashes, splits, adjustment declaration, code commit, and immutable manifest identity. The source gate additionally requires confirmed rights/access, retained hashed bytes, authoritative sessions, causal adjustments, point-in-time membership, delistings, stable identifiers/currency, revision policy, and primary evidence. Norgate US Stocks Platinum is the preferred conditional technical candidate, but its standard EULA requires deletion of Data and Derived Data after lapse, restricts use, permits silent corrections, and does not establish historical availability timestamps. Qlib/Yahoo and other reviewed alternatives remain incomplete.
- severity: Critical
- impact: No selected source can be ingested for a decision-grade experiment, so the benchmark cannot start honestly.
- evidence: `kronos_data/source_gate.py` v1.1, its paid-entitlement hash regression, `docs/data/REFERENCE_SOURCE_ASSESSMENT.md`, `docs/data/REFERENCE_SOURCE_ACQUISITION_DECISION.md`, linked provider terms/content/pricing sources, `data/cards/reference_daily/DATA_CARD.md`, and the source/acquisition adversarial reviews.
- owner: Unassigned
- status: Partially resolved — conditional technical candidate selected; licence, acquisition, and real evidence remain promotion blockers
- required work: Obtain a signed Norgate research/retention amendment satisfying the acquisition checklist (or an equivalent provider contract), acquire and hash a trial export, prove availability timing, pass the source gate, then implement the adapter and first real manifest.
- blocking decision: Any evidence-grade experiment
- related PR: `#21` and the data-acquisition closeout PR
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
- related PR: `#16`, `#17`, `#18`, `#19`, `#20`, and `#21`
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
- title: Required quality and security gates need full repository enforcement
- description: PR #23 adds a focused workflow covering Ruff, maintained-surface Mypy, dependency auditing, full-history secret scanning, and explicit archive/leakage/evaluation smoke tests. The Web UI phase adds its security helper, launcher, and 37 route-level boundary regressions. Legacy examples, `finetune_csv`, the large Web UI route/rendering module, older model internals, branch-protection settings, and GitHub-native secret scanning remain outside the proved static-analysis scope.
- severity: Medium
- impact: Important classes of defects can merge without an automated gate.
- evidence: `.github/workflows/quality-security.yml`, `requirements-quality.txt`, and `docs/operations/QUALITY_AND_SECURITY_GATES.md`.
- owner: Unassigned
- status: Partially resolved — focused automated gates implemented; full legacy coverage and repository-setting enforcement remain open
- required work: Require all green workflow jobs in branch protection, confirm GitHub-native secret scanning where available, and bring remaining executable surfaces under staged Ruff, type, and security review.
- blocking decision: Production-readiness classification
- related PR: `#23` and the Web UI security PR
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
- status: Resolved in the quality/security gate phase
- required work: Retain SPDX metadata and `setuptools>=77`; keep package smoke required.
- blocking decision: None for research evaluation; blocks future packaging-readiness claim after the enforcement date.
- related PR: Quality/security gate PR for this phase
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
- related PR: `#20`
- related experiment: None

## GAP-011 — Legacy Web UI is not safe for network exposure

- gap_id: `GAP-011`
- title: Bundled Flask UI retains a non-production trust boundary
- description: The Web UI is now constrained to deliberate single-user loopback use: no debugger/reloader, fixed `127.0.0.1` binding, trusted hosts, no CORS, local data-directory identifiers, symlink/traversal refusal, bounded requests/files/rows/parameters/devices, sanitized errors, strict market-input refusal, no runtime installation, security headers, and pinned browser assets with SRI. It still has no authentication, TLS, rate limiting, user isolation, workload sandbox, production WSGI server, or remotely deployable trust model.
- severity: High
- impact: The former high-risk local defaults are removed, but publishing the UI could still permit unauthorized model use, denial of service, and disclosure of locally saved results.
- evidence: `webui/app.py`, `webui/security.py`, `webui/run.py`, `webui/start.sh`, `.gitignore`, `tests/webui/test_security.py`, and `docs/reviews/ADVERSARIAL_REVIEW_WEBUI_SECURITY.md`.
- owner: Unassigned
- status: Partially resolved — approved for deliberate single-user loopback use only; remote deployment remains blocked
- required work: Before any remote use, design and test authentication/authorization, TLS, rate limiting, multi-user isolation, workload quotas/cancellation, production serving, self-hosted browser assets, and secret/result governance. Exact interactive checkpoint revisions are already enforced.
- blocking decision: Any Web UI deployment, Tailscale exposure, or production-readiness claim
- related PR: Web UI security PR
- related experiment: None

## GAP-012 — Local accelerator performance is not yet measured

- gap_id: `GAP-012`
- title: No RX 9070 operational benchmark artifact exists
- description: The repository now provides pinned-checkpoint doctor, smoke, and latency benchmarking commands plus an AMD Windows runbook. This sandbox proves CPU operability only and cannot measure Cam's RX 9070, current driver stability, or the relative mini/small/base latency-memory trade-off.
- severity: Medium operational gap; not a scientific promotion blocker
- impact: The best local model/context/horizon/sample setting cannot be selected from measured Radeon evidence yet.
- evidence: `kronos_runtime/`, `docs/operations/LOCAL_RUNBOOK.md`, and the local-runtime adversarial review.
- owner: Local workstation operator
- status: Partially resolved — instrumentation and acceptance commands complete; hardware run pending
- required work: Run identical `kronos-runtime benchmark` settings for mini/small/base on the RX 9070, retain the JSON outputs, and choose the local default on observed latency/memory without treating it as alpha evidence.
- blocking decision: Local performance tuning only
- related PR: Local-runtime readiness PR
- related experiment: None; operational benchmark outputs are not market experiments
