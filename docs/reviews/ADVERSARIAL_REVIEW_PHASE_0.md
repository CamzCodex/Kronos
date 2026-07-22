# Adversarial review — Phase 0 repository reconciliation

Date: 2026-07-22  
Evidence baseline: `master` at `c94cf3be1af5f57849e67defeb25c82ddd93815d`

## Decision

The repository is substantially hardened as software but cannot yet generate a trustworthy answer about forecast or trading value. Classification remains **RESEARCH ONLY**.

## How could the current repository produce false confidence?

1. Green unit and package tests may be misreported as evidence that the model forecasts markets well.
2. The Qlib demo date ranges overlap across train/validation and validation/test far beyond a lookback buffer.
3. The top-K backtest can produce attractive output without mandatory naive baselines, untouched holdout, survivorship evidence, or conservative cost sensitivity.
4. Mean aggregation of stochastic forecast paths discards uncertainty and prevents calibration assessment.
5. Released-checkpoint numerical compatibility can be mistaken for independent checkpoint efficacy.
6. A fixed `csi300` label without point-in-time membership evidence can conceal survivorship or universe-selection effects.
7. Path-filtered CI leaves lint, typing, dependency, secret, leakage, and evaluation controls unenforced.

## Could the code pass tests while being financially invalid?

Yes. Existing tests cover selected mechanics and storage behavior. They do not prove fair baseline comparison, causal corporate-action handling, point-in-time feature availability, realistic execution, or holdout independence.

## Are transaction costs understated?

Unknown. The demo includes configured open/close costs and delayed execution, but there is no spread/slippage/liquidity sensitivity, cost provenance, or comparison across conservative scenarios. No current economic claim should rely on it.

## Is the final holdout untouched?

No final untouched holdout is implemented. The default validation and test ranges overlap for three months, and hyperparameter/model-selection access is not governed by an evaluator.

## Are results dominated by one period, seed, instrument, or regime?

Unknown because no registered walk-forward experiment exists. The current repository cannot answer this question.

## Does Kronos add information beyond naive alternatives?

Unknown. Mandatory last-value, drift, seasonal, smoothing, momentum, mean-reversion, linear, tree, ARIMA-style, and volatility baselines have not been evaluated on identical folds.

## Blocking findings

- Critical: `GAP-001` overlapping demo splits.
- Critical: `GAP-002` no canonical dataset contract/identity.
- Critical: `GAP-003` no reusable leakage auditor.
- Critical: `GAP-005` no walk-forward baseline engine.
- Critical: `GAP-006` no zero-shot reference benchmark.

These findings block fine-tuning promotion, paper-portfolio construction, and any claim of economic usefulness.

## Required next review

Repeat adversarial review after the canonical market-data contract and again after the leakage auditor. The benchmark review must explicitly test whether generated-candle projection masks failure, whether results concentrate in one fold/regime, and whether the best naive baseline produces substantially the same portfolio.
