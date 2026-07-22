"""Regression tests for the audit-gated development-fold runner."""

import hashlib
import json
from dataclasses import replace

import pandas as pd
import pytest

from kronos_data import REQUIRED_LEAKAGE_CHECKS, LeakageAuditResult
from kronos_eval import (
    MANDATORY_BASELINES,
    AuditedWalkForwardFold,
    CostAssumptions,
    CostEvaluationRequest,
    EvaluationContext,
    EvaluationRunnerError,
    EvaluationRunRequest,
    ForecastMetricRequest,
    ForecastSubmission,
    WalkForwardConfig,
    attach_leakage_audit,
    build_walk_forward_plan,
    run_evaluation_fold,
    write_evaluation_fold_result,
)


def _audited_fold():
    timestamps = pd.date_range("2020-01-01", periods=80, freq="B", tz="UTC")
    context = EvaluationContext.create(
        dataset_id="kds-runner-fixture",
        code_commit="a" * 40,
        feature_schema_version="1.0.0",
        model_revision="checkpoint-fixture",
        cost_assumptions={
            "commission_bps": 1.0,
            "half_spread_bps": 5.0,
            "slippage_bps": 3.0,
        },
        seed=42,
    )
    plan = build_walk_forward_plan(
        timestamps,
        configuration=WalkForwardConfig(
            mode="expanding",
            train_size=10,
            validation_size=4,
            calibration_size=2,
            test_size=3,
            final_holdout_size=5,
            purge_size=1,
            embargo_size=2,
            minimum_folds=2,
        ),
        context=context,
        created_at="2026-07-22T04:00:00Z",
    )
    fold = plan.folds[0]
    audit = LeakageAuditResult(
        passed=True,
        checks=REQUIRED_LEAKAGE_CHECKS,
        failures=(),
        warnings=(),
        dataset_id=fold.dataset_id,
        code_commit=fold.code_commit,
        audited_at="2026-07-22T04:01:00+00:00",
        audit_id="kla-0123456789abcdef01234567",
        split_hash=fold.split_hash,
    )
    return attach_leakage_audit(fold, audit)


def _observations(audited, model_number):
    rows = []
    targets = pd.date_range(
        audited.fold.test.start,
        audited.fold.test.end,
        freq="B",
    )
    for target_number, target in enumerate(targets):
        for instrument_number in range(6):
            reference = 100.0 + instrument_number
            actual_return = (instrument_number - 2.5) * 0.01 + target_number * 0.001
            forecast_return = actual_return + model_number * 0.0001
            actual = reference * (1.0 + actual_return)
            point = reference * (1.0 + forecast_return)
            rows.append(
                {
                    "instrument_id": f"I{instrument_number}",
                    "as_of_timestamp": target - pd.offsets.BDay(),
                    "target_timestamp": target,
                    "horizon": 1,
                    "reference_value": reference,
                    "actual_value": actual,
                    "point_forecast": point,
                    "scale_error": 2.0,
                    "probability_positive": 0.75 if forecast_return > 0 else 0.25,
                    "market_regime": "up" if target_number else "flat",
                    "volatility_regime": "high" if instrument_number >= 3 else "low",
                    "quantile_0.05": point * 0.98,
                    "quantile_0.5": point,
                    "quantile_0.95": point * 1.02,
                }
            )
    return pd.DataFrame(rows)


def _submission(audited, model_name, model_number, *, information_hash="1" * 64):
    metric_request = ForecastMetricRequest(
        model_name=model_name,
        dataset_id=audited.fold.dataset_id,
        fold_id=audited.fold.fold_id,
        code_commit=audited.fold.code_commit,
        observations=_observations(audited, model_number),
        minimum_cross_section=5,
        calibration_bins=5,
    )
    return ForecastSubmission(
        request=metric_request,
        information_set_hash=information_hash,
        forecast_configuration_hash=hashlib.sha256(f"config-{model_name}".encode()).hexdigest(),
        forecast_artifact_hash=hashlib.sha256(f"artifact-{model_name}".encode()).hexdigest(),
        is_baseline=model_name in MANDATORY_BASELINES,
    )


def _submissions(audited):
    names = (*MANDATORY_BASELINES, "kronos")
    return tuple(
        _submission(audited, name, number)
        for number, name in enumerate(names)
    )


