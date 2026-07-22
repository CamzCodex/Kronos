"""Safe, deterministic storage for mappings of names to pandas DataFrames.

Kronos historically used :mod:`pickle` for prepared Qlib datasets and
backtest outputs.  Loading an untrusted pickle can execute arbitrary Python
code.  This module provides a versioned ZIP container containing only JSON and
SHA-256 checksums, plus an explicitly gated migration helper for legacy files.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import pickle
import re
import stat
import warnings
import zipfile
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any

import pandas as pd

FORMAT_NAME = "kronos-frame-map"
FORMAT_VERSION = 1
MANIFEST_NAME = "manifest.json"
DEFAULT_MAX_MEMBERS = 100_001
DEFAULT_MAX_MEMBER_BYTES = 2 * 1024**3
DEFAULT_MAX_UNCOMPRESSED_BYTES = 64 * 1024**3
_JSON_ENCODING = "utf-8"
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


class DataArchiveError(ValueError):
    """Raised when a Kronos data archive is malformed or fails validation."""


class UnsafeLegacyFormatError(DataArchiveError):
    """Raised when loading a pickle was not explicitly authorised."""


def _validate_frame_mapping(data: Any) -> dict[str, pd.DataFrame]:
    if not isinstance(data, Mapping):
        raise DataArchiveError("data must be a mapping of string keys to DataFrames")

    validated: dict[str, pd.DataFrame] = {}
    for key, frame in data.items():
        if not isinstance(key, str):
            raise DataArchiveError("all frame-map keys must be strings")
        if key in validated:
            raise DataArchiveError(f"duplicate frame-map key: {key!r}")
        if not isinstance(frame, pd.DataFrame):
            raise DataArchiveError(f"value for {key!r} is not a pandas DataFrame")
        if not frame.columns.is_unique:
            raise DataArchiveError(f"DataFrame {key!r} has duplicate column names")
        validated[key] = frame
    return validated


def _member_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(filename=name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = (stat.S_IFREG | 0o644) << 16
    return info


def _write_member(archive: zipfile.ZipFile, name: str, payload: bytes) -> None:
    archive.writestr(
        _member_info(name),
        payload,
        compress_type=zipfile.ZIP_DEFLATED,
        compresslevel=6,
    )


def _frame_to_bytes(frame: pd.DataFrame) -> bytes:
    text = frame.to_json(
        orient="table",
        date_format="iso",
        date_unit="ns",
        double_precision=15,
        index=True,
    )
    return text.encode(_JSON_ENCODING)


def _frame_from_bytes(payload: bytes, *, key: str) -> pd.DataFrame:
    try:
        text = payload.decode(_JSON_ENCODING)
        frame = pd.read_json(io.StringIO(text), orient="table")
    except (UnicodeDecodeError, ValueError, TypeError) as exc:
        raise DataArchiveError(f"could not decode DataFrame {key!r}") from exc
    if not isinstance(frame, pd.DataFrame):
        raise DataArchiveError(f"decoded value for {key!r} is not a DataFrame")
    return frame


def save_frame_mapping(
    data: Mapping[str, pd.DataFrame],
    path: str | os.PathLike[str],
) -> Path:
    """Atomically write through the memory-bounded archive implementation.

    The import is deliberately lazy.  It avoids a module-import cycle while
    ensuring both ``python -m finetune.data_io`` and direct script execution
    use the same one-frame-at-a-time writer as package callers.
    """

    try:
        from .archive_writer import save_frame_mapping as stream_save
    except ImportError:  # Script-style execution from the finetune directory.
        from archive_writer import save_frame_mapping as stream_save

    return stream_save(data, path)


def _validate_member_name(name: str) -> None:
    if not name or "\\" in name:
        raise DataArchiveError(f"unsafe archive member path: {name!r}")
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise DataArchiveError(f"unsafe archive member path: {name!r}")


def _read_manifest(archive: zipfile.ZipFile) -> dict[str, Any]:
    try:
        payload = archive.read(MANIFEST_NAME)
    except KeyError as exc:
        raise DataArchiveError("archive is missing manifest.json") from exc
    try:
        manifest = json.loads(payload.decode(_JSON_ENCODING))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DataArchiveError("manifest.json is not valid UTF-8 JSON") from exc
    if not isinstance(manifest, dict):
        raise DataArchiveError("manifest root must be a JSON object")
    return manifest


def _validate_archive_structure(
    archive: zipfile.ZipFile,
    *,
    max_members: int,
    max_member_bytes: int,
    max_uncompressed_bytes: int,
) -> dict[str, zipfile.ZipInfo]:
    infos = archive.infolist()
    if len(infos) > max_members:
        raise DataArchiveError(
            f"archive contains {len(infos)} members; limit is {max_members}"
        )

    members: dict[str, zipfile.ZipInfo] = {}
    total_size = 0
    for info in infos:
        _validate_member_name(info.filename)
        if info.filename in members:
            raise DataArchiveError(f"archive contains duplicate member {info.filename!r}")
        if info.is_dir():
            raise DataArchiveError(f"archive contains unexpected directory {info.filename!r}")
        if info.flag_bits & 0x1:
            raise DataArchiveError("encrypted ZIP members are not supported")
        unix_mode = info.external_attr >> 16
        if unix_mode and stat.S_ISLNK(unix_mode):
            raise DataArchiveError(f"archive member {info.filename!r} is a symbolic link")
        if info.file_size > max_member_bytes:
            raise DataArchiveError(
                f"archive member {info.filename!r} exceeds the size limit"
            )
        total_size += info.file_size
        if total_size > max_uncompressed_bytes:
            raise DataArchiveError("archive exceeds the total uncompressed size limit")
        members[info.filename] = info
    return members


def load_safe_frame_mapping(
    path: str | os.PathLike[str],
    *,
    max_members: int = DEFAULT_MAX_MEMBERS,
    max_member_bytes: int = DEFAULT_MAX_MEMBER_BYTES,
    max_uncompressed_bytes: int = DEFAULT_MAX_UNCOMPRESSED_BYTES,
) -> dict[str, pd.DataFrame]:
    """Load and validate a Kronos JSON/ZIP frame archive."""

    source = Path(path)
    if max_members < 1 or max_member_bytes < 1 or max_uncompressed_bytes < 1:
        raise ValueError("archive safety limits must be positive integers")
    if not source.is_file():
        raise FileNotFoundError(source)
    if not zipfile.is_zipfile(source):
        raise DataArchiveError(f"{source} is not a valid ZIP archive")

    try:
        with zipfile.ZipFile(source, mode="r") as archive:
            members = _validate_archive_structure(
                archive,
                max_members=max_members,
                max_member_bytes=max_member_bytes,
                max_uncompressed_bytes=max_uncompressed_bytes,
            )
            manifest = _read_manifest(archive)

            if manifest.get("format") != FORMAT_NAME:
                raise DataArchiveError("unsupported archive format")
            if manifest.get("version") != FORMAT_VERSION:
                raise DataArchiveError(
                    f"unsupported archive version: {manifest.get('version')!r}"
                )

            entries = manifest.get("entries")
            if not isinstance(entries, list):
                raise DataArchiveError("manifest entries must be a list")
            if manifest.get("frame_count") != len(entries):
                raise DataArchiveError("manifest frame_count does not match entries")

            expected_members = {MANIFEST_NAME}
            result: dict[str, pd.DataFrame] = {}
            for entry in entries:
                if not isinstance(entry, dict):
                    raise DataArchiveError("each manifest entry must be an object")
                key = entry.get("key")
                member_path = entry.get("path")
                expected_hash = entry.get("sha256")
                expected_size = entry.get("size")

                if not isinstance(key, str) or key in result:
                    raise DataArchiveError("manifest keys must be unique strings")
                if not isinstance(member_path, str):
                    raise DataArchiveError(f"manifest path for {key!r} is invalid")
                _validate_member_name(member_path)
                if not member_path.startswith("frames/") or not member_path.endswith(
                    ".json"
                ):
                    raise DataArchiveError(f"manifest path for {key!r} is invalid")
                if member_path in expected_members:
                    raise DataArchiveError(f"duplicate manifest path {member_path!r}")
                if member_path not in members:
                    raise DataArchiveError(f"archive is missing {member_path!r}")
                if not isinstance(expected_hash, str) or not _SHA256_PATTERN.fullmatch(
                    expected_hash
                ):
                    raise DataArchiveError(f"checksum for {key!r} is invalid")
                if (
                    isinstance(expected_size, bool)
                    or not isinstance(expected_size, int)
                    or expected_size < 0
                ):
                    raise DataArchiveError(f"size for {key!r} is invalid")

                info = members[member_path]
                if info.file_size != expected_size:
                    raise DataArchiveError(f"size mismatch for {key!r}")
                payload = archive.read(member_path)
                if hashlib.sha256(payload).hexdigest() != expected_hash:
                    raise DataArchiveError(f"checksum mismatch for {key!r}")

                result[key] = _frame_from_bytes(payload, key=key)
                expected_members.add(member_path)

            unexpected = set(members) - expected_members
            if unexpected:
                raise DataArchiveError(
                    f"archive contains unreferenced members: {sorted(unexpected)!r}"
                )
            return result
    except zipfile.BadZipFile as exc:
        raise DataArchiveError(f"{source} is not a valid ZIP archive") from exc


def load_legacy_pickle(
    path: str | os.PathLike[str],
    *,
    allow_unsafe_pickle: bool = False,
) -> dict[str, pd.DataFrame]:
    """Load a legacy pickle only after an explicit unsafe opt-in.

    Pickle can execute arbitrary code during loading.  This function is meant
    solely for migration of files whose origin and integrity are already
    trusted.
    """

    source = Path(path)
    if not allow_unsafe_pickle:
        raise UnsafeLegacyFormatError(
            "refusing to load a pickle without allow_unsafe_pickle=True; "
            "migrate trusted files to the Kronos JSON/ZIP format"
        )
    warnings.warn(
        f"loading legacy pickle {source}; only continue for a trusted local file",
        RuntimeWarning,
        stacklevel=2,
    )
    with source.open("rb") as handle:
        data = pickle.load(handle)
    return _validate_frame_mapping(data)


def load_frame_mapping(
    path: str | os.PathLike[str],
    *,
    allow_unsafe_pickle: bool = False,
    **safe_load_limits: int,
) -> dict[str, pd.DataFrame]:
    """Load a safe archive, or an explicitly authorised legacy pickle."""

    source = Path(path)
    if source.suffix.lower() in {".pkl", ".pickle"}:
        if safe_load_limits:
            raise TypeError("archive safety limits do not apply to legacy pickle files")
        return load_legacy_pickle(
            source,
            allow_unsafe_pickle=allow_unsafe_pickle,
        )
    return load_safe_frame_mapping(source, **safe_load_limits)


def migrate_legacy_pickle(
    source: str | os.PathLike[str],
    destination: str | os.PathLike[str],
    *,
    allow_unsafe_pickle: bool = False,
) -> Path:
    """Migrate one explicitly trusted pickle into the safe archive format."""

    data = load_legacy_pickle(
        source,
        allow_unsafe_pickle=allow_unsafe_pickle,
    )
    return save_frame_mapping(data, destination)


def _build_cli() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Migrate trusted Kronos pickle datasets to safe JSON/ZIP archives"
    )
    parser.add_argument("source", type=Path, help="trusted .pkl or .pickle file")
    parser.add_argument("destination", type=Path, help="output .kronos.zip archive")
    parser.add_argument(
        "--allow-unsafe-pickle",
        action="store_true",
        help="acknowledge that loading the source may execute arbitrary code",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_cli().parse_args(argv)
    migrate_legacy_pickle(
        args.source,
        args.destination,
        allow_unsafe_pickle=args.allow_unsafe_pickle,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
