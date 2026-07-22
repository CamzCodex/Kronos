"""Memory-bounded writer for Kronos DataFrame archives.

The archive reader and file format live in :mod:`finetune.data_io`.  This
module keeps writing separate so prepared datasets can be serialized one
DataFrame at a time rather than retaining every JSON payload in memory.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import zipfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pandas as pd

try:
    from .data_io import (
        FORMAT_NAME,
        FORMAT_VERSION,
        MANIFEST_NAME,
        _frame_to_bytes,
        _validate_frame_mapping,
        _write_member,
    )
except ImportError:  # Script-style execution from the finetune directory.
    from data_io import (
        FORMAT_NAME,
        FORMAT_VERSION,
        MANIFEST_NAME,
        _frame_to_bytes,
        _validate_frame_mapping,
        _write_member,
    )

_JSON_ENCODING = "utf-8"


def _manifest_bytes(entries: list[dict[str, Any]]) -> bytes:
    manifest = {
        "format": FORMAT_NAME,
        "version": FORMAT_VERSION,
        "frame_count": len(entries),
        "entries": entries,
    }
    return json.dumps(
        manifest,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode(_JSON_ENCODING)


def save_frame_mapping(
    data: Mapping[str, pd.DataFrame],
    path: str | os.PathLike[str],
) -> Path:
    """Atomically stream a deterministic, checksummed frame archive.

    At most one serialized DataFrame payload is retained at a time.  Member
    metadata is accumulated in memory and the manifest is written last.  ZIP
    member order is not part of format semantics, and existing readers locate
    members by name.
    """

    frames = _validate_frame_mapping(data)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
    )
    os.close(file_descriptor)
    temporary_path = Path(temporary_name)

    entries: list[dict[str, Any]] = []
    try:
        with zipfile.ZipFile(temporary_path, mode="w") as archive:
            for index, key in enumerate(sorted(frames)):
                member_path = f"frames/{index:08d}.json"
                payload = _frame_to_bytes(frames[key])
                _write_member(archive, member_path, payload)
                entries.append(
                    {
                        "key": key,
                        "path": member_path,
                        "sha256": hashlib.sha256(payload).hexdigest(),
                        "size": len(payload),
                    }
                )
                del payload

            _write_member(archive, MANIFEST_NAME, _manifest_bytes(entries))

        with temporary_path.open("rb") as handle:
            os.fsync(handle.fileno())
        os.replace(temporary_path, destination)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise

    return destination
