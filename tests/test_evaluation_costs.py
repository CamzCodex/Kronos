"""Regression tests for causal paper-return cost accounting."""

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from kronos_eval import (
    CostAssumptions,
    CostEvaluationRequest,
    CostModelError,
    evaluate_cost_scenarios,
    evaluate_paper_returns,
)


def _decisions():
    rows = []
    targets = ((0.5, -0.5), (0.5, -0.5), (0.0, 0.0))
    returns = ((0.02, -0.01), (0.01, 0.02), (0.03, -0.02))
    for period, (weights, outcomes) in enumerate(zip(targets, returns, strict=True)):
        decision = pd.Timestamp("2024-01-02", tz="UTC") + pd.Timedelta(days=period)
        realization = decision + pd.Timedelta(days=1)
        for instrument_number, instrument in enumerate(("A", "B")):
            rows.append(
                {
                    "decision_timestamp": decision,
                    "realization_timestamp": realization,
                    "dollar_volume_as_of_timestamp": decision,
                    "instrument_id": instrument,
                    "target_weight": weights[instrument_number],
                    "realized_return": outcomes[instrument_number],
                    "dollar_volume": 100_000_000.0,
                    "sector": "tech" if instrument == "A" else "finance",
                }
            )
    return pd.DataFrame(rows)


def _assumptions(**overrides):
    values = {
        "commission_bps": 1.0,
        "half_spread_bps": 2.0,
        "slippage_bps": 1.0,
        "impact_coefficient_bps": 10.0,
        "maximum_participation_rate": 0.1,
    }
    values.update(overrides)
    return CostAssumptions(**values)


def _request(**overrides):
    values = {
        "strategy_name": "paper-fixture",
        "dataset_id": "kds-cost-fixture",
        "fold_id": "fold-001",
        "code_commit": "a" * 40,
        "decisions": _decisions(),
        "assumptions": _assumptions(),
        "portfolio_notional": 1_000_000.0,
    }
    values.update(overrides)
    return CostEvaluationRequest(**values)


def test_cost_ledger_has_causal_periods_turnover_and_component_identity():
    result = evaluate_paper_returns(_request())

    assert list(result.period_ledger["turnover"]) == pytest.approx([1.0, 0.0, 1.0])
    assert result.metrics["total_turnover"] == pytest.approx(2.0)
    components = (
        result.metrics["commission_cost_return"]
        + result.metrics["spread_cost_return"]
        + result.metrics["slippage_cost_return"]
        + result.metrics["impact_cost_return"]
    )
    assert result.metrics["total_cost_return"] == pytest.approx(components)
    assert (
        result.period_ledger["net_return"]
        == result.period_ledger["gross_return"]
        - result.period_ledger["total_cost_return"]
    ).all()
    assert (
        result.trade_ledger["realization_timestamp"]
        > result.trade_ledger["decision_timestamp"]
    ).all()
    assert len(result.input_hash) == 64
    assert len(result.assumptions_hash) == 64


def test_gross_returns_use_declared_target_weights_and_later_outcomes():
    result = evaluate_paper_returns(_request())

    assert list(result.period_ledger["gross_return"]) == pytest.approx(
        [0.5 * 0.02 + -0.5 * -0.01, 0.5 * 0.01 + -0.5 * 0.02, 0.0]
    )
    assert result.metrics["gross_compounded_return"] == pytest.approx(
        np.prod(1.0 + result.period_ledger["gross_return"]) - 1.0
    )
    assert result.metrics["net_compounded_return"] < result.metrics["gross_compounded_return"]


def test_zero_cost_scenario_matches_gross_return():
    zero = _assumptions(
        commission_bps=0.0,
        half_spread_bps=0.0,
        slippage_bps=0.0,
        impact_coefficient_bps=0.0,
    )
    result = evaluate_paper_returns(_request(assumptions=zero))

    assert result.metrics["total_cost_return"] == pytest.approx(0.0)
    assert result.metrics["net_compounded_return"] == pytest.approx(
        result.metrics["gross_compounded_return"]
    )


def test_cost_sensitivity_uses_one_unchanged_decision_identity():
    request = _request()
    np.random.seed(99)
    scenarios = evaluate_cost_scenarios(
        request,
        {
            "low": _assumptions(
                commission_bps=0.0,
                half_spread_bps=0.0,
                slippage_bps=0.0,
                impact_coefficient_bps=0.0,
            ),
            "high": _assumptions(
                commission_bps=5.0,
                half_spread_bps=10.0,
                slippage_bps=10.0,
                impact_coefficient_bps=50.0,
            ),
        },
    )

    assert tuple(scenarios) == ("high", "low")
    assert scenarios["high"].input_hash == scenarios["low"].input_hash
    assert scenarios["high"].metrics["total_cost_return"] > scenarios["low"].metrics[
        "total_cost_return"
    ]
    assert scenarios["high"].metrics["net_compounded_return"] < scenarios["low"].metrics[
        "net_compounded_return"
    ]


