"""Audit-gated fold execution and immutable result artifacts."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd

from kronos_data.hashing import canonical_json, hash_configuration
from kronos_data.leakage import REQUIRED_LEAKAGE_CHECKS

from .baselines import MANDATORY_BASELINES
from .costs import (
    CostEvaluationRequest,
    CostEvaluationResult,
    evaluate_paper_returns,
)
from .metrics import (
    ForecastMetricRequest,
    ForecastScorecard,
    score_forecasts,
)
from .walk_forward import AuditedWalkForwardFold

EVALUATION_RUNNER_VERSION = "1.0.0"
COMPARABLE_METRIC_DIRECTIONS = {
    "mae": False,
    "rmse": False,
    "mase": False,
    "directional_accuracy": True,
    "positive_precision": True,
    "positive_recall": True,
    "mean_quantile_loss": False,
    "brier_score_positive": False,
    "crps": False,
    "downside_tail_recall": True,
    "expected_calibration_error": False,
    "ic_mean": True,
    "rank_ic_mean": True,
    "top_minus_bottom_quantile_spread": True,
    "interval_coverage_error": False,
}
_TRUTH_COLUMNS = (
    "instrument_id",
    "as_of_timestamp",
    "target_timestamp",
    "horizon",
    "reference_value",
    "actual_value",
    "scale_error",
    "market_regime",
    "volatility_regime",
)


class EvaluationRunnerError(ValueError):
    """Raised when a fold is unaudited, incomplete, unfair, or out of bounds."""


@dataclass(frozen=True)
class ForecastSubmission:
    """One model's normalized scoring request and upstream forecast identity."""

    request: ForecastMetricRequest
    information_set_hash: str
    forecast_configuration_hash: str
    forecast_artifact_hash: str
    is_baseline: bool

    def __post_init__(self) -> None:
        if not isinstance(self.request, ForecastMetricRequest):
            raise TypeError("request must be a ForecastMetricRequest")
        for name in (
            "information_set_hash",
            "forecast_configuration_hash",
            "forecast_artifact_hash",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
                raise EvaluationRunnerError(f"{name} must be a SHA-256 hexadecimal digest")
        if not isinstance(self.is_baseline, bool):
            raise TypeError("is_baseline must be a boolean")


@dataclass(frozen=True)
class EvaluationRunRequest:
    audited_fold: AuditedWalkForwardFold
    submissions: tuple[ForecastSubmission, ...]
    candidate_model_name: str
    reference_baseline: str
    created_at: pd.Timestamp | str
    cost_requests: tuple[CostEvaluationRequest, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.audited_fold, AuditedWalkForwardFold):
            raise TypeError("audited_fold must be an AuditedWalkForwardFold")
        if not isinstance(self.submissions, tuple) or not self.submissions:
            raise EvaluationRunnerError("submissions must be a non-empty tuple")
        if not all(isinstance(item, ForecastSubmission) for item in self.submissions):
            raise TypeError("every submission must be a ForecastSubmission")
        for name in ("candidate_model_name", "reference_baseline"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise EvaluationRunnerError(f"{name} must be a non-empty string")
        if self.candidate_model_name in MANDATORY_BASELINES:
            raise EvaluationRunnerError("candidate_model_name cannot be a mandatory baseline")
        if self.reference_baseline not in MANDATORY_BASELINES:
            raise EvaluationRunnerError("reference_baseline must be a mandatory baseline")
        if not isinstance(self.cost_requests, tuple):
            raise TypeError("cost_requests must be a tuple")
        if not all(isinstance(item, CostEvaluationRequest) for item in self.cost_requests):
            raise TypeError("every cost request must be a CostEvaluationRequest")


@dataclass(frozen=True)
class EvaluationFoldResult:
    runner_version: str
    run_id: str
    created_at: pd.Timestamp
    dataset_id: str
    fold_id: str
    code_commit: str
    split_hash: str
    audit_id: str
    audit_hash: str
    candidate_model_name: str
    reference_baseline: str
    information_set_hash: str
    truth_hash: str
    submissions_hash: str
    scorecards: dict[str, ForecastScorecard]
    cost_results: dict[str, CostEvaluationResult]
    comparable_scores: pd.DataFrame
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "runner_version": self.runner_version,
            "run_id": self.run_id,
            "created_at": self.created_at.isoformat(),
            "dataset_id": self.dataset_id,
            "fold_id": self.fold_id,
            "code_commit": self.code_commit,
            "split_hash": self.split_hash,
            "audit_id": self.audit_id,
            "audit_hash": self.audit_hash,
            "candidate_model_name": self.candidate_model_name,
            "reference_baseline": self.reference_baseline,
            "information_set_hash": self.information_set_hash,
            "truth_hash": self.truth_hash,
            "submissions_hash": self.submissions_hash,
            "scorecards": {
                name: _scorecard_dict(scorecard)
                for name, scorecard in sorted(self.scorecards.items())
            },
            "cost_results": {
                name: _cost_result_dict(result)
                for name, result in sorted(self.cost_results.items())
            },
            "comparable_scores": _frame_records(self.comparable_scores),
            "warnings": list(self.warnings),
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        ) + "\n"


def run_evaluation_fold(request: EvaluationRunRequest) -> EvaluationFoldResult:
    """Score one complete audited development fold and optional paper paths."""

    if not isinstance(request, EvaluationRunRequest):
        raise TypeError("request must be an EvaluationRunRequest")
    audited = request.audited_fold
    _validate_audit(audited)
    fold = audited.fold
    created_at = _aware_timestamp(request.created_at, "created_at")
    if created_at < fold.test.end:
        raise EvaluationRunnerError("created_at cannot precede the fold test end")
    audited_at = _aware_timestamp(audited.leakage_audit.audited_at, "audited_at")
    if created_at < audited_at:
        raise EvaluationRunnerError("created_at cannot precede the leakage audit")

    submissions = {item.request.model_name: item for item in request.submissions}
    if len(submissions) != len(request.submissions):
        raise EvaluationRunnerError("submission model names must be unique")
    required_models = set(MANDATORY_BASELINES) | {request.candidate_model_name}
    if set(submissions) != required_models:
        missing = sorted(required_models - set(submissions))
        extra = sorted(set(submissions) - required_models)
        raise EvaluationRunnerError(
            f"submission suite must contain exactly the candidate and mandatory baselines; "
            f"missing={missing}, extra={extra}"
        )
    baseline_labels = {name for name, item in submissions.items() if item.is_baseline}
    if baseline_labels != set(MANDATORY_BASELINES):
        raise EvaluationRunnerError("is_baseline labels must match mandatory baselines exactly")

    information_hashes = {item.information_set_hash for item in submissions.values()}
    if len(information_hashes) != 1:
        raise EvaluationRunnerError("all forecast submissions must share one information set")
    truth_hashes = {}
    scorecards = {}
    for model_name in sorted(submissions):
        submission = submissions[model_name]
        metric_request = submission.request
        _validate_metric_identity(metric_request, fold)
        _validate_development_targets(metric_request.observations, fold)
        truth_hashes[model_name] = _truth_hash(metric_request.observations)
        scorecards[model_name] = score_forecasts(metric_request)
    if len(set(truth_hashes.values())) != 1:
        raise EvaluationRunnerError(
            "all models must be scored on identical targets, references, scales, and regimes"
        )

    cost_results = {}
    for cost_request in request.cost_requests:
        if cost_request.strategy_name in cost_results:
            raise EvaluationRunnerError("cost strategy names must be unique")
        _validate_cost_identity(cost_request, fold)
        _validate_cost_targets(cost_request.decisions, fold)
        _validate_fold_cost_assumptions(cost_request, fold.cost_assumptions)
        cost_results[cost_request.strategy_name] = evaluate_paper_returns(cost_request)

    comparable = _comparable_scores(scorecards)
    audit_hash = hashlib.sha256(canonical_json(audited.leakage_audit.to_dict()).encode()).hexdigest()
    submission_payload = [
        {
            "model_name": name,
            "is_baseline": item.is_baseline,
            "information_set_hash": item.information_set_hash,
            "forecast_configuration_hash": item.forecast_configuration_hash,
            "forecast_artifact_hash": item.forecast_artifact_hash,
            "metric_observation_hash": scorecards[name].observation_hash,
            "metric_configuration_hash": scorecards[name].configuration_hash,
        }
        for name, item in sorted(submissions.items())
    ]
    cost_payload = [
        {
            "strategy_name": name,
            "input_hash": result.input_hash,
            "assumptions_hash": result.assumptions_hash,
        }
        for name, result in sorted(cost_results.items())
    ]
    submissions_hash = hash_configuration(
        {"forecast_submissions": submission_payload, "cost_submissions": cost_payload}
    )
    identity = {
        "runner_version": EVALUATION_RUNNER_VERSION,
        "dataset_id": fold.dataset_id,
        "fold_id": fold.fold_id,
        "code_commit": fold.code_commit,
        "split_hash": fold.split_hash,
        "audit_hash": audit_hash,
        "candidate_model_name": request.candidate_model_name,
        "reference_baseline": request.reference_baseline,
        "information_set_hash": next(iter(information_hashes)),
        "truth_hash": next(iter(truth_hashes.values())),
        "submissions_hash": submissions_hash,
    }
    warnings = [
        "a passed software runner does not establish forecast or economic usefulness",
        "the final holdout is excluded from this development-fold runner",
        "multiple-comparison, dependence, perturbation, and final-confirmation controls remain required",
    ]
    if not cost_results:
        warnings.append("no paper target path was supplied; economic metrics are unavailable")
    return EvaluationFoldResult(
        runner_version=EVALUATION_RUNNER_VERSION,
        run_id=f"ker-{hash_configuration(identity)[:24]}",
        created_at=created_at,
        dataset_id=fold.dataset_id,
        fold_id=fold.fold_id,
        code_commit=fold.code_commit,
        split_hash=fold.split_hash,
        audit_id=audited.leakage_audit.audit_id,
        audit_hash=audit_hash,
        candidate_model_name=request.candidate_model_name,
        reference_baseline=request.reference_baseline,
        information_set_hash=next(iter(information_hashes)),
        truth_hash=next(iter(truth_hashes.values())),
        submissions_hash=submissions_hash,
        scorecards=scorecards,
        cost_results=cost_results,
        comparable_scores=comparable,
        warnings=tuple(warnings),
    )


def write_evaluation_fold_result(
    result: EvaluationFoldResult,
    path: str | os.PathLike[str],
) -> Path:
    """Persist a fold result once, accepting only byte-identical evidence."""

    if not isinstance(result, EvaluationFoldResult):
        raise TypeError("result must be an EvaluationFoldResult")
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = result.to_json().encode()
    if destination.exists():
        if destination.read_bytes() == payload:
            return destination
        raise FileExistsError(f"refusing to replace immutable result {destination}")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
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


def _validate_audit(audited: AuditedWalkForwardFold) -> None:
    audit = audited.leakage_audit
    fold = audited.fold
    if not audit.passed or audit.failures:
        raise EvaluationRunnerError("failed leakage audits invalidate evaluation")
    if audit.dataset_id != fold.dataset_id or audit.code_commit != fold.code_commit:
        raise EvaluationRunnerError("leakage audit identity does not match the fold")
    if audit.split_hash != fold.split_hash or not audit.audit_id.startswith("kla-"):
        raise EvaluationRunnerError("leakage audit split or audit identity is invalid")
    missing = set(REQUIRED_LEAKAGE_CHECKS) - set(audit.checks)
    if missing:
        raise EvaluationRunnerError(f"leakage audit is missing checks: {sorted(missing)}")


def _validate_metric_identity(request: ForecastMetricRequest, fold: Any) -> None:
    if request.dataset_id != fold.dataset_id:
        raise EvaluationRunnerError("metric dataset_id does not match audited fold")
    if request.fold_id != fold.fold_id:
        raise EvaluationRunnerError("metric fold_id does not match audited fold")
    if request.code_commit != fold.code_commit:
        raise EvaluationRunnerError("metric code_commit does not match audited fold")


def _validate_development_targets(frame: pd.DataFrame, fold: Any) -> None:
    if not isinstance(frame, pd.DataFrame) or "target_timestamp" not in frame.columns:
        raise EvaluationRunnerError("metric observations require target_timestamp")
    targets = _aware_index(frame["target_timestamp"], "target_timestamp")
    if (targets >= fold.final_holdout.start).any():
        raise EvaluationRunnerError("development runner refuses final-holdout targets")
    if (targets < fold.test.start).any() or (targets > fold.test.end).any():
        raise EvaluationRunnerError("forecast targets must remain inside the audited test boundary")


def _validate_cost_identity(request: CostEvaluationRequest, fold: Any) -> None:
    if request.dataset_id != fold.dataset_id:
        raise EvaluationRunnerError("cost dataset_id does not match audited fold")
    if request.fold_id != fold.fold_id:
        raise EvaluationRunnerError("cost fold_id does not match audited fold")
    if request.code_commit != fold.code_commit:
        raise EvaluationRunnerError("cost code_commit does not match audited fold")


def _validate_cost_targets(frame: pd.DataFrame, fold: Any) -> None:
    if not isinstance(frame, pd.DataFrame) or "realization_timestamp" not in frame.columns:
        raise EvaluationRunnerError("cost decisions require realization_timestamp")
    targets = _aware_index(frame["realization_timestamp"], "realization_timestamp")
    if (targets >= fold.final_holdout.start).any():
        raise EvaluationRunnerError("development runner refuses final-holdout realizations")
    if (targets < fold.test.start).any() or (targets > fold.test.end).any():
        raise EvaluationRunnerError("paper realizations must remain inside the audited test boundary")


def _validate_fold_cost_assumptions(
    request: CostEvaluationRequest,
    declared: dict[str, Any],
) -> None:
    actual = request.assumptions.to_dict()
    for key in ("commission_bps", "half_spread_bps", "slippage_bps"):
        if key not in declared:
            raise EvaluationRunnerError(f"audited fold does not declare required cost {key}")
        if float(declared[key]) != actual[key]:
            raise EvaluationRunnerError(f"cost assumption {key} does not match audited fold")


def _truth_hash(frame: pd.DataFrame) -> str:
    missing = [column for column in _TRUTH_COLUMNS if column not in frame.columns]
    if missing:
        raise EvaluationRunnerError(f"metric observations are missing truth columns: {missing}")
    canonical = frame.loc[:, _TRUTH_COLUMNS].copy()
    canonical["as_of_timestamp"] = _aware_index(
        canonical["as_of_timestamp"], "as_of_timestamp"
    )
    canonical["target_timestamp"] = _aware_index(
        canonical["target_timestamp"], "target_timestamp"
    )
    canonical = canonical.sort_values(
        ["target_timestamp", "horizon", "instrument_id", "as_of_timestamp"],
        kind="mergesort",
    )
    return hashlib.sha256(canonical_json(_frame_records(canonical)).encode()).hexdigest()


def _comparable_scores(scorecards: dict[str, ForecastScorecard]) -> pd.DataFrame:
    aggregates = {}
    for model_name, scorecard in sorted(scorecards.items()):
        aggregate = dict(scorecard.aggregate)
        nominal_coverage = (
            aggregate["interval_upper_probability"]
            - aggregate["interval_lower_probability"]
        )
        aggregate["interval_coverage_error"] = abs(
            aggregate["interval_coverage"] - nominal_coverage
        )
        aggregates[model_name] = aggregate
    rows = []
    for metric_name, higher_is_better in COMPARABLE_METRIC_DIRECTIONS.items():
        if any(aggregate.get(metric_name) is None for aggregate in aggregates.values()):
            continue
        for model_name, aggregate in sorted(aggregates.items()):
            value = aggregate[metric_name]
            if value is None:  # guarded above; retained for type narrowing
                continue
            rows.append(
                {
                    "model_name": model_name,
                    "metric_name": metric_name,
                    "value": float(value),
                    "higher_is_better": higher_is_better,
                }
            )
    return pd.DataFrame(rows)


def _scorecard_dict(scorecard: ForecastScorecard) -> dict[str, Any]:
    return {
        "metric_suite_version": scorecard.metric_suite_version,
        "model_name": scorecard.model_name,
        "dataset_id": scorecard.dataset_id,
        "fold_id": scorecard.fold_id,
        "code_commit": scorecard.code_commit,
        "observation_hash": scorecard.observation_hash,
        "configuration_hash": scorecard.configuration_hash,
        "aggregate": _json_safe(scorecard.aggregate),
        "by_horizon": _frame_records(scorecard.by_horizon),
        "by_instrument": _frame_records(scorecard.by_instrument),
        "by_market_regime": _frame_records(scorecard.by_market_regime),
        "by_volatility_regime": _frame_records(scorecard.by_volatility_regime),
        "cross_sectional_periods": _frame_records(scorecard.cross_sectional_periods),
        "calibration": _frame_records(scorecard.calibration),
        "calibration_by_market_regime": _frame_records(
            scorecard.calibration_by_market_regime
        ),
        "calibration_by_volatility_regime": _frame_records(
            scorecard.calibration_by_volatility_regime
        ),
        "quantile_loss": _frame_records(scorecard.quantile_loss),
        "warnings": list(scorecard.warnings),
    }


def _cost_result_dict(result: CostEvaluationResult) -> dict[str, Any]:
    return {
        "cost_model_version": result.cost_model_version,
        "strategy_name": result.strategy_name,
        "dataset_id": result.dataset_id,
        "fold_id": result.fold_id,
        "code_commit": result.code_commit,
        "input_hash": result.input_hash,
        "assumptions_hash": result.assumptions_hash,
        "trade_ledger": _frame_records(result.trade_ledger),
        "period_ledger": _frame_records(result.period_ledger),
        "sector_exposure": _frame_records(result.sector_exposure),
        "metrics": _json_safe(result.metrics),
        "warnings": list(result.warnings),
    }


def _frame_records(frame: pd.DataFrame) -> dict[str, Any]:
    return {
        "columns": [str(column) for column in frame.columns],
        "records": [
            [_json_safe(value) for value in row]
            for row in frame.itertuples(index=False, name=None)
        ],
    }


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, pd.Timestamp):
        if pd.isna(value) or value.tzinfo is None:
            raise EvaluationRunnerError("result timestamps must be non-missing and aware")
        return value.tz_convert("UTC").isoformat()
    if isinstance(value, (np.bool_, np.integer)):
        return value.item()
    if isinstance(value, (float, np.floating)):
        numeric = float(value)
        if np.isnan(numeric):
            return None
        if not np.isfinite(numeric):
            raise EvaluationRunnerError("result artifacts cannot contain infinity")
        return numeric
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if pd.isna(value):
        return None
    return str(value)


def _aware_index(values: object, name: str) -> pd.DatetimeIndex:
    converted = []
    try:
        iterator = iter(cast(Iterable[object], values))
    except TypeError as exc:
        raise EvaluationRunnerError(f"{name} must be an iterable of timestamps") from exc
    for value in iterator:
        timestamp = _aware_timestamp(value, name)
        converted.append(timestamp)
    return pd.DatetimeIndex(converted)


def _aware_timestamp(value: object, name: str) -> pd.Timestamp:
    try:
        timestamp = pd.Timestamp(value)
    except (TypeError, ValueError) as exc:
        raise EvaluationRunnerError(f"{name} must contain valid timestamps") from exc
    if pd.isna(timestamp) or timestamp.tzinfo is None:
        raise EvaluationRunnerError(f"{name} must be timezone-aware")
    return timestamp.tz_convert("UTC")


__all__ = [
    "COMPARABLE_METRIC_DIRECTIONS",
    "EVALUATION_RUNNER_VERSION",
    "EvaluationFoldResult",
    "EvaluationRunRequest",
    "EvaluationRunnerError",
    "ForecastSubmission",
    "run_evaluation_fold",
    "write_evaluation_fold_result",
]
