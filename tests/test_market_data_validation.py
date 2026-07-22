from __future__ import annotations

from datetime import date, time, timedelta

import pandas as pd

from kronos_data import CalendarSpec, ValidationConfig, validate_bars


def _valid_bars(periods: int = 3) -> pd.DataFrame:
    timestamps = pd.date_range("2025-01-02T00:00:00Z", periods=periods, freq="D")
    return pd.DataFrame(
        {
            "instrument_id": ["BHP.AX"] * periods,
            "timestamp_utc": timestamps,
            "exchange": ["XASX"] * periods,
            "currency": ["AUD"] * periods,
            "frequency": ["1D"] * periods,
            "open": [40.0 + index for index in range(periods)],
            "high": [41.0 + index for index in range(periods)],
            "low": [39.0 + index for index in range(periods)],
            "close": [40.5 + index for index in range(periods)],
            "volume": [1_000.0 + index for index in range(periods)],
            "amount": [40_500.0 + index for index in range(periods)],
            "adjustment_factor": [1.0] * periods,
            "is_adjusted": [True] * periods,
            "source": ["fixture"] * periods,
            "ingested_at": [pd.Timestamp("2025-01-10T00:00:00Z")] * periods,
        }
    )


def _codes(report) -> set[str]:
    return {issue.code for issue in report.issues}


def test_valid_bars_return_structured_report_with_calendar_warning():
    report = validate_bars(_valid_bars(2))

    assert report.passed
    assert not report.failures
    assert "calendar_holidays_unverified" in _codes(report)
    assert "corporate_action_causality_unverified" in _codes(report)
    assert "staleness_not_evaluated" in _codes(report)
    assert report.row_count == 2
    assert report.instrument_count == 1
    assert report.to_dict()["passed"] is True


def test_validation_collects_multiple_failures_in_one_pass():
    bars = _valid_bars(3)
    bars.loc[1, "timestamp_utc"] = bars.loc[0, "timestamp_utc"]
    bars.loc[1, "high"] = 1.0
    bars.loc[1, "low"] = 100.0
    bars.loc[1, "volume"] = -1.0
    bars.loc[1, "currency"] = "USD"
    bars.loc[2, "instrument_id"] = ""

    report = validate_bars(bars)
    codes = _codes(report)

    assert not report.passed
    assert {
        "duplicate_instrument_timestamp",
        "invalid_high",
        "invalid_low",
        "negative_volume",
        "changing_currency",
        "invalid_instrument_id",
    } <= codes


def test_naive_timestamps_are_rejected_without_hiding_other_errors():
    bars = _valid_bars(1)
    bars["timestamp_utc"] = pd.Series(["2025-01-02 00:00:00"], dtype="object")
    bars.loc[0, "amount"] = -2.0

    report = validate_bars(bars)

    assert not report.passed
    assert "invalid_timestamp_utc_timezone" in _codes(report)
    assert "negative_amount" in _codes(report)


def test_non_utc_offsets_are_rejected_even_when_timezone_aware():
    bars = _valid_bars(1)
    bars["timestamp_utc"] = pd.Series(
        ["2025-01-02T10:00:00+10:00"], dtype="object"
    )

    report = validate_bars(bars)

    assert not report.passed
    assert "non_utc_timestamp_utc" in _codes(report)


def test_strict_order_and_duplicate_checks_are_instrument_scoped():
    bars = _valid_bars(3).iloc[[1, 0, 2]].copy()

    report = validate_bars(bars)

    assert not report.passed
    assert "timestamps_not_strictly_increasing" in _codes(report)


def test_authoritative_calendar_detects_holidays():
    bars = _valid_bars(1)
    calendar = CalendarSpec(
        exchange="XASX",
        timezone="Australia/Sydney",
        session_open=time(10, 0),
        session_close=time(16, 0),
        holidays=frozenset({date(2025, 1, 2)}),
        authoritative_holidays=True,
    )

    report = validate_bars(
        bars,
        ValidationConfig(calendars={"XASX": calendar}, require_authoritative_calendar=True),
    )

    assert not report.passed
    assert "calendar_misalignment" in _codes(report)
    assert "calendar_holidays_unverified" not in _codes(report)


def test_missing_daily_session_is_reported():
    bars = _valid_bars(2)
    bars.loc[1, "timestamp_utc"] = pd.Timestamp("2025-01-06T00:00:00Z")

    report = validate_bars(bars)

    assert report.passed
    missing = [issue for issue in report.warnings if issue.code == "missing_expected_bars"]
    assert len(missing) == 1
    assert missing[0].count == 1


def test_stale_records_require_explicit_as_of_and_are_rejected():
    bars = _valid_bars(1)

    missing_reference = validate_bars(
        bars,
        ValidationConfig(stale_after=timedelta(days=2)),
    )
    stale = validate_bars(
        bars,
        ValidationConfig(
            stale_after=timedelta(days=2),
            as_of_utc=pd.Timestamp("2025-01-10T00:00:00Z"),
        ),
    )

    assert "invalid_staleness_reference" in _codes(missing_reference)
    assert "stale_record" in _codes(stale)


def test_raw_and_adjusted_rows_cannot_be_mixed_for_one_instrument():
    bars = _valid_bars(2)
    bars.loc[1, "is_adjusted"] = False

    report = validate_bars(bars)

    assert not report.passed
    assert "mixed_adjustment_state" in _codes(report)


def test_missing_required_columns_return_report_instead_of_raising():
    bars = _valid_bars(1).drop(columns=["currency", "amount"])

    report = validate_bars(bars)

    assert not report.passed
    assert report.failures[0].code == "missing_required_columns"
    assert report.failures[0].details["missing"] == ["currency", "amount"]


def test_empty_dataset_and_infinite_values_are_rejected():
    empty = _valid_bars(1).iloc[:0]
    infinite = _valid_bars(1)
    infinite.loc[0, "high"] = float("inf")

    empty_report = validate_bars(empty)
    infinite_report = validate_bars(infinite)

    assert "empty_dataset" in _codes(empty_report)
    assert "invalid_numeric_high" in _codes(infinite_report)
