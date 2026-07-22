"""Corporate-action adjustment policy declarations."""

from __future__ import annotations

from enum import Enum


class AdjustmentPolicy(str, Enum):
    """Declared relationship between stored bars and corporate actions."""

    RAW = "raw"
    BACKWARD = "backward_adjusted"
    FORWARD = "forward_adjusted"
    SPLIT_ONLY = "split_adjusted"
    TOTAL_RETURN = "total_return_adjusted"
    DECLARED = "declared_per_row"


def coerce_adjustment_policy(value: AdjustmentPolicy | str) -> AdjustmentPolicy:
    if isinstance(value, AdjustmentPolicy):
        return value
    try:
        return AdjustmentPolicy(value)
    except ValueError as exc:
        supported = ", ".join(policy.value for policy in AdjustmentPolicy)
        raise ValueError(
            f"unsupported adjustment policy {value!r}; expected one of {supported}"
        ) from exc
