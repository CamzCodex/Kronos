"""Integration tests for prepared-dataset archive resolution and loading."""

from __future__ import annotations

import ast
import pickle
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from finetune import archive_paths, data_io
from finetune import dataset as dataset_module
from finetune.config import Config


def _frames(rows: int = 8) -> dict[str, pd.DataFrame]:
    index = pd.date_range("2025-01-01", periods=rows, freq="D", name="datetime")
    base = np.arange(rows, dtype=np.float32) + 10.0
    return {
        "TEST": pd.DataFrame(
            {
                "open": base,
                "high": base + 1.0,
                "low": base - 1.0,
                "close": base + 0.5,
                "vol": base * 100.0,
                "amt": base * 1_000.0,
            },
            index=index,
        )
    }


def _assert_semantically_equal(actual: pd.DataFrame, expected: pd.DataFrame) -> None:
    pd.testing.assert_frame_equal(
        actual,
        expected,
        check_freq=False,
        check_dtype=False,
        check_exact=False,
        rtol=1e-12,
        atol=1e-12,
    )


def test_canonical_archive_paths_reject_path_injection(tmp_path):
    assert archive_paths.safe_archive_path(tmp_path, "train_data") == (
        tmp_path / "train_data.kronos.zip"
    )
    assert archive_paths.legacy_pickle_path(tmp_path, "train_data") == (
        tmp_path / "train_data.pkl"
    )

    for invalid in (
        "",
        ".",
        "..",
        "../train_data",
        "nested/train_data",
        r"nested\train_data",
    ):
        with pytest.raises(ValueError, match="dataset name"):
            archive_paths.safe_archive_path(tmp_path, invalid)


def test_safe_archive_is_preferred_over_legacy_pickle(tmp_path, monkeypatch):
    expected = _frames()
    archive_paths.save_named_frame_mapping(expected, tmp_path, "train_data")
    archive_paths.legacy_pickle_path(tmp_path, "train_data").write_bytes(b"not a pickle")

    def fail_if_called(_handle):
        pytest.fail("safe archive resolution must not attempt pickle loading")

    monkeypatch.setattr(data_io.pickle, "load", fail_if_called)
    actual = archive_paths.load_named_frame_mapping(tmp_path, "train_data")

    _assert_semantically_equal(actual["TEST"], expected["TEST"])


def test_legacy_pickle_is_blocked_with_a_migration_command(tmp_path, monkeypatch):
    legacy_path = archive_paths.legacy_pickle_path(tmp_path, "train_data")
    with legacy_path.open("wb") as handle:
        pickle.dump(_frames(), handle)

    def fail_if_called(_handle):
        pytest.fail("blocked legacy resolution must not call pickle.load")

    monkeypatch.setattr(data_io.pickle, "load", fail_if_called)
    with pytest.raises(data_io.UnsafeLegacyFormatError) as error:
        archive_paths.load_named_frame_mapping(tmp_path, "train_data")

    message = str(error.value)
    assert "python -m finetune.data_io" in message
    assert "--allow-unsafe-pickle" in message
    assert str(legacy_path) in message


def test_explicit_trusted_legacy_compatibility(tmp_path):
    expected = _frames()
    legacy_path = archive_paths.legacy_pickle_path(tmp_path, "train_data")
    with legacy_path.open("wb") as handle:
        pickle.dump(expected, handle)

    with pytest.warns(RuntimeWarning, match="trusted local file"):
        actual = archive_paths.load_named_frame_mapping(
            tmp_path,
            "train_data",
            allow_unsafe_pickle=True,
        )

    pd.testing.assert_frame_equal(actual["TEST"], expected["TEST"])


def test_missing_prepared_dataset_lists_both_expected_paths(tmp_path):
    with pytest.raises(FileNotFoundError) as error:
        archive_paths.load_named_frame_mapping(tmp_path, "val_data")

    message = str(error.value)
    assert "val_data.kronos.zip" in message
    assert "val_data.pkl" in message


def test_qlib_dataset_loads_the_safe_archive(tmp_path, monkeypatch):
    archive_paths.save_named_frame_mapping(_frames(), tmp_path, "train_data")

    class TestConfig:
        seed = 7
        dataset_path = str(tmp_path)
        allow_unsafe_pickle = False
        n_train_iter = 10
        n_val_iter = 5
        lookback_window = 3
        predict_window = 2
        clip = 5.0
        feature_list = ["open", "high", "low", "close", "vol", "amt"]
        time_feature_list = ["minute", "hour", "weekday", "day", "month"]

    monkeypatch.setattr(dataset_module, "Config", TestConfig)
    dataset = dataset_module.QlibDataset("train")

    assert dataset.data_path == tmp_path / "train_data.kronos.zip"
    assert len(dataset) == 3
    features, timestamps = dataset[0]
    assert features.shape == (6, 6)
    assert timestamps.shape == (6, 5)


def test_qlib_dataset_refuses_legacy_pickle_by_default(tmp_path, monkeypatch):
    with archive_paths.legacy_pickle_path(tmp_path, "train_data").open("wb") as handle:
        pickle.dump(_frames(), handle)

    class TestConfig:
        seed = 7
        dataset_path = str(tmp_path)
        allow_unsafe_pickle = False
        n_train_iter = 10
        n_val_iter = 5
        lookback_window = 3
        predict_window = 2
        clip = 5.0
        feature_list = ["open", "high", "low", "close", "vol", "amt"]
        time_feature_list = ["minute", "hour", "weekday", "day", "month"]

    monkeypatch.setattr(dataset_module, "Config", TestConfig)
    with pytest.raises(data_io.UnsafeLegacyFormatError):
        dataset_module.QlibDataset("train")


def test_unsafe_pickle_compatibility_defaults_to_false():
    assert Config().allow_unsafe_pickle is False


def test_script_style_dataset_import_remains_supported():
    repository_root = Path(__file__).resolve().parents[1]
    finetune_directory = repository_root / "finetune"
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import archive_paths; import dataset; assert dataset.QlibDataset is not None",
        ],
        cwd=finetune_directory,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_training_dataset_sources_have_no_direct_pickle_calls():
    repository_root = Path(__file__).resolve().parents[1]
    guarded_sources = [
        repository_root / "finetune" / "dataset.py",
        repository_root / "finetune" / "qlib_data_preprocess.py",
    ]

    for source_path in guarded_sources:
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        imported_pickle_names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "pickle":
                        imported_pickle_names.add(alias.asname or alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module == "pickle":
                imported_pickle_names.update(alias.asname or alias.name for alias in node.names)

        assert not imported_pickle_names, (
            f"{source_path.relative_to(repository_root)} must use finetune.data_io "
            "instead of importing pickle directly"
        )
