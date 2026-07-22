from __future__ import annotations

import json

import pandas as pd
import pytest

from kronos_data import (
    ValidationConfig,
    build_dataset_manifest,
    hash_dataframe,
    sha256_file,
    validate_bars,
    write_manifest,
)


def _bars() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "instrument_id": ["AAPL", "AAPL"],
            "timestamp_utc": pd.to_datetime(
                ["2025-01-02T20:00:00Z", "2025-01-03T20:00:00Z"], utc=True
            ),
            "exchange": ["XNAS", "XNAS"],
            "currency": ["USD", "USD"],
            "frequency": ["1D", "1D"],
            "open": [100.0, 101.0],
            "high": [102.0, 103.0],
            "low": [99.0, 100.0],
            "close": [101.0, 102.0],
            "volume": [1_000.0, 1_100.0],
            "amount": [101_000.0, 112_200.0],
            "adjustment_factor": [1.0, 1.0],
            "is_adjusted": [True, True],
            "source": ["fixture", "fixture"],
            "ingested_at": pd.to_datetime(
                ["2025-01-04T00:00:00Z", "2025-01-04T00:00:00Z"], utc=True
            ),
        }
    )


def _manifest(bars: pd.DataFrame):
    report = validate_bars(bars, ValidationConfig())
    assert report.passed
    return build_dataset_manifest(
        bars,
        source="fixture",
        created_at=pd.Timestamp("2025-01-05T00:00:00Z"),
        frequency="1D",
        universe="AAPL fixture",
        adjustment_policy="backward_adjusted",
        raw_data_hashes={"fixture.csv": "a" * 64},
        split_boundaries={"test": {"start": "2025-01-02", "end": "2025-01-03"}},
        code_commit="0123456789abcdef",
        configuration={"frequency": "1D", "lookback": 90},
        validation_report=report,
    )


def test_dataframe_hash_is_row_order_independent_but_content_sensitive():
    bars = _bars()
    reordered = bars.iloc[::-1].copy()
    changed = bars.copy()
    changed.loc[0, "close"] = 100.5

    assert hash_dataframe(bars) == hash_dataframe(reordered)
    assert hash_dataframe(bars) != hash_dataframe(changed)


def test_manifest_identity_is_deterministic():
    first = _manifest(_bars())
    second = _manifest(_bars().copy())

    assert first.dataset_id == second.dataset_id
    assert first.configuration_hash == second.configuration_hash
    assert first.content_hash == second.content_hash
    assert first.to_json() == second.to_json()
    assert first.dataset_id.startswith("kds-")


def test_manifest_rejects_validation_report_from_different_input_order():
    bars = _bars()
    report = validate_bars(bars)
    reordered = bars.iloc[::-1].copy()

    with pytest.raises(ValueError, match="validation report does not match"):
        build_dataset_manifest(
            reordered,
            source="fixture",
            created_at="2025-01-05T00:00:00Z",
            frequency="1D",
            universe="fixture",
            adjustment_policy="backward_adjusted",
            raw_data_hashes={"fixture.csv": "a" * 64},
            split_boundaries={},
            code_commit="0123456",
            configuration={},
            validation_report=report,
        )


def test_failed_validation_cannot_produce_manifest():
    bars = _bars()
    bars.loc[0, "low"] = 999.0
    report = validate_bars(bars)

    with pytest.raises(ValueError, match="failed market-data validation"):
        build_dataset_manifest(
            bars,
            source="fixture",
            created_at="2025-01-05T00:00:00Z",
            frequency="1D",
            universe="fixture",
            adjustment_policy="backward_adjusted",
            raw_data_hashes={"fixture.csv": "a" * 64},
            split_boundaries={},
            code_commit="0123456",
            configuration={},
            validation_report=report,
        )


def test_manifest_write_is_immutable_and_idempotent(tmp_path):
    manifest = _manifest(_bars())
    path = tmp_path / "manifest.json"

    first = write_manifest(manifest, path)
    second = write_manifest(manifest, path)

    assert first == second == path
    assert json.loads(path.read_text())["dataset_id"] == manifest.dataset_id

    path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(FileExistsError, match="immutable manifest"):
        write_manifest(manifest, path)


def test_raw_hashes_must_be_sha256():
    bars = _bars()
    report = validate_bars(bars)

    with pytest.raises(ValueError, match="invalid SHA-256"):
        build_dataset_manifest(
            bars,
            source="fixture",
            created_at="2025-01-05T00:00:00Z",
            frequency="1D",
            universe="fixture",
            adjustment_policy="backward_adjusted",
            raw_data_hashes={"fixture.csv": "not-a-hash"},
            split_boundaries={},
            code_commit="0123456",
            configuration={},
            validation_report=report,
        )


def test_manifest_created_at_cannot_precede_ingestion():
    bars = _bars()
    report = validate_bars(bars)

    with pytest.raises(ValueError, match="cannot precede"):
        build_dataset_manifest(
            bars,
            source="fixture",
            created_at="2025-01-03T00:00:00Z",
            frequency="1D",
            universe="fixture",
            adjustment_policy="backward_adjusted",
            raw_data_hashes={"fixture.csv": "a" * 64},
            split_boundaries={"test": {"start": "2025-01-02", "end": "2025-01-03"}},
            code_commit="0123456",
            configuration={},
            validation_report=report,
        )


def test_sha256_file_streams_known_content(tmp_path):
    path = tmp_path / "raw.csv"
    path.write_bytes(b"abc")

    assert sha256_file(path) == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )
