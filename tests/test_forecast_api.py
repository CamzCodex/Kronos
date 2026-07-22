"""Regression tests for typed probabilistic forecasts and candle accounting."""

import hashlib
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest
import torch

from model import ForecastRequest, ForecastRequestError
from model.forecast import FEATURE_COLUMNS
from model.kronos import Kronos, KronosPredictor, KronosTokenizer, auto_regressive_inference


@pytest.fixture
def predictor(small_tokenizer_config, small_model_config):
    torch.manual_seed(42)
    tokenizer = KronosTokenizer(**small_tokenizer_config).eval()
    model = Kronos(**small_model_config).eval()
    return KronosPredictor(
        model,
        tokenizer,
        device="cpu",
        max_context=32,
        model_version="Kronos-test",
        model_revision="model-revision-test",
        tokenizer_revision="tokenizer-revision-test",
        code_commit="a" * 40,
    )


@pytest.fixture
def valid_inputs():
    close = np.arange(100.0, 108.0)
    history = pd.DataFrame(
        {
            "open": close - 0.25,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": np.arange(1000.0, 1008.0),
            "amount": close * np.arange(1000.0, 1008.0),
        }
    )
    historical = pd.date_range("2025-01-01", periods=len(history), freq="h", tz="UTC")
    future = pd.date_range(historical[-1] + pd.Timedelta(hours=1), periods=3, freq="h")
    return history, historical, future


def _request(valid_inputs, **overrides):
    history, historical, future = valid_inputs
    values = {
        "instrument_id": "TEST",
        "history": history,
        "historical_timestamps": historical,
        "future_timestamps": future,
        "horizon": len(future),
        "sample_count": 2,
        "seed": 123,
        "top_k": 0,
        "top_p": 1.0,
        "dataset_version": "dataset-test",
        "expected_frequency": "h",
        "verbose": False,
    }
    values.update(overrides)
    return ForecastRequest(**values)


def _install_paths(monkeypatch, predictor, history, paths):
    values = history.loc[:, FEATURE_COLUMNS].to_numpy(dtype=np.float32)
    mean = values.mean(axis=0)
    std = values.std(axis=0)
    normalized = (np.asarray(paths, dtype=np.float32) - mean) / (std + 1e-5)
    generated = normalized[np.newaxis, :]

    def fake_generate(*args, **kwargs):
        return generated.copy()

    monkeypatch.setattr(predictor, "generate_sample_paths", fake_generate)


def _valid_paths():
    return np.asarray(
        [
            [
                [108.0, 110.0, 107.0, 109.0, 1100.0, 119900.0],
                [109.0, 112.0, 108.0, 111.0, 1200.0, 133200.0],
                [111.0, 113.0, 109.0, 110.0, 1300.0, 143000.0],
            ],
            [
                [107.0, 109.0, 106.0, 108.0, 1000.0, 108000.0],
                [108.0, 110.0, 105.0, 106.0, 900.0, 95400.0],
                [106.0, 108.0, 103.0, 104.0, 800.0, 83200.0],
            ],
        ],
        dtype=np.float32,
    )


def test_forecast_returns_every_sample_and_probabilistic_summaries(
    predictor,
    valid_inputs,
    monkeypatch,
):
    history, _, future = valid_inputs
    paths = _valid_paths()
    _install_paths(monkeypatch, predictor, history, paths)

    result = predictor.forecast(_request(valid_inputs, quantiles=(0.25, 0.75)))

    np.testing.assert_allclose(result.raw_sample_paths, paths, rtol=1e-6)
    np.testing.assert_allclose(result.validated_sample_paths, paths, rtol=1e-6)
    assert result.projected_sample_paths is None
    assert result.raw_sample_paths.shape == (2, 3, 6)
    assert result.summary_sample_count == 2
    assert result.summary_source == "valid_raw_paths"
    assert result.validity_report.passed
    assert result.repair_count == 0
    assert tuple(result.mean_path.index) == tuple(future)
    np.testing.assert_allclose(result.mean_path.to_numpy(), paths.mean(axis=0))
    np.testing.assert_allclose(result.median_path.to_numpy(), np.median(paths, axis=0))
    np.testing.assert_allclose(
        result.quantiles[0.25].to_numpy(),
        np.quantile(paths, 0.25, axis=0),
    )
    expected_returns = paths[:, :, 3] / history["close"].iloc[-1] - 1.0
    np.testing.assert_allclose(result.return_samples, expected_returns)
    np.testing.assert_allclose(
        result.probability_positive_return.to_numpy(),
        np.mean(expected_returns > 0.0, axis=0),
    )
    assert result.model_revision == "model-revision-test"
    assert result.dataset_version == "dataset-test"
    assert result.seed == 123
    assert result.generator_state is not None
    assert result.generator_state_sha256 == hashlib.sha256(result.generator_state).hexdigest()
    with pytest.raises(ValueError, match="read-only"):
        result.raw_sample_paths[0, 0, 0] = 0.0


