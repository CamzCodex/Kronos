"""Tests for immutable, leakage-gated walk-forward split plans."""

from dataclasses import replace

import pandas as pd
import pytest

from kronos_data import (
    REQUIRED_LEAKAGE_CHECKS,
    LeakageAuditResult,
    SplitRole,
    hash_split_boundaries,
)
from kronos_eval import (
    EvaluationContext,
    WalkForwardConfig,
    WalkForwardMode,
    attach_leakage_audit,
    build_walk_forward_plan,
    write_walk_forward_plan,
)


def _timestamps(count: int = 80) -> pd.DatetimeIndex:
    return pd.date_range("2020-01-01", periods=count, freq="B", tz="UTC")


def _context(**overrides) -> EvaluationContext:
    values = {
        "dataset_id": "kds-walk-forward-fixture",
        "code_commit": "a" * 40,
        "feature_schema_version": "1.0.0",
        "model_revision": "model-revision-fixture",
        "cost_assumptions": {
            "commission_bps": 1.0,
            "half_spread_bps": 5.0,
            "slippage_bps": 3.0,
        },
        "seed": 42,
    }
    values.update(overrides)
    return EvaluationContext.create(**values)


def _config(**overrides) -> WalkForwardConfig:
    values = {
        "mode": "expanding",
        "train_size": 10,
        "validation_size": 4,
        "calibration_size": 2,
        "test_size": 3,
        "purge_size": 1,
        "embargo_size": 2,
        "final_holdout_size": 5,
        "minimum_folds": 2,
    }
    values.update(overrides)
    return WalkForwardConfig(**values)


def _plan(**config_overrides):
    return build_walk_forward_plan(
        _timestamps(),
        configuration=_config(**config_overrides),
        context=_context(),
        created_at="2026-07-22T04:00:00Z",
    )


def _passed_audit(fold, **overrides) -> LeakageAuditResult:
    values = {
        "passed": True,
        "checks": REQUIRED_LEAKAGE_CHECKS,
        "failures": (),
        "warnings": (),
        "dataset_id": fold.dataset_id,
        "code_commit": fold.code_commit,
        "audited_at": "2026-07-22T04:01:00+00:00",
        "audit_id": "kla-0123456789abcdef01234567",
        "split_hash": fold.split_hash,
    }
    values.update(overrides)
    return LeakageAuditResult(**values)


def test_expanding_plan_records_every_boundary_purge_and_final_holdout():
    plan = _plan()
    first, second = plan.folds[:2]

    assert plan.configuration.mode is WalkForwardMode.EXPANDING
    assert len(plan.folds) == 5
    assert first.train.start_position == 0
    assert first.train.end_position == 9
    assert first.validation.start_position == 11
    assert first.validation.end_position == 14
    assert first.calibration.start_position == 16
    assert first.calibration.end_position == 17
    assert first.test.start_position == 19
    assert first.test.end_position == 21
    assert [window.observation_count for window in first.purged_windows] == [1, 1, 1]
    assert second.train.start_position == 0
    assert second.train.end_position == first.test.end_position
    assert first.test.end_position < second.validation.start_position
    assert plan.final_embargo.start_position == 73
    assert plan.final_embargo.end_position == 74
    assert plan.final_holdout.start_position == 75
    assert plan.final_holdout.end_position == 79
    assert all(fold.final_holdout == plan.final_holdout for fold in plan.folds)
    assert all(fold.test.end < plan.final_embargo.start for fold in plan.folds)
    assert plan.unused_development_window.start_position == 70
    assert plan.unused_development_window.end_position == 72


def test_rolling_plan_keeps_a_fixed_training_window():
    plan = _plan(mode="rolling")
    first, second = plan.folds[:2]

    assert first.train.observation_count == 10
    assert second.train.observation_count == 10
    assert first.train.start_position == 0
    assert second.train.start_position == 12
    assert second.train.end_position == first.test.end_position


def test_optional_calibration_is_omitted_without_reusing_roles():
    plan = _plan(calibration_size=0)
    first, second = plan.folds[:2]

    assert first.calibration is None
    assert len(first.purged_windows) == 2
    assert [boundary.role for boundary in first.split_boundaries()] == [
        SplitRole.TRAIN,
        SplitRole.VALIDATION,
        SplitRole.TEST,
        SplitRole.FINAL_HOLDOUT,
    ]
    assert second.train.end_position == first.test.end_position
    assert first.split_hash == hash_split_boundaries(first.split_boundaries())


def test_step_size_cannot_reuse_selection_or_test_observations():
    with pytest.raises(ValueError, match="cannot reuse"):
        _config(step_size=3)


def test_maximum_folds_selects_most_recent_development_periods():
    full = _plan()
    recent = _plan(maximum_folds=2)

    assert len(recent.folds) == 2
    assert recent.folds[0].train.end == full.folds[-2].train.end
    assert recent.folds[1].test.end == full.folds[-1].test.end
    assert recent.candidate_fold_count == 5
    assert recent.folds_truncated
    assert not recent.decision_grade_protocol


