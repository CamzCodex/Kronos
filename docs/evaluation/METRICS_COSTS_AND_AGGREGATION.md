# Metrics, costs, and fold aggregation

Status: reference evaluation contracts; no market-performance result

## Forecast scoring contract

`ForecastMetricRequest` accepts one normalized observation row per
instrument/target timestamp/horizon. Every row binds:

- reference, realized, and point-forecast values;
- a timezone-aware as-of timestamp strictly before the target timestamp;
- a strictly positive training-derived scale error;
- positive-return probability;
- ordered quantile forecasts;
- market and volatility regime labels; and
- model, dataset, fold, and code identity.

Optional empirical sample forecasts enable CRPS. Without samples, CRPS is explicitly
`None`; quantile loss and Brier score remain proper-score references. The scorer
reports MAE, RMSE, MASE, direction precision/recall, interval coverage, calibration,
downside-tail recall, IC, RankIC, ICIR, and top-minus-bottom spread. Point/direction
errors are also grouped by horizon, instrument, market regime, and volatility regime.
Calibration curves are reported overall and separately by both regime labels.

The observation hash binds normalized values after deterministic sorting. The
configuration hash separately binds quantile interpretation, calibration bins,
cross-sectional minimum, quantile fraction, tail threshold, and sample availability.

## Paper-return cost contract

`CostEvaluationRequest` consumes externally produced target weights. It never creates
a signal, approves risk, creates an order, or contacts a broker. Each row must declare
a decision timestamp strictly before its realized-return timestamp. Every rebalance
must contain the same complete universe, including explicit zero targets, so omitted
positions cannot evade turnover.

The one-way paper cost is:

`abs(delta_weight) * (commission + half spread + slippage + impact) / 10,000`

where impact in basis points is the declared coefficient multiplied by participation
raised to the declared exponent. Participation is trade notional divided by a
causally available dollar-volume capacity estimate whose as-of timestamp cannot be
later than the decision. A trade above the declared participation ceiling invalidates
the evaluation; it is not silently filled or clipped.

Outputs include trade and period ledgers, gross/net compounded returns, turnover,
cost components, drawdown, annualized volatility, a cautiously labelled Sharpe-like
statistic, gross/net/position/concentration exposure, liquidity participation, and
sector exposure when labels are supplied. Cost-scenario evaluation reuses exactly one
decision identity.

## Fold aggregation contract

`FoldAggregationRequest` requires a complete model/fold/metric grid and one
predeclared reference baseline. It never chooses the best baseline after seeing the
scores. Metrics declare whether higher or lower is better; signed improvement is
positive only when the candidate improves on the reference.

The fixed final-holdout fold, when supplied, is removed before development means,
fold-win counts, and paired bootstrap intervals are calculated. Its values are
reported separately. Bootstrap randomness is locally seeded per metric/model so
global RNG state and unrelated added models cannot alter an existing comparison.

## Interpretation boundaries

- Bootstrap intervals resample folds; they do not remove serial or cross-sectional
  market dependence.
- A majority of positive folds is necessary but not sufficient for promotion.
- Multiple metrics, models, horizons, regimes, seeds, and perturbations require an
  explicit multiplicity warning.
- Cost parameters are scenarios, not observed execution evidence.
- MASE scale errors must be computed from training-only history by the future runner.
- Regime labels must be assigned causally by the future data/evaluation adapter.
- Factor exposure is not inferred without an approved point-in-time factor dataset.
- Passing these unit tests creates no forecast, economic, or promotion result.

The common runner must still connect passed fold audits, Kronos/baseline outputs,
targets, causal regimes, costs, immutable artifacts, and the experiment registry.
