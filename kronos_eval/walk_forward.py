"""Deterministic expanding and rolling walk-forward split plans."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from numbers import Integral
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from kronos_data.hashing import hash_configuration
from kronos_data.leakage import (
    REQUIRED_LEAKAGE_CHECKS,
    LeakageAuditResult,
    SplitBoundary,
    SplitRole,
    hash_split_boundaries,
)


class WalkForwardMode(str, Enum):
    EXPANDING = "expanding"
    ROLLING = "rolling"


@dataclass(frozen=True)
class WalkForwardConfig:
    """Observation-count split protocol for an ordered validated timestamp index."""

    mode: WalkForwardMode | str
    train_size: int
    validation_size: int
    test_size: int
    final_holdout_size: int
    calibration_size: int = 0
    purge_size: int = 0
    embargo_size: int = 0
    step_size: int | None = None
    minimum_folds: int = 2
    maximum_folds: int | None = None

    def __post_init__(self) -> None:
        try:
            mode = (
                self.mode
                if isinstance(self.mode, WalkForwardMode)
                else WalkForwardMode(self.mode)
            )
        except ValueError as exc:
            raise ValueError("mode must be 'expanding' or 'rolling'") from exc
        object.__setattr__(self, "mode", mode)
        for name in (
            "train_size",
            "validation_size",
            "test_size",
            "final_holdout_size",
            "minimum_folds",
        ):
            _positive_integer(getattr(self, name), name)
        for name in ("calibration_size", "purge_size", "embargo_size"):
            _non_negative_integer(getattr(self, name), name)
        if self.step_size is not None:
            _positive_integer(self.step_size, "step_size")
            if self.step_size < self.fold_stride_floor:
                raise ValueError(
                    "step_size cannot reuse validation, calibration, purge, or test "
                    f"observations across folds; minimum is {self.fold_stride_floor}"
                )
        if self.maximum_folds is not None:
            _positive_integer(self.maximum_folds, "maximum_folds")
            if self.maximum_folds < self.minimum_folds:
                raise ValueError("maximum_folds cannot be smaller than minimum_folds")

    @property
    def purge_transition_count(self) -> int:
        return 3 if self.calibration_size else 2

    @property
    def fold_stride_floor(self) -> int:
        return (
            self.validation_size
            + self.calibration_size
            + self.test_size
            + self.purge_size * self.purge_transition_count
        )

    @property
    def effective_step_size(self) -> int:
        return self.step_size or self.fold_stride_floor

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "train_size": self.train_size,
            "validation_size": self.validation_size,
            "calibration_size": self.calibration_size,
            "test_size": self.test_size,
            "final_holdout_size": self.final_holdout_size,
            "purge_size": self.purge_size,
            "embargo_size": self.embargo_size,
            "step_size": self.step_size,
            "effective_step_size": self.effective_step_size,
            "minimum_folds": self.minimum_folds,
            "maximum_folds": self.maximum_folds,
        }


@dataclass(frozen=True)
class EvaluationContext:
    """Immutable experiment identity copied into every fold record."""

    dataset_id: str
    code_commit: str
    feature_schema_version: str
    model_revision: str
    cost_assumptions_json: str
    seed: int

    def __post_init__(self) -> None:
        for name in ("dataset_id", "feature_schema_version", "model_revision"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if not isinstance(self.code_commit, str) or re.fullmatch(
            r"[0-9a-f]{7,64}", self.code_commit
        ) is None:
            raise ValueError("code_commit must be a lowercase hexadecimal Git SHA")
        if isinstance(self.seed, bool) or not isinstance(self.seed, Integral):
            raise TypeError("seed must be an integer")
        if not 0 <= int(self.seed) < 2**63:
            raise ValueError("seed must be between 0 and 2**63 - 1")
        assumptions = _parse_json_object(self.cost_assumptions_json, "cost_assumptions_json")
        if not assumptions:
            raise ValueError("cost_assumptions_json must declare at least one assumption")
        canonical = _canonical_json(assumptions)
        if canonical != self.cost_assumptions_json:
            raise ValueError("cost_assumptions_json must use canonical JSON encoding")

    @classmethod
    def create(
        cls,
        *,
        dataset_id: str,
        code_commit: str,
        feature_schema_version: str,
        model_revision: str,
        cost_assumptions: Mapping[str, Any],
        seed: int,
    ) -> EvaluationContext:
        return cls(
            dataset_id=dataset_id,
            code_commit=code_commit,
            feature_schema_version=feature_schema_version,
            model_revision=model_revision,
            cost_assumptions_json=_canonical_json(dict(cost_assumptions)),
            seed=seed,
        )

    @property
    def cost_assumptions(self) -> dict[str, Any]:
        return json.loads(self.cost_assumptions_json)

    @property
    def cost_assumptions_hash(self) -> str:
        return hashlib.sha256(self.cost_assumptions_json.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "code_commit": self.code_commit,
            "feature_schema_version": self.feature_schema_version,
            "model_revision": self.model_revision,
            "cost_assumptions": self.cost_assumptions,
            "cost_assumptions_hash": self.cost_assumptions_hash,
            "seed": int(self.seed),
        }


@dataclass(frozen=True)
class FoldBoundary:
    name: str
    role: SplitRole
    start: pd.Timestamp
    end: pd.Timestamp
    start_position: int
    end_position: int
    observation_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "role": self.role.value,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "start_position": self.start_position,
            "end_position": self.end_position,
            "observation_count": self.observation_count,
        }


@dataclass(frozen=True)
class ExcludedWindow:
    name: str
    reason: str
    start: pd.Timestamp
    end: pd.Timestamp
    start_position: int
    end_position: int
    observation_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "reason": self.reason,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "start_position": self.start_position,
            "end_position": self.end_position,
            "observation_count": self.observation_count,
        }


@dataclass(frozen=True)
class WalkForwardFold:
    fold_id: str
    fold_number: int
    mode: WalkForwardMode
    dataset_id: str
    code_commit: str
    feature_schema_version: str
    model_revision: str
    cost_assumptions_json: str
    cost_assumptions_hash: str
    seed: int
    configuration_hash: str
    train: FoldBoundary
    validation: FoldBoundary
    calibration: FoldBoundary | None
    test: FoldBoundary
    final_holdout: FoldBoundary
    purged_windows: tuple[ExcludedWindow, ...]
    final_embargo: ExcludedWindow | None
    split_hash: str

    @property
    def cost_assumptions(self) -> dict[str, Any]:
        return json.loads(self.cost_assumptions_json)

    def split_boundaries(self) -> tuple[SplitBoundary, ...]:
        boundaries = [
            _audit_boundary(self.train),
            _audit_boundary(self.validation),
        ]
        if self.calibration is not None:
            boundaries.append(_audit_boundary(self.calibration))
        boundaries.extend([_audit_boundary(self.test), _audit_boundary(self.final_holdout)])
        return tuple(boundaries)

    def to_dict(self) -> dict[str, Any]:
        return {
            "fold_id": self.fold_id,
            "fold_number": self.fold_number,
            "mode": self.mode.value,
            "dataset_id": self.dataset_id,
            "code_commit": self.code_commit,
            "feature_schema_version": self.feature_schema_version,
            "model_revision": self.model_revision,
            "cost_assumptions": self.cost_assumptions,
            "cost_assumptions_hash": self.cost_assumptions_hash,
            "seed": self.seed,
            "configuration_hash": self.configuration_hash,
            "train": self.train.to_dict(),
            "validation": self.validation.to_dict(),
            "calibration": self.calibration.to_dict() if self.calibration else None,
            "test": self.test.to_dict(),
            "final_holdout": self.final_holdout.to_dict(),
            "purged_windows": [window.to_dict() for window in self.purged_windows],
            "final_embargo": self.final_embargo.to_dict() if self.final_embargo else None,
            "split_hash": self.split_hash,
        }


@dataclass(frozen=True)
class WalkForwardPlan:
    plan_id: str
    created_at: pd.Timestamp
    timestamp_index_hash: str
    configuration: WalkForwardConfig
    configuration_hash: str
    context: EvaluationContext
    folds: tuple[WalkForwardFold, ...]
    candidate_fold_count: int
    folds_truncated: bool
    final_holdout: FoldBoundary
    final_embargo: ExcludedWindow | None
    unused_development_window: ExcludedWindow | None

    @property
    def decision_grade_fold_count_met(self) -> bool:
        return len(self.folds) >= 2

    @property
    def decision_grade_protocol(self) -> bool:
        return self.decision_grade_fold_count_met and not self.folds_truncated

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "created_at": self.created_at.isoformat(),
            "timestamp_index_hash": self.timestamp_index_hash,
            "configuration": self.configuration.to_dict(),
            "configuration_hash": self.configuration_hash,
            "context": self.context.to_dict(),
            "fold_count": len(self.folds),
            "candidate_fold_count": self.candidate_fold_count,
            "folds_truncated": self.folds_truncated,
            "decision_grade_fold_count_met": self.decision_grade_fold_count_met,
            "decision_grade_protocol": self.decision_grade_protocol,
            "folds": [fold.to_dict() for fold in self.folds],
            "final_holdout": self.final_holdout.to_dict(),
            "final_embargo": self.final_embargo.to_dict() if self.final_embargo else None,
            "unused_development_window": (
                self.unused_development_window.to_dict()
                if self.unused_development_window
                else None
            ),
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        ) + "\n"


@dataclass(frozen=True)
class AuditedWalkForwardFold:
    """Only this passed, identity-bound object is eligible for evaluation."""

    fold: WalkForwardFold
    leakage_audit: LeakageAuditResult

    def to_dict(self) -> dict[str, Any]:
        return {
            "fold": self.fold.to_dict(),
            "leakage_audit": self.leakage_audit.to_dict(),
        }


def build_walk_forward_plan(
    timestamps: object,
    *,
    configuration: WalkForwardConfig,
    context: EvaluationContext,
    created_at: pd.Timestamp | str,
) -> WalkForwardPlan:
    """Build a deterministic split plan from validated ordered observation times."""

    if not isinstance(configuration, WalkForwardConfig):
        raise TypeError("configuration must be a WalkForwardConfig")
    if not isinstance(context, EvaluationContext):
        raise TypeError("context must be an EvaluationContext")
    index = _validated_index(timestamps)
    created = _aware_timestamp(created_at, "created_at")
    if created < index[-1]:
        raise ValueError("created_at cannot precede the latest dataset timestamp")
    configuration_hash = hash_configuration(configuration.to_dict())
    timestamp_index_hash = hashlib.sha256(index.asi8.tobytes()).hexdigest()

    final_start = len(index) - configuration.final_holdout_size
    if final_start <= 0:
        raise ValueError("final_holdout_size leaves no development observations")
    final_holdout = _boundary(
        index,
        name="final_holdout",
        role=SplitRole.FINAL_HOLDOUT,
        start_position=final_start,
        end_position=len(index) - 1,
    )
    final_embargo_start = final_start - configuration.embargo_size
    if final_embargo_start < 0:
        raise ValueError("embargo_size leaves no development observations")
    final_embargo = _excluded(
        index,
        name="final_holdout_embargo",
        reason="embargo",
        start_position=final_embargo_start,
        end_position=final_start - 1,
    )
    development_end = final_embargo_start - 1

    candidates: list[tuple[int, int, int, int, int | None, int | None, int, int]] = []
    offset = 0
    while True:
        train_start = 0 if configuration.mode is WalkForwardMode.EXPANDING else offset
        train_end = configuration.train_size - 1 + offset
        validation_start = train_end + configuration.purge_size + 1
        validation_end = validation_start + configuration.validation_size - 1
        cursor = validation_end
        calibration_start: int | None = None
        calibration_end: int | None = None
        if configuration.calibration_size:
            calibration_start = cursor + configuration.purge_size + 1
            calibration_end = calibration_start + configuration.calibration_size - 1
            cursor = calibration_end
        test_start = cursor + configuration.purge_size + 1
        test_end = test_start + configuration.test_size - 1
        if test_end > development_end:
            break
        candidates.append(
            (
                train_start,
                train_end,
                validation_start,
                validation_end,
                calibration_start,
                calibration_end,
                test_start,
                test_end,
            )
        )
        offset += configuration.effective_step_size

    candidate_fold_count = len(candidates)
    if configuration.maximum_folds is not None:
        candidates = candidates[-configuration.maximum_folds :]
    if len(candidates) < configuration.minimum_folds:
        raise ValueError(
            f"split protocol produced {len(candidates)} folds; "
            f"minimum_folds={configuration.minimum_folds}"
        )

    identity_payload = {
        "timestamp_index_hash": timestamp_index_hash,
        "timestamp_count": len(index),
        "timestamp_start": index[0].isoformat(),
        "timestamp_end": index[-1].isoformat(),
        "configuration_hash": configuration_hash,
        "context": context.to_dict(),
    }
    plan_id = f"kwf-{hash_configuration(identity_payload)[:24]}"

    folds = tuple(
        _build_fold(
            index,
            candidate,
            fold_number=fold_number,
            plan_id=plan_id,
            configuration=configuration,
            configuration_hash=configuration_hash,
            context=context,
            final_holdout=final_holdout,
            final_embargo=final_embargo,
        )
        for fold_number, candidate in enumerate(candidates)
    )
    last_test_end = folds[-1].test.end_position
    unused_development = _excluded(
        index,
        name="unused_development_tail",
        reason="unused_development",
        start_position=last_test_end + 1,
        end_position=development_end,
    )
    return WalkForwardPlan(
        plan_id=plan_id,
        created_at=created,
        timestamp_index_hash=timestamp_index_hash,
        configuration=configuration,
        configuration_hash=configuration_hash,
        context=context,
        folds=folds,
        candidate_fold_count=candidate_fold_count,
        folds_truncated=len(folds) < candidate_fold_count,
        final_holdout=final_holdout,
        final_embargo=final_embargo,
        unused_development_window=unused_development,
    )


def attach_leakage_audit(
    fold: WalkForwardFold,
    audit: LeakageAuditResult,
) -> AuditedWalkForwardFold:
    """Bind a passed audit to exactly the fold split identity it evaluated."""

    if not isinstance(fold, WalkForwardFold):
        raise TypeError("fold must be a WalkForwardFold")
    if not isinstance(audit, LeakageAuditResult):
        raise TypeError("audit must be a LeakageAuditResult")
    if not audit.passed:
        raise ValueError("failed leakage audits invalidate a fold")
    if audit.dataset_id != fold.dataset_id:
        raise ValueError("leakage audit dataset_id does not match the fold")
    if audit.code_commit != fold.code_commit:
        raise ValueError("leakage audit code_commit does not match the fold")
    if audit.split_hash != fold.split_hash:
        raise ValueError("leakage audit split_hash does not match the fold boundaries")
    if not audit.audit_id.startswith("kla-"):
        raise ValueError("leakage audit identity is invalid")
    missing_checks = set(REQUIRED_LEAKAGE_CHECKS) - set(audit.checks)
    if missing_checks:
        raise ValueError(
            f"leakage audit is missing required checks: {sorted(missing_checks)}"
        )
    return AuditedWalkForwardFold(fold=fold, leakage_audit=audit)


def write_walk_forward_plan(
    plan: WalkForwardPlan,
    path: str | os.PathLike[str],
) -> Path:
    """Persist a plan once, accepting only a byte-identical existing artifact."""

    if not isinstance(plan, WalkForwardPlan):
        raise TypeError("plan must be a WalkForwardPlan")
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = plan.to_json().encode("utf-8")
    if destination.exists():
        if destination.read_bytes() == payload:
            return destination
        raise FileExistsError(f"refusing to replace immutable plan {destination}")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
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


def _build_fold(
    index: pd.DatetimeIndex,
    candidate: tuple[int, int, int, int, int | None, int | None, int, int],
    *,
    fold_number: int,
    plan_id: str,
    configuration: WalkForwardConfig,
    configuration_hash: str,
    context: EvaluationContext,
    final_holdout: FoldBoundary,
    final_embargo: ExcludedWindow | None,
) -> WalkForwardFold:
    (
        train_start,
        train_end,
        validation_start,
        validation_end,
        calibration_start,
        calibration_end,
        test_start,
        test_end,
    ) = candidate
    train = _boundary(index, "train", SplitRole.TRAIN, train_start, train_end)
    validation = _boundary(
        index,
        "validation",
        SplitRole.VALIDATION,
        validation_start,
        validation_end,
    )
    calibration = None
    if calibration_start is not None and calibration_end is not None:
        calibration = _boundary(
            index,
            "calibration",
            SplitRole.CALIBRATION,
            calibration_start,
            calibration_end,
        )
    test = _boundary(index, "test", SplitRole.TEST, test_start, test_end)
    purged = _purged_windows(index, train, validation, calibration, test)
    provisional_boundaries = [
        _audit_boundary(train),
        _audit_boundary(validation),
    ]
    if calibration is not None:
        provisional_boundaries.append(_audit_boundary(calibration))
    provisional_boundaries.extend([_audit_boundary(test), _audit_boundary(final_holdout)])
    split_hash = hash_split_boundaries(tuple(provisional_boundaries))
    return WalkForwardFold(
        fold_id=f"{plan_id}-f{fold_number:03d}",
        fold_number=fold_number,
        mode=configuration.mode,
        dataset_id=context.dataset_id,
        code_commit=context.code_commit,
        feature_schema_version=context.feature_schema_version,
        model_revision=context.model_revision,
        cost_assumptions_json=context.cost_assumptions_json,
        cost_assumptions_hash=context.cost_assumptions_hash,
        seed=int(context.seed),
        configuration_hash=configuration_hash,
        train=train,
        validation=validation,
        calibration=calibration,
        test=test,
        final_holdout=final_holdout,
        purged_windows=purged,
        final_embargo=final_embargo,
        split_hash=split_hash,
    )


def _purged_windows(
    index: pd.DatetimeIndex,
    train: FoldBoundary,
    validation: FoldBoundary,
    calibration: FoldBoundary | None,
    test: FoldBoundary,
) -> tuple[ExcludedWindow, ...]:
    pairs = [(train, validation)]
    if calibration is None:
        pairs.append((validation, test))
    else:
        pairs.extend([(validation, calibration), (calibration, test)])
    windows = []
    for before, after in pairs:
        window = _excluded(
            index,
            name=f"purge_{before.role.value}_to_{after.role.value}",
            reason="purge",
            start_position=before.end_position + 1,
            end_position=after.start_position - 1,
        )
        if window is not None:
            windows.append(window)
    return tuple(windows)


def _boundary(
    index: pd.DatetimeIndex,
    name: str,
    role: SplitRole,
    start_position: int,
    end_position: int,
) -> FoldBoundary:
    if start_position < 0 or end_position >= len(index) or start_position > end_position:
        raise ValueError(f"invalid {name} boundary positions")
    return FoldBoundary(
        name=name,
        role=role,
        start=index[start_position],
        end=index[end_position],
        start_position=start_position,
        end_position=end_position,
        observation_count=end_position - start_position + 1,
    )


def _excluded(
    index: pd.DatetimeIndex,
    *,
    name: str,
    reason: str,
    start_position: int,
    end_position: int,
) -> ExcludedWindow | None:
    if start_position > end_position:
        return None
    if start_position < 0 or end_position >= len(index):
        raise ValueError(f"invalid {name} boundary positions")
    return ExcludedWindow(
        name=name,
        reason=reason,
        start=index[start_position],
        end=index[end_position],
        start_position=start_position,
        end_position=end_position,
        observation_count=end_position - start_position + 1,
    )


def _audit_boundary(boundary: FoldBoundary) -> SplitBoundary:
    return SplitBoundary(
        name=boundary.name,
        role=boundary.role,
        target_start=boundary.start,
        target_end=boundary.end,
    )


def _validated_index(timestamps: object) -> pd.DatetimeIndex:
    try:
        index = pd.DatetimeIndex(timestamps)
    except (TypeError, ValueError) as exc:
        raise ValueError("timestamps must contain valid datetimes") from exc
    if index.empty:
        raise ValueError("timestamps must not be empty")
    if index.hasnans:
        raise ValueError("timestamps must not contain NaT")
    if index.tz is None:
        raise ValueError("timestamps must be timezone-aware")
    index = index.tz_convert("UTC")
    if len(index) > 1 and not bool(np.all(np.diff(index.asi8) > 0)):
        raise ValueError("timestamps must be strictly increasing without duplicates")
    return index


def _aware_timestamp(value: pd.Timestamp | str, name: str) -> pd.Timestamp:
    try:
        timestamp = pd.Timestamp(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a valid timestamp") from exc
    if pd.isna(timestamp) or timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return timestamp.tz_convert("UTC")


def _positive_integer(value: object, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, Integral) or int(value) <= 0:
        raise ValueError(f"{name} must be a positive integer")


def _non_negative_integer(value: object, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, Integral) or int(value) < 0:
        raise ValueError(f"{name} must be a non-negative integer")


def _canonical_json(value: Mapping[str, Any]) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("cost assumptions must be finite JSON-compatible values") from exc


def _parse_json_object(value: str, name: str) -> dict[str, Any]:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be non-empty canonical JSON")
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{name} must be valid JSON") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"{name} must encode a JSON object")
    return parsed


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
