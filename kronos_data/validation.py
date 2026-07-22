"""Structured validation for canonical market bars."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd

from .adjustments import AdjustmentPolicy, coerce_adjustment_policy
from .calendars import CalendarSpec, calendar_for
from .hashing import hash_dataframe
from .schema import (
    CANONICAL_BAR_FIELDS,
    NON_NEGATIVE_FIELDS,
    PRICE_FIELDS,
    TEXT_FIELDS,
    TIMESTAMP_FIELDS,
)


class IssueSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    severity: IssueSeverity
    message: str
    count: int = 1
    row_indices: tuple[str, ...] = ()
    instruments: tuple[str, ...] = ()
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity.value,
            "message": self.message,
            "count": self.count,
            "row_indices": list(self.row_indices),
            "instruments": list(self.instruments),
            "details": self.details,
        }


@dataclass(frozen=True)
class ValidationReport:
    passed: bool
    checks: tuple[str, ...]
    issues: tuple[ValidationIssue, ...]
    row_count: int
    instrument_count: int
    start: str | None
    end: str | None
    content_hash: str | None = None
    input_hash: str | None = None
    feature_schema_version: str = "1.0.0"

    @property
    def failures(self) -> tuple[ValidationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity is IssueSeverity.ERROR)

    @property
    def warnings(self) -> tuple[ValidationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity is IssueSeverity.WARNING)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "checks": list(self.checks),
            "failures": [issue.to_dict() for issue in self.failures],
            "warnings": [issue.to_dict() for issue in self.warnings],
            "row_count": self.row_count,
            "instrument_count": self.instrument_count,
            "start": self.start,
            "end": self.end,
            "content_hash": self.content_hash,
            "input_hash": self.input_hash,
            "feature_schema_version": self.feature_schema_version,
        }


@dataclass(frozen=True)
class ValidationConfig:
    adjustment_policy: AdjustmentPolicy | str = AdjustmentPolicy.DECLARED
    calendars: dict[str, CalendarSpec] | None = None
    require_authoritative_calendar: bool = False
    as_of_utc: pd.Timestamp | str | None = None
    stale_after: timedelta | None = None
    max_gap_multiple: int = 20
    issue_row_limit: int = 20

    def __post_init__(self) -> None:
        coerce_adjustment_policy(self.adjustment_policy)
        if self.stale_after is not None and self.stale_after <= timedelta(0):
            raise ValueError("stale_after must be positive")
        if self.max_gap_multiple < 1:
            raise ValueError("max_gap_multiple must be at least 1")
        if self.issue_row_limit < 1:
            raise ValueError("issue_row_limit must be at least 1")


_CHECKS = (
    "required_schema",
    "non_empty_dataset",
    "text_identifiers",
    "timezone_consistency",
    "timestamp_ordering",
    "duplicate_keys",
    "exchange_calendar_alignment",
    "declared_frequency",
    "missing_and_unsupported_gaps",
    "ohlc_relationships",
    "positive_prices",
    "non_negative_activity",
    "staleness",
    "corporate_action_declaration",
    "instrument_metadata_consistency",
)


def _aware_timestamp(value: Any) -> bool:
    try:
        timestamp = pd.Timestamp(value)
    except (TypeError, ValueError):
        return False
    return (
        not pd.isna(timestamp)
        and timestamp.tzinfo is not None
        and timestamp.utcoffset() is not None
    )


def _indices(mask: pd.Series, limit: int) -> tuple[str, ...]:
    return tuple(str(value) for value in mask.index[mask][:limit])


def _instruments(frame: pd.DataFrame, mask: pd.Series) -> tuple[str, ...]:
    if "instrument_id" not in frame:
        return ()
    values = frame.loc[mask, "instrument_id"].dropna().astype(str).unique().tolist()
    return tuple(sorted(values)[:20])


def _issue(
    issues: list[ValidationIssue],
    frame: pd.DataFrame,
    mask: pd.Series,
    *,
    code: str,
    severity: IssueSeverity,
    message: str,
    limit: int,
    details: dict[str, Any] | None = None,
) -> None:
    count = int(mask.sum())
    if count:
        issues.append(
            ValidationIssue(
                code=code,
                severity=severity,
                message=message,
                count=count,
                row_indices=_indices(mask, limit),
                instruments=_instruments(frame, mask),
                details=details or {},
            )
        )


def _parse_fixed_frequency(value: str) -> pd.Timedelta | None:
    try:
        offset = pd.tseries.frequencies.to_offset(value)
        return pd.Timedelta(offset)
    except (TypeError, ValueError):
        return None


def validate_bars(
    bars: pd.DataFrame,
    config: ValidationConfig | None = None,
) -> ValidationReport:
    """Validate all supported invariants and return every discovered issue."""

    config = config or ValidationConfig()
    issues: list[ValidationIssue] = []
    if not isinstance(bars, pd.DataFrame):
        issue = ValidationIssue(
            code="not_a_dataframe",
            severity=IssueSeverity.ERROR,
            message="bars must be a pandas DataFrame",
        )
        return ValidationReport(False, _CHECKS, (issue,), 0, 0, None, None)

    missing = [field for field in CANONICAL_BAR_FIELDS if field not in bars.columns]
    if missing:
        issue = ValidationIssue(
            code="missing_required_columns",
            severity=IssueSeverity.ERROR,
            message="canonical bar columns are missing",
            count=len(missing),
            details={"missing": missing},
        )
        return ValidationReport(False, _CHECKS, (issue,), len(bars), 0, None, None)

    if bars.empty:
        issue = ValidationIssue(
            code="empty_dataset",
            severity=IssueSeverity.ERROR,
            message="canonical market-data datasets must contain at least one row",
            count=0,
        )
        return ValidationReport(False, _CHECKS, (issue,), 0, 0, None, None)

    frame = bars.loc[:, CANONICAL_BAR_FIELDS].copy()
    limit = config.issue_row_limit

    for field_name in TEXT_FIELDS:
        values = frame[field_name]
        invalid = values.isna() | values.astype(str).str.strip().eq("")
        _issue(
            issues,
            frame,
            invalid,
            code=f"invalid_{field_name}",
            severity=IssueSeverity.ERROR,
            message=f"{field_name} must be a non-empty value",
            limit=limit,
        )

    for field_name in TIMESTAMP_FIELDS:
        aware = frame[field_name].map(_aware_timestamp)
        _issue(
            issues,
            frame,
            ~aware,
            code=f"invalid_{field_name}_timezone",
            severity=IssueSeverity.ERROR,
            message=f"{field_name} must contain timezone-aware values",
            limit=limit,
        )
        utc = frame[field_name].map(
            lambda value: _aware_timestamp(value)
            and pd.Timestamp(value).utcoffset() == timedelta(0)
        )
        _issue(
            issues,
            frame,
            ~utc,
            code=f"non_utc_{field_name}",
            severity=IssueSeverity.ERROR,
            message=f"{field_name} must use a UTC zero-offset timestamp",
            limit=limit,
        )
        parsed = pd.to_datetime(frame[field_name], errors="coerce", utc=True)
        invalid = parsed.isna()
        _issue(
            issues,
            frame,
            invalid,
            code=f"invalid_{field_name}",
            severity=IssueSeverity.ERROR,
            message=f"{field_name} contains invalid timestamps",
            limit=limit,
        )
        frame[field_name] = parsed

    valid_timestamp = frame["timestamp_utc"].notna()
    valid_ingested = frame["ingested_at"].notna()
    ingested_before_bar = valid_timestamp & valid_ingested & (
        frame["ingested_at"] < frame["timestamp_utc"]
    )
    _issue(
        issues,
        frame,
        ingested_before_bar,
        code="ingested_before_bar",
        severity=IssueSeverity.ERROR,
        message="ingested_at cannot precede timestamp_utc",
        limit=limit,
    )

    duplicates = frame.duplicated(["instrument_id", "timestamp_utc"], keep=False)
    _issue(
        issues,
        frame,
        duplicates,
        code="duplicate_instrument_timestamp",
        severity=IssueSeverity.ERROR,
        message="instrument_id and timestamp_utc must be unique",
        limit=limit,
    )

    for instrument, group in frame.groupby("instrument_id", sort=False, dropna=False):
        timestamps = group["timestamp_utc"]
        if timestamps.notna().all() and not timestamps.is_monotonic_increasing:
            issues.append(
                ValidationIssue(
                    code="timestamps_not_strictly_increasing",
                    severity=IssueSeverity.ERROR,
                    message="timestamps must be strictly increasing within each instrument",
                    count=len(group),
                    row_indices=tuple(str(value) for value in group.index[:limit]),
                    instruments=(str(instrument),),
                )
            )

    numeric: dict[str, pd.Series] = {}
    for field_name in (*PRICE_FIELDS, *NON_NEGATIVE_FIELDS, "adjustment_factor"):
        numeric[field_name] = pd.to_numeric(frame[field_name], errors="coerce")
        invalid = numeric[field_name].isna() | ~np.isfinite(numeric[field_name])
        _issue(
            issues,
            frame,
            invalid,
            code=f"invalid_numeric_{field_name}",
            severity=IssueSeverity.ERROR,
            message=f"{field_name} must be finite numeric data",
            limit=limit,
        )

    positive_prices = pd.Series(False, index=frame.index)
    for field_name in PRICE_FIELDS:
        positive_prices |= numeric[field_name].le(0)
    _issue(
        issues,
        frame,
        positive_prices,
        code="non_positive_price",
        severity=IssueSeverity.ERROR,
        message="OHLC prices must be positive",
        limit=limit,
    )

    invalid_high = numeric["high"] < pd.concat(
        [numeric["open"], numeric["close"]], axis=1
    ).max(axis=1)
    invalid_low = numeric["low"] > pd.concat(
        [numeric["open"], numeric["close"]], axis=1
    ).min(axis=1)
    _issue(
        issues,
        frame,
        invalid_high,
        code="invalid_high",
        severity=IssueSeverity.ERROR,
        message="high must be greater than or equal to open and close",
        limit=limit,
    )
    _issue(
        issues,
        frame,
        invalid_low,
        code="invalid_low",
        severity=IssueSeverity.ERROR,
        message="low must be less than or equal to open and close",
        limit=limit,
    )

    for field_name in NON_NEGATIVE_FIELDS:
        _issue(
            issues,
            frame,
            numeric[field_name].lt(0),
            code=f"negative_{field_name}",
            severity=IssueSeverity.ERROR,
            message=f"{field_name} must be non-negative",
            limit=limit,
        )

    _issue(
        issues,
        frame,
        numeric["adjustment_factor"].le(0),
        code="invalid_adjustment_factor",
        severity=IssueSeverity.ERROR,
        message="adjustment_factor must be positive",
        limit=limit,
    )
    valid_adjustment_flag = frame["is_adjusted"].map(
        lambda value: isinstance(value, (bool, np.bool_))
    )
    _issue(
        issues,
        frame,
        ~valid_adjustment_flag,
        code="invalid_is_adjusted",
        severity=IssueSeverity.ERROR,
        message="is_adjusted must contain booleans",
        limit=limit,
    )
    adjustment_policy = coerce_adjustment_policy(config.adjustment_policy)
    if valid_adjustment_flag.all():
        flags = frame["is_adjusted"].astype(bool)
        if flags.any():
            issues.append(
                ValidationIssue(
                    code="corporate_action_causality_unverified",
                    severity=IssueSeverity.WARNING,
                    message=(
                        "adjusted rows require a separate effective-time causality audit"
                    ),
                    count=int(flags.sum()),
                    instruments=tuple(
                        sorted(frame.loc[flags, "instrument_id"].astype(str).unique())[:20]
                    ),
                )
            )
        if adjustment_policy is AdjustmentPolicy.RAW:
            _issue(
                issues,
                frame,
                flags,
                code="adjusted_row_under_raw_policy",
                severity=IssueSeverity.ERROR,
                message="raw adjustment policy cannot contain adjusted rows",
                limit=limit,
            )
        elif adjustment_policy is not AdjustmentPolicy.DECLARED:
            _issue(
                issues,
                frame,
                ~flags,
                code="raw_row_under_adjusted_policy",
                severity=IssueSeverity.ERROR,
                message="adjusted policy cannot contain raw rows",
                limit=limit,
            )
        else:
            mixed = frame.assign(_flag=flags).groupby("instrument_id")["_flag"].nunique()
            mixed_instruments = set(mixed[mixed > 1].index.astype(str))
            mixed_mask = frame["instrument_id"].astype(str).isin(mixed_instruments)
            _issue(
                issues,
                frame,
                mixed_mask,
                code="mixed_adjustment_state",
                severity=IssueSeverity.ERROR,
                message="an instrument cannot mix raw and adjusted rows in one dataset",
                limit=limit,
            )

    for field_name in ("exchange", "currency", "frequency"):
        counts = frame.groupby("instrument_id")[field_name].nunique(dropna=True)
        changed = set(counts[counts > 1].index.astype(str))
        mask = frame["instrument_id"].astype(str).isin(changed)
        _issue(
            issues,
            frame,
            mask,
            code=f"changing_{field_name}",
            severity=IssueSeverity.ERROR,
            message=f"{field_name} must be consistent within each instrument_id",
            limit=limit,
        )

    parsed_frequencies: dict[str, pd.Timedelta] = {}
    for value in sorted(frame["frequency"].dropna().astype(str).unique()):
        parsed = _parse_fixed_frequency(value)
        if parsed is None or parsed <= pd.Timedelta(0):
            mask = frame["frequency"].astype(str).eq(value)
            _issue(
                issues,
                frame,
                mask,
                code="unsupported_frequency",
                severity=IssueSeverity.ERROR,
                message="frequency must be a positive fixed pandas-compatible offset",
                limit=limit,
                details={"frequency": value},
            )
        else:
            parsed_frequencies[value] = parsed

    warned_calendars: set[str] = set()
    for exchange, group in frame.groupby("exchange", sort=False):
        exchange_name = str(exchange).upper()
        calendar = calendar_for(exchange_name, config.calendars)
        if calendar is None:
            issues.append(
                ValidationIssue(
                    code="unknown_exchange_calendar",
                    severity=IssueSeverity.ERROR,
                    message="no calendar was supplied for the exchange",
                    count=len(group),
                    row_indices=tuple(str(value) for value in group.index[:limit]),
                    instruments=tuple(sorted(group["instrument_id"].astype(str).unique())[:20]),
                    details={"exchange": exchange_name},
                )
            )
            continue
        if not calendar.authoritative_holidays and exchange_name not in warned_calendars:
            warned_calendars.add(exchange_name)
            severity = (
                IssueSeverity.ERROR
                if config.require_authoritative_calendar
                else IssueSeverity.WARNING
            )
            issues.append(
                ValidationIssue(
                    code="calendar_holidays_unverified",
                    severity=severity,
                    message="calendar holiday coverage is not authoritative",
                    count=len(group),
                    instruments=tuple(sorted(group["instrument_id"].astype(str).unique())[:20]),
                    details={"exchange": exchange_name},
                )
            )
        for index, row in group.iterrows():
            timestamp = row["timestamp_utc"]
            frequency = parsed_frequencies.get(str(row["frequency"]))
            if pd.isna(timestamp) or frequency is None:
                continue
            local = calendar.local_timestamp(timestamp)
            valid_calendar = (
                calendar.is_session_date(local.date())
                if frequency >= pd.Timedelta(days=1)
                else calendar.is_session_timestamp(timestamp)
            )
            if not valid_calendar:
                mask = pd.Series(False, index=frame.index)
                mask.loc[index] = True
                _issue(
                    issues,
                    frame,
                    mask,
                    code="calendar_misalignment",
                    severity=IssueSeverity.ERROR,
                    message="bar timestamp is outside the declared exchange calendar",
                    limit=limit,
                    details={"exchange": exchange_name},
                )

    for instrument, group in frame.groupby("instrument_id", sort=False):
        group = group.sort_values("timestamp_utc")
        if len(group) < 2 or group["timestamp_utc"].isna().any():
            continue
        frequency_name = str(group["frequency"].iloc[0])
        expected = parsed_frequencies.get(frequency_name)
        calendar = calendar_for(str(group["exchange"].iloc[0]), config.calendars)
        if expected is None:
            continue
        timestamps = group["timestamp_utc"].tolist()
        for previous, current in zip(timestamps, timestamps[1:]):
            delta = current - previous
            missing_count = 0
            unsupported = False
            if expected >= pd.Timedelta(days=1) and calendar is not None:
                previous_date = calendar.local_timestamp(previous).date()
                current_date = calendar.local_timestamp(current).date()
                missing_count = max(0, calendar.sessions_between(previous_date, current_date) - 2)
            elif calendar is not None:
                previous_local = calendar.local_timestamp(previous)
                current_local = calendar.local_timestamp(current)
                if previous_local.date() == current_local.date():
                    ratio = delta / expected
                    unsupported = ratio != int(ratio)
                    missing_count = max(0, int(ratio) - 1) if not unsupported else 0
            if unsupported:
                issues.append(
                    ValidationIssue(
                        code="unsupported_gap",
                        severity=IssueSeverity.ERROR,
                        message="an intraday gap is not an integer multiple of frequency",
                        instruments=(str(instrument),),
                        details={"previous": previous.isoformat(), "current": current.isoformat()},
                    )
                )
            elif missing_count:
                severity = (
                    IssueSeverity.ERROR
                    if missing_count > config.max_gap_multiple
                    else IssueSeverity.WARNING
                )
                issues.append(
                    ValidationIssue(
                        code=(
                            "unsupported_gap"
                            if severity is IssueSeverity.ERROR
                            else "missing_expected_bars"
                        ),
                        severity=severity,
                        message="expected bars are missing between consecutive observations",
                        count=missing_count,
                        instruments=(str(instrument),),
                        details={"previous": previous.isoformat(), "current": current.isoformat()},
                    )
                )

    if config.stale_after is None:
        issues.append(
            ValidationIssue(
                code="staleness_not_evaluated",
                severity=IssueSeverity.WARNING,
                message="stale_after was not configured; record age was not evaluated",
                count=len(frame),
            )
        )
    else:
        if config.as_of_utc is None or not _aware_timestamp(config.as_of_utc):
            issues.append(
                ValidationIssue(
                    code="invalid_staleness_reference",
                    severity=IssueSeverity.ERROR,
                    message="a timezone-aware as_of_utc is required when stale_after is set",
                )
            )
        else:
            as_of = pd.Timestamp(config.as_of_utc).tz_convert("UTC")
            stale = frame["timestamp_utc"].notna() & (
                frame["timestamp_utc"] < as_of - config.stale_after
            )
            future_ingestion = frame["ingested_at"].notna() & (frame["ingested_at"] > as_of)
            _issue(
                issues,
                frame,
                stale,
                code="stale_record",
                severity=IssueSeverity.ERROR,
                message="bar timestamp exceeds the configured maximum age",
                limit=limit,
            )
            _issue(
                issues,
                frame,
                future_ingestion,
                code="future_ingestion_timestamp",
                severity=IssueSeverity.ERROR,
                message="ingested_at cannot be later than as_of_utc",
                limit=limit,
            )

    valid_times = frame["timestamp_utc"].dropna()
    instruments = frame["instrument_id"].dropna().astype(str).nunique()
    failures = [issue for issue in issues if issue.severity is IssueSeverity.ERROR]
    content_hash = None
    input_hash = None
    try:
        content_hash = hash_dataframe(frame)
        input_hash = hash_dataframe(frame, sort_rows=False)
    except (TypeError, ValueError):
        pass
    return ValidationReport(
        passed=not failures,
        checks=_CHECKS,
        issues=tuple(issues),
        row_count=len(frame),
        instrument_count=int(instruments),
        start=valid_times.min().isoformat() if not valid_times.empty else None,
        end=valid_times.max().isoformat() if not valid_times.empty else None,
        content_hash=content_hash,
        input_hash=input_hash,
    )