def test_invalid_raw_candles_are_not_silently_repaired(
    predictor,
    valid_inputs,
    monkeypatch,
):
    history, _, _ = valid_inputs
    invalid = _valid_paths()[:1]
    invalid[0, 0] = [110.0, 105.0, 112.0, 108.0, -1.0, -2.0]
    _install_paths(monkeypatch, predictor, history, invalid)

    result = predictor.forecast(
        _request(valid_inputs, sample_count=1, projection_policy="none")
    )

    np.testing.assert_allclose(result.raw_sample_paths, invalid)
    assert result.validated_sample_paths.shape == (0, 3, 6)
    assert result.projected_sample_paths is None
    assert result.repair_count == 0
    assert result.repair_rules == ()
    assert not result.validity_report.raw_passed
    assert not result.validity_report.passed
    assert result.summary_sample_count == 0
    assert result.summary_source == "no_valid_paths"
    assert result.mean_path.isna().all().all()
    assert any("excluded" in warning for warning in result.warnings)


def test_explicit_projection_preserves_raw_and_accounts_for_every_repair(
    predictor,
    valid_inputs,
    monkeypatch,
):
    history, _, _ = valid_inputs
    invalid = _valid_paths()[:1]
    invalid[0, 0] = [110.0, 105.0, 112.0, 108.0, -1.0, -2.0]
    _install_paths(monkeypatch, predictor, history, invalid)

    result = predictor.forecast(
        _request(valid_inputs, sample_count=1, projection_policy="ohlcv_v1")
    )

    np.testing.assert_allclose(result.raw_sample_paths, invalid)
    projected = result.projected_sample_paths
    assert projected[0, 0, 1] == 110.0
    assert projected[0, 0, 2] == 108.0
    assert projected[0, 0, 4] == 0.0
    assert projected[0, 0, 5] == 0.0
    assert result.repair_count == 4
    assert len(result.repair_rules) == 4
    assert not result.validity_report.raw_passed
    assert result.validity_report.passed
    assert result.validated_sample_paths.shape == (1, 3, 6)
    assert result.summary_source == "explicitly_projected_valid_paths"
    assert len(result.validity_report.paths[0].repairs) == 4


def test_non_finite_output_is_reported_and_never_projected(
    predictor,
    valid_inputs,
    monkeypatch,
):
    history, _, _ = valid_inputs
    invalid = _valid_paths()[:1]
    invalid[0, 0, 3] = np.nan
    _install_paths(monkeypatch, predictor, history, invalid)

    result = predictor.forecast(
        _request(valid_inputs, sample_count=1, projection_policy="ohlcv_v1")
    )

    assert np.isnan(result.raw_sample_paths[0, 0, 3])
    assert np.isnan(result.projected_sample_paths[0, 0, 3])
    assert result.validated_sample_paths.shape[0] == 0
    assert result.repair_count == 0
    assert any(
        issue.code == "non_finite"
        for issue in result.validity_report.paths[0].output_issues
    )


def test_sample_paths_can_be_omitted_without_dropping_summaries(
    predictor,
    valid_inputs,
    monkeypatch,
):
    history, _, _ = valid_inputs
    paths = _valid_paths()
    _install_paths(monkeypatch, predictor, history, paths)

    result = predictor.forecast(_request(valid_inputs, return_sample_paths=False))

    assert result.raw_sample_paths is None
    assert result.validated_sample_paths is None
    assert result.projected_sample_paths is None
    assert result.return_samples.shape == (2, 3)
    assert result.summary_sample_count == 2


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"horizon": 2}, "future_timestamps length"),
        ({"historical_timestamps": pd.DatetimeIndex(["2025-01-01"] * 8)}, "strictly"),
        (
            {"future_timestamps": pd.date_range("2025-01-01", periods=3, freq="h", tz="UTC")},
            "later",
        ),
        ({"future_timestamps": pd.date_range("2025-01-02", periods=3, freq="h")}, "timezone"),
        ({"expected_frequency": "D"}, "frequency"),
    ],
)
def test_timestamp_contract_rejects_inconsistent_requests(
    predictor,
    valid_inputs,
    change,
    message,
):
    request = _request(valid_inputs, **change)
    with pytest.raises(ForecastRequestError, match=message):
        predictor.forecast(request)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ((0, "open", np.nan), "NaN or infinity"),
        ((0, "close", 0.0), "positive"),
        ((0, "high", 1.0), "high"),
        ((0, "low", 1000.0), "low"),
        ((0, "volume", -1.0), "non-negative"),
        ((0, "amount", -1.0), "non-negative"),
    ],
)
def test_history_candle_contract_rejects_contamination(
    predictor,
    valid_inputs,
    mutation,
    message,
):
    history, historical, future = valid_inputs
    history = history.copy()
    row, column, value = mutation
    history.loc[row, column] = value
    request = ForecastRequest(
        instrument_id="TEST",
        history=history,
        historical_timestamps=historical,
        future_timestamps=future,
        horizon=3,
        sample_count=1,
        seed=123,
    )
    with pytest.raises(ForecastRequestError, match=message):
        predictor.forecast(request)


