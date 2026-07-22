# Adversarial review — Phase 5B mandatory baseline suite

Date: 2026-07-22  
Scope: `evaluation/baseline-suite`

## Decision

The eleven v1 baseline implementations are suitable inputs to a common evaluation
runner after cross-version and package gates pass. They establish comparison methods,
not a result. Kronos remains `RESEARCH ONLY`.

## How this could produce false confidence

### Hyperparameter tuning can favor Kronos or a chosen baseline

Severity: critical. Seasonal period, lookbacks, smoothing, reversion strength, tree
depth, AR order, volatility decay, and sampling count can all be searched after
seeing test performance.

Control: every control is validated and hashed. The runner must log selection events,
freeze them before test/final use, report sensitivity, and compare against the best
required naive baseline.

### Passing the same frame does not mean equal model capacity

Severity: high. Kronos can use OHLCVA jointly while most simple baselines deliberately
use close only. An apparent improvement may reflect richer feature use rather than a
superior representation.

Control: the information hash binds the same full frame and prevents future-data
advantage. Reports must disclose per-method feature use and later include
feature-matched linear/tree comparators before claiming representation lift.

### Deterministic paths are not probabilistic forecasts

Severity: critical for calibration claims. Ten methods have one degenerate path, so
sample frequencies of zero or one have no probability interpretation.

Control: results label deterministic mode and warn explicitly. Probabilistic scoring
must distinguish point baselines from sampled distributions and include suitable
proper-score references.

### The volatility baseline's Monte Carlo distribution is assumed, not learned

Severity: high. Lognormal zero-arithmetic-drift paths with EWMA variance can be badly
misspecified under jumps, leverage effects, autocorrelation, or changing regimes.

Control: method, decay, seed, and sample count are hashed. Calibration/coverage and
regime breakdowns are required; its paths must not be described as true probabilities.

### Recursive tree and AR forecasts can compound errors

Severity: high. One-step relations are fed their own predictions. A tree can overfit
small histories; an AR recursion can become unstable.

Control: the tree is depth/min-leaf limited and deterministic. AR fitting uses a small
declared ridge penalty and training-range innovation bounds. Both require lookback,
depth/order, and perturbation sensitivity; failure must invalidate the fold rather
than silently removing the method.

### Adjustment errors can dominate every price baseline

Severity: critical. Splits, dividends, inconsistent adjusted/raw prices, stale bars,
or future-known adjustment factors can make naive forecasts appear arbitrarily good
or bad.

Control: the suite validates candle mechanics but relies on the canonical dataset and
leakage audit for adjustment causality. No real result is permitted without them.

### One baseline family can be systematically mismatched to the target

Severity: medium. Daily price-level accuracy, return direction, cross-sectional rank,
and portfolio utility are different objectives. A baseline can look weak on one and
strong on another.

Control: the future metric layer must report all required point, direction, ranking,
probabilistic, regime, and economic views without selecting the favorable one.

### Implementation correctness is not competitiveness

Severity: high. Exact formula tests and finite outputs only prove the references behave
as declared. They do not show these are the strongest conventional models for a real
universe.

Control: report limitations, add feature-matched/statistical comparators when justified,
and never equate beating a weak baseline with useful alpha.

## Regression evidence

Tests cover:

- all eleven mandatory names and output shapes;
- one shared full-OHLCVA information hash;
- exact last-value, seasonal, drift, and log-linear definitions;
- deterministic degenerate-distribution labels;
- seeded volatility repeatability independent of NumPy/PyTorch global RNG;
- return anchoring to the last observed close;
- non-mutation and immutable sample arrays;
- future timestamps without future target values;
- information/configuration identity sensitivity;
- all-or-nothing history sufficiency;
- timestamp, OHLCVA, and control rejection;
- explicit AR stability after endpoint perturbation; and
- quantile ordering for sampled volatility paths.

No real dataset, fold, target, metric, cost, or comparison has been evaluated.

## Checkpoint compatibility

No model, tokenizer, predictor, sampling, inference, tensor, or checkpoint changes.
Baselines are dependency-light NumPy/Pandas code in `kronos_eval`. Released checkpoint
behavior is unaffected.

## Security and operations

The suite processes in-memory frames and writes nothing. It contacts no service,
loads no unsafe object, and creates no trading instruction. Monte Carlo uses a local
NumPy generator. Trading remains paper/simulation only.

## Promotion blockers

- Build the common metric, cost, robustness, and aggregation runner.
- Add feature-matched conventional comparators or qualify representation claims.
- Select an approved point-in-time dataset and generate passed fold audits.
- Freeze baseline/Kronos controls without test/final access.
- Run and register every fold plus one final evaluation.

Passing Phase 5B permits metric-runner integration only. It does not permit
fine-tuning, paper portfolio construction, or financial claims.
