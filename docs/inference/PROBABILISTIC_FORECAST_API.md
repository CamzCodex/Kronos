# Probabilistic forecast API

Status: research interface; no broker execution

## Purpose

`ForecastRequest` and `ForecastResult` expose the sampled paths that the legacy
`KronosPredictor.predict` method averages internally. The interface preserves raw
model outputs, separates validation from optional projection, and records enough
randomness and model identity to reproduce an inference call when the referenced
checkpoint, data, code, and hardware are available.

This API does not establish that sample frequencies are calibrated probabilities.
Calibration must be measured out of sample by the walk-forward engine.

## Minimal usage

```python
from model import ForecastRequest, KronosPredictor

predictor = KronosPredictor(
    model,
    tokenizer,
    device="cpu",
    model_version="NeoQuasar/Kronos-small",
    model_revision="901c26c1332695a2a8f243eb2f37243a37bea320",
    tokenizer_revision="0e0117387f39004a9016484a186a908917e22426",
    code_commit="<40-character Git commit>",
)

request = ForecastRequest(
    instrument_id="EXAMPLE",
    history=history[["open", "high", "low", "close", "volume", "amount"]],
    historical_timestamps=historical_timestamps,
    future_timestamps=future_timestamps,
    horizon=5,
    sample_count=100,
    seed=7,
    deterministic=False,
    quantiles=(0.05, 0.25, 0.5, 0.75, 0.95),
    projection_policy="none",
    dataset_version="<dataset_id>",
)

result = predictor.forecast(request)
```

Stochastic requests require an explicit `seed` or a device-compatible
`torch.Generator`. A seed creates an isolated generator; the result does not depend
on the ambient PyTorch random-number state. `deterministic=True` selects tokens
greedily and requires `sample_count=1`. The pre-generation state of either an
internally created or caller-supplied generator is captured in `generator_state`
with `generator_state_sha256`, so an already-advanced generator can be reconstructed
rather than misrepresented by its initial seed alone.

## Input contract

The typed API rejects a request when:

- any required OHLCVA column is absent, non-numeric, NaN, or infinite;
- historical prices are non-positive;
- historical high/low relationships are invalid;
- historical volume or amount is negative;
- timestamp lengths do not match the data and horizon;
- timestamps are duplicated, not strictly increasing, timezone-inconsistent, or
  place a future observation at or before the as-of time;
- inferred history and future frequencies conflict;
- a declared expected frequency conflicts with an inferred frequency;
- history exceeds the predictor context instead of silently truncating;
- stochastic generation lacks isolated randomness; or
- quantiles, temperature, top-k, top-p, or projection controls are invalid.

Exchange-session and holiday correctness remain the responsibility of the canonical
data contract. Short horizons may be too small for frequency inference; the result
warns rather than pretending calendar alignment was proven.

## Raw, validated, and projected paths

The result distinguishes:

- `raw_sample_paths`: every unmodified decoded path when requested;
- `validated_sample_paths`: paths that pass all post-policy candle checks;
- `projected_sample_paths`: post-policy paths, present only when explicit projection
  was requested;
- `validity_report`: per-path raw/output issues and every cell-level repair;
- `repair_rules` and `repair_count`: exact projection accounting; and
- `summary_source`: `valid_raw_paths`, `explicitly_projected_valid_paths`, or
  `no_valid_paths`.

The default `projection_policy="none"` performs no repair. Invalid paths remain in
the raw output and are excluded from summaries. If every path is invalid, the path
statistics are NaN and the result reports zero summary samples.

`ohlcv_v1` is an opt-in mechanical projection. It only:

- raises high to `max(high, open, close)`;
- lowers low to `min(low, open, close)`;
- floors volume at zero; and
- floors amount at zero.

It does not repair non-finite or non-positive prices. Projection is not evidence
that the model generated a valid candle; raw validity and repair rate must be
reported separately.

## Probabilistic summaries

The interface returns mean and median paths separately, configurable path quantiles,
close-return samples for every forecast step relative to the last observed close,
probability of positive return, and a configurable downside-tail return quantile.

All summaries are conditional on `summary_source`. An evaluator must report:

- generated and summary sample counts;
- raw and post-policy invalid-path rates;
- repair count and rules;
- the projection policy; and
- calibration against realised observations.

Ignoring invalid paths or repairs can create selection bias and false confidence.

## Compatibility

`KronosPredictor.predict`, `predict_batch`, and `generate` retain their legacy return
types and mean-over-samples behavior. `auto_regressive_inference` returns the same
mean by default and exposes unaggregated paths only with `return_samples=True`.
No tokenizer, model layer, tensor parameter, or checkpoint key is changed.

The checkpoint regression workflow remains the authoritative numerical compatibility
gate for the pinned released model and tokenizer revisions.
