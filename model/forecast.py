"""Typed probabilistic forecasting and explicit generated-candle validation.

This module deliberately separates raw model generation from candle projection
and statistical summaries.  Raw samples are never overwritten.  Projection is
only performed when a request names a supported policy, and every changed cell
is recorded in the result.
"""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass, field
from numbers import Integral, Real
from typing import TYPE_CHECKING, Literal

import numpy as np
import pandas as pd
import torch

if TYPE_CHECKING:
    from model.kronos import KronosPredictor


FEATURE_COLUMNS = ("open", "high", "low", "close", "volume", "amount")
PRICE_COLUMNS = ("open", "high", "low", "close")
PROJECTION_POLICIES = ("none", "ohlcv_v1")


class ForecastRequestError(ValueError):
    """Raised when a forecast request violates the public input contract."""


@dataclass(frozen=True)
class ForecastRequest:
    """All inputs and stochastic controls required for one forecast."""

    instrument_id: str
    history: pd.DataFrame = field(repr=False, compare=False)
    historical_timestamps: object = field(repr=False, compare=False)
    future_timestamps: object = field(repr=False, compare=False)
    horizon: int
    sample_count: int = 20
    temperature: float = 1.0
    top_k: int | None = 0
    top_p: float | None = 0.9
    seed: int | None = 0
    deterministic: bool = False
    generator: torch.Generator | None = field(default=None, repr=False, compare=False)
    quantiles: tuple[float, ...] = (0.05, 0.5, 0.95)
    lower_tail_quantile: float = 0.05
    projection_policy: Literal["none", "ohlcv_v1"] = "none"
    return_sample_paths: bool = True
    expected_frequency: str | None = None
    dataset_version: str = "Unknown"
    verbose: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.instrument_id, str) or not self.instrument_id.strip():
            raise ForecastRequestError("instrument_id must be a non-empty string")
        _positive_integer(self.horizon, "horizon")
        _positive_integer(self.sample_count, "sample_count")
        if not isinstance(self.deterministic, bool):
            raise ForecastRequestError("deterministic must be a boolean")
        if self.deterministic and self.sample_count != 1:
            raise ForecastRequestError("deterministic generation requires sample_count=1")
        if self.generator is not None and not isinstance(self.generator, torch.Generator):
            raise ForecastRequestError("generator must be a torch.Generator or None")
        if self.generator is not None and self.seed is not None:
            raise ForecastRequestError("seed and generator are mutually exclusive")
        if not self.deterministic and self.seed is None and self.generator is None:
            raise ForecastRequestError(
                "stochastic generation requires an explicit seed or torch.Generator"
            )
        if self.seed is not None:
            if isinstance(self.seed, bool) or not isinstance(self.seed, Integral):
                raise ForecastRequestError("seed must be an integer or None")
            if not 0 <= int(self.seed) < 2**63:
                raise ForecastRequestError("seed must be between 0 and 2**63 - 1")
        _positive_real(self.temperature, "temperature")
        if self.top_k is not None:
            if isinstance(self.top_k, bool) or not isinstance(self.top_k, Integral):
                raise ForecastRequestError("top_k must be an integer or None")
            if int(self.top_k) < 0:
                raise ForecastRequestError("top_k must be greater than or equal to 0")
        if self.top_p is not None:
            _bounded_probability(self.top_p, "top_p", inclusive_zero=True)
        if not isinstance(self.return_sample_paths, bool):
            raise ForecastRequestError("return_sample_paths must be a boolean")
        if not isinstance(self.verbose, bool):
            raise ForecastRequestError("verbose must be a boolean")
        if self.projection_policy not in PROJECTION_POLICIES:
            raise ForecastRequestError(
                f"projection_policy must be one of {PROJECTION_POLICIES}"
            )
        if not self.quantiles:
            raise ForecastRequestError("quantiles must contain at least one probability")
        normalized_quantiles = tuple(float(value) for value in self.quantiles)
        for value in normalized_quantiles:
            _bounded_probability(value, "quantile", inclusive_zero=True)
        if len(set(normalized_quantiles)) != len(normalized_quantiles):
            raise ForecastRequestError("quantiles must not contain duplicates")
        object.__setattr__(self, "quantiles", tuple(sorted(normalized_quantiles)))
        _bounded_probability(
            self.lower_tail_quantile,
            "lower_tail_quantile",
            inclusive_zero=True,
        )
        if not isinstance(self.dataset_version, str) or not self.dataset_version.strip():
            raise ForecastRequestError("dataset_version must be a non-empty string")
        if self.expected_frequency is not None:
            if not isinstance(self.expected_frequency, str) or not self.expected_frequency.strip():
                raise ForecastRequestError(
                    "expected_frequency must be a non-empty string or None"
                )
            try:
                pd.tseries.frequencies.to_offset(self.expected_frequency)
            except ValueError as exc:
                raise ForecastRequestError("expected_frequency is not a valid offset") from exc