def test_sector_concentration_liquidity_and_exposure_are_reported():
    result = evaluate_paper_returns(_request())

    assert set(result.sector_exposure["sector"]) == {"tech", "finance"}
    assert result.metrics["maximum_gross_exposure"] == pytest.approx(1.0)
    assert result.metrics["maximum_absolute_net_exposure"] == pytest.approx(0.0)
    assert result.metrics["maximum_absolute_position"] == pytest.approx(0.5)
    assert result.metrics["maximum_concentration_hhi"] == pytest.approx(0.5)
    assert result.metrics["minimum_dollar_volume"] == pytest.approx(100_000_000.0)
    assert result.metrics["maximum_sector_gross_exposure"] == pytest.approx(0.5)
    assert any("not evidence of fills" in warning for warning in result.warnings)


def test_input_is_not_mutated_and_identity_changes_with_data_or_costs():
    request = _request()
    before = request.decisions.copy(deep=True)
    first = evaluate_paper_returns(request)
    changed_data = request.decisions.copy(deep=True)
    changed_data.loc[0, "realized_return"] += 0.001
    second = evaluate_paper_returns(replace(request, decisions=changed_data))
    third = evaluate_paper_returns(
        replace(request, assumptions=_assumptions(commission_bps=2.0))
    )
    fourth = evaluate_paper_returns(replace(request, portfolio_notional=2_000_000.0))

    pd.testing.assert_frame_equal(request.decisions, before)
    assert first.input_hash != second.input_hash
    assert first.assumptions_hash == second.assumptions_hash
    assert first.input_hash == third.input_hash
    assert first.assumptions_hash != third.assumptions_hash
    assert first.input_hash == fourth.input_hash
    assert first.assumptions_hash != fourth.assumptions_hash


def test_liquidity_cap_blocks_understated_cost_evaluation():
    decisions = _decisions()
    decisions.loc[0, "dollar_volume"] = 100_000.0

    with pytest.raises(CostModelError, match="exceeds declared maximum"):
        evaluate_paper_returns(_request(decisions=decisions))


def test_realization_must_follow_decision():
    decisions = _decisions()
    decisions.loc[0, "realization_timestamp"] = decisions.loc[0, "decision_timestamp"]

    with pytest.raises(CostModelError, match="later than"):
        evaluate_paper_returns(_request(decisions=decisions))


def test_cost_timestamps_must_be_aware_and_periods_non_overlapping():
    naive = _decisions()
    naive["decision_timestamp"] = naive["decision_timestamp"].dt.tz_localize(None)
    with pytest.raises(CostModelError, match="timezone-aware"):
        evaluate_paper_returns(_request(decisions=naive))

    overlapping = _decisions()
    third_period = overlapping["realization_timestamp"] == pd.Timestamp(
        "2024-01-05", tz="UTC"
    )
    overlapping.loc[third_period, "decision_timestamp"] = pd.Timestamp(
        "2024-01-03 12:00", tz="UTC"
    )
    overlapping.loc[third_period, "dollar_volume_as_of_timestamp"] = pd.Timestamp(
        "2024-01-03 12:00", tz="UTC"
    )
    with pytest.raises(CostModelError, match="must not overlap"):
        evaluate_paper_returns(_request(decisions=overlapping))


def test_liquidity_estimate_cannot_be_timestamped_after_decision():
    decisions = _decisions()
    decisions.loc[0, "dollar_volume_as_of_timestamp"] = (
        decisions.loc[0, "decision_timestamp"] + pd.Timedelta(seconds=1)
    )
    with pytest.raises(CostModelError, match="cannot be later"):
        evaluate_paper_returns(_request(decisions=decisions))


def test_complete_universe_and_unique_rows_are_required():
    missing = _decisions().drop(index=0).reset_index(drop=True)
    with pytest.raises(CostModelError, match="same complete instrument universe"):
        evaluate_paper_returns(_request(decisions=missing))

    duplicated = pd.concat([_decisions(), _decisions().iloc[[0]]], ignore_index=True)
    with pytest.raises(CostModelError, match="must be unique"):
        evaluate_paper_returns(_request(decisions=duplicated))


@pytest.mark.parametrize(
    ("column", "value", "message"),
    [
        ("target_weight", np.nan, "finite"),
        ("realized_return", -1.0, "greater than -1"),
        ("dollar_volume", 0.0, "positive"),
        ("sector", "", "non-empty"),
    ],
)
def test_invalid_decision_values_are_rejected(column, value, message):
    decisions = _decisions()
    decisions.loc[0, column] = value
    with pytest.raises(CostModelError, match=message):
        evaluate_paper_returns(_request(decisions=decisions))


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"commission_bps": -1.0}, "non-negative"),
        ({"half_spread_bps": np.nan}, "finite"),
        ({"impact_exponent": 0.0}, "positive"),
        ({"maximum_participation_rate": 1.1}, "at most one"),
        ({"periods_per_year": 0}, "positive integer"),
    ],
)
def test_invalid_cost_assumptions_are_rejected(change, message):
    with pytest.raises(CostModelError, match=message):
        _assumptions(**change)


def test_invalid_request_controls_are_rejected():
    with pytest.raises(CostModelError, match="Git SHA"):
        _request(code_commit="bad")
    with pytest.raises(CostModelError, match="positive"):
        _request(portfolio_notional=0.0)
    with pytest.raises(CostModelError, match="non-empty"):
        evaluate_cost_scenarios(_request(), {})
