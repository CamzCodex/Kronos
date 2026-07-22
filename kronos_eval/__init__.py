"""Leakage-gated evaluation protocols for Kronos research."""

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
    "AuditedWalkForwardFold",
    "EvaluationContext",
    "ExcludedWindow",
    "FoldBoundary",
    "WalkForwardConfig",
    "WalkForwardFold",
    "WalkForwardMode",
    "WalkForwardPlan",
    "attach_leakage_audit",
    "build_walk_forward_plan",
    "write_walk_forward_plan",
]
