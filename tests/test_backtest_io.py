"""Tests for safe Qlib inference and backtest persistence."""

from __future__ import annotations

import ast
import pickle
from pathlib import Path

import pandas as pd
import pytest

from finetune import archive_paths, backtest_io, data_io


def _test_data() -> dict[str, pd.DataFrame]:
    index = pd.date_range("2025-01-01", periods=4, freq="D", name="datetime")
    return {
        "TEST": pd.DataFrame(
            {
                "open": [10.0, 11.0, 12.0, 13.0],
                "high": [11.0, 12.0, 13.0, 14.0],
                "low": [9.0, 10.0, 11.0, 12.0],
                "close": [10.5, 11.5, 12.5, 13.5],
                "vol": [100.0, 110.0, 120.0, 130.0],
                "amt": [1_000.0, 1_100.0, 1_200.0, 1_300.0],
            },
            index=index,
        )
    }


def _signals() -> dict[str, pd.DataFrame]:
    index = pd.date_range("2025-02-01", periods=3, freq="D", name="datetime")
    return {
        "mean": pd.DataFrame({"TEST": [0.1, -0.2, 0.3]}, index=index),
        "last": pd.DataFrame({"TEST": [0.2, -0.1, 0.4]}, index=index),
    }


def _assert_mapping_equal(
    actual: dict[str, pd.DataFrame], expected: dict[str, pd.DataFrame]
) -> None:
    assert actual.keys() == expected.keys()
    for name in expected:
        pd.testing.assert_frame_equal(
            actual[name],
            expected[name],
            check_freq=False,
            check_dtype=False,
            check_exact=False,
            rtol=1e-12,
            atol=1e-12,
        )


def test_load_test_data_uses_the_canonical_safe_archive(tmp_path):
    expected = _test_data()
    archive_paths.save_named_frame_mapping(expected, tmp_path, "test_data")

    actual = backtest_io.load_test_data(tmp_path)

    _assert_mapping_equal(actual, expected)


def test_load_test_data_refuses_legacy_pickle_before_deserialisation(
    tmp_path, monkeypatch
):
    legacy_path = archive_paths.legacy_pickle_path(tmp_path, "test_data")
    with legacy_path.open("wb") as handle:
        pickle.dump(_test_data(), handle)

    def fail_if_called(_handle):
        pytest.fail("backtest loading must not touch pickle without explicit opt-in")

    monkeypatch.setattr(data_io.pickle, "load", fail_if_called)
    with pytest.raises(data_io.UnsafeLegacyFormatError):
        backtest_io.load_test_data(tmp_path)


def test_load_test_data_allows_explicit_trusted_legacy_compatibility(tmp_path):
    expected = _test_data()
    legacy_path = archive_paths.legacy_pickle_path(tmp_path, "test_data")
    with legacy_path.open("wb") as handle:
        pickle.dump(expected, handle)

    with pytest.warns(RuntimeWarning, match="trusted local file"):
        actual = backtest_io.load_test_data(
            tmp_path,
            allow_unsafe_pickle=True,
        )

    _assert_mapping_equal(actual, expected)


def test_prediction_signals_round_trip_through_safe_archive(tmp_path):
    expected = _signals()

    path = backtest_io.save_prediction_signals(expected, tmp_path)
    actual = archive_paths.load_named_frame_mapping(tmp_path, "predictions")

    assert path == tmp_path / "predictions.kronos.zip"
    _assert_mapping_equal(actual, expected)


def test_qlib_test_source_contains_no_direct_pickle_calls():
    source_path = Path(__file__).resolve().parents[1] / "finetune" / "qlib_test.py"
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(source_path))

    pickle_imports: list[ast.AST] = []
    pickle_calls: list[ast.Call] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            pickle_imports.extend(
                node for alias in node.names if alias.name == "pickle"
            )
        elif isinstance(node, ast.ImportFrom) and node.module == "pickle":
            pickle_imports.append(node)
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "pickle"
        ):
            pickle_calls.append(node)

    assert not pickle_imports
    assert not pickle_calls
    assert "load_test_data" in source
    assert "save_prediction_signals" in source
    assert "predictions.pkl" not in source