def _cost_request(audited, **overrides):
    rows = []
    targets = pd.date_range(
        audited.fold.test.start,
        audited.fold.test.end,
        freq="B",
    )
    for target_number, target in enumerate(targets):
        decision = target - pd.offsets.BDay()
        for instrument, weight, outcome in (
            ("I0", 0.5 if target_number < 2 else 0.0, 0.01),
            ("I1", -0.5 if target_number < 2 else 0.0, -0.005),
        ):
            rows.append(
                {
                    "decision_timestamp": decision,
                    "realization_timestamp": target,
                    "dollar_volume_as_of_timestamp": decision,
                    "instrument_id": instrument,
                    "target_weight": weight,
                    "realized_return": outcome,
                    "dollar_volume": 100_000_000.0,
                    "sector": "one" if instrument == "I0" else "two",
                }
            )
    values = {
        "strategy_name": "paper-kronos",
        "dataset_id": audited.fold.dataset_id,
        "fold_id": audited.fold.fold_id,
        "code_commit": audited.fold.code_commit,
        "decisions": pd.DataFrame(rows),
        "assumptions": CostAssumptions(
            commission_bps=1.0,
            half_spread_bps=5.0,
            slippage_bps=3.0,
            impact_coefficient_bps=10.0,
        ),
        "portfolio_notional": 1_000_000.0,
    }
    values.update(overrides)
    return CostEvaluationRequest(**values)


def _request(**overrides):
    audited = overrides.pop("audited_fold", _audited_fold())
    values = {
        "audited_fold": audited,
        "submissions": _submissions(audited),
        "candidate_model_name": "kronos",
        "reference_baseline": "last_value",
        "created_at": "2026-07-22T04:02:00Z",
        "cost_requests": (),
    }
    values.update(overrides)
    return EvaluationRunRequest(**values)


def test_complete_passed_audited_suite_produces_all_scorecards_and_comparable_grid():
    result = run_evaluation_fold(_request())

    assert set(result.scorecards) == set(MANDATORY_BASELINES) | {"kronos"}
    assert result.audit_id.startswith("kla-")
    assert result.run_id.startswith("ker-")
    assert len(result.truth_hash) == 64
    assert len(result.submissions_hash) == 64
    assert set(result.comparable_scores["model_name"]) == set(result.scorecards)
    counts = result.comparable_scores.groupby("metric_name")["model_name"].nunique()
    assert (counts == 12).all()
    assert any("economic metrics are unavailable" in warning for warning in result.warnings)


def test_paper_cost_path_is_downstream_and_bound_to_the_same_fold():
    request = _request()
    cost = _cost_request(request.audited_fold)
    result = run_evaluation_fold(replace(request, cost_requests=(cost,)))

    assert set(result.cost_results) == {"paper-kronos"}
    assert result.cost_results["paper-kronos"].metrics["total_turnover"] > 0
    assert not any("economic metrics are unavailable" in warning for warning in result.warnings)
    payload = result.to_dict()
    assert payload["cost_results"]["paper-kronos"]["trade_ledger"]["records"]
    assert json.loads(result.to_json())["cost_results"]["paper-kronos"]["metrics"]


def test_missing_extra_or_mislabeled_baselines_are_rejected():
    request = _request()
    with pytest.raises(EvaluationRunnerError, match="missing="):
        run_evaluation_fold(replace(request, submissions=request.submissions[:-1]))

    extra = _submission(request.audited_fold, "extra", 20)
    with pytest.raises(EvaluationRunnerError, match="extra="):
        run_evaluation_fold(replace(request, submissions=(*request.submissions, extra)))

    mislabeled = replace(request.submissions[0], is_baseline=False)
    with pytest.raises(EvaluationRunnerError, match="labels"):
        run_evaluation_fold(replace(request, submissions=(mislabeled, *request.submissions[1:])))


def test_failed_or_incomplete_audit_cannot_run_even_if_manually_wrapped():
    request = _request()
    audit = request.audited_fold.leakage_audit
    failed = replace(audit, passed=False)
    manual = AuditedWalkForwardFold(fold=request.audited_fold.fold, leakage_audit=failed)
    with pytest.raises(EvaluationRunnerError, match="failed leakage"):
        run_evaluation_fold(_request(audited_fold=manual))

    incomplete = replace(audit, checks=("split_boundaries",))
    manual = AuditedWalkForwardFold(fold=request.audited_fold.fold, leakage_audit=incomplete)
    with pytest.raises(EvaluationRunnerError, match="missing checks"):
        run_evaluation_fold(_request(audited_fold=manual))


def test_submission_identity_and_information_set_must_match():
    request = _request()
    first = request.submissions[0]
    bad_metric = replace(first.request, dataset_id="wrong")
    with pytest.raises(EvaluationRunnerError, match="dataset_id"):
        run_evaluation_fold(
            replace(request, submissions=(replace(first, request=bad_metric), *request.submissions[1:]))
        )

    different_info = replace(request.submissions[-1], information_set_hash="2" * 64)
    with pytest.raises(EvaluationRunnerError, match="one information set"):
        run_evaluation_fold(replace(request, submissions=(*request.submissions[:-1], different_info)))