def test_context_length_is_rejected_instead_of_silently_truncated(
    predictor,
    valid_inputs,
):
    history, _, _ = valid_inputs
    history = pd.concat([history] * 5, ignore_index=True)
    historical = pd.date_range("2025-01-01", periods=len(history), freq="h", tz="UTC")
    future = pd.date_range(historical[-1] + pd.Timedelta(hours=1), periods=3, freq="h")
    request = ForecastRequest(
        instrument_id="TEST",
        history=history,
        historical_timestamps=historical,
        future_timestamps=future,
        horizon=3,
        sample_count=1,
        seed=123,
    )
    with pytest.raises(ForecastRequestError, match="max_context"):
        predictor.forecast(request)


def test_stochastic_request_requires_isolated_randomness(valid_inputs):
    with pytest.raises(ForecastRequestError, match="explicit seed"):
        _request(valid_inputs, seed=None, generator=None)
    with pytest.raises(ForecastRequestError, match="mutually exclusive"):
        _request(valid_inputs, generator=torch.Generator())
    with pytest.raises(ForecastRequestError, match="sample_count=1"):
        _request(valid_inputs, deterministic=True)


def test_explicit_generator_is_accepted_and_recorded(
    predictor,
    valid_inputs,
    monkeypatch,
):
    history, _, _ = valid_inputs
    paths = _valid_paths()
    _install_paths(monkeypatch, predictor, history, paths)
    generator = torch.Generator().manual_seed(987)

    result = predictor.forecast(
        _request(valid_inputs, seed=None, generator=generator)
    )

    assert result.seed == 987
    assert result.generator_state is not None


def test_advanced_generator_state_is_captured_for_exact_reconstruction(
    predictor,
    valid_inputs,
):
    first_generator = torch.Generator().manual_seed(456)
    torch.rand(7, generator=first_generator)
    first_request = _request(
        valid_inputs,
        horizon=1,
        future_timestamps=valid_inputs[2][:1],
        seed=None,
        generator=first_generator,
    )
    first = predictor.forecast(first_request)

    reconstructed = torch.Generator()
    reconstructed.set_state(torch.frombuffer(bytearray(first.generator_state), dtype=torch.uint8))
    second_request = replace(first_request, generator=reconstructed)
    second = predictor.forecast(second_request)

    np.testing.assert_array_equal(first.raw_sample_paths, second.raw_sample_paths)


def test_invalid_code_commit_provenance_is_rejected(
    predictor,
    valid_inputs,
    monkeypatch,
):
    history, _, _ = valid_inputs
    _install_paths(monkeypatch, predictor, history, _valid_paths())
    predictor.code_commit = "not-a-git-sha"

    with pytest.raises(ForecastRequestError, match="40-character Git SHA"):
        predictor.forecast(_request(valid_inputs))


def test_seeded_stochastic_generation_is_repeatable_without_global_rng(
    predictor,
    valid_inputs,
):
    request = _request(valid_inputs, horizon=1, future_timestamps=valid_inputs[2][:1])
    torch.manual_seed(1)
    first = predictor.forecast(request)
    torch.manual_seed(9999)
    second = predictor.forecast(request)

    np.testing.assert_array_equal(first.raw_sample_paths, second.raw_sample_paths)


def test_greedy_generation_is_explicit_and_repeatable(predictor, valid_inputs):
    request = _request(
        valid_inputs,
        horizon=1,
        future_timestamps=valid_inputs[2][:1],
        sample_count=1,
        deterministic=True,
        seed=77,
    )
    first = predictor.forecast(request)
    torch.manual_seed(9999)
    second = predictor.forecast(request)

    np.testing.assert_array_equal(first.raw_sample_paths, second.raw_sample_paths)
    assert first.deterministic
    assert any("greedy" in warning for warning in first.warnings)


def test_legacy_mean_is_identical_to_mean_of_raw_paths(
    small_tokenizer_config,
    small_model_config,
):
    torch.manual_seed(42)
    tokenizer = KronosTokenizer(**small_tokenizer_config).eval()
    model = Kronos(**small_model_config).eval()
    x = torch.zeros((1, 4, 6), dtype=torch.float32)
    x_stamp = torch.zeros((1, 4, 5), dtype=torch.float32)
    y_stamp = torch.ones((1, 1, 5), dtype=torch.float32)
    first_generator = torch.Generator().manual_seed(321)
    second_generator = torch.Generator().manual_seed(321)

    samples = auto_regressive_inference(
        tokenizer,
        model,
        x,
        x_stamp,
        y_stamp,
        max_context=8,
        pred_len=1,
        top_p=1.0,
        sample_count=3,
        return_samples=True,
        generator=first_generator,
    )
    legacy_mean = auto_regressive_inference(
        tokenizer,
        model,
        x,
        x_stamp,
        y_stamp,
        max_context=8,
        pred_len=1,
        top_p=1.0,
        sample_count=3,
        generator=second_generator,
    )

    np.testing.assert_array_equal(legacy_mean, samples.mean(axis=1))


def test_request_is_a_typed_value_object(valid_inputs):
    request = _request(valid_inputs)
    deterministic = replace(request, deterministic=True, sample_count=1)
    assert deterministic.instrument_id == "TEST"
    assert deterministic.quantiles == (0.05, 0.5, 0.95)
