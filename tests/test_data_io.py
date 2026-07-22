"""Tests for the safe Kronos DataFrame archive format."""

from __future__ import annotations

import json
import pickle
import zipfile
from pathlib import Path

import pandas as pd
import pytest

from finetune import archive_writer, data_io, save_frame_mapping


def _sample_frames() -> dict[str, pd.DataFrame]:
    index = pd.date_range(
        "2025-01-01",
        periods=4,
        freq="5min",
        tz="Australia/Adelaide",
        name="datetime",
    )
    return {
        "AAPL": pd.DataFrame(
            {
                "open": [100.0, 101.5, 102.0, 101.0],
                "close": [101.0, 102.0, 101.5, 103.0],
                "volume": [10.0, 20.0, 15.0, 30.0],
            },
            index=index,
        ),
        "符号/二": pd.DataFrame(
            {
                "score": [0.1, float("nan"), -0.2, 0.0],
                "rank": [1, 2, 3, 4],
            },
            index=index,
        ),
    }


def _labelled_frames() -> dict[str, pd.DataFrame]:
    frames = {
        "B": pd.DataFrame({"value": [2.0]}),
        "A": pd.DataFrame({"value": [1.0]}),
    }
    for key, frame in frames.items():
        frame.attrs["label"] = key
    return frames


def _assert_frame_maps_equal(
    actual: dict[str, pd.DataFrame], expected: dict[str, pd.DataFrame]
) -> None:
    assert actual.keys() == expected.keys()
    for key in expected:
        pd.testing.assert_frame_equal(
            actual[key],
            expected[key],
            check_freq=False,
            check_dtype=False,
            check_exact=False,
            rtol=1e-12,
            atol=1e-12,
        )


def _rewrite_archive(
    source: Path,
    destination: Path,
    replacements: dict[str, bytes],
) -> None:
    with zipfile.ZipFile(source, "r") as original:
        members = {name: original.read(name) for name in original.namelist()}
    members.update(replacements)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as output:
        for name, payload in members.items():
            output.writestr(name, payload)


def test_public_save_paths_use_the_streaming_writer():
    assert save_frame_mapping is archive_writer.save_frame_mapping
    assert data_io.save_frame_mapping is archive_writer.save_frame_mapping


def test_safe_archive_round_trip(tmp_path):
    frames = _sample_frames()
    archive_path = tmp_path / "dataset.kronos.zip"

    written_path = data_io.save_frame_mapping(frames, archive_path)
    loaded = data_io.load_frame_mapping(written_path)

    assert written_path == archive_path
    _assert_frame_maps_equal(loaded, frames)


def test_safe_archive_is_deterministic(tmp_path):
    frames = _sample_frames()
    first = tmp_path / "first.kronos.zip"
    second = tmp_path / "second.kronos.zip"

    data_io.save_frame_mapping(frames, first)
    data_io.save_frame_mapping(dict(reversed(list(frames.items()))), second)

    assert first.read_bytes() == second.read_bytes()


def test_frames_are_written_before_the_next_frame_is_serialized(tmp_path, monkeypatch):
    events: list[tuple[str, str]] = []
    original_serialize = archive_writer._frame_to_bytes
    original_write = archive_writer._write_member

    def tracked_serialize(frame: pd.DataFrame) -> bytes:
        events.append(("serialize", frame.attrs["label"]))
        return original_serialize(frame)

    def tracked_write(archive, name: str, payload: bytes) -> None:
        events.append(("write", name))
        original_write(archive, name, payload)

    monkeypatch.setattr(archive_writer, "_frame_to_bytes", tracked_serialize)
    monkeypatch.setattr(archive_writer, "_write_member", tracked_write)

    archive_writer.save_frame_mapping(
        _labelled_frames(),
        tmp_path / "streamed.kronos.zip",
    )

    assert events == [
        ("serialize", "A"),
        ("write", "frames/00000000.json"),
        ("serialize", "B"),
        ("write", "frames/00000001.json"),
        ("write", data_io.MANIFEST_NAME),
    ]


