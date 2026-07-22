# Kronos research status

Status date: 2026-07-22  
Evidence baseline: `master` at `7f99e93962f1a4baee617874605871433578731e` plus the data-acquisition closeout phase

## Decision

Current classification: **RESEARCH ONLY**.

There is currently no defensible repository-backed answer to whether Kronos provides incremental, economically useful forecasting information over simple baselines. The correct answer is **Unknown**. Fine-tuning promotion and the paper-portfolio vertical slice are blocked pending a real causally approved dataset, walk-forward evaluation, and a released-checkpoint zero-shot benchmark.

## What has been scientifically validated

Very little market science has been independently validated in this fork.

- Exact Hugging Face revisions for `NeoQuasar/Kronos-small` (`901c26c1332695a2a8f243eb2f37243a37bea320`) and `NeoQuasar/Kronos-Tokenizer-base` (`0e0117387f39004a9016484a186a908917e22426`) load and reproduce committed numerical regression expectations on the bundled fixture under the tested environment.
- Covered inference mechanics remain numerically compatible after the merged hardening changes.

These are software and checkpoint-reproducibility results. They are not independent evidence of alpha, calibration, robustness, or economic value.

## What has only been engineered

- causal normalization for one custom CSV path;
- corrected and validated sampling controls;
- selected quantizer, autograd, attention, and embedding fixes;
- installable packages and cross-version test workflows;
- safe deterministic portable DataFrame archives;
- safe Qlib I/O and legacy-pickle refusal;
- memory-bounded multi-frame archive writing.
- canonical bar field semantics and multi-issue validation reports;
- deterministic dataset content/configuration identity and immutable manifest persistence;
- reference data-card and scalable-storage policy templates.
- reusable split, normalization, feature, adjustment, universe, selection, and holdout causality audits with deliberately contaminated fixtures.
- typed raw-path forecasting, isolated seeded or greedy generation, configurable path summaries, and explicit generated-candle validation/projection accounting, with pinned-checkpoint compatibility confirmed in PR #15.
- deterministic expanding/rolling split planning, exact purge/embargo and fixed-holdout records, and identity-bound leakage-audit attachment merged in PR #16.
- eleven frozen, identity-bound forecast baselines receiving the same validated OHLCVA information set, merged in PR #17. Their deterministic or seeded output correctness has been tested, but no comparative market metric has been calculated.
- common point, direction, ranking, probabilistic, regime, paper-cost, exposure, cost-sensitivity, paired bootstrap, and final-isolation calculations merged in PR #18. Only synthetic formula and failure-mode fixtures have been evaluated.
- a complete-suite, passed-audit-only development runner with truth matching, test/final boundary refusal, optional downstream cost binding, and immutable JSON results merged in PR #19. Its tests use synthetic audits and forecasts only.
- a content-addressed local experiment/model registry with exact-byte reconstruction, immutable records and alias history, and mechanically gated aliases merged in PR #20. Its tests use synthetic files and metadata only.
- a fail-closed reference-source evidence gate merged in PR #21. Its tests validate refusal/identity mechanics only; no real source passes and no source artifact is invented.
- source-gate v1.1 paid-entitlement binding: authorized paid access cannot pass without the SHA-256 identity of a retained confidential contract artifact. This strengthens evidence identity but does not approve a licence.
- required quality/security CI merged in PR #23, plus a local-only Web UI boundary with strict market-input refusal and 37 route-level regressions. These are security and integrity mechanics; interactive UI predictions are not benchmark evidence.

Engineering completion must not be reported as financial validation.

## What remains untested

- zero-shot performance against identical-information baselines;
- expanding and rolling walk-forward performance;
- final untouched holdout behavior;
- probabilistic calibration, CRPS, interval coverage, and downside-tail recall;
- cross-sectional IC, RankIC, ICIR, and quantile spread;
- stability across instruments, sectors, volatility states, and market regimes;
- survivorship and delisting effects;
- causal corporate-action adjustment policy;
- conservative spread, commission, slippage, liquidity, turnover, and market-impact sensitivity;
- bootstrap uncertainty and parameter perturbation;
- whether Kronos adds information beyond price persistence, smoothing, momentum, or mean reversion;
- independently attested launcher capture and any real registered experiment/model lineage;
- any paper-trading portfolio, risk, execution, or monitoring control.

## Known data limitations

- A canonical bar schema and manifest implementation exists, but no real benchmark dataset has yet been ingested and approved through it. Norgate US Stocks Platinum is the preferred conditional technical candidate; its standard EULA is rejected because use/retention terms conflict with durable evidence, and no custom agreement, payment, bytes, or gate result exists.
- Built-in exchange calendars deliberately lack authoritative holiday histories; a selected source must supply one for evidence-grade validation.
- No raw-data hash register, universe-history record, or real adjustment-policy artifact exists for a benchmark dataset.
- The example Qlib universe is `csi300`, but membership history and survivorship treatment are not captured.
- Default Qlib train/validation/test ranges materially overlap. The current split cannot be treated as independent evidence.
- The bundled checkpoint-regression CSV is a software fixture, not a declared reference benchmark dataset.
- Provider/product priority is decided, but licensing, permitted publication, indefinite retention, revision capture, corporate-action availability, constituent availability, and acquisition-host transfer remain unresolved contract/evidence gates.

## Checkpoint provenance

Exact checkpoint revisions are pinned in `tests/test_kronos_regression.py`. Unknowns remain:

- the full training-data manifest and point-in-time universe used for released checkpoints;
- whether checkpoint preprocessing predates later normalization corrections;
- whether training inputs contain data that would overlap a proposed benchmark universe or period;
- the released checkpoints' adjustment and corporate-action policies.

Until resolved, benchmark reports must state this uncertainty and avoid claims of fully independent evaluation where pretraining overlap is possible.

## Confidence assessment

| Claim | Confidence | Basis |
|---|---|---|
| Covered software hardening behaves as tested | High | Green cross-version and package workflows |
| Pinned checkpoint loads and matches committed fixture | High | Green checkpoint regression workflow |
| Archive outputs are deterministic and failure-atomic for covered cases | High | PR #11 tests and CI |
| Current demo split is suitable for model selection | Very low / rejected | Material date overlap |
| Kronos improves forecasts over naive baselines | Unknown | No comparable walk-forward benchmark |
| Kronos remains profitable after realistic costs | Unknown | No evidence-grade costed strategy evaluation |
| System is ready for production or live trading | None | Required data, evaluation, risk, execution, and monitoring controls absent |

## Promotion gate

Permitted next classification is not automatically “direct forecaster.” After the benchmark, the evidence must select one of:

- APPROVED AS DIRECT FORECASTER;
- APPROVED AS FEATURE GENERATOR;
- APPROVED FOR LIMITED REGIMES/HORIZONS;
- RESEARCH ONLY;
- REJECTED.

No classification above `RESEARCH ONLY` is currently supported.
