# Adversarial review — Phase 4 probabilistic forecast API

Date: 2026-07-22  
Scope: `inference/probabilistic-forecast-api`

## Decision

The typed API is suitable for evaluation integration after offline, package, and
released-checkpoint regression gates pass. It exposes evidence that the legacy API
discarded, but it does not show that Kronos uncertainty is calibrated or financially
useful. Model classification remains `RESEARCH ONLY`.

## How this could produce false confidence

### Sample frequencies are not calibrated probabilities

Severity: critical for probabilistic claims. Temperature, top-k, and top-p define a
token sampling procedure. A frequency such as `probability_positive_return=0.7`
does not mean a 70% empirical success rate until walk-forward calibration supports
that interpretation.

Control: the API calls the value a sampled probability and preserves all generation
controls. Promotion requires interval coverage, quantile loss, calibration curves,
and a proper scoring rule on untouched observations.

### Excluding invalid paths can bias summaries

Severity: high. Invalid volume or candle geometry may be associated with price paths.
Conditioning summaries on valid paths can alter mean, quantiles, and return signs.

Control: the result exposes generated count, summary count, raw/output validity,
`summary_source`, issues, and warnings. Evaluation must report invalid rates and run
sensitivity with no projection and the explicit projection policy.

### Projection can conceal model failure

Severity: high. Mechanically fixing high/low or flooring volume can make output look
financially plausible without improving model quality.

Control: raw arrays are immutable copies, projection is opt-in, every changed cell is
recorded, and non-finite/non-positive prices are never projected. Repair rate is a
model-quality metric and a promotion input.

### Reproducible sampling is not cross-platform numerical equivalence

Severity: medium. An isolated seed reproduces the tested device/runtime path, but
PyTorch kernels and hardware can differ. Greedy generation avoids sampling variance
but is not a probabilistic forecast.

Control: results record seed, the complete pre-generation generator state and hash,
deterministic mode, code, and checkpoint identity fields. The experiment registry
must additionally capture hardware and library versions.

### Provenance identity is caller supplied

Severity: high. `model_revision`, `dataset_version`, and `code_commit` can be left
`Unknown` or supplied incorrectly.

Control: Unknown values generate warnings. The evaluation and registry layers must
derive and verify these values rather than accepting manual labels.

### Timestamp checks do not prove exchange-calendar validity

Severity: high. Monotonic, timezone-consistent timestamps can still include holidays,
missing sessions, or invalid bar cutoffs.

Control: the forecast API validates local sequence consistency only. Evidence-grade
runs must use a canonical dataset that passed calendar, stale-data, gap, adjustment,
and leakage audits.

### Legacy wrappers still average samples

Severity: medium. Existing callers receive the historical mean-only DataFrame and can
ignore validity evidence.

Control: backward compatibility is intentionally retained. New evaluation code must
use `forecast`, and direct model-to-order paths remain prohibited.

## Regression evidence

The focused tests cover:

- every sampled path and separate mean/median/quantiles;
- horizon return distributions, sampled positive-return probability, and lower tail;
- explicit seeded and greedy reproducibility;
- generator validation and isolation from global RNG;
- timestamp length/order/timezone/frequency and context checks;
- NaN, infinity, OHLC, volume, and amount input rejection;
- invalid raw-path preservation with zero silent repairs;
- cell-level explicit projection and repair accounting;
- no projection of non-finite outputs;
- optional omission of bulky paths without losing summaries; and
- equality of the legacy mean to the mean of raw paths for identical random state.

Local evidence before the pull request: 170 offline tests passed on Python 3.12.
GitHub Actions supplies the required Python 3.10/3.12, wheel, and pinned-checkpoint
evidence.

## Checkpoint compatibility

No model/tokenizer layer, parameter shape, state key, or architecture changes. The
legacy inference default remains mean-over-samples, with `generator=None` preserving
the existing PyTorch random stream. The path-return mode and generator are appended
optional controls. Compatibility is still classified Unknown until the path-triggered
released-checkpoint workflow passes on this change.

## Security and integrity

The API loads no files, deserializes no external objects, contacts no service, and
creates no orders. A supplied `torch.Generator` is used in-process. Results are
research objects and not an execution instruction.

## Promotion blockers

- Pass the pinned released-checkpoint numerical regression.
- Bind provenance fields from the experiment registry rather than manual input.
- Attach a passed leakage audit to every evaluation fold.
- Measure invalid/repair rate and probabilistic calibration out of sample.
- Compare against identical-information baselines on the untouched holdout.

Passing Phase 4 permits walk-forward integration only. It does not permit
fine-tuning promotion, paper portfolio construction, or financial claims.