@dataclass(frozen=True)
class CandleIssue:
    """One generated-candle validity failure."""

    sample_index: int
    horizon_index: int
    code: str
    field: str
    message: str


@dataclass(frozen=True)
class CandleRepair:
    """One explicit projection operation applied to a generated cell."""

    sample_index: int
    horizon_index: int
    field: str
    rule: str
    before: float
    after: float


@dataclass(frozen=True)
class SamplePathValidity:
    """Raw and post-policy validity for one sampled path."""

    sample_index: int
    raw_valid: bool
    output_valid: bool
    raw_issues: tuple[CandleIssue, ...]
    output_issues: tuple[CandleIssue, ...]
    repairs: tuple[CandleRepair, ...]


@dataclass(frozen=True)
class ForecastValidityReport:
    """Aggregate generated-candle validation and projection evidence."""

    passed: bool
    raw_passed: bool
    total_sample_count: int
    raw_valid_sample_count: int
    output_valid_sample_count: int
    projection_policy: str
    paths: tuple[SamplePathValidity, ...]


@dataclass(frozen=True)
class ForecastResult:
    """Probabilistic forecast, provenance, samples, and validity accounting."""

    instrument_id: str
    as_of_timestamp: pd.Timestamp
    future_timestamps: pd.DatetimeIndex
    model_version: str
    model_revision: str
    tokenizer_revision: str
    dataset_version: str
    code_commit: str
    raw_sample_paths: np.ndarray | None
    validated_sample_paths: np.ndarray | None
    projected_sample_paths: np.ndarray | None
    mean_path: pd.DataFrame
    median_path: pd.DataFrame
    quantiles: dict[float, pd.DataFrame]
    return_samples: np.ndarray
    probability_positive_return: pd.Series
    lower_tail_return: pd.Series
    lower_tail_quantile: float
    validity_report: ForecastValidityReport
    repair_rules: tuple[str, ...]
    repair_count: int
    warnings: tuple[str, ...]
    seed: int | None
    generator_state: bytes | None = field(repr=False)
    generator_state_sha256: str | None
    deterministic: bool
    generated_sample_count: int
    summary_sample_count: int
    summary_source: str


