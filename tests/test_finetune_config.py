"""Regression tests for the demonstration split safety boundary."""

from datetime import date

import pytest

from finetune.config import Config


def _dates(value):
    return tuple(date.fromisoformat(item) for item in value)


def test_default_target_ranges_are_disjoint_and_ordered() -> None:
    config = Config()
    train_start, train_end = _dates(config.train_time_range)
    val_start, val_end = _dates(config.val_time_range)
    test_start, test_end = _dates(config.test_time_range)

    assert train_start <= train_end < val_start <= val_end < test_start <= test_end


def test_backtest_range_is_contained_by_test_range() -> None:
    config = Config()
    test_start, test_end = _dates(config.test_time_range)
    backtest_start, backtest_end = _dates(config.backtest_time_range)

    assert test_start <= backtest_start <= backtest_end <= test_end


def test_overlap_is_refused_even_when_config_is_mutated() -> None:
    config = Config()
    config.val_time_range = ["2022-12-31", "2024-06-30"]

    with pytest.raises(ValueError, match="must not overlap"):
        config._validate_ranges()


def test_context_is_not_disguised_as_target_overlap() -> None:
    config = Config()
    train_end = _dates(config.train_time_range)[1]
    validation_start = _dates(config.val_time_range)[0]

    assert validation_start > train_end
    assert config.lookback_window > 0
