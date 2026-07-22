"""Regression tests for common forecast metrics."""

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from kronos_eval import (
    ForecastMetricError,
    ForecastMetricRequest,
    score_forecasts,
)


def _observations():
    rows = []
    timestamps = pd.date_range("2024-01-02", periods=3, freq="B", tz="UTC")
    for date_number, timestamp in enumerate(timestamps):
        for instrument_number in range(6):
            reference = 100.0 + instrument_number
            actual_return = (instrument_number - 2.5) * 0.01 + date_number * 0.001
            actual = reference * (1.0 + actual_return)
            rows.append(
                {
                    "instrument_id": f"I{instrument_number}",
                    "as_of_timestamp": timestamp - pd.Timedelta(days=1),
                    "target_timestamp": timestamp,
                    "horizon": 1,
                    "reference_value": reference,
                    "actual_value": actual,
                    "point_forecast": actual,
                    "scale_error": 2.0,
                    "probability_positive": 1.0 if actual_return > 0 else 0.0,
                    "market_regime": "up" if date_number > 0 else "flat",
                    "volatility_regime": "high" if instrument_number >= 3 else "low",
                    "quantile_0.05": actual * 0.99,
                    "quantile_0.5": actual,
                    "quantile_0.95": actual * 1.01,
                }
            )
    return pd.DataFrame(rows)


def _request(**overrides):
    observations = overrides.pop("observations", _observations())
    values = {
        "model_name": "candidate",
        "dataset_id": "kds-metrics-fixture",
        "fold_id": "fold-001",
        "code_commit": "a" * 40,
        "observations": observations,
        "minimum_cross_section": 5,
        "calibration_bins": 5,
    }
    values.update(overrides)
    return ForecastMetricRequest(**values)


def test_perfect_point_forecasts_have_exact_point_direction_and_rank_scores():
    result = score_forecasts(_request())

    assert result.aggregate["mae"] == pytest.approx(0.0)
    assert result.aggregate["rmse"] == pytest.approx(0.0)
    assert result.aggregate["mase"] == pytest.approx(0.0)
    assert result.aggregate["directional_accuracy"] == pytest.approx(1.0)
    assert result.aggregate["positive_precision"] == pytest.approx(1.0)
    assert result.aggregate["positive_recall"] == pytest.approx(1.0)
    assert result.aggregate["rank_ic_mean"] == pytest.approx(1.0)
    assert result.aggregate["ic_mean"] == pytest.approx(1.0)
    assert result.aggregate["top_minus_bottom_quantile_spread"] > 0
    assert result.aggregate["brier_score_positive"] == pytest.approx(0.0)
    assert result.aggregate["expected_calibration_error"] == pytest.approx(0.0)


def test_scorecard_contains_required_group_breakdowns_and_identity():
    result = score_forecasts(_request())

    assert result.aggregate["observation_count"] == 18
    assert set(result.by_horizon["horizon"]) == {1}
    assert set(result.by_instrument["instrument_id"]) == {f"I{i}" for i in range(6)}
    assert set(result.by_market_regime["market_regime"]) == {"flat", "up"}
    assert set(result.by_volatility_regime["volatility_regime"]) == {"high", "low"}
    assert len(result.cross_sectional_periods) == 3
    assert set(result.calibration_by_market_regime["market_regime"]) == {"flat", "up"}
    assert set(result.calibration_by_volatility_regime["volatility_regime"]) == {
        "high",
        "low",
    }
    assert len(result.observation_hash) == 64
    assert len(result.configuration_hash) == 64
    assert result.aggregate["crps"] is None
    assert any("CRPS unavailable" in warning for warning in result.warnings)


def test_empirical_crps_is_zero_for_samples_equal_to_actual():
    observations = _observations()
    samples = np.repeat(observations["actual_value"].to_numpy()[:, None], 4, axis=1)

    result = score_forecasts(_request(observations=observations, sample_forecasts=samples))

    assert result.aggregate["crps"] == pytest.approx(0.0, abs=1e-12)
    assert not any("CRPS unavailable" in warning for warning in result.warnings)


def test_empirical_crps_matches_two_sample_closed_form():
    observations = _observations().iloc[:1].copy()
    observations["actual_value"] = 2.0
    observations["reference_value"] = 2.0
    observations["point_forecast"] = 2.0
    observations["quantile_0.05"] = 1.0
    observations["quantile_0.5"] = 2.0
    observations["quantile_0.95"] = 3.0
    samples = np.array([[1.0, 3.0]])

    result = score_forecasts(
        _request(
            observations=observations,
            sample_forecasts=samples,
            minimum_cross_section=1,
        )
    )

    assert result.aggregate["crps"] == pytest.approx(0.5)


