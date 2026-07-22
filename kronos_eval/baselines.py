"""Identical-information baseline forecasts for Kronos evaluation."""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from numbers import Integral, Real

import numpy as np
import pandas as pd

from kronos_data.hashing import hash_configuration

BASELINE_SUITE_VERSION = "1.0.0"
BASELINE_FEATURE_COLUMNS = ("open", "high", "low", "close", "volume", "amount")
MANDATORY_BASELINES = (
    "last_value",
    "drift",
    "seasonal_naive",
    "rolling_mean",
    "exponential_smoothing",
    "momentum",
    "mean_reversion",
    "linear_regression",
    "simple_tree",
    "arima_style",
    "volatility",
)


class BaselineRequestError(ValueError):
    """Raised when the common baseline information contract is invalid."""


class BaselineFitError(RuntimeError):
    """Raised when a mandatory baseline cannot produce a valid forecast."""


@dataclass(frozen=True)
class BaselineRequest:
    """One information set and configuration shared by every baseline."""

    instrument_id: str
    history: pd.DataFrame = field(repr=False, compare=False)
    historical_timestamps: object = field(repr=False, compare=False)
    future_timestamps: object = field(repr=False, compare=False)
    horizon: int
    dataset_id: str
    fold_id: str
    code_commit: str
    seed: int = 0
    sample_count: int = 500
    quantiles: tuple[float, ...] = (0.05, 0.5, 0.95)
    lower_tail_quantile: float = 0.05
    seasonal_period: int = 5
    rolling_window: int = 20
    exponential_alpha: float = 0.2
    momentum_lookback: int = 20
    mean_reversion_window: int = 20
    mean_reversion_strength: float = 0.25
    linear_lookback: int = 60
    tree_max_depth: int = 2
    tree_min_leaf: int = 3
    ar_order: int = 5
    volatility_decay: float = 0.94

    def __post_init__(self) -> None:
        for name in ("instrument_id", "dataset_id", "fold_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise BaselineRequestError(f"{name} must be a non-empty string")
        if not isinstance(self.code_commit, str) or re.fullmatch(
            r"[0-9a-f]{7,64}", self.code_commit
        ) is None:
            raise BaselineRequestError(
                "code_commit must be a lowercase hexadecimal Git SHA"
            )
        for name in (
            "horizon",
            "sample_count",
            "seasonal_period",
            "rolling_window",
            "momentum_lookback",
            "mean_reversion_window",
            "linear_lookback",
            "tree_max_depth",
            "tree_min_leaf",
            "ar_order",
        ):
            _positive_integer(getattr(self, name), name)
        if self.linear_lookback < 3:
            raise BaselineRequestError("linear_lookback must be at least 3")
        if self.tree_max_depth > 8:
            raise BaselineRequestError("tree_max_depth cannot exceed 8")
        if self.sample_count * self.horizon > 5_000_000:
            raise BaselineRequestError(
                "sample_count * horizon cannot exceed 5,000,000 generated values"
            )
        if isinstance(self.seed, bool) or not isinstance(self.seed, Integral):
            raise BaselineRequestError("seed must be an integer")
        if not 0 <= int(self.seed) < 2**63:
            raise BaselineRequestError("seed must be between 0 and 2**63 - 1")
        _open_unit(self.exponential_alpha, "exponential_alpha")
        _open_unit(self.mean_reversion_strength, "mean_reversion_strength")
        _open_unit(self.volatility_decay, "volatility_decay")
        if not self.quantiles:
            raise BaselineRequestError("quantiles must contain at least one value")
        normalized_quantiles = tuple(sorted(float(value) for value in self.quantiles))
        if len(set(normalized_quantiles)) != len(normalized_quantiles):
            raise BaselineRequestError("quantiles must not contain duplicates")
        for value in normalized_quantiles:
            _closed_unit(value, "quantile")
        object.__setattr__(self, "quantiles", normalized_quantiles)
        _closed_unit(self.lower_tail_quantile, "lower_tail_quantile")


@dataclass(frozen=True)
class BaselineResult:
    """One baseline's point or sampled close-price forecast."""

    baseline_name: str
    baseline_version: str
    instrument_id: str
    as_of_timestamp: pd.Timestamp
    future_timestamps: pd.DatetimeIndex
    dataset_id: str
    fold_id: str
    code_commit: str
    information_set_hash: str
    configuration_hash: str
    deterministic: bool
    seed: int | None
    sample_paths: np.ndarray
    mean_path: pd.Series
    median_path: pd.Series
    quantiles: dict[float, pd.Series]
    return_samples: np.ndarray
    probability_positive_return: pd.Series
    lower_tail_return: pd.Series
    lower_tail_quantile: float
    expected_volatility: pd.Series
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class _TreeNode:
    value: float
    feature_index: int | None = None
    threshold: float | None = None
    left: _TreeNode | None = None
    right: _TreeNode | None = None

    def predict(self, row: np.ndarray) -> float:
        if self.feature_index is None or self.threshold is None:
            return self.value
        branch = self.left if row[self.feature_index] <= self.threshold else self.right
        if branch is None:
            return self.value
        return branch.predict(row)


def run_baseline_suite(request: BaselineRequest) -> dict[str, BaselineResult]:
    """Run every mandatory baseline on exactly one validated information set."""

    history, close, historical_index, future_index = _validated_information_set(request)
    minimum = required_history_size(request)
    if len(close) < minimum:
        raise BaselineRequestError(
            f"history contains {len(close)} observations; mandatory suite requires {minimum}"
        )
    information_hash = _information_set_hash(history, historical_index, future_index)
    results: dict[str, BaselineResult] = {}
    for baseline_name in MANDATORY_BASELINES:
        paths, deterministic, volatility, configuration = _GENERATORS[baseline_name](
            close,
            request,
        )
        results[baseline_name] = _result(
            baseline_name,
            paths,
            deterministic=deterministic,
            volatility=volatility,
            configuration=configuration,
            request=request,
            historical_index=historical_index,
            future_index=future_index,
            information_set_hash=information_hash,
        )
    if tuple(results) != MANDATORY_BASELINES:
        raise RuntimeError("mandatory baseline registry is incomplete or unordered")
    return results


def required_history_size(request: BaselineRequest) -> int:
    """Return the shared minimum history required to run the full suite."""

    if not isinstance(request, BaselineRequest):
        raise TypeError("request must be a BaselineRequest")
    return max(
        request.seasonal_period,
        request.rolling_window,
        request.momentum_lookback + 1,
        request.mean_reversion_window,
        min(request.linear_lookback, 3),
        request.ar_order + 3,
        25 + request.tree_min_leaf * 2,
    )


def _last_value(close: np.ndarray, request: BaselineRequest):
    path = np.full(request.horizon, close[-1])
    return _deterministic(path, close, {"method": "last_value"})


def _drift(close: np.ndarray, request: BaselineRequest):
    log_drift = (math.log(close[-1]) - math.log(close[0])) / (len(close) - 1)
    steps = np.arange(1, request.horizon + 1, dtype=float)
    path = close[-1] * np.exp(log_drift * steps)
    return _deterministic(path, close, {"method": "log_random_walk_drift"})


def _seasonal_naive(close: np.ndarray, request: BaselineRequest):
    seasonal = close[-request.seasonal_period :]
    indices = np.arange(request.horizon) % request.seasonal_period
    path = seasonal[indices]
    return _deterministic(
        path,
        close,
        {"method": "seasonal_naive", "seasonal_period": request.seasonal_period},
    )


def _rolling_mean(close: np.ndarray, request: BaselineRequest):
    level = float(np.mean(close[-request.rolling_window :]))
    path = np.full(request.horizon, level)
    return _deterministic(
        path,
        close,
        {"method": "rolling_mean", "window": request.rolling_window},
    )


def _exponential_smoothing(close: np.ndarray, request: BaselineRequest):
    level = float(close[0])
    for value in close[1:]:
        level = request.exponential_alpha * float(value) + (
            1.0 - request.exponential_alpha
        ) * level
    path = np.full(request.horizon, level)
    return _deterministic(
        path,
        close,
        {"method": "simple_exponential_smoothing", "alpha": request.exponential_alpha},
    )


def _momentum(close: np.ndarray, request: BaselineRequest):
    recent = close[-(request.momentum_lookback + 1) :]
    mean_log_return = float(np.mean(np.diff(np.log(recent))))
    steps = np.arange(1, request.horizon + 1, dtype=float)
    path = close[-1] * np.exp(mean_log_return * steps)
    return _deterministic(
        path,
        close,
        {"method": "mean_log_return", "lookback": request.momentum_lookback},
    )


def _mean_reversion(close: np.ndarray, request: BaselineRequest):
    target = float(np.mean(close[-request.mean_reversion_window :]))
    steps = np.arange(1, request.horizon + 1, dtype=float)
    remaining = (1.0 - request.mean_reversion_strength) ** steps
    path = target + (close[-1] - target) * remaining
    return _deterministic(
        path,
        close,
        {
            "method": "geometric_mean_reversion",
            "window": request.mean_reversion_window,
            "strength": request.mean_reversion_strength,
        },
    )


def _linear_regression(close: np.ndarray, request: BaselineRequest):
    lookback = min(request.linear_lookback, len(close))
    y = np.log(close[-lookback:])
    x = np.arange(lookback, dtype=float)
    design = np.column_stack([np.ones(lookback), x])
    intercept, slope = np.linalg.lstsq(design, y, rcond=None)[0]
    future_x = np.arange(lookback, lookback + request.horizon, dtype=float)
    path = np.exp(intercept + slope * future_x)
    return _deterministic(
        path,
        close,
        {"method": "log_price_ols", "lookback": lookback},
    )


def _simple_tree(close: np.ndarray, request: BaselineRequest):
    features = []
    targets = []
    for end_position in range(20, len(close) - 1):
        partial = close[: end_position + 1]
        features.append(_tree_features(partial))
        targets.append(math.log(close[end_position + 1] / close[end_position]))
    x = np.asarray(features, dtype=float)
    y = np.asarray(targets, dtype=float)
    if len(y) < request.tree_min_leaf * 2:
        raise BaselineFitError("simple_tree has insufficient training rows")
    tree = _fit_tree(
        x,
        y,
        depth=0,
        max_depth=request.tree_max_depth,
        min_leaf=request.tree_min_leaf,
    )
    generated = list(float(value) for value in close)
    for _ in range(request.horizon):
        feature_row = _tree_features(np.asarray(generated, dtype=float))
        predicted_return = tree.predict(feature_row)
        generated.append(generated[-1] * math.exp(predicted_return))
    path = np.asarray(generated[-request.horizon :])
    return _deterministic(
        path,
        close,
        {
            "method": "deterministic_regression_tree",
            "max_depth": request.tree_max_depth,
            "min_leaf": request.tree_min_leaf,
            "features": ["return_1", "mean_return_5", "volatility_5", "gap_to_mean_20"],
        },
    )


def _arima_style(close: np.ndarray, request: BaselineRequest):
    differences = np.diff(np.log(close))
    order = min(request.ar_order, len(differences) - 2)
    rows = []
    targets = []
    for position in range(order, len(differences)):
        rows.append([1.0, *differences[position - order : position][::-1]])
        targets.append(differences[position])
    design = np.asarray(rows, dtype=float)
    target = np.asarray(targets, dtype=float)
    ridge = 1e-6
    penalty = np.eye(design.shape[1]) * ridge
    penalty[0, 0] = 0.0
    coefficients = np.linalg.solve(design.T @ design + penalty, design.T @ target)
    innovation_lower = float(np.min(differences))
    innovation_upper = float(np.max(differences))
    state = list(float(value) for value in differences)
    generated = []
    price = float(close[-1])
    for _ in range(request.horizon):
        predictors = np.asarray([1.0, *state[-order:][::-1]])
        predicted_difference = float(predictors @ coefficients)
        predicted_difference = float(
            np.clip(predicted_difference, innovation_lower, innovation_upper)
        )
        price *= math.exp(predicted_difference)
        generated.append(price)
        state.append(predicted_difference)
    return _deterministic(
        np.asarray(generated),
        close,
        {
            "method": "ridge_arima_style",
            "order": [order, 1, 0],
            "ma_terms": 0,
            "ridge": ridge,
            "innovation_bounds": [innovation_lower, innovation_upper],
        },
    )


def _volatility(close: np.ndarray, request: BaselineRequest):
    returns = np.diff(np.log(close))
    variance = float(returns[0] ** 2)
    for value in returns[1:]:
        variance = request.volatility_decay * variance + (
            1.0 - request.volatility_decay
        ) * float(value**2)
    sigma = math.sqrt(max(variance, np.finfo(float).tiny))
    generator = np.random.default_rng(int(request.seed))
    shocks = generator.standard_normal((request.sample_count, request.horizon))
    log_steps = -0.5 * sigma**2 + sigma * shocks
    paths = close[-1] * np.exp(np.cumsum(log_steps, axis=1))
    configuration = {
        "method": "ewma_zero_arithmetic_drift_lognormal",
        "decay": request.volatility_decay,
        "sample_count": request.sample_count,
        "seed": int(request.seed),
    }
    return paths, False, sigma, configuration


def _deterministic(path: np.ndarray, close: np.ndarray, configuration: dict):
    sigma = _historical_volatility(close)
    return np.asarray(path, dtype=float)[np.newaxis, :], True, sigma, configuration


def _result(
    baseline_name: str,
    paths: np.ndarray,
    *,
    deterministic: bool,
    volatility: float,
    configuration: dict,
    request: BaselineRequest,
    historical_index: pd.DatetimeIndex,
    future_index: pd.DatetimeIndex,
    information_set_hash: str,
) -> BaselineResult:
    paths = np.asarray(paths, dtype=float)
    expected_shape = (
        1 if deterministic else request.sample_count,
        request.horizon,
    )
    if paths.shape != expected_shape:
        raise BaselineFitError(
            f"{baseline_name} produced shape {paths.shape}; expected {expected_shape}"
        )
    if not np.isfinite(paths).all() or (paths <= 0).any():
        raise BaselineFitError(f"{baseline_name} produced non-finite or non-positive prices")
    observed_close = _request_last_close(request)
    returns = paths / observed_close - 1.0
    configuration_payload = {
        "suite_version": BASELINE_SUITE_VERSION,
        "baseline": baseline_name,
        "horizon": request.horizon,
        "quantiles": list(request.quantiles),
        "lower_tail_quantile": request.lower_tail_quantile,
        "expected_volatility_method": (
            "ewma_log_returns" if baseline_name == "volatility" else "sample_std_log_returns"
        ),
        **configuration,
    }
    warnings = []
    if deterministic:
        warnings.append(
            "deterministic point forecast has a degenerate one-path distribution; "
            "sample frequency is not a calibrated probability"
        )
    else:
        warnings.append(
            "Monte Carlo frequencies are baseline simulation outputs and require "
            "out-of-sample calibration"
        )
    readonly_paths = _readonly(paths)
    readonly_returns = _readonly(returns)
    return BaselineResult(
        baseline_name=baseline_name,
        baseline_version=BASELINE_SUITE_VERSION,
        instrument_id=request.instrument_id.strip(),
        as_of_timestamp=historical_index[-1],
        future_timestamps=future_index.copy(),
        dataset_id=request.dataset_id.strip(),
        fold_id=request.fold_id.strip(),
        code_commit=request.code_commit,
        information_set_hash=information_set_hash,
        configuration_hash=hash_configuration(configuration_payload),
        deterministic=deterministic,
        seed=None if deterministic else int(request.seed),
        sample_paths=readonly_paths,
        mean_path=pd.Series(paths.mean(axis=0), index=future_index, name="close"),
        median_path=pd.Series(np.median(paths, axis=0), index=future_index, name="close"),
        quantiles={
            probability: pd.Series(
                np.quantile(paths, probability, axis=0),
                index=future_index,
                name="close",
            )
            for probability in request.quantiles
        },
        return_samples=readonly_returns,
        probability_positive_return=pd.Series(
            np.mean(returns > 0.0, axis=0),
            index=future_index,
            name="probability_positive_return",
        ),
        lower_tail_return=pd.Series(
            np.quantile(returns, request.lower_tail_quantile, axis=0),
            index=future_index,
            name=f"return_q{request.lower_tail_quantile:g}",
        ),
        lower_tail_quantile=float(request.lower_tail_quantile),
        expected_volatility=pd.Series(
            np.full(request.horizon, volatility),
            index=future_index,
            name="expected_log_return_volatility",
        ),
        warnings=tuple(warnings),
    )


def _validated_information_set(
    request: BaselineRequest,
) -> tuple[pd.DataFrame, np.ndarray, pd.DatetimeIndex, pd.DatetimeIndex]:
    if not isinstance(request, BaselineRequest):
        raise TypeError("request must be a BaselineRequest")
    if not isinstance(request.history, pd.DataFrame):
        raise BaselineRequestError("history must be a pandas DataFrame")
    missing = [
        column for column in BASELINE_FEATURE_COLUMNS if column not in request.history.columns
    ]
    if missing:
        raise BaselineRequestError(f"history is missing required columns: {missing}")
    try:
        history_values = request.history.loc[:, BASELINE_FEATURE_COLUMNS].to_numpy(
            dtype=float,
            copy=True,
        )
    except (TypeError, ValueError) as exc:
        raise BaselineRequestError("history features must be numeric") from exc
    if history_values.ndim != 2 or len(history_values) < 2:
        raise BaselineRequestError("history must contain at least two observations")
    if not np.isfinite(history_values).all():
        raise BaselineRequestError("history features must contain finite values")
    if (history_values[:, :4] <= 0).any():
        raise BaselineRequestError("historical OHLC prices must be positive")
    if (history_values[:, 4:] < 0).any():
        raise BaselineRequestError("historical volume and amount must be non-negative")
    if (history_values[:, 1] < np.maximum(history_values[:, 0], history_values[:, 3])).any():
        raise BaselineRequestError("historical high must be at least max(open, close)")
    if (history_values[:, 2] > np.minimum(history_values[:, 0], history_values[:, 3])).any():
        raise BaselineRequestError("historical low must be at most min(open, close)")
    history = pd.DataFrame(history_values, columns=BASELINE_FEATURE_COLUMNS)
    close = history["close"].to_numpy(copy=True)
    historical_index = _timestamp_index(
        request.historical_timestamps,
        "historical_timestamps",
    )
    future_index = _timestamp_index(request.future_timestamps, "future_timestamps")
    if len(historical_index) != len(history):
        raise BaselineRequestError(
            "historical_timestamps length must equal history length"
        )
    if len(future_index) != request.horizon:
        raise BaselineRequestError("future_timestamps length must equal horizon")
    if (historical_index.tz is None) != (future_index.tz is None):
        raise BaselineRequestError("historical and future timezone awareness must match")
    if str(historical_index.tz) != str(future_index.tz):
        raise BaselineRequestError("historical and future timestamps must use one timezone")
    if future_index[0] <= historical_index[-1]:
        raise BaselineRequestError(
            "future_timestamps must begin after the final historical timestamp"
        )
    return history, close, historical_index, future_index


def _timestamp_index(value: object, name: str) -> pd.DatetimeIndex:
    try:
        index = pd.DatetimeIndex(value)
    except (TypeError, ValueError) as exc:
        raise BaselineRequestError(f"{name} must contain valid timestamps") from exc
    if index.empty or index.hasnans:
        raise BaselineRequestError(f"{name} must contain non-missing timestamps")
    if index.tz is None:
        raise BaselineRequestError(f"{name} must be timezone-aware")
    if len(index) > 1 and not bool(np.all(np.diff(index.asi8) > 0)):
        raise BaselineRequestError(f"{name} must be strictly increasing without duplicates")
    return index


def _information_set_hash(
    history: pd.DataFrame,
    historical_index: pd.DatetimeIndex,
    future_index: pd.DatetimeIndex,
) -> str:
    digest = hashlib.sha256()
    digest.update("\x1f".join(BASELINE_FEATURE_COLUMNS).encode("utf-8"))
    digest.update(np.asarray(history, dtype="<f8").tobytes())
    digest.update(historical_index.tz_convert("UTC").asi8.astype("<i8").tobytes())
    digest.update(future_index.tz_convert("UTC").asi8.astype("<i8").tobytes())
    return digest.hexdigest()


def _request_last_close(request: BaselineRequest) -> float:
    return float(request.history["close"].iloc[-1])


def _historical_volatility(close: np.ndarray) -> float:
    returns = np.diff(np.log(close))
    if len(returns) < 2:
        return 0.0
    return float(np.std(returns, ddof=1))


def _tree_features(close: np.ndarray) -> np.ndarray:
    log_returns = np.diff(np.log(close))
    recent_five = log_returns[-5:]
    return np.asarray(
        [
            log_returns[-1],
            np.mean(recent_five),
            np.std(recent_five),
            close[-1] / np.mean(close[-20:]) - 1.0,
        ],
        dtype=float,
    )


def _fit_tree(
    x: np.ndarray,
    y: np.ndarray,
    *,
    depth: int,
    max_depth: int,
    min_leaf: int,
) -> _TreeNode:
    value = float(np.mean(y))
    if depth >= max_depth or len(y) < min_leaf * 2 or np.allclose(y, y[0]):
        return _TreeNode(value=value)
    best: tuple[float, int, float, np.ndarray] | None = None
    for feature_index in range(x.shape[1]):
        unique = np.unique(x[:, feature_index])
        if len(unique) < 2:
            continue
        thresholds = (unique[:-1] + unique[1:]) / 2.0
        if len(thresholds) > 32:
            positions = np.linspace(0, len(thresholds) - 1, 32, dtype=int)
            thresholds = thresholds[positions]
        for threshold in thresholds:
            left_mask = x[:, feature_index] <= threshold
            left_count = int(left_mask.sum())
            if left_count < min_leaf or len(y) - left_count < min_leaf:
                continue
            loss = float(
                np.sum((y[left_mask] - np.mean(y[left_mask])) ** 2)
                + np.sum((y[~left_mask] - np.mean(y[~left_mask])) ** 2)
            )
            candidate = (loss, feature_index, float(threshold), left_mask)
            if best is None or candidate[:3] < best[:3]:
                best = candidate
    if best is None:
        return _TreeNode(value=value)
    _, feature_index, threshold, left_mask = best
    return _TreeNode(
        value=value,
        feature_index=feature_index,
        threshold=threshold,
        left=_fit_tree(
            x[left_mask],
            y[left_mask],
            depth=depth + 1,
            max_depth=max_depth,
            min_leaf=min_leaf,
        ),
        right=_fit_tree(
            x[~left_mask],
            y[~left_mask],
            depth=depth + 1,
            max_depth=max_depth,
            min_leaf=min_leaf,
        ),
    )


def _readonly(values: np.ndarray) -> np.ndarray:
    copied = np.array(values, copy=True)
    copied.setflags(write=False)
    return copied


def _positive_integer(value: object, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, Integral) or int(value) <= 0:
        raise BaselineRequestError(f"{name} must be a positive integer")


def _open_unit(value: object, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise BaselineRequestError(f"{name} must be a real number")
    numeric = float(value)
    if not math.isfinite(numeric) or not 0.0 < numeric < 1.0:
        raise BaselineRequestError(f"{name} must be finite and strictly between 0 and 1")


def _closed_unit(value: object, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise BaselineRequestError(f"{name} must be a real number")
    numeric = float(value)
    if not math.isfinite(numeric) or not 0.0 <= numeric <= 1.0:
        raise BaselineRequestError(f"{name} must be finite and between 0 and 1")


_GENERATORS: dict[str, Callable] = {
    "last_value": _last_value,
    "drift": _drift,
    "seasonal_naive": _seasonal_naive,
    "rolling_mean": _rolling_mean,
    "exponential_smoothing": _exponential_smoothing,
    "momentum": _momentum,
    "mean_reversion": _mean_reversion,
    "linear_regression": _linear_regression,
    "simple_tree": _simple_tree,
    "arima_style": _arima_style,
    "volatility": _volatility,
}


__all__ = [
    "BASELINE_FEATURE_COLUMNS",
    "BASELINE_SUITE_VERSION",
    "MANDATORY_BASELINES",
    "BaselineFitError",
    "BaselineRequest",
    "BaselineRequestError",
    "BaselineResult",
    "required_history_size",
    "run_baseline_suite",
]