def test_failed_streaming_write_preserves_existing_destination(tmp_path, monkeypatch):
    destination = tmp_path / "dataset.kronos.zip"
    original_bytes = b"existing archive placeholder"
    destination.write_bytes(original_bytes)
    original_serialize = archive_writer._frame_to_bytes

    def fail_on_second_frame(frame: pd.DataFrame) -> bytes:
        if frame.attrs["label"] == "B":
            raise RuntimeError("synthetic serialization failure")
        return original_serialize(frame)

    monkeypatch.setattr(archive_writer, "_frame_to_bytes", fail_on_second_frame)

    with pytest.raises(RuntimeError, match="synthetic serialization failure"):
        archive_writer.save_frame_mapping(_labelled_frames(), destination)

    assert destination.read_bytes() == original_bytes
    assert not list(tmp_path.glob(f".{destination.name}.*.tmp"))


def test_legacy_pickle_is_blocked_before_deserialisation(tmp_path, monkeypatch):
    legacy_path = tmp_path / "dataset.pkl"
    with legacy_path.open("wb") as handle:
        pickle.dump(_sample_frames(), handle)

    def fail_if_called(_handle):
        pytest.fail("pickle.load must not be called without explicit authorisation")

    monkeypatch.setattr(data_io.pickle, "load", fail_if_called)
    with pytest.raises(data_io.UnsafeLegacyFormatError, match="refusing to load"):
        data_io.load_frame_mapping(legacy_path)


def test_explicit_legacy_migration_round_trip(tmp_path):
    frames = _sample_frames()
    legacy_path = tmp_path / "dataset.pkl"
    safe_path = tmp_path / "dataset.kronos.zip"
    with legacy_path.open("wb") as handle:
        pickle.dump(frames, handle)

    with pytest.warns(RuntimeWarning, match="trusted local file"):
        migrated = data_io.migrate_legacy_pickle(
            legacy_path,
            safe_path,
            allow_unsafe_pickle=True,
        )

    assert migrated == safe_path
    _assert_frame_maps_equal(data_io.load_frame_mapping(safe_path), frames)


def test_checksum_tampering_is_rejected(tmp_path):
    source = tmp_path / "valid.kronos.zip"
    tampered = tmp_path / "tampered.kronos.zip"
    data_io.save_frame_mapping(_sample_frames(), source)

    with zipfile.ZipFile(source, "r") as archive:
        manifest = json.loads(archive.read(data_io.MANIFEST_NAME))
        member_name = manifest["entries"][0]["path"]
        payload = bytearray(archive.read(member_name))
    payload[len(payload) // 2] ^= 1
    _rewrite_archive(source, tampered, {member_name: bytes(payload)})

    with pytest.raises(data_io.DataArchiveError, match="checksum mismatch"):
        data_io.load_frame_mapping(tampered)


def test_path_traversal_member_is_rejected(tmp_path):
    archive_path = tmp_path / "unsafe.kronos.zip"
    manifest = {
        "format": data_io.FORMAT_NAME,
        "version": data_io.FORMAT_VERSION,
        "frame_count": 0,
        "entries": [],
    }
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr(data_io.MANIFEST_NAME, json.dumps(manifest))
        archive.writestr("../escape.json", b"{}")

    with pytest.raises(data_io.DataArchiveError, match="unsafe archive member"):
        data_io.load_frame_mapping(archive_path)


def test_unreferenced_member_is_rejected(tmp_path):
    archive_path = tmp_path / "extra.kronos.zip"
    manifest = {
        "format": data_io.FORMAT_NAME,
        "version": data_io.FORMAT_VERSION,
        "frame_count": 0,
        "entries": [],
    }
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr(data_io.MANIFEST_NAME, json.dumps(manifest))
        archive.writestr("frames/unreferenced.json", b"{}")

    with pytest.raises(data_io.DataArchiveError, match="unreferenced members"):
        data_io.load_frame_mapping(archive_path)


def test_archive_size_limit_is_enforced(tmp_path):
    archive_path = tmp_path / "dataset.kronos.zip"
    data_io.save_frame_mapping(_sample_frames(), archive_path)

    with pytest.raises(data_io.DataArchiveError, match="size limit"):
        data_io.load_safe_frame_mapping(
            archive_path,
            max_member_bytes=1,
        )


def test_invalid_mapping_values_are_rejected(tmp_path):
    with pytest.raises(data_io.DataArchiveError, match="keys must be strings"):
        data_io.save_frame_mapping({1: pd.DataFrame()}, tmp_path / "bad.zip")
    with pytest.raises(data_io.DataArchiveError, match="not a pandas DataFrame"):
        data_io.save_frame_mapping({"bad": []}, tmp_path / "bad.zip")
