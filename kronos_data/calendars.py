"""Small dependency-free exchange-calendar contracts.

The built-in entries validate weekdays, local session hours, and explicitly
provided holidays. They do not claim exhaustive historical holiday coverage.
Evidence-grade datasets should supply a fully populated :class:`CalendarSpec`
from their licensed or authoritative calendar source.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time
from zoneinfo import ZoneInfo

import pandas as pd


@dataclass(frozen=True)
class CalendarSpec:
    exchange: str
    timezone: str
    session_open: time
    session_close: time
    weekdays: frozenset[int] = field(default_factory=lambda: frozenset(range(5)))
    holidays: frozenset[date] = field(default_factory=frozenset)
    authoritative_holidays: bool = False

    def local_timestamp(self, timestamp_utc: pd.Timestamp) -> pd.Timestamp:
        return timestamp_utc.tz_convert(ZoneInfo(self.timezone))

    def is_session_date(self, value: date) -> bool:
        return value.weekday() in self.weekdays and value not in self.holidays

    def is_session_timestamp(self, timestamp_utc: pd.Timestamp) -> bool:
        local = self.local_timestamp(timestamp_utc)
        local_time = local.time().replace(tzinfo=None)
        return (
            self.is_session_date(local.date())
            and self.session_open <= local_time <= self.session_close
        )

    def sessions_between(self, start: date, end: date) -> int:
        if end < start:
            return 0
        days = pd.date_range(start=start, end=end, freq="D")
        return sum(self.is_session_date(timestamp.date()) for timestamp in days)


BUILTIN_CALENDARS: dict[str, CalendarSpec] = {
    "XASX": CalendarSpec(
        exchange="XASX",
        timezone="Australia/Sydney",
        session_open=time(10, 0),
        session_close=time(16, 0),
    ),
    "XNYS": CalendarSpec(
        exchange="XNYS",
        timezone="America/New_York",
        session_open=time(9, 30),
        session_close=time(16, 0),
    ),
    "XNAS": CalendarSpec(
        exchange="XNAS",
        timezone="America/New_York",
        session_open=time(9, 30),
        session_close=time(16, 0),
    ),
}


def calendar_for(
    exchange: str,
    calendars: dict[str, CalendarSpec] | None = None,
) -> CalendarSpec | None:
    registry = BUILTIN_CALENDARS if calendars is None else calendars
    return registry.get(exchange.upper())