def forecast_with_predictor(
    predictor: KronosPredictor,
    request: ForecastRequest,
) -> ForecastResult:
    """Validate, generate, validate paths, and summarize a typed request."""

    if not isinstance(request, ForecastRequest):
        raise TypeError("request must be a ForecastRequest")

    history, historical_index, future_index, warnings = _validate_request_data(
        request,
        max_context=predictor.max_context,
    )
    generator, recorded_seed, generator_state = _resolve_generator(
        predictor.device,
        request,
    )

    values = history.loc[:, FEATURE_COLUMNS].to_numpy(dtype=np.float32, copy=True)
    mean = np.mean(values, axis=0)
    std = np.std(values, axis=0)
    normalized = np.clip((values - mean) / (std + 1e-5), -predictor.clip, predictor.clip)

    historical_stamp = _time_features(historical_index)
    future_stamp = _time_features(future_index)
    raw_normalized = predictor.generate_sample_paths(
        normalized[np.newaxis, :],
        historical_stamp[np.newaxis, :],
        future_stamp[np.newaxis, :],
        request.horizon,
        request.temperature,
        request.top_k,
        request.top_p,
        request.sample_count,
        request.verbose,
        deterministic=request.deterministic,
        generator=generator,
    )
    expected_shape = (1, request.sample_count, request.horizon, len(FEATURE_COLUMNS))
    if raw_normalized.shape != expected_shape:
        raise RuntimeError(
            f"generator returned shape {raw_normalized.shape}; expected {expected_shape}"
        )
    raw_paths = raw_normalized[0] * (std + 1e-5) + mean

    output_paths, path_reports, repair_rules = _validate_and_project_paths(
        raw_paths,
        projection_policy=request.projection_policy,
    )
    output_valid_mask = np.asarray(
        [path_report.output_valid for path_report in path_reports],
        dtype=bool,
    )
    validated_paths = output_paths[output_valid_mask]
    repair_count = sum(len(path_report.repairs) for path_report in path_reports)

    if repair_count:
        warnings.append(
            f"explicit projection changed {repair_count} generated cells under "
            f"{request.projection_policy}"
        )
    invalid_count = request.sample_count - int(output_valid_mask.sum())
    if invalid_count:
        warnings.append(
            f"{invalid_count} generated sample paths were excluded from summaries "
            "because candle validation failed"
        )
    if request.deterministic:
        warnings.append("generation used greedy token selection; stochastic uncertainty is absent")

    model_version = _identity_value(predictor.model_version)
    model_revision = _identity_value(predictor.model_revision)
    tokenizer_revision = _identity_value(predictor.tokenizer_revision)
    code_commit = _identity_value(predictor.code_commit)
    if code_commit != "Unknown" and re.fullmatch(r"[0-9a-fA-F]{40}", code_commit) is None:
        raise ForecastRequestError(
            "predictor code_commit must be Unknown or a 40-character Git SHA"
        )
    for name, value in (
        ("model_version", model_version),
        ("model_revision", model_revision),
        ("tokenizer_revision", tokenizer_revision),
        ("code_commit", code_commit),
        ("dataset_version", request.dataset_version),
    ):
        if value == "Unknown":
            warnings.append(f"{name} provenance is Unknown")

    summaries = _summarize_paths(
        validated_paths,
        last_observed_close=float(values[-1, FEATURE_COLUMNS.index("close")]),
        future_index=future_index,
        quantiles=request.quantiles,
        lower_tail_quantile=float(request.lower_tail_quantile),
    )

    raw_valid_count = sum(path_report.raw_valid for path_report in path_reports)
    output_valid_count = int(output_valid_mask.sum())
    if not output_valid_count:
        summary_source = "no_valid_paths"
    elif request.projection_policy == "none":
        summary_source = "valid_raw_paths"
    else:
        summary_source = "explicitly_projected_valid_paths"
    validity_report = ForecastValidityReport(
        passed=output_valid_count == request.sample_count,
        raw_passed=raw_valid_count == request.sample_count,
        total_sample_count=request.sample_count,
        raw_valid_sample_count=raw_valid_count,
        output_valid_sample_count=output_valid_count,
        projection_policy=request.projection_policy,
        paths=tuple(path_reports),
    )

    include_paths = request.return_sample_paths
    projected = output_paths if request.projection_policy != "none" else None
    return ForecastResult(
        instrument_id=request.instrument_id.strip(),
        as_of_timestamp=historical_index[-1],
        future_timestamps=future_index.copy(),
        model_version=model_version,
        model_revision=model_revision,
        tokenizer_revision=tokenizer_revision,
        dataset_version=request.dataset_version.strip(),
        code_commit=code_commit,
        raw_sample_paths=_readonly(raw_paths) if include_paths else None,
        validated_sample_paths=_readonly(validated_paths) if include_paths else None,
        projected_sample_paths=(
            _readonly(projected) if include_paths and projected is not None else None
        ),
        mean_path=summaries["mean_path"],
        median_path=summaries["median_path"],
        quantiles=summaries["quantiles"],
        return_samples=_readonly(summaries["return_samples"]),
        probability_positive_return=summaries["probability_positive_return"],
        lower_tail_return=summaries["lower_tail_return"],
        lower_tail_quantile=float(request.lower_tail_quantile),
        validity_report=validity_report,
        repair_rules=tuple(sorted(repair_rules)),
        repair_count=repair_count,
        warnings=tuple(dict.fromkeys(warnings)),
        seed=recorded_seed,
        generator_state=generator_state,
        generator_state_sha256=(
            hashlib.sha256(generator_state).hexdigest()
            if generator_state is not None
            else None
        ),
        deterministic=request.deterministic,
        generated_sample_count=request.sample_count,
        summary_sample_count=output_valid_count,
        summary_source=summary_source,
    )


