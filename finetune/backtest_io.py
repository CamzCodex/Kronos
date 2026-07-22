"""Safe data loading and signal persistence for Qlib inference/backtesting."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

import pandas as pd

try:
    from .archive_paths import load_named_frame_mapping, save_named_frame_mapping
except ImportError:  # Script-style execution from the finetune directory.
    from archive_paths import load_named_frame_mapping, save_named_frame_mapping


def load_test_data(
    dataset_directory: str | os.PathLike[str],
    *,
    allow_unsafe_pickle: bool = False,
) -> dict[str, pd.DataFrame]:
    """Load the canonical prepared test dataset through the safe resolver."""

    return load_named_frame_mapping(
        dataset_directory,
        "test_data",
        allow_unsafe_pickle=allow_unsafe_pickle,
    )


def save_prediction_signals(
    signals: Mapping[str, pd.DataFrame],
    result_directory: str | os.PathLike[str],
) -> Path:
    """Persist prediction signal DataFrames to `predictions.kronos.zip`."""

    return save_named_frame_mapping(signals, result_directory, "predictions")
