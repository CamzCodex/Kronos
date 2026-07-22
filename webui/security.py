"""Security boundary helpers for the local-only Web UI."""

from __future__ import annotations

import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any

ALLOWED_DATA_SUFFIXES = {".csv"}
ALLOWED_DEVICES = {"cpu", "cuda", "mps"}


class RequestValidationError(ValueError):
    """Raised when a Web UI request crosses a declared trust boundary."""


def require_json_object(value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RequestValidationError("Request body must be a JSON object")
    return value


def resolve_data_file(data_dir: Path, identifier: object, max_bytes: int) -> Path:
    if not isinstance(identifier, str) or not identifier:
        raise RequestValidationError("Data file must be selected")
    if len(identifier) > 255 or "\x00" in identifier:
        raise RequestValidationError("Invalid data file identifier")
    if "/" in identifier or "\\" in identifier or Path(identifier).name != identifier:
        raise RequestValidationError("Invalid data file identifier")

    data_root = data_dir.resolve()
    try:
        candidate = (data_root / identifier).resolve(strict=True)
        candidate.relative_to(data_root)
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise RequestValidationError("Selected data file is unavailable") from exc

    if not candidate.is_file() or candidate.suffix.lower() not in ALLOWED_DATA_SUFFIXES:
        raise RequestValidationError("Selected data file is unavailable")
    try:
        size = candidate.stat().st_size
    except OSError as exc:
        raise RequestValidationError("Selected data file is unavailable") from exc
    if size > max_bytes:
        raise RequestValidationError("Selected data file exceeds the local size limit")
    return candidate


def bounded_int(
    data: Mapping[str, Any],
    name: str,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    value = data.get(name, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise RequestValidationError(f"{name} must be an integer")
    if not minimum <= value <= maximum:
        raise RequestValidationError(f"{name} must be between {minimum} and {maximum}")
    return value


def bounded_float(
    data: Mapping[str, Any],
    name: str,
    default: float,
    minimum: float,
    maximum: float,
) -> float:
    value = data.get(name, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RequestValidationError(f"{name} must be a number")
    converted = float(value)
    if not math.isfinite(converted) or not minimum <= converted <= maximum:
        raise RequestValidationError(f"{name} must be between {minimum} and {maximum}")
    return converted


def validate_device(value: object) -> str:
    if not isinstance(value, str) or value not in ALLOWED_DEVICES:
        raise RequestValidationError("Unsupported model device")
    return value


def validate_optional_start_date(value: object) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str) or len(value) > 64:
        raise RequestValidationError("Invalid start_date")
    return value
