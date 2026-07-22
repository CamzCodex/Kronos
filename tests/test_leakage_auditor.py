from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import numpy as np
import pandas as pd

from kronos_data.leakage import (
    LeakageAuditSpec,
    NormalizationProbe,
    SplitBoundary,
    SplitRole,
    UniversePolicy,
    audit_leakage,
)


def _causal_normalizer(frame: pd.DataFrame, boundary: int) -> np.ndarray:
    history = frame.iloc[:boundary][["close"]].to_numpy(dtype=float)
    return (history - history.mean(axis=0)) / history.std(axis=0)


def _leaky_normalizer(frame: pd.DataFrame, boundary: int) -> np.ndarray:
    all_values = frame[["close"]].to_numpy(dtype=float)
    history = all_values[:boundary]
    return (history - all_values.mean(axis=0)) / all_values.std(axis=0)


def _splits() -> tuple[SplitBoundary, ...]:
    return (
        SplitBoundary("train", SplitRole.TRAIN, "2025-01-01T00:00:00Z", "2025-01-31T00:00:00Z"),
        SplitBoundary(
            "validation",
            SplitRole.VALIDATION,
            "2025-02-03T00:00:00Z",
            "2025-02-14T00:00:00Z",
        ),
        SplitBoundary(
            "calibration",
            SplitRole.CALIBRATION,
            "2025-02-17T00:00:00Z",
            "2025-02-21T00:00:00Z",
        ),
        SplitBoundary("test", SplitRole.TEST, "2025-02-24T00:00:00Z", "2025-02-28T00:00:00Z"),
        SplitBoundary(
            "final",
            SplitRole.FINAL_HOLDOUT,
            "2025-03-03T00:00:00Z",
            "2025-03-07T00:00:00Z",
        ),
    )


def _sample_windows() -> pd.DataFrame:
    rows = []
    targets = {
        "train": "2025-01-15",
        "validation": "2025-02-10",
        "calibration": "2025-02-19",
        "test": "2025-02-26",
        "final": "2025-03-05",
    }
    for split, target in targets.items():
        target_start = pd.Timestamp(target, tz="UTC")
        prediction = target_start - pd.Timedelta(days=1)
        rows.append(
            {
                "sample_id": f"{split}-1",
                "instrument_id": "AAPL",
                "split": split,
                "prediction_timestamp": prediction,
                "lookback_start": prediction - pd.Timedelta(days=10),
                "lookback_end": prediction,
                "target_start": target_start,
                "target_end": target_start,
                "normalization_end": prediction,
            }
        )
    return pd.DataFrame(rows)


def _clean_spec() -> LeakageAuditSpec:
    normalization_frame = pd.DataFrame({"close": [10.0, 11.0, 12.0, 13.0, 14.0, 15.0]})
    windows = _sample_windows()
    features = pd.DataFrame(
        [
            {
                "sample_id": row.sample_id,
                "feature_name": "rolling_mean_5",
                "prediction_timestamp": row.prediction_timestamp,
                "observation_timestamp": row.prediction_timestamp - pd.Timedelta(hours=1),
                "available_at": row.prediction_timestamp,
                "window_end": row.prediction_timestamp,
                "derived_from_target": False,
            }
            for row in windows.itertuples()
        ]
    )
    memberships = pd.DataFrame(
        [
            {
                "instrument_id": row.instrument_id,
                "prediction_timestamp": row.prediction_timestamp,
                "member_from": "2020-01-01T00:00:00Z",
                "member_to": "2026-01-01T00:00:00Z",
                "membership_known_at": "2024-12-01T00:00:00Z",
                "included": True,
            }
            for row in windows.itertuples()
        ]
    )
    return LeakageAuditSpec(
        dataset_id="kds-fixture",
        code_commit="0123456789abcdef",
        audited_at="2025-03-08T00:00:00Z",
        splits=_splits(),
        sample_windows=windows,
        feature_provenance=features,
        universe_policy=UniversePolicy(True, True, True, "fixture membership history"),
        universe_membership=memberships,
        selection_events=pd.DataFrame(
            [
                {
                    "purpose": "select",
                    "split": "validation",
                    "occurred_at": "2025-02-15T00:00:00Z",
                },
                {
                    "purpose": "final_evaluate",
                    "split": "final",
                    "occurred_at": "2025-03-08T00:00:00Z",
                },
            ]
        ),
        final_config_frozen_at="2025-02-22T00:00:00Z",
        normalization_probes=(
            NormalizationProbe(
                normalization_frame,
                prediction_position=4,
                feature_columns=("close",),
                normalizer=_causal_normalizer,
            ),
        ),
        expected_feature_names=("rolling_mean_5",),
        adjustment_policy="backward_adjusted",
        corporate_action_provenance_complete=True,
        required_embargo=timedelta(days=1),
        require_final_holdout_evaluation=True,
    )


