# Adversarial review — Phase 5C metrics, costs, and aggregation

Date: 2026-07-22  
Scope: `evaluation/metrics-and-costs`

## Decision

The scoring, paper-cost, and fold-aggregation contracts are suitable for integration
after cross-version and package gates pass. They do not constitute an evaluation run.
Kronos remains `RESEARCH ONLY`.

## How this could produce false confidence

### Metrics can be chosen after observing results

Severity: critical. A model can look favorable on one horizon, regime, error measure,
direction threshold, interval, or ranking statistic while failing elsewhere.

Control: configuration and normalized inputs are hashed; all required views are
returned together. The run configuration must pre-register primary metrics and retain
unfavorable outputs. The result carries an explicit multiple-comparison warning.

### MASE can leak through its scale denominator

Severity: critical. A denominator calculated with validation, test, or final values
can leak both volatility and future level information.

Control: the scorer requires a positive row-level scale but cannot prove its origin.
The runner must derive it from training-only history and bind its provenance to the
passed fold audit. Until then, MASE is engineered but not causally validated.

### Regime labels can be hindsight labels

Severity: critical. Full-period drawdowns, realized future volatility, or revised
macro series can create apparently useful “limited regime” conclusions.

Control: regime labels are mandatory but their causality belongs to the dataset/audit
adapter. Any label unavailable at prediction time must invalidate the experiment.

### Quantile and probability outputs may not be calibrated

Severity: high. Brier, coverage, quantile loss, CRPS, and reliability curves describe
the supplied distribution; they do not make token-sample frequencies probabilities.
Conditioning on valid/repaired candles can further bias them.

Control: absent samples produce no CRPS. Benchmark reports must separate raw,
validated, and projected distributions, invalid/repair rates, and calibration by
fold/regime. Deterministic baselines remain explicitly degenerate.

### Cross-sectional metrics can be dominated by ties or small universes

Severity: high. Sparse cross-sections, repeated prices, sector clusters, or one period
can inflate IC and quantile spreads.

Control: a declared minimum cross-section is enforced; constant cross-sections are
omitted rather than scored as zero; every included period is retained. Reports must
show counts, sector neutrality sensitivity, and dependence-aware cautions.

### Cost assumptions can be understated

Severity: critical. Fixed spreads, zero rejected orders, unlimited liquidity, or low
impact can turn turnover into fictitious profit.

Control: commission, half spread, slippage, participation impact, notional, and a hard
participation ceiling are identity-bound. The module refuses over-limit trades and
supports unchanged-path scenario sensitivity. These are still assumptions, not fills.

### Missing instruments can hide exits and turnover

Severity: critical. Dropping an instrument after a sell or delisting can omit the
closing trade, loss, and liquidity cost.

Control: every rebalance requires the same complete instrument set and explicit zero
targets. The real adapter must additionally retain delistings and terminal outcomes.

### Sharpe-like statistics can be overstated

Severity: high. Naive annualization ignores autocorrelation, fat tails, overlapping
horizons, data mining, and changing exposure.

Control: the output is named `sharpe_like` and carries an explicit warning. Promotion
requires drawdown, turnover, concentration, regime/fold results, confidence intervals,
and cost sensitivity rather than one annualized ratio.

### Bootstrap intervals can imply independence that does not exist

Severity: high. Resampling a small set of folds does not remove shared market regimes,
overlapping training histories, or cross-asset dependence.

Control: paired folds are resampled with fixed local seeds and reported with a
dependence warning. Final values are never pooled into development intervals. A later
benchmark may require block/bootstrap variants justified by its sampling design.

### A “best baseline” can be selected using the final holdout

Severity: critical. Choosing the comparator after final results destroys confirmation.

Control: aggregation requires one named reference baseline and performs no selection.
Its provenance must show that selection used training/validation/calibration only.

## Regression evidence

Tests cover exact point/direction/ranking values, empirical CRPS, quantile loss,
coverage, overall/regime calibration, deterministic input identity, invalid/crossed
distributions, causal paper timestamps, complete universes, cost components, turnover,
liquidity refusal, cost sensitivity, exposure summaries, complete paired grids, metric
direction, deterministic bootstrap isolation, and final-holdout exclusion.

No real dataset, forecast, fold audit, portfolio, cost estimate, confidence interval,
or benchmark conclusion has been produced.

## Checkpoint compatibility

No model, tokenizer, predictor, sampling, inference tensor, or checkpoint changes.
Released checkpoint behavior is unaffected.

## Promotion blockers

- Build the audit-gated common fold runner and immutable result writer.
- Prove training-only MASE scale and causal regime-label provenance.
- Add point-in-time factor exposure only with an approved source.
- Select, manifest, and audit the reference data and universe.
- Register every development fold before opening the fixed final holdout.
- Run the released-checkpoint zero-shot benchmark and cost perturbations.

Passing Phase 5C permits runner/registry integration only. It does not permit
fine-tuning, paper portfolio construction, live trading, or financial claims.
