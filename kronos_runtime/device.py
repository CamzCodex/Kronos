"""Device selection shared by local operational commands."""

from __future__ import annotations

import platform
import re
import sys
from importlib.metadata import PackageNotFoundError, version
from typing import Any

import torch


def resolve_device(requested: str = "auto") -> torch.device:
    """Resolve an explicit device and fail clearly when it is unavailable."""

    if not isinstance(requested, str):
        raise TypeError("device must be a string")
    requested = requested.strip().lower()
    if requested == "auto":
        if torch.cuda.is_available():
            requested = "cuda:0"
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            requested = "mps"
        else:
            requested = "cpu"

    if requested == "cpu":
        return torch.device("cpu")
    if requested == "mps":
        if not hasattr(torch.backends, "mps") or not torch.backends.mps.is_available():
            raise RuntimeError("MPS was requested but is not available")
        return torch.device("mps")
    if requested == "cuda" or requested.startswith("cuda:"):
        if not torch.cuda.is_available():
            raise RuntimeError(
                "CUDA/ROCm was requested but this PyTorch build reports no compatible GPU"
            )
        device = torch.device(requested)
        index = 0 if device.index is None else device.index
        if index < 0 or index >= torch.cuda.device_count():
            raise RuntimeError(
                f"GPU index {index} is unavailable; detected {torch.cuda.device_count()} device(s)"
            )
        return torch.device("cuda", index)
    raise ValueError("device must be auto, cpu, mps, cuda, or cuda:<index>")


def _package_version(distribution: str) -> str:
    try:
        return version(distribution)
    except PackageNotFoundError:
        return "not-installed"


def _torch_meets_generic_security_floor() -> bool:
    """Return whether the public version is newer than the known affected range."""

    match = re.match(r"^(\d+)\.(\d+)", torch.__version__)
    return bool(match and tuple(map(int, match.groups())) >= (2, 11))


def device_report(requested: str = "auto") -> dict[str, Any]:
    """Return a JSON-serializable local runtime and accelerator report."""

    device = resolve_device(requested)
    cuda_available = torch.cuda.is_available()
    mps_available = bool(
        hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
    )
    gpu_names = (
        [torch.cuda.get_device_name(index) for index in range(torch.cuda.device_count())]
        if cuda_available
        else []
    )
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "kronos_package": _package_version("kronos-timeseries"),
        "torch": torch.__version__,
        "torch_generic_security_floor": "2.11",
        "torch_meets_generic_security_floor": _torch_meets_generic_security_floor(),
        "torch_cuda_runtime": torch.version.cuda,
        "torch_rocm_runtime": torch.version.hip,
        "cuda_api_available": cuda_available,
        "mps_available": mps_available,
        "gpu_names": gpu_names,
        "selected_device": str(device),
        "accelerated": device.type in {"cuda", "mps"},
    }