def _codes(result) -> set[str]:
    return {finding.code for finding in result.failures}


def test_clean_causal_fixture_passes_every_audit():
    result = audit_leakage(_clean_spec())

    assert result.passed, result.to_dict()
    assert not result.failures
    assert result.dataset_id == "kds-fixture"


def test_future_target_perturbation_catches_leaky_normalization():
    spec = _clean_spec()
    leaky_probe = replace(spec.normalization_probes[0], normalizer=_leaky_normalizer)

    result = audit_leakage(replace(spec, normalization_probes=(leaky_probe,)))

    assert not result.passed
    assert "future_changes_historical_normalization" in _codes(result)


def test_overlapping_split_targets_are_rejected():
    spec = _clean_spec()
    overlapping = list(spec.splits)
    overlapping[1] = replace(
        overlapping[1], target_start="2025-01-30T00:00:00Z"
    )

    result = audit_leakage(replace(spec, splits=tuple(overlapping)))

    assert "split_target_overlap" in _codes(result)


def test_target_label_crossing_split_is_rejected():
    spec = _clean_spec()
    windows = spec.sample_windows.copy()
    windows.loc[windows["split"].eq("validation"), "target_end"] = pd.Timestamp(
        "2025-02-20T00:00:00Z"
    )

    result = audit_leakage(replace(spec, sample_windows=windows))

    assert "sample_label_crosses_split" in _codes(result)


def test_future_feature_availability_and_window_are_rejected():
    spec = _clean_spec()
    features = spec.feature_provenance.copy()
    features.loc[0, "available_at"] = "2025-02-11T00:00:00Z"
    features.loc[0, "window_end"] = "2025-02-12T00:00:00Z"

    result = audit_leakage(replace(spec, feature_provenance=features))

    assert {
        "feature_available_after_prediction",
        "rolling_window_uses_future",
    } <= _codes(result)


def test_future_corporate_action_adjustment_is_rejected():
    spec = _clean_spec()
    actions = pd.DataFrame(
        [
            {
                "instrument_id": "AAPL",
                "prediction_timestamp": "2025-02-10T00:00:00Z",
                "feature_timestamp": "2025-02-09T00:00:00Z",
                "action_effective_at": "2025-02-12T00:00:00Z",
                "action_known_at": "2025-02-11T00:00:00Z",
                "adjustment_applied": True,
            }
        ]
    )

    result = audit_leakage(replace(spec, corporate_actions=actions))

    assert {
        "future_corporate_action_knowledge",
        "future_effective_action_applied",
    } <= _codes(result)


def test_survivorship_prone_universe_policy_is_rejected():
    spec = _clean_spec()
    policy = replace(spec.universe_policy, includes_delisted=False)

    result = audit_leakage(replace(spec, universe_policy=policy))

    assert "delisted_instruments_excluded" in _codes(result)


def test_model_selection_cannot_access_final_holdout():
    spec = _clean_spec()
    events = spec.selection_events.copy()
    events.loc[len(events)] = {
        "purpose": "hyperparameter_search",
        "split": "final",
        "occurred_at": "2025-03-09T00:00:00Z",
    }

    result = audit_leakage(replace(spec, selection_events=events))

    assert "selection_accesses_evaluation_split" in _codes(result)
    assert "selection_after_final_holdout" in _codes(result)


def test_missing_normalization_probe_invalidates_audit():
    result = audit_leakage(replace(_clean_spec(), normalization_probes=()))

    assert "normalization_probe_missing" in _codes(result)


def test_missing_feature_provenance_for_one_sample_is_rejected():
    spec = _clean_spec()
    features = spec.feature_provenance.iloc[:-1].copy()

    result = audit_leakage(replace(spec, feature_provenance=features))

    assert "feature_provenance_incomplete" in _codes(result)
