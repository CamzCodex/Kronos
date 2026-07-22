"""Reusable leakage and point-in-time causality audits."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import timedelta
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd

from .adjustments import coerce_adjustment_policy
from .hashing import hash_configuration


class AuditSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"


class SplitRole(str, Enum):
    TRAIN = "train"
    VALIDATION = "validation"
    CALIBRATION = "calibration"
    TEST = "test"
    FINAL_HOLDOUT = "final_holdout"


@dataclass(frozen=True)
class AuditFinding:
    code: str
    severity: AuditSeverity
    message: str
    count: int = 1
    rows: tuple[str, ...] = ()
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity.value,
            "message": self.message,
            "count": self.count,
            "rows": list(self.rows),
            "details": self.details,
        }


@dataclass(frozen=True)
class LeakageAuditResult:
    passed: bool
    checks: tuple[str, ...]
    failures: tuple[AuditFinding, ...]
    warnings: tuple[AuditFinding, ...]
    dataset_id: str
    code_commit: str
    audited_at: str
    audit_id: str
    split_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "checks": list(self.checks),
            "failures": [finding.to_dict() for finding in self.failures],
            "warnings": [finding.to_dict() for finding in self.warnings],
            "dataset_id": self.dataset_id,
            "code_commit": self.code_commit,
            "audited_at": self.audited_at,
            "audit_id": self.audit_id,
            "split_hash": self.split_hash,
        }


@dataclass(frozen=True)
class SplitBoundary:
    name: str
    role: SplitRole | str
    target_start: pd.Timestamp | str
    target_end: pd.Timestamp | str


@dataclass(frozen=True)
class UniversePolicy:
    point_in_time_membership: bool
    includes_delisted: bool
    stable_identifier_mapping: bool
    membership_source: str


@dataclass(frozen=True)
class NormalizationProbe:
    frame: pd.DataFrame
    prediction_position: int
    feature_columns: tuple[str, ...]
    normalizer: Callable[[pd.DataFrame, int], Any]
    rtol: float = 1e-12
    atol: float = 1e-12


@dataclass(frozen=True)
class LeakageAuditSpec:
    dataset_id: str
    code_commit: str
    audited_at: pd.Timestamp | str
    splits: tuple[SplitBoundary, ...]
    sample_windows: pd.DataFrame
    feature_provenance: pd.DataFrame
    universe_policy: UniversePolicy
    universe_membership: pd.DataFrame
    selection_events: pd.DataFrame
    final_config_frozen_at: pd.Timestamp | str
    normalization_probes: tuple[NormalizationProbe, ...]
    expected_feature_names: tuple[str, ...]
    adjustment_policy: str
    corporate_action_provenance_complete: bool
    corporate_actions: pd.DataFrame = field(default_factory=pd.DataFrame)
    required_embargo: timedelta = timedelta(0)
    require_final_holdout_evaluation: bool = False
    require_calibration: bool = True
    row_limit: int = 20

    def __post_init__(self) -> None:
        if self.required_embargo < timedelta(0):
            raise ValueError("required_embargo cannot be negative")
        if self.row_limit < 1:
            raise ValueError("row_limit must be at least 1")
        if not isinstance(self.require_calibration, bool):
            raise TypeError("require_calibration must be a boolean")


def hash_split_boundaries(splits: tuple[SplitBoundary, ...]) -> str:
    """Return a deterministic identity for the declared target boundaries."""

    payload = []
    for boundary in splits:
        role = _role(boundary.role)
        start = _timestamp(boundary.target_start)
        end = _timestamp(boundary.target_end)
        payload.append(
            {
                "name": str(boundary.name),
                "role": role.value if role is not None else str(boundary.role),
                "target_start": (
                    start.isoformat() if start is not None else str(boundary.target_start)
                ),
                "target_end": end.isoformat() if end is not None else str(boundary.target_end),
            }
        )
    encoded = json.dumps(
        sorted(payload, key=lambda item: (item["name"], item["role"])),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _audit_identity(spec: LeakageAuditSpec, split_hash: str) -> str:
    probes = []
    for probe in spec.normalization_probes:
        normalizer_name = getattr(probe.normalizer, "__qualname__", type(probe.normalizer).__name__)
        normalizer_module = getattr(probe.normalizer, "__module__", "Unknown")
        probes.append(
            {
                "frame_hash": _audit_frame_hash(probe.frame),
                "prediction_position": probe.prediction_position,
                "feature_columns": list(probe.feature_columns),
                "normalizer": f"{normalizer_module}.{normalizer_name}",
                "rtol": probe.rtol,
                "atol": probe.atol,
            }
        )
    payload = {
        "dataset_id": spec.dataset_id,
        "code_commit": spec.code_commit,
        "audited_at": str(spec.audited_at),
        "split_hash": split_hash,
        "sample_windows_hash": _audit_frame_hash(spec.sample_windows),
        "feature_provenance_hash": _audit_frame_hash(spec.feature_provenance),
        "universe_policy": {
            "point_in_time_membership": spec.universe_policy.point_in_time_membership,
            "includes_delisted": spec.universe_policy.includes_delisted,
            "stable_identifier_mapping": spec.universe_policy.stable_identifier_mapping,
            "membership_source": spec.universe_policy.membership_source,
        },
        "universe_membership_hash": _audit_frame_hash(spec.universe_membership),
        "selection_events_hash": _audit_frame_hash(spec.selection_events),
        "final_config_frozen_at": str(spec.final_config_frozen_at),
        "normalization_probes": probes,
        "expected_feature_names": list(spec.expected_feature_names),
        "adjustment_policy": spec.adjustment_policy,
        "corporate_action_provenance_complete": (
            spec.corporate_action_provenance_complete
        ),
        "corporate_actions_hash": _audit_frame_hash(spec.corporate_actions),
        "required_embargo_seconds": spec.required_embargo.total_seconds(),
        "require_final_holdout_evaluation": spec.require_final_holdout_evaluation,
        "require_calibration": spec.require_calibration,
    }
    return f"kla-{hash_configuration(payload)[:24]}"


def _audit_frame_hash(frame: pd.DataFrame) -> str:
    payload = {
        "columns": [str(column) for column in frame.columns],
        "index": [_audit_scalar(value) for value in frame.index],
        "records": [
            [_audit_scalar(value) for value in row]
            for row in frame.itertuples(index=False, name=None)
        ],
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _audit_scalar(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, pd.Timestamp):
        if pd.isna(value):
            return {"missing": "NaT"}
        if value.tzinfo is None or value.utcoffset() is None:
            return {"naive_timestamp": value.isoformat()}
        return value.tz_convert("UTC").isoformat()
    if isinstance(value, (np.bool_, np.integer)):
        return value.item()
    if isinstance(value, (float, np.floating)):
        numeric = float(value)
        if np.isnan(numeric):
            return {"non_finite": "NaN"}
        if np.isposinf(numeric):
            return {"non_finite": "Infinity"}
        if np.isneginf(numeric):
            return {"non_finite": "-Infinity"}
        return numeric
    missing = pd.isna(value)
    if isinstance(missing, (bool, np.bool_)) and bool(missing):
        return {"missing": type(value).__name__}
    return {"type": type(value).__name__, "value": str(value)}


REQUIRED_LEAKAGE_CHECKS = (
    "audit_identity",
    "split_boundaries",
    "embargo",
    "sample_window_causality",
    "normalization_invariance",
    "rolling_feature_causality",
    "feature_availability",
    "corporate_action_causality",
    "point_in_time_universe",
    "model_selection_isolation",
    "final_holdout_isolation",
)

_TIMESTAMP_COLUMNS = (
    "prediction_timestamp",
    "lookback_start",
    "lookback_end",
    "target_start",
    "target_end",
    "normalization_end",
)


def _timestamp(value: Any) -> pd.Timestamp | None:
    try:
        parsed = pd.Timestamp(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(parsed) or parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.tz_convert("UTC")


def _role(value: SplitRole | str) -> SplitRole | None:
    try:
        return value if isinstance(value, SplitRole) else SplitRole(value)
    except ValueError:
        return None


def _rows(mask: pd.Series, limit: int) -> tuple[str, ...]:
    return tuple(str(index) for index in mask.index[mask][:limit])


def _finding_from_mask(
    findings: list[AuditFinding],
    mask: pd.Series,
    *,
    code: str,
    severity: AuditSeverity,
    message: str,
    limit: int,
) -> None:
    count = int(mask.sum())
    if count:
        findings.append(
            AuditFinding(
                code=code,
                severity=severity,
                message=message,
                count=count,
                rows=_rows(mask, limit),
            )
        )


def _require_columns(
    frame: pd.DataFrame,
    required: tuple[str, ...],
    findings: list[AuditFinding],
    *,
    subject: str,
) -> bool:
    missing = [column for column in required if column not in frame.columns]
    if missing:
        findings.append(
            AuditFinding(
                code=f"{subject}_columns_missing",
                severity=AuditSeverity.ERROR,
                message=f"{subject} is missing required columns",
                count=len(missing),
                details={"missing": missing},
            )
        )
        return False
    return True


def _parse_columns(
    frame: pd.DataFrame,
    columns: tuple[str, ...],
    findings: list[AuditFinding],
    *,
    subject: str,
    limit: int,
) -> pd.DataFrame:
    parsed = frame.copy()
    for column in columns:
        aware = parsed[column].map(lambda value: _timestamp(value) is not None)
        _finding_from_mask(
            findings,
            ~aware,
            code=f"{subject}_{column}_invalid",
            severity=AuditSeverity.ERROR,
            message=f"{subject}.{column} must contain timezone-aware timestamps",
            limit=limit,
        )
        parsed[column] = pd.to_datetime(parsed[column], errors="coerce", utc=True)
    return parsed


def _audit_splits(
    spec: LeakageAuditSpec,
    findings: list[AuditFinding],
) -> dict[str, tuple[SplitRole, pd.Timestamp, pd.Timestamp]]:
    parsed: dict[str, tuple[SplitRole, pd.Timestamp, pd.Timestamp]] = {}
    for boundary in spec.splits:
        role = _role(boundary.role)
        start = _timestamp(boundary.target_start)
        end = _timestamp(boundary.target_end)
        if not boundary.name.strip() or role is None or start is None or end is None:
            findings.append(
                AuditFinding(
                    code="invalid_split_boundary",
                    severity=AuditSeverity.ERROR,
                    message="split boundaries require a name, role, and aware timestamps",
                    details={"split": boundary.name},
                )
            )
            continue
        if boundary.name in parsed:
            findings.append(
                AuditFinding(
                    code="duplicate_split_name",
                    severity=AuditSeverity.ERROR,
                    message="split names must be unique",
                    details={"split": boundary.name},
                )
            )
            continue
        if start > end:
            findings.append(
                AuditFinding(
                    code="split_start_after_end",
                    severity=AuditSeverity.ERROR,
                    message="split target_start cannot be later than target_end",
                    details={"split": boundary.name},
                )
            )
        parsed[boundary.name] = (role, start, end)

    ordered = sorted(parsed.items(), key=lambda item: item[1][1])
    role_rank = {
        SplitRole.TRAIN: 0,
        SplitRole.VALIDATION: 1,
        SplitRole.CALIBRATION: 2,
        SplitRole.TEST: 3,
        SplitRole.FINAL_HOLDOUT: 4,
    }
    roles = [details[0] for _, details in ordered]
    if roles != sorted(roles, key=lambda role: role_rank[role]):
        findings.append(
            AuditFinding(
                code="split_role_order_invalid",
                severity=AuditSeverity.ERROR,
                message="split roles must follow train through final holdout chronologically",
            )
        )
    for role in SplitRole:
        count = roles.count(role)
        if role is SplitRole.CALIBRATION and not spec.require_calibration:
            if count <= 1:
                continue
            expected_message = "optional calibration may be declared at most once"
        else:
            expected_message = "each required split role must be declared exactly once"
        if count != 1:
            findings.append(
                AuditFinding(
                    code="split_role_count_invalid",
                    severity=AuditSeverity.ERROR,
                    message=expected_message,
                    count=count,
                    details={"role": role.value},
                )
            )
    for (previous_name, (_, _, previous_end)), (name, (_, start, _)) in zip(
        ordered, ordered[1:]
    ):
        if start <= previous_end:
            findings.append(
                AuditFinding(
                    code="split_target_overlap",
                    severity=AuditSeverity.ERROR,
                    message="target intervals for evaluation splits must not overlap",
                    details={"previous": previous_name, "current": name},
                )
            )
        elif start - previous_end < spec.required_embargo:
            findings.append(
                AuditFinding(
                    code="split_embargo_too_short",
                    severity=AuditSeverity.ERROR,
                    message="the gap between split targets is shorter than required embargo",
                    details={"previous": previous_name, "current": name},
                )
            )

    final_names = [
        name for name, (role, _, _) in parsed.items() if role is SplitRole.FINAL_HOLDOUT
    ]
    if len(final_names) != 1:
        findings.append(
            AuditFinding(
                code="final_holdout_count_invalid",
                severity=AuditSeverity.ERROR,
                message="exactly one final holdout split must be declared",
                count=len(final_names),
            )
        )
    return parsed


def _audit_sample_windows(
    spec: LeakageAuditSpec,
    splits: dict[str, tuple[SplitRole, pd.Timestamp, pd.Timestamp]],
    findings: list[AuditFinding],
) -> None:
    required = ("sample_id", "instrument_id", "split", *_TIMESTAMP_COLUMNS)
    if not _require_columns(spec.sample_windows, required, findings, subject="sample_windows"):
        return
    windows = _parse_columns(
        spec.sample_windows,
        _TIMESTAMP_COLUMNS,
        findings,
        subject="sample_windows",
        limit=spec.row_limit,
    )
    unknown = ~windows["split"].astype(str).isin(splits)
    _finding_from_mask(
        findings,
        unknown,
        code="sample_split_unknown",
        severity=AuditSeverity.ERROR,
        message="sample windows reference an undeclared split",
        limit=spec.row_limit,
    )
    _finding_from_mask(
        findings,
        windows["lookback_start"] > windows["lookback_end"],
        code="lookback_interval_invalid",
        severity=AuditSeverity.ERROR,
        message="lookback_start cannot be later than lookback_end",
        limit=spec.row_limit,
    )
    _finding_from_mask(
        findings,
        windows["lookback_end"] >= windows["target_start"],
        code="lookback_overlaps_target",
        severity=AuditSeverity.ERROR,
        message="lookback windows must end before target labels begin",
        limit=spec.row_limit,
    )
    _finding_from_mask(
        findings,
        windows["prediction_timestamp"] < windows["lookback_end"],
        code="prediction_precedes_lookback_end",
        severity=AuditSeverity.ERROR,
        message="prediction timestamps cannot precede the available lookback end",
        limit=spec.row_limit,
    )
    _finding_from_mask(
        findings,
        windows["prediction_timestamp"] >= windows["target_start"],
        code="prediction_not_before_target",
        severity=AuditSeverity.ERROR,
        message="predictions must be made before target labels begin",
        limit=spec.row_limit,
    )
    _finding_from_mask(
        findings,
        windows["normalization_end"] > windows["prediction_timestamp"],
        code="normalization_uses_future_rows",
        severity=AuditSeverity.ERROR,
        message="normalization inputs cannot extend beyond prediction time",
        limit=spec.row_limit,
    )
    _finding_from_mask(
        findings,
        windows["normalization_end"] < windows["lookback_start"],
        code="normalization_precedes_lookback",
        severity=AuditSeverity.ERROR,
        message="normalization interval cannot end before lookback data begins",
        limit=spec.row_limit,
    )
    _finding_from_mask(
        findings,
        windows["target_end"] < windows["target_start"],
        code="sample_target_interval_invalid",
        severity=AuditSeverity.ERROR,
        message="sample target_end cannot precede target_start",
        limit=spec.row_limit,
    )

    outside = pd.Series(False, index=windows.index)
    for index, row in windows.loc[~unknown].iterrows():
        _, split_start, split_end = splits[str(row["split"])]
        outside.loc[index] = row["target_start"] < split_start or row["target_end"] > split_end
    _finding_from_mask(
        findings,
        outside,
        code="sample_label_crosses_split",
        severity=AuditSeverity.ERROR,
        message="sample target labels must remain inside their declared split",
        limit=spec.row_limit,
    )


def _audit_normalization(spec: LeakageAuditSpec, findings: list[AuditFinding]) -> None:
    if not spec.normalization_probes:
        findings.append(
            AuditFinding(
                code="normalization_probe_missing",
                severity=AuditSeverity.ERROR,
                message="at least one future-perturbation normalization probe is required",
            )
        )
        return
    for probe_index, probe in enumerate(spec.normalization_probes):
        if not 0 < probe.prediction_position < len(probe.frame):
            findings.append(
                AuditFinding(
                    code="normalization_probe_boundary_invalid",
                    severity=AuditSeverity.ERROR,
                    message="prediction_position must separate history from future rows",
                    details={"probe_index": probe_index},
                )
            )
            continue
        missing = [
            column for column in probe.feature_columns if column not in probe.frame.columns
        ]
        if missing:
            findings.append(
                AuditFinding(
                    code="normalization_probe_columns_missing",
                    severity=AuditSeverity.ERROR,
                    message="normalization probe feature columns are missing",
                    count=len(missing),
                    details={"probe_index": probe_index, "missing": missing},
                )
            )
            continue
        try:
            baseline = np.asarray(
                probe.normalizer(probe.frame.copy(deep=True), probe.prediction_position)
            )
            contaminated = probe.frame.copy(deep=True)
            future_index = contaminated.index[probe.prediction_position :]
            for column in probe.feature_columns:
                numeric = pd.to_numeric(
                    contaminated.loc[future_index, column], errors="raise"
                )
                contaminated.loc[future_index, column] = (
                    numeric * -17.0 + 1_000_003.0
                )
            perturbed = np.asarray(
                probe.normalizer(contaminated, probe.prediction_position)
            )
        except Exception as exc:
            findings.append(
                AuditFinding(
                    code="normalization_probe_failed",
                    severity=AuditSeverity.ERROR,
                    message="normalization probe raised an exception",
                    details={
                        "probe_index": probe_index,
                        "exception": type(exc).__name__,
                    },
                )
            )
            continue
        if baseline.shape != perturbed.shape or not np.allclose(
            baseline,
            perturbed,
            rtol=probe.rtol,
            atol=probe.atol,
            equal_nan=True,
        ):
            findings.append(
                AuditFinding(
                    code="future_changes_historical_normalization",
                    severity=AuditSeverity.ERROR,
                    message="perturbing future values changed historical normalized outputs",
                    details={
                        "probe_index": probe_index,
                        "baseline_shape": list(baseline.shape),
                        "perturbed_shape": list(perturbed.shape),
                    },
                )
            )


def _audit_features(spec: LeakageAuditSpec, findings: list[AuditFinding]) -> None:
    required = (
        "sample_id",
        "feature_name",
        "prediction_timestamp",
        "observation_timestamp",
        "available_at",
        "window_end",
        "derived_from_target",
    )
    if not _require_columns(
        spec.feature_provenance, required, findings, subject="feature_provenance"
    ):
        return
    columns = ("prediction_timestamp", "observation_timestamp", "available_at", "window_end")
    features = _parse_columns(
        spec.feature_provenance,
        columns,
        findings,
        subject="feature_provenance",
        limit=spec.row_limit,
    )
    for mask, code, message in (
        (
            features["available_at"] > features["prediction_timestamp"],
            "feature_available_after_prediction",
            "feature values must be available by prediction time",
        ),
        (
            features["observation_timestamp"] > features["prediction_timestamp"],
            "future_observation_used",
            "feature observations cannot occur after prediction time",
        ),
        (
            features["window_end"] > features["prediction_timestamp"],
            "rolling_window_uses_future",
            "rolling feature windows cannot extend beyond prediction time",
        ),
        (
            features["available_at"] < features["observation_timestamp"],
            "feature_available_before_observation",
            "feature availability cannot precede its observation timestamp",
        ),
        (
            features["derived_from_target"].eq(True),
            "feature_derived_from_target",
            "features used for prediction cannot be derived from target labels",
        ),
    ):
        _finding_from_mask(
            findings,
            mask,
            code=code,
            severity=AuditSeverity.ERROR,
            message=message,
            limit=spec.row_limit,
        )
    if not spec.expected_feature_names:
        findings.append(
            AuditFinding(
                code="expected_feature_names_missing",
                severity=AuditSeverity.ERROR,
                message="the complete expected feature set must be declared",
            )
        )
    elif "sample_id" in spec.sample_windows:
        missing_pairs: list[str] = []
        expected = set(spec.expected_feature_names)
        for sample_id in spec.sample_windows["sample_id"].astype(str):
            actual = set(
                features.loc[
                    features["sample_id"].astype(str).eq(sample_id), "feature_name"
                ].astype(str)
            )
            for feature_name in sorted(expected - actual):
                missing_pairs.append(f"{sample_id}:{feature_name}")
        if missing_pairs:
            findings.append(
                AuditFinding(
                    code="feature_provenance_incomplete",
                    severity=AuditSeverity.ERROR,
                    message="every sample requires provenance for every expected feature",
                    count=len(missing_pairs),
                    details={"sample_features": missing_pairs[: spec.row_limit]},
                )
            )


def _audit_corporate_actions(spec: LeakageAuditSpec, findings: list[AuditFinding]) -> None:
    try:
        policy = coerce_adjustment_policy(spec.adjustment_policy)
    except ValueError:
        findings.append(
            AuditFinding(
                code="adjustment_policy_invalid",
                severity=AuditSeverity.ERROR,
                message="adjustment policy is unsupported",
            )
        )
        return
    adjusted = policy.value != "raw"
    if adjusted and not spec.corporate_action_provenance_complete:
        findings.append(
            AuditFinding(
                code="corporate_action_provenance_incomplete",
                severity=AuditSeverity.ERROR,
                message="adjusted data requires complete corporate-action provenance",
            )
        )
    if spec.corporate_actions.empty:
        return
    required = (
        "instrument_id",
        "prediction_timestamp",
        "feature_timestamp",
        "action_effective_at",
        "action_known_at",
        "adjustment_applied",
    )
    if not _require_columns(
        spec.corporate_actions, required, findings, subject="corporate_actions"
    ):
        return
    columns = (
        "prediction_timestamp",
        "feature_timestamp",
        "action_effective_at",
        "action_known_at",
    )
    actions = _parse_columns(
        spec.corporate_actions,
        columns,
        findings,
        subject="corporate_actions",
        limit=spec.row_limit,
    )
    valid_applied = actions["adjustment_applied"].map(
        lambda value: isinstance(value, (bool, np.bool_))
    )
    _finding_from_mask(
        findings,
        ~valid_applied,
        code="adjustment_applied_invalid",
        severity=AuditSeverity.ERROR,
        message="adjustment_applied must contain booleans",
        limit=spec.row_limit,
    )
    applied = actions["adjustment_applied"].eq(True)
    future_feature = applied & (
        actions["feature_timestamp"] > actions["prediction_timestamp"]
    )
    future_known = applied & (actions["action_known_at"] > actions["prediction_timestamp"])
    future_effective = applied & (
        actions["action_effective_at"] > actions["prediction_timestamp"]
    )
    _finding_from_mask(
        findings,
        future_feature,
        code="future_adjusted_feature_used",
        severity=AuditSeverity.ERROR,
        message="adjusted feature timestamps cannot occur after prediction time",
        limit=spec.row_limit,
    )
    _finding_from_mask(
        findings,
        future_known,
        code="future_corporate_action_knowledge",
        severity=AuditSeverity.ERROR,
        message="adjustments cannot use actions unknown at prediction time",
        limit=spec.row_limit,
    )
    _finding_from_mask(
        findings,
        future_effective,
        code="future_effective_action_applied",
        severity=AuditSeverity.ERROR,
        message="historical features cannot apply actions not yet effective at prediction time",
        limit=spec.row_limit,
    )


def _audit_universe(spec: LeakageAuditSpec, findings: list[AuditFinding]) -> None:
    policy = spec.universe_policy
    for valid, code, message in (
        (
            policy.point_in_time_membership,
            "universe_not_point_in_time",
            "universe membership must be point-in-time",
        ),
        (
            policy.includes_delisted,
            "delisted_instruments_excluded",
            "universe evidence must include delisted instruments",
        ),
        (
            policy.stable_identifier_mapping,
            "instrument_mapping_unstable",
            "universe evidence requires stable identifier mapping",
        ),
        (
            bool(policy.membership_source.strip()),
            "membership_source_missing",
            "universe membership source must be declared",
        ),
    ):
        if not valid:
            findings.append(
                AuditFinding(
                    code=code,
                    severity=AuditSeverity.ERROR,
                    message=message,
                )
            )
    required = (
        "instrument_id",
        "prediction_timestamp",
        "member_from",
        "member_to",
        "membership_known_at",
        "included",
    )
    if spec.universe_membership.empty:
        findings.append(
            AuditFinding(
                code="universe_membership_empty",
                severity=AuditSeverity.ERROR,
                message="point-in-time universe membership records are required",
            )
        )
        return
    if not _require_columns(
        spec.universe_membership, required, findings, subject="universe_membership"
    ):
        return
    columns = ("prediction_timestamp", "member_from", "member_to", "membership_known_at")
    membership = _parse_columns(
        spec.universe_membership,
        columns,
        findings,
        subject="universe_membership",
        limit=spec.row_limit,
    )
    valid_included = membership["included"].map(
        lambda value: isinstance(value, (bool, np.bool_))
    )
    _finding_from_mask(
        findings,
        ~valid_included,
        code="universe_included_invalid",
        severity=AuditSeverity.ERROR,
        message="universe included flags must be booleans",
        limit=spec.row_limit,
    )
    included = membership["included"].eq(True)
    outside = included & (
        (membership["prediction_timestamp"] < membership["member_from"])
        | (membership["prediction_timestamp"] > membership["member_to"])
    )
    future_known = included & (
        membership["membership_known_at"] > membership["prediction_timestamp"]
    )
    _finding_from_mask(
        findings,
        outside,
        code="instrument_outside_membership_interval",
        severity=AuditSeverity.ERROR,
        message="included instruments must be members at prediction time",
        limit=spec.row_limit,
    )
    _finding_from_mask(
        findings,
        future_known,
        code="future_universe_membership_knowledge",
        severity=AuditSeverity.ERROR,
        message="membership decisions cannot be known after prediction time",
        limit=spec.row_limit,
    )
    if {"sample_id", "instrument_id", "prediction_timestamp"} <= set(
        spec.sample_windows.columns
    ):
        samples = _parse_columns(
            spec.sample_windows,
            ("prediction_timestamp",),
            findings,
            subject="universe_sample_windows",
            limit=spec.row_limit,
        )
        missing_ids: list[str] = []
        for _, sample in samples.iterrows():
            matches = membership[
                membership["instrument_id"].astype(str).eq(str(sample["instrument_id"]))
                & membership["prediction_timestamp"].eq(sample["prediction_timestamp"])
                & membership["included"].eq(True)
                & membership["member_from"].le(sample["prediction_timestamp"])
                & membership["member_to"].ge(sample["prediction_timestamp"])
                & membership["membership_known_at"].le(sample["prediction_timestamp"])
            ]
            if matches.empty:
                missing_ids.append(str(sample["sample_id"]))
        if missing_ids:
            findings.append(
                AuditFinding(
                    code="sample_universe_membership_missing",
                    severity=AuditSeverity.ERROR,
                    message="every sample requires causal point-in-time membership evidence",
                    count=len(missing_ids),
                    details={"sample_ids": missing_ids[: spec.row_limit]},
                )
            )


def _audit_selection(
    spec: LeakageAuditSpec,
    splits: dict[str, tuple[SplitRole, pd.Timestamp, pd.Timestamp]],
    findings: list[AuditFinding],
) -> None:
    required = ("purpose", "split", "occurred_at")
    if not _require_columns(
        spec.selection_events, required, findings, subject="selection_events"
    ):
        return
    events = _parse_columns(
        spec.selection_events,
        ("occurred_at",),
        findings,
        subject="selection_events",
        limit=spec.row_limit,
    )
    unknown = ~events["split"].astype(str).isin(splits)
    _finding_from_mask(
        findings,
        unknown,
        code="selection_split_unknown",
        severity=AuditSeverity.ERROR,
        message="selection events reference an undeclared split",
        limit=spec.row_limit,
    )
    selection_purposes = {
        "tune",
        "select",
        "calibrate",
        "threshold_select",
        "hyperparameter_search",
        "model_select",
    }
    selection = events["purpose"].astype(str).isin(selection_purposes)
    forbidden = pd.Series(False, index=events.index)
    for index, row in events.loc[selection & ~unknown].iterrows():
        role = splits[str(row["split"])][0]
        forbidden.loc[index] = role in {SplitRole.TEST, SplitRole.FINAL_HOLDOUT}
    _finding_from_mask(
        findings,
        forbidden,
        code="selection_accesses_evaluation_split",
        severity=AuditSeverity.ERROR,
        message="model selection cannot access test or final-holdout metrics",
        limit=spec.row_limit,
    )

    frozen_at = _timestamp(spec.final_config_frozen_at)
    if frozen_at is None:
        findings.append(
            AuditFinding(
                code="final_config_freeze_invalid",
                severity=AuditSeverity.ERROR,
                message="final_config_frozen_at must be a timezone-aware timestamp",
            )
        )
        return
    after_freeze = selection & (events["occurred_at"] > frozen_at)
    _finding_from_mask(
        findings,
        after_freeze,
        code="selection_after_final_config_freeze",
        severity=AuditSeverity.ERROR,
        message="selection or tuning occurred after final configuration freeze",
        limit=spec.row_limit,
    )

    final_names = {
        name for name, (role, _, _) in splits.items() if role is SplitRole.FINAL_HOLDOUT
    }
    final_events = events[
        events["purpose"].astype(str).eq("final_evaluate")
        & events["split"].astype(str).isin(final_names)
    ]
    wrong_final = events["purpose"].astype(str).eq("final_evaluate") & ~events[
        "split"
    ].astype(str).isin(final_names)
    _finding_from_mask(
        findings,
        wrong_final,
        code="final_evaluation_uses_wrong_split",
        severity=AuditSeverity.ERROR,
        message="final_evaluate events must use the declared final holdout",
        limit=spec.row_limit,
    )
    if len(final_events) > 1:
        findings.append(
            AuditFinding(
                code="final_holdout_evaluated_multiple_times",
                severity=AuditSeverity.ERROR,
                message="the final holdout may be evaluated at most once",
                count=len(final_events),
                rows=tuple(str(index) for index in final_events.index[: spec.row_limit]),
            )
        )
    if spec.require_final_holdout_evaluation and len(final_events) != 1:
        findings.append(
            AuditFinding(
                code="final_holdout_evaluation_missing",
                severity=AuditSeverity.ERROR,
                message="this audit requires exactly one final-holdout evaluation",
                count=len(final_events),
            )
        )
    if not final_events.empty:
        first_final = final_events["occurred_at"].min()
        if first_final < frozen_at:
            findings.append(
                AuditFinding(
                    code="final_holdout_before_config_freeze",
                    severity=AuditSeverity.ERROR,
                    message="final holdout was evaluated before configuration freeze",
                )
            )
        post_final_selection = selection & (events["occurred_at"] > first_final)
        _finding_from_mask(
            findings,
            post_final_selection,
            code="selection_after_final_holdout",
            severity=AuditSeverity.ERROR,
            message="model selection cannot continue after final-holdout evaluation",
            limit=spec.row_limit,
        )
    audited_at = _timestamp(spec.audited_at)
    if audited_at is not None:
        after_audit = events["occurred_at"] > audited_at
        _finding_from_mask(
            findings,
            after_audit,
            code="event_after_audit_timestamp",
            severity=AuditSeverity.ERROR,
            message="selection events cannot occur after the audit timestamp",
            limit=spec.row_limit,
        )


def audit_leakage(spec: LeakageAuditSpec) -> LeakageAuditResult:
    """Run every configured causal check; any error invalidates the audit."""

    findings: list[AuditFinding] = []
    split_hash = hash_split_boundaries(spec.splits)
    audit_id = _audit_identity(spec, split_hash)
    audited_at = _timestamp(spec.audited_at)
    if not spec.dataset_id.strip():
        findings.append(
            AuditFinding(
                code="dataset_id_missing",
                severity=AuditSeverity.ERROR,
                message="dataset_id is required",
            )
        )
    if not re.fullmatch(r"[0-9a-f]{7,64}", spec.code_commit):
        findings.append(
            AuditFinding(
                code="code_commit_invalid",
                severity=AuditSeverity.ERROR,
                message="code_commit must be a lowercase hexadecimal Git SHA",
            )
        )
    if audited_at is None:
        findings.append(
            AuditFinding(
                code="audit_timestamp_invalid",
                severity=AuditSeverity.ERROR,
                message="audited_at must be timezone-aware",
            )
        )

    splits = _audit_splits(spec, findings)
    _audit_sample_windows(spec, splits, findings)
    _audit_normalization(spec, findings)
    _audit_features(spec, findings)
    _audit_corporate_actions(spec, findings)
    _audit_universe(spec, findings)
    _audit_selection(spec, splits, findings)

    failures = tuple(
        finding for finding in findings if finding.severity is AuditSeverity.ERROR
    )
    warnings = tuple(
        finding for finding in findings if finding.severity is AuditSeverity.WARNING
    )
    return LeakageAuditResult(
        passed=not failures,
        checks=REQUIRED_LEAKAGE_CHECKS,
        failures=failures,
        warnings=warnings,
        dataset_id=spec.dataset_id,
        code_commit=spec.code_commit,
        audited_at=audited_at.isoformat() if audited_at is not None else "Invalid",
        audit_id=audit_id,
        split_hash=split_hash,
    )
