"""Leakage-gated evaluation protocols for Kronos research."""

from .baselines import (
    BASELINE_FEATURE_COLUMNS,
    BASELINE_SUITE_VERSION,
    MANDATORY_BASELINES,
    BaselineFitError,
    BaselineRequest,
    BaselineRequestError,
    BaselineResult,
    required_history_size,
    run_baseline_suite,
)
from .walk_forward import (
    AuditedWalkForwardFold,
    EvaluationContext,
    ExcludedWindow,
    FoldBoundary,
    WalkForwardConfig,
    WalkForwardFold,
    WalkForwardMode,
    WalkForwardPlan,
    attach_leakage_audit,
    build_walk_forward_plan,
    write_walk_forward_plan,
)

__all__ = [
    "BASELINE_FEATURE_COLUMNS",
    "BASELINE_SUITE_VERSION",
    "MANDATORY_BASELINES",
    "AuditedWalkForwardFold",
    "BaselineFitError",
    "BaselineRequest",
    "BaselineRequestError",
    "BaselineResult",
    "EvaluationContext",
    "ExcludedWindow",
    "FoldBoundary",
    "WalkForwardConfig",
    "WalkForwardFold",
    "WalkForwardMode",
    "WalkForwardPlan",
    "attach_leakage_audit",
    "build_walk_forward_plan",
    "required_history_size",
    "run_baseline_suite",
    "write_walk_forward_plan",
]