def test_shuffled_rows_and_corresponding_samples_preserve_scores_and_hash():
    observations = _observations()
    samples = np.column_stack(
        [observations["actual_value"] * 0.99, observations["actual_value"] * 1.01]
    )
    order = np.random.default_rng(4).permutation(len(observations))

    first = score_forecasts(_request(observations=observations, sample_forecasts=samples))
    shuffled = score_forecasts(
        _request(
            observations=observations.iloc[order].reset_index(drop=True),
            sample_forecasts=samples[order],
        )
    )

    assert first.observation_hash == shuffled.observation_hash
    assert first.aggregate == shuffled.aggregate


def test_observation_and_configuration_identity_change_independently():
    request = _request()
    changed = request.observations.copy(deep=True)
    changed.loc[0, "actual_value"] *= 1.001

    first = score_forecasts(request)
    data_changed = score_forecasts(replace(request, observations=changed))
    config_changed = score_forecasts(replace(request, calibration_bins=4))

    assert first.observation_hash != data_changed.observation_hash
    assert first.configuration_hash == data_changed.configuration_hash
    assert first.observation_hash == config_changed.observation_hash
    assert first.configuration_hash != config_changed.configuration_hash


def test_quantile_loss_and_interval_coverage_are_reported():
    result = score_forecasts(_request())

    assert list(result.quantile_loss["probability"]) == [0.05, 0.5, 0.95]
    assert (result.quantile_loss["quantile_loss"] >= 0).all()
    assert result.aggregate["mean_quantile_loss"] >= 0
    assert result.aggregate["interval_coverage"] == pytest.approx(1.0)


def test_missing_cross_sections_are_explicit_not_silently_zero():
    observations = _observations().iloc[:3].copy()

    result = score_forecasts(_request(observations=observations, minimum_cross_section=5))

    assert result.cross_sectional_periods.empty
    assert result.aggregate["ic_mean"] is None
    assert any("ranking metrics are unavailable" in warning for warning in result.warnings)


@pytest.mark.parametrize(
    ("column", "value", "message"),
    [
        ("actual_value", np.nan, "finite"),
        ("reference_value", 0.0, "positive"),
        ("scale_error", 0.0, "scale_error"),
        ("probability_positive", 1.1, "between 0 and 1"),
        ("quantile_0.05", -1.0, "quantile forecasts must be positive"),
        ("quantile_0.05", 1_000.0, "non-decreasing"),
    ],
)
def test_invalid_numeric_observations_are_rejected(column, value, message):
    observations = _observations()
    observations.loc[0, column] = value

    with pytest.raises(ForecastMetricError, match=message):
        score_forecasts(_request(observations=observations))


def test_duplicate_observations_are_rejected():
    observations = _observations()
    observations = pd.concat([observations, observations.iloc[[0]]], ignore_index=True)

    with pytest.raises(ForecastMetricError, match="must be unique"):
        score_forecasts(_request(observations=observations))


def test_as_of_must_be_timezone_aware_and_precede_target():
    observations = _observations()
    observations.loc[0, "as_of_timestamp"] = observations.loc[0, "target_timestamp"]
    with pytest.raises(ForecastMetricError, match="later than"):
        score_forecasts(_request(observations=observations))

    observations = _observations()
    observations["as_of_timestamp"] = observations["as_of_timestamp"].dt.tz_localize(None)
    with pytest.raises(ForecastMetricError, match="timezone-aware"):
        score_forecasts(_request(observations=observations))


def test_sample_shape_and_values_are_rejected():
    observations = _observations()
    with pytest.raises(ForecastMetricError, match="shape"):
        score_forecasts(_request(observations=observations, sample_forecasts=np.ones((2, 3))))
    invalid = np.ones((len(observations), 2))
    invalid[0, 0] = np.inf
    with pytest.raises(ForecastMetricError, match="finite and positive"):
        score_forecasts(_request(observations=observations, sample_forecasts=invalid))


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"code_commit": "not-a-sha"}, "Git SHA"),
        ({"calibration_bins": 0}, "positive integer"),
        ({"calibration_bins": 101}, "cannot exceed"),
        ({"minimum_cross_section": 0}, "positive integer"),
        ({"top_quantile_fraction": 1.0}, "strictly between"),
        ({"downside_threshold": np.nan}, "finite"),
        ({"quantile_columns": ((0.5, "q1"), (0.5, "q2"))}, "unique"),
    ],
)
def test_invalid_metric_controls_are_rejected(change, message):
    with pytest.raises(ForecastMetricError, match=message):
        _request(**change)
