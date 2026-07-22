"""Canonical hashing primitives shared by validation and manifests."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .schema import CANONICAL_BAR_FIELDS


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, np.bool_, int)):
        if isinstance(value, np.bool_):
            return bool(value)
        return value
    if isinstance(value, float):
        if not np.isfinite(value):
            raise ValueError("hash inputs cannot contain NaN or infinity")
        return value
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        numeric = float(value)
        if not np.isfinite(numeric):
            raise ValueError("hash inputs cannot contain NaN or infinity")
        return numeric
    if isinstance(value, pd.Timestamp):
        if value.tzinfo is None:
            raise ValueError("hash timestamps must be timezone-aware")
        return value.tz_convert("UTC").isoformat()
    if isinstance(value, Mapping):
        ordered = sorted(value.items(), key=lambda pair: str(pair[0]))
        return {str(key): _json_value(item) for key, item in ordered}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    raise TypeError(f"unsupported hash value type: {type(value).__name__}")


def canonical_json(value: Any) -> str:
    return json.dumps(
        _json_value(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def hash_configuration(configuration: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(configuration).encode("utf-8")).hexdigest()


def sha256_file(path: str | os.PathLike[str], chunk_size: int = 1024 * 1024) -> str:
    if chunk_size < 1:
        raise ValueError("chunk_size must be positive")
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_dataframe(frame: pd.DataFrame, *, sort_rows: bool = True) -> str:
    missing = [field for field in CANONICAL_BAR_FIELDS if field not in frame.columns]
    if missing:
        raise ValueError(f"cannot hash bars missing canonical fields: {missing}")
    canonical = frame.loc[:, CANONICAL_BAR_FIELDS].copy()
    canonical["timestamp_utc"] = pd.to_datetime(canonical["timestamp_utc"], utc=True)
    canonical["ingested_at"] = pd.to_datetime(canonical["ingested_at"], utc=True)
    if sort_rows:
        canonical = canonical.sort_values(
            ["instrument_id", "timestamp_utc"], kind="mergesort"
        )
    records = [
        [_json_value(value) for value in row]
        for row in canonical.itertuples(index=False, name=None)
    ]
    payload = {"columns": list(CANONICAL_BAR_FIELDS), "records": records}
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
