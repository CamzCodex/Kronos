"""Common point, direction, ranking, and probabilistic forecast metrics."""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from numbers import Integral, Real
from typing import Any, cast

import numpy as np
import pandas as pd

from kronos_data.hashing import canonical_json, hash_configuration

METRIC_SUITE_VERSION = "1.0.0"
REQUIRED_EVALUATION_COLUMNS = (
    "instrument_id",
    "as_of_timestamp",
    "target_timestamp",
    "horizon",
    "reference_value",
    "actual_value",
    "point_forecast",
    "scale_error",
    "probability_positive",
    "market_regime",
    "volatility_regime",
)


class ForecastMetricError(ValueError):
    """Raised when a forecast scoring input is invalid or incomparable."""


@dataclass(frozen=True)
class ForecastMetricRequest:
    """Normalized, identity-bound forecasts and realized targets for one fold."""

    model_name: str
    dataset_id: str
    fold_id: str
    code_commit: str
    observations: pd.DataFrame = field(repr=False, compare=False)
    quantile_columns: tuple[tuple[float, str], ...] = (
        (0.05, "quantile_0.05"),
        (0.5, "quantile_0.5"),
        (0.95, "quantile_0.95"),
    )
    sample_forecasts: np.ndarray | None = field(default=None, repr=False, compare=False)
    calibration_bins: int = 10
    minimum_cross_section: int = 5
    top_quantile_fraction: float = 0.2
    downside_threshold: float = -0.02

    def __post_init__(self) -> None:
        for name in ("model_name", "dataset_id", "fold_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ForecastMetricError(f"{name} must be a non-empty string")
        if not isinstance(self.code_commit, str) or re.fullmatch(
            r"[0-9a-f]{7,64}", self.code_commit
        ) is None:
            raise ForecastMetricError(
                "code_commit must be a lowercase hexadecimal Git SHA"
            )
        _positive_integer(self.calibration_bins, "calibration_bins")
        _positive_integer(self.minimum_cross_section, "minimum_cross_section")
        if self.calibration_bins > 100:
            raise ForecastMetricError("calibration_bins cannot exceed 100")
        _open_unit(self.top_quantile_fraction, "top_quantile_fraction")
        if not isinstance(self.downside_threshold, Real) or isinstance(
            self.downside_threshold, bool
        ):
            raise ForecastMetricError("downside_threshold must be a real number")
        if not math.isfinite(float(self.downside_threshold)):
            raise ForecastMetricError("downside_threshold must be finite")
        normalized = tuple(sorted((float(q), str(column)) for q, column in self.quantile_columns))
        if len(normalized) < 2:
            raise ForecastMetricError("at least two quantile columns are required")
        if len({q for q, _ in normalized}) != len(normalized):
            raise ForecastMetricError("quantile probabilities must be unique")
        if len({column for _, column in normalized}) != len(normalized):
            raise ForecastMetricError("quantile column names must be unique")
        for probability, column in normalized:
            if not 0.0 < probability < 1.0:
                raise ForecastMetricError("quantile probabilities must be between 0 and 1")
            if not column:
                raise ForecastMetricError("quantile column names must be non-empty")
            if column in REQUIRED_EVALUATION_COLUMNS:
                raise ForecastMetricError(
                    "quantile column names cannot replace required observation columns"
                )
        object.__setattr__(self, "quantile_columns", normalized)


@dataclass(frozen=True)
class ForecastScorecard:
    metric_suite_version: str
    model_name: str
    dataset_id: str
    fold_id: str
    code_commit: str
    observation_hash: str
    configuration_hash: str
    aggregate: dict[str, Any]
    by_horizon: pd.DataFrame
    by_instrument: pd.DataFrame
    by_market_regime: pd.DataFrame
    by_volatility_regime: pd.DataFrame
    cross_sectional_periods: pd.DataFrame
    calibration: pd.DataFrame
    calibration_by_market_regime: pd.DataFrame
    calibration_by_volatility_regime: pd.DataFrame
    quantile_loss: pd.DataFrame
    warnings: tuple[str, ...]


def score_forecasts(request: ForecastMetricRequest) -> ForecastScorecard:
    """Score one fold without choosing, tuning, or transforming a model."""

    observations, samples = _validated_request(request)
    actual_return = observations["actual_value"] / observations["reference_value"] - 1.0
    forecast_return = (
        observations["point_forecast"] / observations["reference_value"] - 1.0
    )
    aggregate = _point_direction_metrics(observations, actual_return, forecast_return)
    quantile_loss = _quantile_scores(observations, request.quantile_columns)
    lower_probability, lower_column = request.quantile_columns[0]
    upper_probability, upper_column = request.quantile_columns[-1]
    aggregate.update(
        {
            "interval_lower_probability": lower_probability,
            "interval_upper_probability": upper_probability,
            "interval_coverage": float(
                np.mean(
                    (observations["actual_value"] >= observations[lower_column])
                    & (observations["actual_value"] <= observations[upper_column])
                )
            ),
            "mean_quantile_loss": float(quantile_loss["quantile_loss"].mean()),
            "brier_score_positive": float(
                np.mean(
                    (
                        observations["probability_positive"].to_numpy()
                        - (actual_return.to_numpy() > 0.0)
                    )
                    ** 2
                )
            ),
        }
    )
    predicted_lower_return = (
        observations[lower_column] / observations["reference_value"] - 1.0
    )
    aggregate["downside_tail_recall"] = _recall(
        actual_return.to_numpy() <= float(request.downside_threshold),
        predicted_lower_return.to_numpy() <= float(request.downside_threshold),
    )
    if samples is not None:
        aggregate["crps"] = float(
            np.mean(_empirical_crps(samples, observations["actual_value"].to_numpy()))
        )
    else:
        aggregate["crps"] = None

    cross_sectional = _cross_sectional_scores(
        observations,
        actual_return,
        forecast_return,
        minimum_size=request.minimum_cross_section,
        top_fraction=float(request.top_quantile_fraction),
    )
    aggregate.update(_aggregate_cross_sectional(cross_sectional))
    calibration = _calibration_table(
        observations["probability_positive"].to_numpy(),
        actual_return.to_numpy() > 0.0,
        bins=request.calibration_bins,
    )
    aggregate["expected_calibration_error"] = float(
        np.sum(calibration["weight"] * calibration["absolute_gap"])
    )

    warnings = [
        "metric implementation correctness is not evidence of model usefulness",
        "multiple models, horizons, regimes, and perturbations require multiplicity disclosure",
    ]
    if samples is None:
        warnings.append("CRPS unavailable because empirical sample forecasts were not supplied")
    if aggregate["downside_tail_recall"] is None:
        warnings.append("downside-tail recall is undefined because no realized tail event occurred")
    if cross_sectional.empty:
        warnings.append(
            "ranking metrics are unavailable because no timestamp/horizon cross-section met "
            "the declared minimum"
        )

    configuration = {
        "metric_suite_version": METRIC_SUITE_VERSION,
        "quantile_columns": [[q, column] for q, column in request.quantile_columns],
        "calibration_bins": request.calibration_bins,
        "minimum_cross_section": request.minimum_cross_section,
        "top_quantile_fraction": request.top_quantile_fraction,
        "downside_threshold": request.downside_threshold,
        "crps_supplied": samples is not None,
    }
    return ForecastScorecard(
        metric_suite_version=METRIC_SUITE_VERSION,
        model_name=request.model_name.strip(),
        dataset_id=request.dataset_id.strip(),
        fold_id=request.fold_id.strip(),
        code_commit=request.code_commit,
        observation_hash=_observation_hash(observations, samples),
        configuration_hash=hash_configuration(configuration),
        aggregate=aggregate,
        by_horizon=_group_scores(observations, ["horizon"]),
        by_instrument=_group_scores(observations, ["instrument_id"]),
        by_market_regime=_group_scores(observations, ["market_regime"]),
        by_volatility_regime=_group_scores(observations, ["volatility_regime"]),
        cross_sectional_periods=cross_sectional,
        calibration=calibration,
        calibration_by_market_regime=_calibration_by_group(
            observations,
            actual_return,
            group_column="market_regime",
            bins=request.calibration_bins,
        ),
        calibration_by_volatility_regime=_calibration_by_group(
            observations,
            actual_return,
            group_column="volatility_regime",
            bins=request.calibration_bins,
        ),
        quantile_loss=quantile_loss,
        warnings=tuple(warnings),
    )


def _validated_request(
    request: ForecastMetricRequest,
) -> tuple[pd.DataFrame, np.ndarray | None]:
    if not isinstance(request, ForecastMetricRequest):
        raise TypeError("request must be a ForecastMetricRequest")
    if not isinstance(request.observations, pd.DataFrame):
        raise ForecastMetricError("observations must be a pandas DataFrame")
    quantile_names = tuple(column for _, column in request.quantile_columns)
    required = (*REQUIRED_EVALUATION_COLUMNS, *quantile_names)
    missing = [column for column in required if column not in request.observations.columns]
    if missing:
        raise ForecastMetricError(f"observations are missing required columns: {missing}")
    frame = request.observations.loc[:, required].copy(deep=True)
    if frame.empty:
        raise ForecastMetricError("observations must not be empty")
    frame["instrument_id"] = frame["instrument_id"].astype("string")
    for column in ("instrument_id", "market_regime", "volatility_regime"):
        frame[column] = frame[column].astype("string")
        if frame[column].isna().any() or (frame[column].astype(str).str.strip() == "").any():
            raise ForecastMetricError(f"{column} must contain non-empty labels")
    frame["as_of_timestamp"] = _aware_utc_index(
        frame["as_of_timestamp"], "as_of_timestamp"
    )
    frame["target_timestamp"] = _aware_utc_index(
        frame["target_timestamp"], "target_timestamp"
    )
    if (frame["target_timestamp"] <= frame["as_of_timestamp"]).any():
        raise ForecastMetricError(
            "every target_timestamp must be later than its as_of_timestamp"
        )
    if frame.duplicated(
        ["instrument_id", "as_of_timestamp", "target_timestamp", "horizon"]
    ).any():
        raise ForecastMetricError(
            "instrument/as-of/target/horizon observations must be unique"
        )
    if frame["horizon"].map(lambda value: isinstance(value, bool) or not isinstance(value, Integral)).any():
        raise ForecastMetricError("horizon must contain integers")
    frame["horizon"] = frame["horizon"].astype(int)
    if (frame["horizon"] <= 0).any():
        raise ForecastMetricError("horizon must be positive")
    numeric_columns = (
        "reference_value",
        "actual_value",
        "point_forecast",
        "scale_error",
        "probability_positive",
        *quantile_names,
    )
    for column in numeric_columns:
        try:
            frame[column] = pd.to_numeric(frame[column], errors="raise")
        except (TypeError, ValueError) as exc:
            raise ForecastMetricError(f"{column} must be numeric") from exc
    if not np.isfinite(frame.loc[:, numeric_columns].to_numpy(dtype=float)).all():
        raise ForecastMetricError("numeric observations must be finite")
    if (frame[["reference_value", "actual_value", "point_forecast"]] <= 0).any().any():
        raise ForecastMetricError("reference, actual, and point forecast values must be positive")
    if (frame["scale_error"] <= 0).any():
        raise ForecastMetricError("scale_error must be positive and training-derived")
    if ((frame["probability_positive"] < 0) | (frame["probability_positive"] > 1)).any():
        raise ForecastMetricError("probability_positive must be between 0 and 1")
    quantile_values = frame.loc[:, quantile_names].to_numpy(dtype=float)
    if (quantile_values <= 0).any():
        raise ForecastMetricError("quantile forecasts must be positive")
    if (np.diff(quantile_values, axis=1) < 0).any():
        raise ForecastMetricError("quantile forecasts must be non-decreasing per observation")
    frame["_original_position"] = np.arange(len(frame))
    frame = frame.sort_values(
        ["target_timestamp", "horizon", "instrument_id", "as_of_timestamp"],
        kind="mergesort",
    ).reset_index(drop=True)
    order = frame.pop("_original_position").to_numpy()

    samples = None
    if request.sample_forecasts is not None:
        try:
            samples = np.asarray(request.sample_forecasts, dtype=float)
        except (TypeError, ValueError) as exc:
            raise ForecastMetricError("sample_forecasts must be numeric") from exc
        if samples.ndim != 2 or samples.shape[0] != len(request.observations):
            raise ForecastMetricError(
                "sample_forecasts must have shape (observation_count, sample_count)"
            )
        if samples.shape[1] < 2:
            raise ForecastMetricError("sample_forecasts require at least two samples")
        if not np.isfinite(samples).all() or (samples <= 0).any():
            raise ForecastMetricError("sample_forecasts must be finite and positive")
        samples = np.array(samples[order], copy=True)
    return frame, samples


def _point_direction_metrics(
    frame: pd.DataFrame,
    actual_return: pd.Series,
    forecast_return: pd.Series,
) -> dict[str, Any]:
    errors = frame["point_forecast"].to_numpy() - frame["actual_value"].to_numpy()
    actual_positive = actual_return.to_numpy() > 0.0
    predicted_positive = forecast_return.to_numpy() > 0.0
    return {
        "observation_count": len(frame),
        "mae": float(np.mean(np.abs(errors))),
        "rmse": float(np.sqrt(np.mean(errors**2))),
        "mase": float(np.mean(np.abs(errors) / frame["scale_error"].to_numpy())),
        "directional_accuracy": float(np.mean(actual_positive == predicted_positive)),
        "positive_precision": _precision(actual_positive, predicted_positive),
        "positive_recall": _recall(actual_positive, predicted_positive),
    }


def _group_scores(frame: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    rows = []
    grouper: str | list[str] = group_columns[0] if len(group_columns) == 1 else group_columns
    for key, group in frame.groupby(grouper, sort=True, observed=True):
        actual_return = group["actual_value"] / group["reference_value"] - 1.0
        forecast_return = group["point_forecast"] / group["reference_value"] - 1.0
        metrics = _point_direction_metrics(group, actual_return, forecast_return)
        values = (key,) if len(group_columns) == 1 else tuple(key)
        rows.append({**dict(zip(group_columns, values, strict=True)), **metrics})
    return pd.DataFrame(rows)


def _quantile_scores(
    frame: pd.DataFrame,
    quantile_columns: tuple[tuple[float, str], ...],
) -> pd.DataFrame:
    actual = frame["actual_value"].to_numpy()
    rows = []
    for probability, column in quantile_columns:
        error = actual - frame[column].to_numpy()
        loss = np.maximum(probability * error, (probability - 1.0) * error)
        rows.append(
            {
                "probability": probability,
                "column": column,
                "quantile_loss": float(np.mean(loss)),
                "observation_count": len(frame),
            }
        )
    return pd.DataFrame(rows)


def _calibration_table(probability: np.ndarray, outcome: np.ndarray, *, bins: int) -> pd.DataFrame:
    edges = np.linspace(0.0, 1.0, bins + 1)
    membership = np.minimum(np.searchsorted(edges, probability, side="right") - 1, bins - 1)
    rows = []
    for bin_number in range(bins):
        mask = membership == bin_number
        count = int(mask.sum())
        mean_probability = float(np.mean(probability[mask])) if count else None
        observed_frequency = float(np.mean(outcome[mask])) if count else None
        gap = (
            abs(mean_probability - observed_frequency)
            if mean_probability is not None and observed_frequency is not None
            else 0.0
        )
        rows.append(
            {
                "bin": bin_number,
                "lower": float(edges[bin_number]),
                "upper": float(edges[bin_number + 1]),
                "count": count,
                "weight": count / len(probability),
                "mean_probability": mean_probability,
                "observed_frequency": observed_frequency,
                "absolute_gap": gap,
            }
        )
    return pd.DataFrame(rows)


def _calibration_by_group(
    frame: pd.DataFrame,
    actual_return: pd.Series,
    *,
    group_column: str,
    bins: int,
) -> pd.DataFrame:
    working = frame[[group_column, "probability_positive"]].copy()
    working["actual_positive"] = actual_return.to_numpy() > 0.0
    tables = []
    for group_name, group in working.groupby(group_column, sort=True, observed=True):
        table = _calibration_table(
            group["probability_positive"].to_numpy(),
            group["actual_positive"].to_numpy(),
            bins=bins,
        )
        table.insert(0, group_column, group_name)
        tables.append(table)
    return pd.concat(tables, ignore_index=True)


def _cross_sectional_scores(
    frame: pd.DataFrame,
    actual_return: pd.Series,
    forecast_return: pd.Series,
    *,
    minimum_size: int,
    top_fraction: float,
) -> pd.DataFrame:
    working = frame[["target_timestamp", "horizon", "instrument_id"]].copy()
    working["actual_return"] = actual_return.to_numpy()
    working["forecast_return"] = forecast_return.to_numpy()
    rows = []
    for (timestamp, horizon), group in working.groupby(
        ["target_timestamp", "horizon"], sort=True, observed=True
    ):
        if len(group) < minimum_size:
            continue
        actual = group["actual_return"].to_numpy()
        forecast = group["forecast_return"].to_numpy()
        if np.ptp(actual) == 0.0 or np.ptp(forecast) == 0.0:
            continue
        count = max(1, int(math.floor(len(group) * top_fraction)))
        order = np.argsort(forecast, kind="mergesort")
        rows.append(
            {
                "target_timestamp": timestamp,
                "horizon": int(horizon),
                "instrument_count": len(group),
                "ic": float(np.corrcoef(forecast, actual)[0, 1]),
                "rank_ic": float(
                    np.corrcoef(
                        pd.Series(forecast).rank(method="average").to_numpy(),
                        pd.Series(actual).rank(method="average").to_numpy(),
                    )[0, 1]
                ),
                "top_minus_bottom_return": float(
                    np.mean(actual[order[-count:]]) - np.mean(actual[order[:count]])
                ),
                "quantile_count": count,
            }
        )
    return pd.DataFrame(rows)


def _aggregate_cross_sectional(periods: pd.DataFrame) -> dict[str, Any]:
    if periods.empty:
        return {
            "cross_section_count": 0,
            "ic_mean": None,
            "ic_standard_deviation": None,
            "icir": None,
            "rank_ic_mean": None,
            "top_minus_bottom_quantile_spread": None,
        }
    ic = periods["ic"].to_numpy()
    standard_deviation = float(np.std(ic, ddof=1)) if len(ic) > 1 else None
    return {
        "cross_section_count": len(periods),
        "ic_mean": float(np.mean(ic)),
        "ic_standard_deviation": standard_deviation,
        "icir": (
            float(np.mean(ic) / standard_deviation)
            if standard_deviation is not None and standard_deviation > 0.0
            else None
        ),
        "rank_ic_mean": float(periods["rank_ic"].mean()),
        "top_minus_bottom_quantile_spread": float(
            periods["top_minus_bottom_return"].mean()
        ),
    }


def _empirical_crps(samples: np.ndarray, actual: np.ndarray) -> np.ndarray:
    ordered = np.sort(samples, axis=1)
    sample_count = ordered.shape[1]
    weights = 2.0 * np.arange(1, sample_count + 1) - sample_count - 1.0
    pair_term = ordered @ weights / sample_count**2
    return np.mean(np.abs(samples - actual[:, np.newaxis]), axis=1) - pair_term


def _observation_hash(frame: pd.DataFrame, samples: np.ndarray | None) -> str:
    records = []
    for row in frame.itertuples(index=False, name=None):
        converted = []
        for value in row:
            if isinstance(value, pd.Timestamp):
                converted.append(value.tz_convert("UTC").isoformat())
            elif isinstance(value, (np.integer, int)):
                converted.append(int(value))
            elif isinstance(value, (np.floating, float)):
                converted.append(float(value))
            else:
                converted.append(str(value))
        records.append(converted)
    digest = hashlib.sha256(
        canonical_json({"columns": list(frame.columns), "records": records}).encode("utf-8")
    )
    if samples is not None:
        digest.update(np.asarray(samples, dtype="<f8").tobytes())
    return digest.hexdigest()


def _precision(actual: np.ndarray, predicted: np.ndarray) -> float | None:
    predicted_count = int(predicted.sum())
    if predicted_count == 0:
        return None
    return float(np.sum(actual & predicted) / predicted_count)


def _recall(actual: np.ndarray, predicted: np.ndarray) -> float | None:
    actual_count = int(actual.sum())
    if actual_count == 0:
        return None
    return float(np.sum(actual & predicted) / actual_count)


def _aware_utc_index(values: object, name: str) -> pd.DatetimeIndex:
    converted = []
    try:
        iterator = iter(cast(Iterable[object], values))
    except TypeError as exc:
        raise ForecastMetricError(f"{name} must be an iterable of timestamps") from exc
    for value in iterator:
        try:
            timestamp = pd.Timestamp(value)
        except (TypeError, ValueError) as exc:
            raise ForecastMetricError(f"{name} must contain valid timestamps") from exc
        if pd.isna(timestamp):
            raise ForecastMetricError(f"{name} must not contain missing values")
        if timestamp.tzinfo is None:
            raise ForecastMetricError(f"{name} must be timezone-aware")
        converted.append(timestamp.tz_convert("UTC"))
    return pd.DatetimeIndex(converted)


def _positive_integer(value: object, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, Integral) or int(value) <= 0:
        raise ForecastMetricError(f"{name} must be a positive integer")


def _open_unit(value: object, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ForecastMetricError(f"{name} must be a real number")
    numeric = float(value)
    if not math.isfinite(numeric) or not 0.0 < numeric < 1.0:
        raise ForecastMetricError(f"{name} must be finite and strictly between 0 and 1")


__all__ = [
    "METRIC_SUITE_VERSION",
    "REQUIRED_EVALUATION_COLUMNS",
    "ForecastMetricError",
    "ForecastMetricRequest",
    "ForecastScorecard",
    "score_forecasts",
]