def test_all_models_must_share_identical_truth_scale_and_regime_rows():
    request = _request()
    changed_frame = request.submissions[-1].request.observations.copy(deep=True)
    changed_frame.loc[0, "actual_value"] *= 1.001
    changed_request = replace(request.submissions[-1].request, observations=changed_frame)
    changed = replace(request.submissions[-1], request=changed_request)

    with pytest.raises(EvaluationRunnerError, match="identical targets"):
        run_evaluation_fold(replace(request, submissions=(*request.submissions[:-1], changed)))


def test_test_boundary_and_final_holdout_are_enforced():
    request = _request()
    first = request.submissions[0]
    outside = first.request.observations.copy(deep=True)
    outside["target_timestamp"] = outside["target_timestamp"] + pd.Timedelta(days=30)
    outside["as_of_timestamp"] = outside["as_of_timestamp"] + pd.Timedelta(days=30)
    changed = replace(first, request=replace(first.request, observations=outside))
    with pytest.raises(EvaluationRunnerError, match="audited test boundary"):
        run_evaluation_fold(replace(request, submissions=(changed, *request.submissions[1:])))

    final = first.request.observations.copy(deep=True)
    final["target_timestamp"] = request.audited_fold.fold.final_holdout.start
    final["as_of_timestamp"] = request.audited_fold.fold.final_holdout.start - pd.offsets.BDay()
    changed = replace(first, request=replace(first.request, observations=final))
    with pytest.raises(EvaluationRunnerError, match="audited test boundary|final-holdout"):
        run_evaluation_fold(replace(request, submissions=(changed, *request.submissions[1:])))


def test_cost_identity_boundary_and_assumptions_must_match_audited_fold():
    request = _request()
    cost = _cost_request(request.audited_fold)
    wrong_cost = replace(cost, dataset_id="wrong")
    with pytest.raises(EvaluationRunnerError, match="cost dataset_id"):
        run_evaluation_fold(replace(request, cost_requests=(wrong_cost,)))

    wrong_assumption = replace(
        cost,
        assumptions=CostAssumptions(
            commission_bps=2.0,
            half_spread_bps=5.0,
            slippage_bps=3.0,
            impact_coefficient_bps=10.0,
        ),
    )
    with pytest.raises(EvaluationRunnerError, match="does not match"):
        run_evaluation_fold(replace(request, cost_requests=(wrong_assumption,)))

    outside = cost.decisions.copy(deep=True)
    outside["realization_timestamp"] += pd.Timedelta(days=30)
    outside["decision_timestamp"] += pd.Timedelta(days=30)
    outside["dollar_volume_as_of_timestamp"] += pd.Timedelta(days=30)
    with pytest.raises(EvaluationRunnerError, match="audited test boundary"):
        run_evaluation_fold(replace(request, cost_requests=(replace(cost, decisions=outside),)))


def test_run_identity_is_deterministic_and_binds_forecast_artifacts():
    request = _request()
    first = run_evaluation_fold(request)
    second = run_evaluation_fold(replace(request, created_at="2026-07-23T04:02:00Z"))
    changed_submission = replace(
        request.submissions[-1],
        forecast_artifact_hash="f" * 64,
    )
    changed = run_evaluation_fold(
        replace(request, submissions=(*request.submissions[:-1], changed_submission))
    )

    assert first.run_id == second.run_id
    assert first.run_id != changed.run_id


def test_immutable_result_writer_is_deterministic_and_preserves_existing(tmp_path):
    request = _request()
    result = run_evaluation_fold(request)
    path = tmp_path / "fold-result.json"

    assert write_evaluation_fold_result(result, path) == path
    first_bytes = path.read_bytes()
    assert write_evaluation_fold_result(result, path) == path
    parsed = json.loads(first_bytes)
    assert parsed["run_id"] == result.run_id
    assert "NaN" not in first_bytes.decode()

    changed = run_evaluation_fold(replace(request, created_at="2026-07-23T04:02:00Z"))
    with pytest.raises(FileExistsError, match="immutable result"):
        write_evaluation_fold_result(changed, path)
    assert path.read_bytes() == first_bytes


def test_created_at_must_follow_test_and_audit():
    with pytest.raises(EvaluationRunnerError, match="test end"):
        run_evaluation_fold(_request(created_at="2020-01-01T00:00:00Z"))
    with pytest.raises(EvaluationRunnerError, match="leakage audit"):
        run_evaluation_fold(_request(created_at="2026-07-22T04:00:30Z"))


def test_submission_hashes_and_runner_controls_are_validated():
    request = _request()
    with pytest.raises(EvaluationRunnerError, match="SHA-256"):
        replace(request.submissions[0], forecast_artifact_hash="bad")
    with pytest.raises(EvaluationRunnerError, match="mandatory baseline"):
        replace(request, reference_baseline="not-required")
    with pytest.raises(EvaluationRunnerError, match="cannot be a mandatory baseline"):
        replace(request, candidate_model_name="last_value")
