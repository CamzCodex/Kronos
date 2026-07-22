# Mandatory forecasting baseline suite

Status: reference forecast implementations; no market-performance result

## Fair information contract

Every baseline receives one `BaselineRequest` containing the exact OHLCVA history,
historical timestamps, future timestamps, horizon, dataset/fold/code identity, and
frozen configuration. The suite validates all six feature columns and hashes every
value and timestamp into one `information_set_hash` shared by all results.

Most classical baselines intentionally use close prices only. Receiving and hashing
the full frame proves that no baseline had later or different observations; it does
not imply each algorithm uses every field. Feature-based conventional comparators
may be added later under a new version, but required v1 methods cannot be silently
changed during an experiment.

The suite refuses partial execution. The common history must be long enough for the
most demanding mandatory method, or no result is returned.

## Required baselines

| Name | Definition |
|---|---|
| `last_value` | Repeats the final observed close. |
| `drift` | Extrapolates average endpoint-to-endpoint log-price drift. |
| `seasonal_naive` | Repeats the last declared seasonal cycle. |
| `rolling_mean` | Repeats the mean close over the declared rolling window. |
| `exponential_smoothing` | Simple exponential-smoothed level with frozen alpha. |
| `momentum` | Compounds the mean recent log return over the horizon. |
| `mean_reversion` | Geometrically closes the gap to a recent mean at a frozen strength. |
| `linear_regression` | Extrapolates OLS log price against time over a frozen lookback. |
| `simple_tree` | Dependency-free deterministic depth-limited regression tree on causal close-derived return, momentum, volatility, and level-gap features. |
| `arima_style` | Ridge-stabilized AR(p) on differenced log prices, equivalent to an ARIMA(p,1,0)-style reference without MA terms. Recursive innovations are explicitly constrained to the observed training-return range. |
| `volatility` | Seeded lognormal paths with zero arithmetic drift and causally estimated EWMA log-return variance. |

The AR innovation bound is a declared stability rule, not an invisible output repair.
Its observed lower/upper values and ridge penalty are included in the result
configuration hash.

## Output contract

Every `BaselineResult` records:

- suite/method version and configuration hash;
- dataset, fold, code, instrument, as-of and future timestamps;
- shared information-set hash;
- immutable sample and return paths;
- mean, median, configured quantiles;
- sampled positive-return frequency and lower-tail return;
- expected per-step log-return volatility; and
- deterministic/stochastic mode, seed where used, and warnings.

The ten deterministic baselines expose a one-path degenerate distribution. Their
positive-return “probability” is necessarily zero or one and is explicitly not a
calibrated probability. Only the volatility baseline uses Monte Carlo samples, and
its frequencies also require out-of-sample calibration.

## Required evaluation use

The later runner must:

- call every baseline and Kronos at the same fold prediction time;
- freeze hyperparameters using training/validation/calibration only;
- compare Kronos with the best required naive baseline, not just their average;
- persist failures instead of dropping a baseline or fold;
- record all method configurations and information hashes;
- score identical target timestamps;
- apply costs downstream of forecast generation; and
- preserve fold-by-fold and final-holdout separation.

This phase implements forecasts only. It does not calculate MAE, calibration,
RankIC, portfolio returns, costs, confidence intervals, or a promotion decision.
