"""Paired fold aggregation with explicit final-holdout isolation."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from numbers import Integral, Real

import numpy as np
import pandas as pd

from kronos_data.hashing import canonical_json, hash_configuration

AGGREGATION_VERSION = "1.0.0"
REQUIRED_FOLD_SCORE_COLUMNS = (
    "model_name",
    "fold_id",
    "metric_name",
    "value",
    "higher_is_better",
)


class FoldAggregationError(ValueError):
    """Raised when fold scores are incomplete or selection-contaminated."""


@dataclass(frozen=True)
class FoldAggregationRequest:
    dataset_id: str
    code_commit: str
    scores: pd.DataFrame = field(repr=False, compare=False)
    reference_baseline: str
    final_holdout_fold_id: str | None = None
    bootstrap_samples: int = 2_000
    confidence_level: float = 0.95
    seed: int = 0

    def __post_init__(self) -> None:
        for name in ("dataset_id", "reference_baseline"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise FoldAggregationError(f"{name} must be a non-empty string")
        if self.final_holdout_fold_id is not None and (
            not isinstance(self.final_holdout_fold_id, str)
            or not self.final_holdout_fold_id.strip()
        ):
            raise FoldAggregationError(
                "final_holdout_fold_id must be a non-empty string when supplied"
            )
        if not isinstance(self.code_commit, str) or re.fullmatch(
            r"[0-9a-f]{7,64}", self.code_commit
        ) is None:
            raise FoldAggregationError(
                "code_commit must be a lowercase hexadecimal Git SHA"
            )
        _positive_integer(self.bootstrap_samples, "bootstrap_samples")
        if self.bootstrap_samples > 1_000_000:
            raise FoldAggregationError("bootstrap_samples cannot exceed 1,000,000")
        if not isinstance(self.confidence_level, Real) or isinstance(
            self.confidence_level, bool
        ):
            raise FoldAggregationError("confidence_level must be a real number")
        if not 0 < float(self.confidence_level) < 1:
            raise FoldAggregationError("confidence_level must be between zero and one")
        if isinstance(self.seed, bool) or not isinstance(self.seed, Integral):
            raise FoldAggregationError("seed must be an integer")
        if not 0 <= int(self.seed) < 2**63:
            raise FoldAggregationError("seed must be between 0 and 2**63 - 1")


@dataclass(frozen=True)
class FoldAggregationResult:
    aggregation_version: str
    dataset_id: str
    code_commit: str
    reference_baseline: str
    final_holdout_fold_id: str | None
    score_hash: str
    configuration_hash: str
    development_comparison: pd.DataFrame
    final_holdout_comparison: pd.DataFrame
    warnings: tuple[str, ...]


def aggregate_fold_scores(request: FoldAggregationRequest) -> FoldAggregationResult:
    """Aggregate paired development folds against one predeclared baseline."""

    scores = _validated_scores(request)
    final_mask = (
        scores["fold_id"] == request.final_holdout_fold_id
        if request.final_holdout_fold_id is not None
        else np.zeros(len(scores), dtype=bool)
    )
    development = scores.loc[~final_mask].copy()
    final = scores.loc[final_mask].copy()
    development_comparison = _paired_comparison(
        development,
        reference_baseline=request.reference_baseline,
        bootstrap_samples=request.bootstrap_samples,
        confidence_level=float(request.confidence_level),
        seed=int(request.seed),
    )
    final_comparison = _final_comparison(
        final,
        reference_baseline=request.reference_baseline,
    )
    warnings = [
        "confidence intervals quantify paired fold resampling only and do not remove market dependence",
        "multiple metrics, models, horizons, regimes, seeds, and perturbations require multiplicity disclosure",
        "the reference baseline must be selected without test or final-holdout outcomes",
        "a majority of fold wins is necessary but not sufficient for model promotion",
    ]
    if request.final_holdout_fold_id is None:
        warnings.append("no final holdout score was supplied; no confirmation claim is possible")
    configuration = {
        "aggregation_version": AGGREGATION_VERSION,
        "reference_baseline": request.reference_baseline,
        "final_holdout_fold_id": request.final_holdout_fold_id,
        "bootstrap_samples": request.bootstrap_samples,
        "confidence_level": request.confidence_level,
        "seed": int(request.seed),
    }
    return FoldAggregationResult(
        aggregation_version=AGGREGATION_VERSION,
        dataset_id=request.dataset_id.strip(),
        code_commit=request.code_commit,
        reference_baseline=request.reference_baseline.strip(),
        final_holdout_fold_id=request.final_holdout_fold_id,
        score_hash=_score_hash(scores),
        configuration_hash=hash_configuration(configuration),
        development_comparison=development_comparison,
        final_holdout_comparison=final_comparison,
        warnings=tuple(warnings),
    )


def _validated_scores(request: FoldAggregationRequest) -> pd.DataFrame:
    if not isinstance(request, FoldAggregationRequest):
        raise TypeError("request must be a FoldAggregationRequest")
    if not isinstance(request.scores, pd.DataFrame):
        raise FoldAggregationError("scores must be a pandas DataFrame")
    missing = [
        column for column in REQUIRED_FOLD_SCORE_COLUMNS if column not in request.scores.columns
    ]
    if missing:
        raise FoldAggregationError(f"scores are missing required columns: {missing}")
    frame = request.scores.loc[:, REQUIRED_FOLD_SCORE_COLUMNS].copy(deep=True)
    if frame.empty:
        raise FoldAggregationError("scores must not be empty")
    for column in ("model_name", "fold_id", "metric_name"):
        frame[column] = frame[column].astype("string")
        if frame[column].isna().any() or (frame[column].astype(str).str.strip() == "").any():
            raise FoldAggregationError(f"{column} must contain non-empty labels")
    try:
        frame["value"] = pd.to_numeric(frame["value"], errors="raise")
    except (TypeError, ValueError) as exc:
        raise FoldAggregationError("score values must be numeric") from exc
    if not np.isfinite(frame["value"].to_numpy(dtype=float)).all():
        raise FoldAggregationError("score values must be finite")
    if not frame["higher_is_better"].map(
        lambda value: isinstance(value, (bool, np.bool_))
    ).all():
        raise FoldAggregationError("higher_is_better must contain booleans")
    frame["higher_is_better"] = frame["higher_is_better"].astype(bool)
    if frame.duplicated(["model_name", "fold_id", "metric_name"]).any():
        raise FoldAggregationError("each model/fold/metric score must be unique")
    direction_counts = frame.groupby("metric_name")["higher_is_better"].nunique()
    if (direction_counts != 1).any():
        raise FoldAggregationError("one metric cannot mix optimization directions")
    if request.reference_baseline not in set(frame["model_name"].astype(str)):
        raise FoldAggregationError("reference_baseline is absent from scores")
    if request.final_holdout_fold_id is not None and request.final_holdout_fold_id not in set(
        frame["fold_id"].astype(str)
    ):
        raise FoldAggregationError("final_holdout_fold_id is absent from scores")
    expected_grid = set(
        frame[["fold_id", "metric_name"]].itertuples(index=False, name=None)
    )
    for model_name, group in frame.groupby("model_name", sort=True, observed=True):
        actual_grid = set(group[["fold_id", "metric_name"]].itertuples(index=False, name=None))
        if actual_grid != expected_grid:
            raise FoldAggregationError(
                f"model {model_name!s} does not cover the complete fold/metric grid"
            )
    development_folds = set(frame["fold_id"].astype(str))
    if request.final_holdout_fold_id is not None:
        development_folds.remove(request.final_holdout_fold_id)
    if len(development_folds) < 2:
        raise FoldAggregationError("at least two development folds are required")
    return frame.sort_values(
        ["metric_name", "model_name", "fold_id"], kind="mergesort"
    ).reset_index(drop=True)


def _paired_comparison(
    scores: pd.DataFrame,
    *,
    reference_baseline: str,
    bootstrap_samples: int,
    confidence_level: float,
    seed: int,
) -> pd.DataFrame:
    rows = []
    for metric_name, metric_scores in scores.groupby("metric_name", sort=True, observed=True):
        direction = bool(metric_scores["higher_is_better"].iloc[0])
        pivot = metric_scores.pivot(index="fold_id", columns="model_name", values="value")
        reference = pivot[reference_baseline].to_numpy()
        for model_name in sorted(pivot.columns.astype(str)):
            values = pivot[model_name].to_numpy()
            signed_difference = values - reference if direction else reference - values
            derived_seed = int.from_bytes(
                hashlib.sha256(
                    f"{seed}\x1f{metric_name}\x1f{model_name}".encode()
                ).digest()[:8],
                "big",
            )
            generator = np.random.default_rng(derived_seed)
            samples = generator.integers(
                0,
                len(signed_difference),
                size=(bootstrap_samples, len(signed_difference)),
            )
            bootstrap_means = np.mean(signed_difference[samples], axis=1)
            alpha = (1.0 - confidence_level) / 2.0
            rows.append(
                {
                    "metric_name": metric_name,
                    "model_name": model_name,
                    "reference_baseline": reference_baseline,
                    "higher_is_better": direction,
                    "fold_count": len(signed_difference),
                    "model_mean": float(np.mean(values)),
                    "reference_mean": float(np.mean(reference)),
                    "signed_improvement_mean": float(np.mean(signed_difference)),
                    "signed_improvement_median": float(np.median(signed_difference)),
                    "improved_fold_count": int(np.sum(signed_difference > 0.0)),
                    "tied_fold_count": int(np.sum(signed_difference == 0.0)),
                    "improved_fold_fraction": float(np.mean(signed_difference > 0.0)),
                    "bootstrap_ci_lower": float(np.quantile(bootstrap_means, alpha)),
                    "bootstrap_ci_upper": float(np.quantile(bootstrap_means, 1.0 - alpha)),
                }
            )
    return pd.DataFrame(rows)


def _final_comparison(scores: pd.DataFrame, *, reference_baseline: str) -> pd.DataFrame:
    columns = [
        "metric_name",
        "model_name",
        "reference_baseline",
        "higher_is_better",
        "model_value",
        "reference_value",
        "signed_improvement",
    ]
    if scores.empty:
        return pd.DataFrame(columns=columns)
    rows = []
    for metric_name, metric_scores in scores.groupby("metric_name", sort=True, observed=True):
        direction = bool(metric_scores["higher_is_better"].iloc[0])
        values = metric_scores.set_index("model_name")["value"]
        reference = float(values.loc[reference_baseline])
        for model_name in sorted(values.index.astype(str)):
            value = float(values.loc[model_name])
            improvement = value - reference if direction else reference - value
            rows.append(
                {
                    "metric_name": metric_name,
                    "model_name": model_name,
                    "reference_baseline": reference_baseline,
                    "higher_is_better": direction,
                    "model_value": value,
                    "reference_value": reference,
                    "signed_improvement": improvement,
                }
            )
    return pd.DataFrame(rows, columns=columns)


def _score_hash(frame: pd.DataFrame) -> str:
    records = []
    for row in frame.itertuples(index=False, name=None):
        records.append(
            [
                bool(value)
                if isinstance(value, (bool, np.bool_))
                else float(value)
                if isinstance(value, (float, np.floating))
                else str(value)
                for value in row
            ]
        )
    return hashlib.sha256(
        canonical_json({"columns": list(frame.columns), "records": records}).encode("utf-8")
    ).hexdigest()


def _positive_integer(value: object, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, Integral) or int(value) <= 0:
        raise FoldAggregationError(f"{name} must be a positive integer")


__all__ = [
    "AGGREGATION_VERSION",
    "REQUIRED_FOLD_SCORE_COLUMNS",
    "FoldAggregationError",
    "FoldAggregationRequest",
    "FoldAggregationResult",
    "aggregate_fold_scores",
]