def test_plan_identity_is_deterministic_and_binds_research_context():
    first = _plan()
    second = build_walk_forward_plan(
        _timestamps(),
        configuration=_config(),
        context=_context(),
        created_at="2026-07-23T04:00:00Z",
    )
    changed_seed = build_walk_forward_plan(
        _timestamps(),
        configuration=_config(),
        context=_context(seed=43),
        created_at="2026-07-22T04:00:00Z",
    )

    assert first.plan_id == second.plan_id
    assert first.configuration_hash == second.configuration_hash
    assert first.timestamp_index_hash == second.timestamp_index_hash
    assert first.plan_id != changed_seed.plan_id
    assert first.folds[0].cost_assumptions_hash == first.context.cost_assumptions_hash
    assert first.folds[0].model_revision == "model-revision-fixture"


def test_immutable_plan_writer_accepts_identical_and_rejects_changed(tmp_path):
    path = tmp_path / "plan.json"
    plan = _plan()

    assert write_walk_forward_plan(plan, path) == path
    assert write_walk_forward_plan(plan, path) == path
    changed_creation_time = replace(
        plan,
        created_at=pd.Timestamp("2026-07-23T04:00:00Z"),
    )
    with pytest.raises(FileExistsError, match="immutable plan"):
        write_walk_forward_plan(changed_creation_time, path)


def test_passed_matching_audit_is_required_for_evaluation_attachment():
    fold = _plan().folds[0]
    audit = _passed_audit(fold)

    attached = attach_leakage_audit(fold, audit)

    assert attached.fold is fold
    assert attached.leakage_audit is audit
    assert attached.to_dict()["leakage_audit"]["split_hash"] == fold.split_hash


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"passed": False}, "failed leakage audits"),
        ({"dataset_id": "wrong-dataset"}, "dataset_id"),
        ({"code_commit": "b" * 40}, "code_commit"),
        ({"split_hash": "0" * 64}, "split_hash"),
        ({"audit_id": "invalid"}, "identity"),
        ({"checks": ("split_boundaries",)}, "missing required checks"),
    ],
)
def test_invalid_or_mismatched_audit_cannot_be_attached(change, message):
    fold = _plan().folds[0]
    audit = _passed_audit(fold, **change)

    with pytest.raises(ValueError, match=message):
        attach_leakage_audit(fold, audit)


@pytest.mark.parametrize(
    ("timestamps", "message"),
    [
        (pd.date_range("2020-01-01", periods=80, freq="B"), "timezone-aware"),
        (pd.DatetimeIndex([pd.Timestamp("2020-01-01", tz="UTC")] * 80), "strictly"),
        (pd.DatetimeIndex([]), "must not be empty"),
    ],
)
def test_invalid_timestamp_indexes_are_rejected(timestamps, message):
    with pytest.raises(ValueError, match=message):
        build_walk_forward_plan(
            timestamps,
            configuration=_config(),
            context=_context(),
            created_at="2026-07-22T04:00:00Z",
        )


def test_insufficient_history_cannot_degrade_to_one_favorable_fold():
    with pytest.raises(ValueError, match="minimum_folds"):
        build_walk_forward_plan(
            _timestamps(35),
            configuration=_config(),
            context=_context(),
            created_at="2026-07-22T04:00:00Z",
        )


def test_single_fold_debug_plan_is_explicitly_not_decision_grade():
    plan = build_walk_forward_plan(
        _timestamps(35),
        configuration=_config(minimum_folds=1),
        context=_context(),
        created_at="2026-07-22T04:00:00Z",
    )

    assert len(plan.folds) == 1
    assert not plan.decision_grade_fold_count_met
    assert not plan.decision_grade_protocol


def test_plan_cannot_be_created_before_its_latest_data_timestamp():
    with pytest.raises(ValueError, match="latest dataset timestamp"):
        build_walk_forward_plan(
            _timestamps(),
            configuration=_config(),
            context=_context(),
            created_at="2019-01-01T00:00:00Z",
        )


def test_cost_assumptions_must_be_canonical_finite_and_nonempty():
    with pytest.raises(ValueError, match="canonical"):
        EvaluationContext(
            dataset_id="dataset",
            code_commit="a" * 40,
            feature_schema_version="1",
            model_revision="model",
            cost_assumptions_json='{ "commission_bps": 1 }',
            seed=1,
        )
    with pytest.raises(ValueError, match="finite JSON"):
        _context(cost_assumptions={"commission_bps": float("nan")})


def test_plan_json_contains_no_implicit_or_unversioned_fold_fields():
    payload = _plan().to_dict()
    first = payload["folds"][0]

    assert payload["plan_id"].startswith("kwf-")
    assert payload["fold_count"] == 5
    assert payload["candidate_fold_count"] == 5
    assert payload["decision_grade_protocol"]
    assert first["dataset_id"] == "kds-walk-forward-fixture"
    assert first["feature_schema_version"] == "1.0.0"
    assert first["model_revision"] == "model-revision-fixture"
    assert first["seed"] == 42
    assert first["cost_assumptions"]["half_spread_bps"] == 5.0
    assert first["final_holdout"] == payload["final_holdout"]
