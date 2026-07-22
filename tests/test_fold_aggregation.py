"""Regression tests for paired fold aggregation and final isolation."""

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from kronos_eval import (
    FoldAggregationError,
    FoldAggregationRequest,
    aggregate_fold_scores,
)


def _scores():
    rows = []
    values = {
        "baseline": {
            "mae": [2.0, 2.2, 1.8, 2.1],
            "directional_accuracy": [0.50, 0.52, 0.48, 0.51],
        },
        "kronos": {
            "mae": [1.8, 2.0, 1.9, 2.0],
            "directional_accuracy": [0.55, 0.54, 0.49, 0.53],
        },
    }
    folds = ("fold-1", "fold-2", "fold-3", "final")
    for model, metrics in values.items():
        for metric, metric_values in metrics.items():
            for fold, value in zip(folds, metric_values, strict=True):
                rows.append(
                    {
                        "model_name": model,
                        "fold_id": fold,
                        "metric_name": metric,
                        "value": value,
                        "higher_is_better": metric == "directional_accuracy",
                    }
                )
    return pd.DataFrame(rows)


def _request(**overrides):
    values = {
        "dataset_id": "kds-aggregation-fixture",
        "code_commit": "a" * 40,
        "scores": _scores(),
        "reference_baseline": "baseline",
        "final_holdout_fold_id": "final",
        "bootstrap_samples": 500,
        "seed": 17,
    }
    values.update(overrides)
    return FoldAggregationRequest(**values)


def test_aggregation_pairs_every_model_metric_against_declared_baseline():
    result = aggregate_fold_scores(_request())
    comparison = result.development_comparison

    assert set(comparison["model_name"]) == {"baseline", "kronos"}
    assert set(comparison["metric_name"]) == {"mae", "directional_accuracy"}
    assert (comparison["fold_count"] == 3).all()
    mae = comparison[
        (comparison["model_name"] == "kronos") & (comparison["metric_name"] == "mae")
    ].iloc[0]
    assert mae["signed_improvement_mean"] == pytest.approx(np.mean([0.2, 0.2, -0.1]))
    assert mae["improved_fold_count"] == 2
    assert mae["improved_fold_fraction"] == pytest.approx(2 / 3)
    baseline = comparison[comparison["model_name"] == "baseline"]
    assert (baseline["signed_improvement_mean"] == 0.0).all()


def test_final_holdout_is_reported_separately_and_cannot_change_development_result():
    request = _request()
    first = aggregate_fold_scores(request)
    changed = request.scores.copy(deep=True)
    changed.loc[
        (changed["fold_id"] == "final") & (changed["model_name"] == "kronos"),
        "value",
    ] = [999.0, -999.0]
    second = aggregate_fold_scores(replace(request, scores=changed))

    pd.testing.assert_frame_equal(
        first.development_comparison,
        second.development_comparison,
    )
    assert not first.final_holdout_comparison.equals(second.final_holdout_comparison)
    assert set(first.final_holdout_comparison["metric_name"]) == {
        "mae",
        "directional_accuracy",
    }


def test_bootstrap_is_seeded_and_independent_of_global_rng():
    request = _request()
    np.random.seed(1)
    first = aggregate_fold_scores(request)
    np.random.seed(999)
    second = aggregate_fold_scores(request)
    changed = aggregate_fold_scores(replace(request, seed=18))

    pd.testing.assert_frame_equal(first.development_comparison, second.development_comparison)
    assert first.score_hash == changed.score_hash
    assert first.configuration_hash != changed.configuration_hash


def test_adding_a_model_cannot_change_existing_model_bootstrap_intervals():
    request = _request()
    first = aggregate_fold_scores(request)
    additional = request.scores.query("model_name == 'kronos'").copy(deep=True)
    additional["model_name"] = "another"
    expanded = pd.concat([request.scores, additional], ignore_index=True)
    second = aggregate_fold_scores(replace(request, scores=expanded))

    first_existing = first.development_comparison.query("model_name != 'another'")
    second_existing = second.development_comparison.query("model_name != 'another'")
    pd.testing.assert_frame_equal(
        first_existing.reset_index(drop=True),
        second_existing.reset_index(drop=True),
    )


def test_identity_changes_for_scores_and_configuration():
    request = _request()
    first = aggregate_fold_scores(request)
    changed_scores = request.scores.copy(deep=True)
    changed_scores.loc[0, "value"] += 0.01
    second = aggregate_fold_scores(replace(request, scores=changed_scores))
    third = aggregate_fold_scores(replace(request, bootstrap_samples=501))

    assert first.score_hash != second.score_hash
    assert first.configuration_hash == second.configuration_hash
    assert first.score_hash == third.score_hash
    assert first.configuration_hash != third.configuration_hash


def test_no_final_holdout_is_explicit_and_does_not_create_confirmation_rows():
    scores = _scores().query("fold_id != 'final'").copy()
    result = aggregate_fold_scores(
        _request(scores=scores, final_holdout_fold_id=None)
    )

    assert result.final_holdout_comparison.empty
    assert any("no final holdout" in warning for warning in result.warnings)


def test_missing_model_fold_metric_cell_is_rejected():
    scores = _scores().drop(index=0).reset_index(drop=True)
    with pytest.raises(FoldAggregationError, match="complete fold/metric grid"):
        aggregate_fold_scores(_request(scores=scores))


def test_duplicate_cell_and_mixed_direction_are_rejected():
    duplicate = pd.concat([_scores(), _scores().iloc[[0]]], ignore_index=True)
    with pytest.raises(FoldAggregationError, match="must be unique"):
        aggregate_fold_scores(_request(scores=duplicate))

    mixed = _scores()
    mixed.loc[0, "higher_is_better"] = True
    with pytest.raises(FoldAggregationError, match="mix optimization directions"):
        aggregate_fold_scores(_request(scores=mixed))


def test_reference_final_and_minimum_development_folds_are_required():
    with pytest.raises(FoldAggregationError, match="reference_baseline is absent"):
        aggregate_fold_scores(_request(reference_baseline="missing"))
    with pytest.raises(FoldAggregationError, match="final_holdout_fold_id is absent"):
        aggregate_fold_scores(_request(final_holdout_fold_id="missing"))
    scores = _scores().query("fold_id in ['fold-1', 'final']").copy()
    with pytest.raises(FoldAggregationError, match="at least two development folds"):
        aggregate_fold_scores(_request(scores=scores))


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"code_commit": "bad"}, "Git SHA"),
        ({"bootstrap_samples": 0}, "positive integer"),
        ({"bootstrap_samples": 1_000_001}, "cannot exceed"),
        ({"confidence_level": 1.0}, "between zero and one"),
        ({"seed": -1}, "seed"),
    ],
)
def test_invalid_aggregation_controls_are_rejected(change, message):
    with pytest.raises(FoldAggregationError, match=message):
        _request(**change)
