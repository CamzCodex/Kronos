"""Regression tests for identical-information mandatory baselines."""

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest
import torch

from kronos_eval import (
    BASELINE_SUITE_VERSION,
    MANDATORY_BASELINES,
    BaselineRequest,
    BaselineRequestError,
    required_history_size,
    run_baseline_suite,
)


@pytest.fixture
def baseline_inputs():
    historical = pd.date_range("2020-01-01", periods=80, freq="B", tz="UTC")
    future = pd.date_range(historical[-1] + pd.offsets.BDay(), periods=5, freq="B")
    positions = np.arange(len(historical), dtype=float)
    close = 100.0 * np.exp(0.001 * positions) * (1.0 + 0.01 * np.sin(positions / 4.0))
    return _history_from_close(close), historical, future


def _history_from_close(close):
    close = np.asarray(close, dtype=float)
    open_price = close * 0.999
    volume = 1000.0 + np.arange(len(close), dtype=float)
    return pd.DataFrame(
        {
            "open": open_price,
            "high": np.maximum(open_price, close) * 1.002,
            "low": np.minimum(open_price, close) * 0.998,
            "close": close,
            "volume": volume,
            "amount": volume * close,
        }
    )


def _request(baseline_inputs, **overrides):
    history, historical, future = baseline_inputs
    values = {
        "instrument_id": "TEST",
        "history": history,
        "historical_timestamps": historical,
        "future_timestamps": future,
        "horizon": len(future),
        "dataset_id": "kds-baseline-fixture",
        "fold_id": "kwf-fixture-f000",
        "code_commit": "a" * 40,
        "seed": 123,
        "sample_count": 100,
    }
    values.update(overrides)
    return BaselineRequest(**values)


def test_suite_runs_every_mandatory_baseline_with_one_information_hash(baseline_inputs):
    request = _request(baseline_inputs)
    results = run_baseline_suite(request)

    assert tuple(results) == MANDATORY_BASELINES
    assert len(results) == 11
    assert {result.information_set_hash for result in results.values()} == {
        results["last_value"].information_set_hash
    }
    for name, result in results.items():
        assert result.baseline_name == name
        assert result.baseline_version == BASELINE_SUITE_VERSION
        assert result.mean_path.shape == (5,)
        assert result.median_path.shape == (5,)
        assert result.return_samples.shape[1] == 5
        assert result.expected_volatility.shape == (5,)
        assert np.isfinite(result.sample_paths).all()
        assert (result.sample_paths > 0).all()
        assert result.dataset_id == "kds-baseline-fixture"
        assert result.fold_id == "kwf-fixture-f000"
        assert result.code_commit == "a" * 40


def test_last_value_and_seasonal_naive_have_exact_definitions(baseline_inputs):
    close = baseline_inputs[0]["close"].to_numpy()
    results = run_baseline_suite(_request(baseline_inputs))

    np.testing.assert_allclose(results["last_value"].mean_path, close[-1])
    np.testing.assert_allclose(
        results["seasonal_naive"].mean_path.to_numpy(),
        close[-5:],
    )


def test_drift_uses_only_observed_endpoint_log_drift(baseline_inputs):
    close = baseline_inputs[0]["close"].to_numpy()
    result = run_baseline_suite(_request(baseline_inputs))["drift"]
    drift = (np.log(close[-1]) - np.log(close[0])) / (len(close) - 1)
    expected = close[-1] * np.exp(drift * np.arange(1, 6))

    np.testing.assert_allclose(result.mean_path, expected)


def test_log_linear_regression_extrapolates_a_log_linear_series():
    historical = pd.date_range("2020-01-01", periods=80, freq="B", tz="UTC")
    future = pd.date_range(historical[-1] + pd.offsets.BDay(), periods=5, freq="B")
    close = 50.0 * np.exp(0.002 * np.arange(80))
    request = BaselineRequest(
        instrument_id="TEST",
        history=_history_from_close(close),
        historical_timestamps=historical,
        future_timestamps=future,
        horizon=5,
        dataset_id="dataset",
        fold_id="fold",
        code_commit="a" * 40,
        linear_lookback=60,
    )

    result = run_baseline_suite(request)["linear_regression"]

    expected = 50.0 * np.exp(0.002 * np.arange(80, 85))
    np.testing.assert_allclose(result.mean_path, expected, rtol=1e-12)


def test_deterministic_baselines_expose_degenerate_distributions(baseline_inputs):
    results = run_baseline_suite(_request(baseline_inputs))

    for name in MANDATORY_BASELINES:
        if name == "volatility":
            continue
        result = results[name]
        assert result.deterministic
        assert result.seed is None
        assert result.sample_paths.shape == (1, 5)
        np.testing.assert_array_equal(result.mean_path, result.median_path)
        np.testing.assert_array_equal(result.quantiles[0.05], result.mean_path)
        assert set(result.probability_positive_return.unique()) <= {0.0, 1.0}
        assert "degenerate" in result.warnings[0]


def test_volatility_paths_are_seeded_and_global_rng_independent(baseline_inputs):
    request = _request(baseline_inputs)
    np.random.seed(1)
    torch.manual_seed(1)
    first = run_baseline_suite(request)["volatility"]
    np.random.seed(999)
    torch.manual_seed(999)
    second = run_baseline_suite(request)["volatility"]
    changed = run_baseline_suite(replace(request, seed=124))["volatility"]

    np.testing.assert_array_equal(first.sample_paths, second.sample_paths)
    assert not np.array_equal(first.sample_paths, changed.sample_paths)
    assert first.sample_paths.shape == (100, 5)
    assert not first.deterministic
    assert first.seed == 123
    assert np.all(first.quantiles[0.05] <= first.quantiles[0.5])
    assert np.all(first.quantiles[0.5] <= first.quantiles[0.95])
    assert "calibration" in first.warnings[0]


