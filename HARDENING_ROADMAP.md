# Kronos hardening roadmap

This fork treats the published model and released checkpoints as research assets that must remain reproducible while the surrounding software is hardened. Changes are intentionally split into small, reviewable phases with explicit regression tests.

## Engineering principles

1. **Correctness before speed.** Bugs that leak target information, change causal behavior, or corrupt tensor shapes take priority over optimization.
2. **Checkpoint compatibility is a contract.** Architecture changes must document whether existing Hugging Face weights still load and produce the same outputs.
3. **Every bug fix gets a regression test.** Offline tests cover mechanics; checkpoint-backed integration tests cover numerical compatibility.
4. **Financial claims require walk-forward evidence.** Charts and in-sample loss are not accepted as evidence of tradable performance.
5. **Preserve attribution.** Upstream contributor commits are imported directly where practical; selective ports credit their source PR and author.

## Phase 1 — correctness and test foundations

Merged in PR #4.

- [x] Remove future-window leakage from custom CSV normalization.
- [x] Apply top-k and top-p filtering together.
- [x] Handle optional sampling filters safely.
- [x] Fix core quantizer/autograd failure paths.
- [x] Correct attention causal-mask semantics covered by the imported module suite.
- [x] Add fast offline unit tests on Python 3.10 and 3.12.
- [x] Add a direct causal-normalization regression test.
- [x] Add and pass the released-checkpoint regression gate.
- [x] Declare dependencies required by the fine-tuning configuration loader.

## Phase 2 — packaging and reproducible environments

Merged in PR #5.

- [x] Add a standards-compliant `pyproject.toml` using `setuptools.build_meta`.
- [x] Support editable and wheel installation without deleting script compatibility prematurely.
- [x] Separate core, web UI, fine-tuning, test, and development dependency groups.
- [x] Verify imports from an installed wheel outside the repository checkout.
- [x] Define focused lint configuration without mixing mass formatting into logic PRs.
- [ ] Replace remaining working-directory-dependent imports with package-relative imports.
- [ ] Add a dependency lock strategy for CI and documented research runs.
- [ ] Run lint and static checks as required CI gates.

## Phase 3 — inference API and financial invariants

Sampling hardening merged in PR #7.

- [x] Make top-k/top-p filtering side-effect-free.
- [x] Validate logits and generation controls before sampling.
- [x] Preserve legacy `model.kronos` sampling imports and internal runtime behavior.
- [x] Add focused compatibility and invalid-input regression tests.
- [x] Return individual sampled paths and configurable quantiles, not only their mean. Calibration remains an evaluation requirement.
- [x] Add deterministic generation controls and explicit random generators.
- [x] Validate timestamp lengths, monotonicity, timezone awareness, frequency consistency, and context limits.
- [x] Preserve raw generated candles and explicitly report OHLC, volume, amount, and projection validity.
- [ ] Add corporate-action guidance and adjusted-price handling.
- [ ] Benchmark memory and throughput before introducing KV caching.

## Phase 4 — data safety and training integrity

The safe archive foundation merged in PR #8. Qlib preprocessing and training wiring merged in PR #9. Inference and backtest wiring is tracked in PR #10.

- [x] Replace implicit pickle exchange with versioned, checksummed data-only archives.
- [x] Refuse legacy pickle before deserialisation unless compatibility is explicitly enabled.
- [x] Provide a documented migration command for verified local legacy files.
- [x] Reject archive traversal, duplicate, encrypted, symbolic-link, oversized, malformed, and unreferenced members.
- [x] Wire Qlib train, validation, and test datasets to canonical `.kronos.zip` archives.
- [x] Persist generated prediction signals without pickle.
- [x] Add cross-version resolver, migration, tampering, path-safety, package, and dataset integration tests.
- [x] Stream archive writes to reduce peak memory for large multi-symbol datasets.
- [ ] Audit every normalization and split path for target leakage.
- [ ] Add tests proving train, validation, test, and backtest boundaries are causal.
- [ ] Record dataset hashes, feature definitions, and preprocessing configuration.
- [ ] Make single-process CPU/GPU debug training possible alongside DDP.

## Phase 5 — reproducible financial evaluation

- [ ] Build expanding-window and rolling walk-forward benchmarks.
- [ ] Compare against last-value, drift, momentum, ARIMA, and volatility baselines.
- [ ] Report directional accuracy, calibration, rank correlation, and price error.
- [ ] Model fees, spreads, slippage, turnover, and market impact in strategy tests.
- [ ] Separate model selection periods from final untouched evaluation periods.
- [ ] Document whether released checkpoints predate any normalization fixes.

## Research data contract

The canonical contract is developed separately from the legacy Qlib demo so that dataset identity and validation can be tested without importing Qlib.

- [x] Merge canonical bar schema and structured multi-issue validation.
- [x] Merge deterministic dataset identity, immutable manifest writes, and data-card templates.
- [ ] Select and document an authoritative exchange-calendar and universe-membership source for the first benchmark.
- [ ] Wire the selected ingestion adapter to Parquet/Arrow research storage and bounded `.kronos.zip` evidence artifacts.

## Leakage and causality audit

- [x] Add a structured audit result whose failures invalidate an experiment.
- [x] Add future-perturbation normalization probes and contaminated regression fixtures.
- [x] Check ordered disjoint split targets, embargo, sample label boundaries, and final-holdout isolation.
- [x] Check feature availability, rolling windows, corporate-action effective time, and point-in-time membership.
- [ ] Bind generated provenance and an audit result to every evaluation fold and immutable experiment record.

## Merge gates

A phase is ready for `master` only when:

- its offline CI is green on supported Python versions;
- new behavior has focused tests;
- checkpoint compatibility has been tested or explicitly declared changed;
- security and data-integrity trade-offs are documented;
- the PR contains no unrelated formatting sweep.
