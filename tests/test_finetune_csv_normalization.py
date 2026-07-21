"""Regression tests for causal normalization in the custom CSV dataset."""

from pathlib import Path
import sys

import numpy as np
import pandas as pd
import torch

# ``finetune_csv`` still uses script-style imports. Add that directory exactly
# as the training entry points do until the package-layout cleanup lands.
FINETUNE_CSV_DIR = Path(__file__).resolve().parents[1] / "finetune_csv"
sys.path.insert(0, str(FINETUNE_CSV_DIR))

from finetune_base_model import CustomKlineDataset  # noqa: E402


FEATURE_COLUMNS = ["open", "high", "low", "close", "volume", "amount"]
TIME_COLUMNS = ["minute", "hour", "weekday", "day", "month"]
LOOKBACK = 3
WINDOW = 6


def _make_dataset(future_rows: np.ndarray) -> CustomKlineDataset:
    history = np.array(
        [
            [10.0, 11.0, 9.0, 10.5, 100.0, 1_000.0],
            [11.0, 12.0, 10.0, 11.5, 110.0, 1_100.0],
            [12.0, 13.0, 11.0, 12.5, 120.0, 1_200.0],
        ],
        dtype=np.float32,
    )
    # One trailing row keeps ``max_start`` positive; index zero still selects
    # exactly the history plus the three supplied target-period rows.
    trailing = np.array(
        [[16.0, 17.0, 15.0, 16.5, 160.0, 1_600.0]], dtype=np.float32
    )
    values = np.concatenate([history, future_rows, trailing], axis=0)

    frame = pd.DataFrame(values, columns=FEATURE_COLUMNS)
    frame[TIME_COLUMNS] = np.array(
        [[0, 9, 0, 1, 1]] * len(frame), dtype=np.float32
    )

    dataset = CustomKlineDataset.__new__(CustomKlineDataset)
    dataset.lookback_window = LOOKBACK
    dataset.window = WINDOW
    dataset.clip = 1_000_000.0
    dataset.data_type = "val"
    dataset.data = frame
    dataset.feature_list = FEATURE_COLUMNS
    dataset.time_feature_list = TIME_COLUMNS
    return dataset


def test_target_values_cannot_change_history_encoding():
    ordinary_future = np.array(
        [
            [13.0, 14.0, 12.0, 13.5, 130.0, 1_300.0],
            [14.0, 15.0, 13.0, 14.5, 140.0, 1_400.0],
            [15.0, 16.0, 14.0, 15.5, 150.0, 1_500.0],
        ],
        dtype=np.float32,
    )
    extreme_future = ordinary_future.copy()
    extreme_future[:, :4] *= 1_000.0
    extreme_future[:, 4:] *= -500.0

    ordinary, _ = _make_dataset(ordinary_future)[0]
    extreme, _ = _make_dataset(extreme_future)[0]

    torch.testing.assert_close(ordinary[:LOOKBACK], extreme[:LOOKBACK])


def test_history_is_standardized_from_its_own_statistics():
    future = np.array(
        [
            [13.0, 14.0, 12.0, 13.5, 130.0, 1_300.0],
            [14.0, 15.0, 13.0, 14.5, 140.0, 1_400.0],
            [15.0, 16.0, 14.0, 15.5, 150.0, 1_500.0],
        ],
        dtype=np.float32,
    )

    normalized, _ = _make_dataset(future)[0]
    history = normalized[:LOOKBACK].numpy()

    np.testing.assert_allclose(history.mean(axis=0), 0.0, atol=2e-5)
    np.testing.assert_allclose(history.std(axis=0), 1.0, atol=2e-5)
