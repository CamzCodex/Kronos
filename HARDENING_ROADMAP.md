# Kronos hardening roadmap

This fork treats the published model and released checkpoints as research assets that must remain reproducible while the surrounding software is hardened. Changes are intentionally split into small, reviewable phases with explicit regression tests.

## Engineering principles

1. **Correctness before speed.** Bugs that leak target information, change causal behavior, or corrupt tensor shapes take priority over optimization.
2. **Checkpoint compatibility is a contract.** Architecture changes must document whether existing Hugging Face weights still load and produce the same outputs.
3. **Every bug fix gets a regression test.** Offline tests cover mechanics; checkpoint-backed integration tests cover numerical compatibility.
4. **Financial claims require walk-forward evidence.** Charts and in-sample loss are not accepted as evidence of tradable performance.
5. **Preserve attribution.** Upstream contributor commits are imported directly where practical; selective ports credit their source PR and author.

## Phase 1 — correctness and test foundations

Tracked in draft PR #4.

- [x] Remove future-window leakage from custom CSV normalization.
- [x] Apply top-k and top-p filtering together.
- [x] Handle optional sampling filters safely.
- [x] Fix core quantizer/autograd failure paths.
- [x] Correct attention causal-mask semantics covered by the imported module suite.
- [x] Add fast offline unit tests on Python 3.10 and 3.12.
- [x] Add a direct causal-normalization regression test.
- [ ] Make sampling filtering non-mutating and remove its expected failure.
- [ ] Run the checkpoint-backed regression suite before merging.

## Phase 2 — packaging and reproducible environments

- [ ] Add a standards-compliant `pyproject.toml` using `setuptools.build_meta`.
- [ ] Support `pip install -e .` without deleting script compatibility prematurely.
- [ ] Replace working-directory-dependent imports with package-relative imports.
- [ ] Separate core, web UI, fine-tuning, and development dependency groups.
- [ ] Add a dependency lock strategy for CI and documented research runs.
- [ ] Add linting and static checks without mixing mass formatting into logic PRs.

## Phase 3 — inference API and financial invariants

- [ ] Return individual sampled paths and calibrated quantiles, not only their mean.
- [ ] Add deterministic generation controls and explicit random generators.
- [ ] Validate timestamp lengths, monotonicity, and frequency consistency.
- [ ] Enforce or explicitly report OHLC validity and non-negative volume/amount.
- [ ] Add corporate-action guidance and adjusted-price handling.
- [ ] Benchmark memory and throughput before introducing KV caching.

## Phase 4 — data safety and training integrity

- [ ] Replace or tightly constrain untrusted pickle deserialization.
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

## Merge gates

A phase is ready for `master` only when:

- its offline CI is green on supported Python versions;
- new behavior has focused tests;
- checkpoint compatibility has been tested or explicitly declared changed;
- security and data-integrity trade-offs are documented;
- the PR contains no unrelated formatting sweep.