def test_all_returns_are_relative_to_the_last_observed_close(baseline_inputs):
    close = baseline_inputs[0]["close"].to_numpy()
    result = run_baseline_suite(_request(baseline_inputs))["volatility"]

    np.testing.assert_allclose(
        result.return_samples,
        result.sample_paths / close[-1] - 1.0,
    )


def test_suite_does_not_mutate_input_history(baseline_inputs):
    history = baseline_inputs[0]
    before = history.copy(deep=True)

    run_baseline_suite(_request(baseline_inputs))

    pd.testing.assert_frame_equal(history, before)


def test_future_timestamps_change_identity_but_never_supply_target_values(baseline_inputs):
    request = _request(baseline_inputs)
    shifted_future = request.future_timestamps + pd.Timedelta(days=30)
    first = run_baseline_suite(request)
    shifted = run_baseline_suite(replace(request, future_timestamps=shifted_future))

    assert first["last_value"].information_set_hash != shifted["last_value"].information_set_hash
    for name in MANDATORY_BASELINES:
        np.testing.assert_array_equal(first[name].sample_paths, shifted[name].sample_paths)


def test_information_hash_changes_when_observed_history_changes(baseline_inputs):
    request = _request(baseline_inputs)
    changed_history = request.history.copy(deep=True)
    changed_history.loc[changed_history.index[-1], "volume"] *= 1.01

    first = run_baseline_suite(request)["last_value"]
    changed = run_baseline_suite(replace(request, history=changed_history))["last_value"]

    assert first.information_set_hash != changed.information_set_hash
    assert first.configuration_hash == changed.configuration_hash


def test_mandatory_suite_refuses_partial_execution_on_short_history(baseline_inputs):
    request = _request(
        baseline_inputs,
        history=baseline_inputs[0].iloc[:20].copy(),
        historical_timestamps=baseline_inputs[1][:20],
    )

    assert required_history_size(request) > 20
    with pytest.raises(BaselineRequestError, match="mandatory suite requires"):
        run_baseline_suite(request)


@pytest.mark.parametrize(
    ("column", "value", "message"),
    [
        ("close", np.nan, "finite values"),
        ("close", 0.0, "positive"),
        ("volume", -1.0, "non-negative"),
        ("high", 1.0, "high"),
        ("low", 1000.0, "low"),
    ],
)
def test_invalid_history_values_are_rejected(baseline_inputs, column, value, message):
    history = baseline_inputs[0].copy(deep=True)
    history.loc[history.index[-1], column] = value
    request = _request(baseline_inputs, history=history)
    with pytest.raises(BaselineRequestError, match=message):
        run_baseline_suite(request)


def test_timezone_naive_information_sets_are_rejected(baseline_inputs):
    with pytest.raises(BaselineRequestError, match="timezone"):
        run_baseline_suite(
            _request(
                baseline_inputs,
                historical_timestamps=pd.DatetimeIndex(["2020-01-01"] * 80),
            )
        )
    with pytest.raises(BaselineRequestError, match="timezone"):
        run_baseline_suite(
            _request(
                baseline_inputs,
                future_timestamps=pd.date_range("2020-05-01", periods=5, freq="B"),
            )
        )


def test_invalid_future_timestamp_text_is_rejected(baseline_inputs):
    request = _request(
        baseline_inputs,
        future_timestamps=["not-a-timestamp"] * 5,
    )
    with pytest.raises(BaselineRequestError, match="valid timestamps"):
        run_baseline_suite(request)


def test_duplicate_or_non_future_timestamps_are_rejected(baseline_inputs):
    request = _request(baseline_inputs)
    duplicate = pd.DatetimeIndex([request.historical_timestamps[0]] * 80)
    with pytest.raises(BaselineRequestError, match="strictly increasing"):
        run_baseline_suite(replace(request, historical_timestamps=duplicate))
    with pytest.raises(BaselineRequestError, match="begin after"):
        run_baseline_suite(
            replace(request, future_timestamps=request.historical_timestamps[:5])
        )


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"code_commit": "not-a-sha"}, "Git SHA"),
        ({"seed": -1}, "seed"),
        ({"sample_count": 0}, "sample_count"),
        ({"sample_count": 1_000_001, "horizon": 5}, "5,000,000"),
        ({"exponential_alpha": 1.0}, "exponential_alpha"),
        ({"linear_lookback": 2}, "linear_lookback"),
        ({"tree_max_depth": 9}, "tree_max_depth"),
        ({"quantiles": (0.5, 0.5)}, "duplicates"),
        ({"lower_tail_quantile": -0.1}, "lower_tail_quantile"),
    ],
)
def test_invalid_baseline_controls_are_rejected(baseline_inputs, change, message):
    with pytest.raises(BaselineRequestError, match=message):
        _request(baseline_inputs, **change)


def test_sample_arrays_are_immutable_evidence(baseline_inputs):
    result = run_baseline_suite(_request(baseline_inputs))["last_value"]

    with pytest.raises(ValueError, match="read-only"):
        result.sample_paths[0, 0] = 0.0
    with pytest.raises(ValueError, match="read-only"):
        result.return_samples[0, 0] = 0.0