def _validate_request_data(
    request: ForecastRequest,
    *,
    max_context: int,
) -> tuple[pd.DataFrame, pd.DatetimeIndex, pd.DatetimeIndex, list[str]]:
    if not isinstance(request.history, pd.DataFrame):
        raise ForecastRequestError("history must be a pandas DataFrame")
    missing = [column for column in FEATURE_COLUMNS if column not in request.history.columns]
    if missing:
        raise ForecastRequestError(f"history is missing required columns: {missing}")
    if request.history.empty:
        raise ForecastRequestError("history must contain at least one row")
    if len(request.history) > max_context:
        raise ForecastRequestError(
            f"history length {len(request.history)} exceeds max_context={max_context}"
        )

    historical_index = _datetime_index(
        request.historical_timestamps,
        "historical_timestamps",
    )
    future_index = _datetime_index(request.future_timestamps, "future_timestamps")
    if len(historical_index) != len(request.history):
        raise ForecastRequestError(
            "historical_timestamps length must equal the number of history rows"
        )
    if len(future_index) != request.horizon:
        raise ForecastRequestError("future_timestamps length must equal horizon")
    _strictly_increasing(historical_index, "historical_timestamps")
    _strictly_increasing(future_index, "future_timestamps")
    if (historical_index.tz is None) != (future_index.tz is None):
        raise ForecastRequestError(
            "historical and future timestamps must use consistent timezone awareness"
        )
    if historical_index.tz is not None and str(historical_index.tz) != str(future_index.tz):
        raise ForecastRequestError("historical and future timestamps must use the same timezone")
    if future_index[0] <= historical_index[-1]:
        raise ForecastRequestError(
            "every future timestamp must be later than the final historical timestamp"
        )

    warnings = _validate_frequency(request, historical_index, future_index)
    history = request.history.loc[:, FEATURE_COLUMNS].copy()
    try:
        values = history.to_numpy(dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ForecastRequestError("history features must be numeric") from exc
    if not np.isfinite(values).all():
        raise ForecastRequestError("history features must not contain NaN or infinity")
    if (values[:, :4] <= 0).any():
        raise ForecastRequestError("historical OHLC prices must be positive")
    if (values[:, 4:] < 0).any():
        raise ForecastRequestError("historical volume and amount must be non-negative")
    if (values[:, 1] < np.maximum(values[:, 0], values[:, 3])).any():
        raise ForecastRequestError("historical high must be at least max(open, close)")
    if (values[:, 2] > np.minimum(values[:, 0], values[:, 3])).any():
        raise ForecastRequestError("historical low must be at most min(open, close)")
    return history, historical_index, future_index, warnings


def _validate_frequency(
    request: ForecastRequest,
    historical_index: pd.DatetimeIndex,
    future_index: pd.DatetimeIndex,
) -> list[str]:
    warnings: list[str] = []
    historical_frequency = pd.infer_freq(historical_index) if len(historical_index) >= 3 else None
    future_frequency = pd.infer_freq(future_index) if len(future_index) >= 3 else None
    if historical_frequency and future_frequency:
        historical_offset = pd.tseries.frequencies.to_offset(historical_frequency)
        future_offset = pd.tseries.frequencies.to_offset(future_frequency)
        if historical_offset.freqstr != future_offset.freqstr:
            raise ForecastRequestError(
                "future timestamps are inconsistent with the inferred historical frequency"
            )
    else:
        warnings.append(
            "timestamp frequency could not be inferred on both history and horizon; "
            "calendar alignment requires the data contract"
        )
    if request.expected_frequency is not None:
        expected = pd.tseries.frequencies.to_offset(request.expected_frequency).freqstr
        for name, inferred in (
            ("historical_timestamps", historical_frequency),
            ("future_timestamps", future_frequency),
        ):
            if inferred is None:
                continue
            actual = pd.tseries.frequencies.to_offset(inferred).freqstr
            if actual != expected:
                raise ForecastRequestError(
                    f"{name} frequency {actual!r} does not match expected {expected!r}"
                )
    return warnings


def _resolve_generator(
    device: str,
    request: ForecastRequest,
) -> tuple[torch.Generator | None, int | None, bytes | None]:
    if request.deterministic:
        if request.generator is not None:
            raise ForecastRequestError("deterministic generation does not use a generator")
        return None, int(request.seed) if request.seed is not None else None, None

    target_device = torch.device(device)
    if request.generator is not None:
        generator_device = torch.device(request.generator.device)
        if generator_device.type != target_device.type:
            raise ForecastRequestError(
                f"generator device {generator_device} does not match predictor device "
                f"{target_device}"
            )
        if target_device.type == "cuda" and generator_device.index != target_device.index:
            raise ForecastRequestError(
                f"generator device {generator_device} does not match predictor device "
                f"{target_device}"
            )
        state = request.generator.get_state().cpu().numpy().tobytes()
        return request.generator, int(request.generator.initial_seed()), state

    try:
        generator = torch.Generator(device=target_device)
    except (RuntimeError, TypeError) as exc:
        raise ForecastRequestError(
            f"isolated seeded generation is not supported on device {target_device}"
        ) from exc
    generator.manual_seed(int(request.seed))
    state = generator.get_state().cpu().numpy().tobytes()
    return generator, int(request.seed), state


def _validate_and_project_paths(
    raw_paths: np.ndarray,
    *,
    projection_policy: str,
) -> tuple[np.ndarray, list[SamplePathValidity], set[str]]:
    output_paths = np.array(raw_paths, dtype=np.float64, copy=True)
    raw_issues_by_sample = [
        _path_issues(raw_paths[sample_index], sample_index)
        for sample_index in range(raw_paths.shape[0])
    ]
    repairs_by_sample: list[list[CandleRepair]] = [
        [] for _ in range(raw_paths.shape[0])
    ]
    repair_rules: set[str] = set()

    if projection_policy == "ohlcv_v1":
        for sample_index in range(output_paths.shape[0]):
            for horizon_index in range(output_paths.shape[1]):
                row = output_paths[sample_index, horizon_index]
                if not np.isfinite(row).all():
                    continue
                required_high = max(row[0], row[1], row[3])
                required_low = min(row[0], row[2], row[3])
                _record_repair(
                    output_paths,
                    repairs_by_sample,
                    repair_rules,
                    sample_index,
                    horizon_index,
                    1,
                    required_high,
                    "high=max(high,open,close)",
                )
                _record_repair(
                    output_paths,
                    repairs_by_sample,
                    repair_rules,
                    sample_index,
                    horizon_index,
                    2,
                    required_low,
                    "low=min(low,open,close)",
                )
                _record_repair(
                    output_paths,
                    repairs_by_sample,
                    repair_rules,
                    sample_index,
                    horizon_index,
                    4,
                    max(row[4], 0.0),
                    "volume=max(volume,0)",
                )
                _record_repair(
                    output_paths,
                    repairs_by_sample,
                    repair_rules,
                    sample_index,
                    horizon_index,
                    5,
                    max(row[5], 0.0),
                    "amount=max(amount,0)",
                )

    reports: list[SamplePathValidity] = []
    for sample_index in range(raw_paths.shape[0]):
        output_issues = _path_issues(output_paths[sample_index], sample_index)
        raw_issues = raw_issues_by_sample[sample_index]
        reports.append(
            SamplePathValidity(
                sample_index=sample_index,
                raw_valid=not raw_issues,
                output_valid=not output_issues,
                raw_issues=tuple(raw_issues),
                output_issues=tuple(output_issues),
                repairs=tuple(repairs_by_sample[sample_index]),
            )
        )
    return output_paths, reports, repair_rules


def _record_repair(
    paths: np.ndarray,
    repairs_by_sample: list[list[CandleRepair]],
    repair_rules: set[str],
    sample_index: int,
    horizon_index: int,
    feature_index: int,
    after: float,
    rule: str,
) -> None:
    before = float(paths[sample_index, horizon_index, feature_index])
    if before == after:
        return
    paths[sample_index, horizon_index, feature_index] = after
    repairs_by_sample[sample_index].append(
        CandleRepair(
            sample_index=sample_index,
            horizon_index=horizon_index,
            field=FEATURE_COLUMNS[feature_index],
            rule=rule,
            before=before,
            after=float(after),
        )
    )
    repair_rules.add(rule)


def _path_issues(path: np.ndarray, sample_index: int) -> list[CandleIssue]:
    issues: list[CandleIssue] = []
    for horizon_index, row in enumerate(path):
        for feature_index, value in enumerate(row):
            if not np.isfinite(value):
                issues.append(
                    CandleIssue(
                        sample_index,
                        horizon_index,
                        "non_finite",
                        FEATURE_COLUMNS[feature_index],
                        "generated value is NaN or infinity",
                    )
                )
        if not np.isfinite(row).all():
            continue
        for feature_index in range(4):
            if row[feature_index] <= 0:
                issues.append(
                    CandleIssue(
                        sample_index,
                        horizon_index,
                        "non_positive_price",
                        FEATURE_COLUMNS[feature_index],
                        "generated OHLC price is not positive",
                    )
                )
        if row[1] < max(row[0], row[3]):
            issues.append(
                CandleIssue(
                    sample_index,
                    horizon_index,
                    "high_below_body",
                    "high",
                    "generated high is below max(open, close)",
                )
            )
        if row[2] > min(row[0], row[3]):
            issues.append(
                CandleIssue(
                    sample_index,
                    horizon_index,
                    "low_above_body",
                    "low",
                    "generated low is above min(open, close)",
                )
            )
        if row[4] < 0:
            issues.append(
                CandleIssue(
                    sample_index,
                    horizon_index,
                    "negative_volume",
                    "volume",
                    "generated volume is negative",
                )
            )
        if row[5] < 0:
            issues.append(
                CandleIssue(
                    sample_index,
                    horizon_index,
                    "negative_amount",
                    "amount",
                    "generated amount is negative",
                )
            )
    return issues


def _summarize_paths(
    paths: np.ndarray,
    *,
    last_observed_close: float,
    future_index: pd.DatetimeIndex,
    quantiles: tuple[float, ...],
    lower_tail_quantile: float,
) -> dict[str, object]:
    horizon = len(future_index)
    feature_count = len(FEATURE_COLUMNS)
    if paths.shape[0]:
        mean = np.mean(paths, axis=0)
        median = np.median(paths, axis=0)
        quantile_values = {
            probability: np.quantile(paths, probability, axis=0)
            for probability in quantiles
        }
        returns = paths[:, :, FEATURE_COLUMNS.index("close")] / last_observed_close - 1.0
        probability_positive = np.mean(returns > 0.0, axis=0)
        lower_tail = np.quantile(returns, lower_tail_quantile, axis=0)
    else:
        mean = np.full((horizon, feature_count), np.nan)
        median = np.full((horizon, feature_count), np.nan)
        quantile_values = {
            probability: np.full((horizon, feature_count), np.nan)
            for probability in quantiles
        }
        returns = np.empty((0, horizon), dtype=np.float64)
        probability_positive = np.full(horizon, np.nan)
        lower_tail = np.full(horizon, np.nan)

    return {
        "mean_path": _path_frame(mean, future_index),
        "median_path": _path_frame(median, future_index),
        "quantiles": {
            probability: _path_frame(values, future_index)
            for probability, values in quantile_values.items()
        },
        "return_samples": returns,
        "probability_positive_return": pd.Series(
            probability_positive,
            index=future_index,
            name="probability_positive_return",
        ),
        "lower_tail_return": pd.Series(
            lower_tail,
            index=future_index,
            name=f"return_q{lower_tail_quantile:g}",
        ),
    }


def _path_frame(values: np.ndarray, index: pd.DatetimeIndex) -> pd.DataFrame:
    return pd.DataFrame(values, columns=FEATURE_COLUMNS, index=index.copy())


def _time_features(index: pd.DatetimeIndex) -> np.ndarray:
    return np.column_stack(
        [
            index.minute,
            index.hour,
            index.weekday,
            index.day,
            index.month,
        ]
    ).astype(np.float32)


def _datetime_index(value: object, name: str) -> pd.DatetimeIndex:
    try:
        index = pd.DatetimeIndex(value)
    except (TypeError, ValueError) as exc:
        raise ForecastRequestError(f"{name} must contain valid timestamps") from exc
    if len(index) == 0:
        raise ForecastRequestError(f"{name} must not be empty")
    if index.hasnans:
        raise ForecastRequestError(f"{name} must not contain NaT")
    return index


def _strictly_increasing(index: pd.DatetimeIndex, name: str) -> None:
    if len(index) > 1 and not bool(np.all(np.diff(index.asi8) > 0)):
        raise ForecastRequestError(f"{name} must be strictly increasing without duplicates")


def _positive_integer(value: object, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, Integral) or int(value) <= 0:
        raise ForecastRequestError(f"{name} must be a positive integer")


def _positive_real(value: object, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ForecastRequestError(f"{name} must be a real number")
    if not math.isfinite(float(value)) or float(value) <= 0:
        raise ForecastRequestError(f"{name} must be finite and greater than 0")


def _bounded_probability(value: object, name: str, *, inclusive_zero: bool) -> None:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ForecastRequestError(f"{name} must be a real number")
    probability = float(value)
    lower_bound_ok = probability >= 0.0 if inclusive_zero else probability > 0.0
    if not math.isfinite(probability) or not lower_bound_ok or probability > 1.0:
        boundary = "[0, 1]" if inclusive_zero else "(0, 1]"
        raise ForecastRequestError(f"{name} must be finite and in {boundary}")


def _identity_value(value: object) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return "Unknown"


def _readonly(values: np.ndarray) -> np.ndarray:
    copy = np.array(values, copy=True)
    copy.setflags(write=False)
    return copy


__all__ = [
    "CandleIssue",
    "CandleRepair",
    "FEATURE_COLUMNS",
    "ForecastRequest",
    "ForecastRequestError",
    "ForecastResult",
    "ForecastValidityReport",
    "SamplePathValidity",
    "forecast_with_predictor",
]
