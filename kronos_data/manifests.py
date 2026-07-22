"""Deterministic dataset identity and immutable manifest persistence."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from .adjustments import coerce_adjustment_policy
from .hashing import (
    _json_value,
    canonical_json,
    hash_configuration,
    hash_dataframe,
)
from .schema import FEATURE_SCHEMA_VERSION
from .validation import ValidationReport

_SHA256 = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class DatasetManifest:
    dataset_id: str
    source: str
    created_at: str
    frequency: str
    universe: str
    start: str
    end: str
    adjustment_policy: str
    feature_schema_version: str
    raw_data_hashes: dict[str, str]
    split_boundaries: dict[str, Any]
    code_commit: str
    configuration_hash: str
    content_hash: str
    validation: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return _json_value(self.__dict__)

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        ) + "\n"


def build_dataset_manifest(
    bars: pd.DataFrame,
    *,
    source: str,
    created_at: pd.Timestamp | str,
    frequency: str,
    universe: str,
    adjustment_policy: str,
    raw_data_hashes: Mapping[str, str],
    split_boundaries: Mapping[str, Any],
    code_commit: str,
    configuration: Mapping[str, Any],
    validation_report: ValidationReport,
    feature_schema_version: str = FEATURE_SCHEMA_VERSION,
) -> DatasetManifest:
    if not validation_report.passed:
        raise ValueError("a failed market-data validation report cannot produce a manifest")
    input_hash = hash_dataframe(bars, sort_rows=False)
    if validation_report.input_hash != input_hash:
        raise ValueError("validation report does not match the supplied canonical bars")
    created = pd.Timestamp(created_at)
    if created.tzinfo is None or created.utcoffset() is None:
        raise ValueError("created_at must be timezone-aware")
    required_text = (source, frequency, universe, code_commit)
    if not all(value.strip() for value in required_text):
        raise ValueError("source, frequency, universe, and code_commit must be non-empty")
    if not re.fullmatch(r"[0-9a-f]{7,64}", code_commit):
        raise ValueError("code_commit must be a lowercase hexadecimal Git commit SHA")
    if feature_schema_version != validation_report.feature_schema_version:
        raise ValueError("feature schema version does not match the validation report")
    policy = coerce_adjustment_policy(adjustment_policy).value
    declared_frequencies = set(bars["frequency"].dropna().astype(str))
    if declared_frequencies != {frequency}:
        raise ValueError("manifest frequency must match every canonical bar")
    declared_sources = set(bars["source"].dropna().astype(str))
    if declared_sources != {source}:
        raise ValueError("manifest source must match every canonical bar")
    hashes = dict(sorted(raw_data_hashes.items()))
    if not hashes:
        raise ValueError("raw_data_hashes must contain at least one source object")
    if any(not name.strip() for name in hashes):
        raise ValueError("raw_data_hashes keys must be non-empty source identifiers")
    invalid_hashes = {name: value for name, value in hashes.items() if not _SHA256.fullmatch(value)}
    if invalid_hashes:
        invalid_names = sorted(invalid_hashes)
        raise ValueError(
            f"raw_data_hashes contains invalid SHA-256 values: {invalid_names}"
        )
    if not split_boundaries:
        raise ValueError("split_boundaries must declare at least one evaluation split")

    content_hash = hash_dataframe(bars)
    if validation_report.content_hash != content_hash:
        raise ValueError("validation report content hash does not match canonical bars")
    configuration_hash = hash_configuration(configuration)
    valid_times = pd.to_datetime(bars["timestamp_utc"], utc=True)
    ingested_times = pd.to_datetime(bars["ingested_at"], utc=True)
    if created.tz_convert("UTC") < ingested_times.max():
        raise ValueError("created_at cannot precede the latest ingested_at timestamp")
    identity = {
        "source": source,
        "frequency": frequency,
        "universe": universe,
        "start": valid_times.min().isoformat(),
        "end": valid_times.max().isoformat(),
        "adjustment_policy": policy,
        "feature_schema_version": feature_schema_version,
        "raw_data_hashes": hashes,
        "split_boundaries": split_boundaries,
        "code_commit": code_commit,
        "configuration_hash": configuration_hash,
        "content_hash": content_hash,
    }
    dataset_id = f"kds-{hashlib.sha256(canonical_json(identity).encode('utf-8')).hexdigest()[:24]}"
    return DatasetManifest(
        dataset_id=dataset_id,
        source=source,
        created_at=created.tz_convert("UTC").isoformat(),
        frequency=frequency,
        universe=universe,
        start=identity["start"],
        end=identity["end"],
        adjustment_policy=policy,
        feature_schema_version=feature_schema_version,
        raw_data_hashes=hashes,
        split_boundaries=_json_value(split_boundaries),
        code_commit=code_commit,
        configuration_hash=configuration_hash,
        content_hash=content_hash,
        validation=validation_report.to_dict(),
    )


def write_manifest(manifest: DatasetManifest, path: str | os.PathLike[str]) -> Path:
    """Write once, or accept an identical existing manifest."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = manifest.to_json().encode("utf-8")
    if destination.exists():
        if destination.read_bytes() == payload:
            return destination
        raise FileExistsError(f"refusing to replace immutable manifest {destination}")

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return destination
