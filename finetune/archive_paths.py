"""Path conventions and safe/legacy resolution for prepared Kronos datasets."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

import pandas as pd

try:
    from .data_io import (
        UnsafeLegacyFormatError,
        load_frame_mapping,
        save_frame_mapping,
    )
except ImportError:  # Script-style execution from the finetune directory.
    from data_io import (
        UnsafeLegacyFormatError,
        load_frame_mapping,
        save_frame_mapping,
    )

SAFE_ARCHIVE_SUFFIX = ".kronos.zip"
LEGACY_PICKLE_SUFFIX = ".pkl"


def _validate_dataset_name(name: str) -> str:
    if not isinstance(name, str) or not name:
        raise ValueError("dataset name must be a non-empty string")
    if name in {".", ".."} or "/" in name or "\\" in name:
        raise ValueError("dataset name must not contain path separators")
    if Path(name).name != name:
        raise ValueError("dataset name must not contain path separators")
    return name


def safe_archive_path(
    directory: str | os.PathLike[str],
    name: str,
) -> Path:
    """Return the canonical safe archive path for a named dataset."""

    name = _validate_dataset_name(name)
    return Path(directory) / f"{name}{SAFE_ARCHIVE_SUFFIX}"


def legacy_pickle_path(
    directory: str | os.PathLike[str],
    name: str,
) -> Path:
    """Return the historical pickle path for a named dataset."""

    name = _validate_dataset_name(name)
    return Path(directory) / f"{name}{LEGACY_PICKLE_SUFFIX}"


def save_named_frame_mapping(
    data: Mapping[str, pd.DataFrame],
    directory: str | os.PathLike[str],
    name: str,
) -> Path:
    """Save a prepared dataset under the canonical safe filename."""

    return save_frame_mapping(data, safe_archive_path(directory, name))


def load_named_frame_mapping(
    directory: str | os.PathLike[str],
    name: str,
    *,
    allow_unsafe_pickle: bool = False,
) -> dict[str, pd.DataFrame]:
    """Load a safe named dataset, with explicit trusted legacy compatibility.

    The safe archive always wins when both formats exist. A legacy pickle is
    never loaded implicitly; callers must opt in after verifying the file's
    origin and integrity.
    """

    safe_path = safe_archive_path(directory, name)
    legacy_path = legacy_pickle_path(directory, name)

    if safe_path.is_file():
        return load_frame_mapping(safe_path)

    if legacy_path.is_file():
        if allow_unsafe_pickle:
            return load_frame_mapping(
                legacy_path,
                allow_unsafe_pickle=True,
            )
        migration_command = (
            f"python -m finetune.data_io {legacy_path!s} {safe_path!s} "
            "--allow-unsafe-pickle"
        )
        raise UnsafeLegacyFormatError(
            f"found legacy pickle {legacy_path}, but unsafe pickle loading is disabled. "
            "For a trusted local file, migrate it with:\n"
            f"  {migration_command}"
        )

    raise FileNotFoundError(
        f"prepared dataset {name!r} was not found. Expected {safe_path}; "
        f"legacy compatibility path is {legacy_path}"
    )
