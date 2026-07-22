"""Versioned canonical schema for market bars."""

from __future__ import annotations

FEATURE_SCHEMA_VERSION = "1.0.0"

CANONICAL_BAR_FIELDS = (
    "instrument_id",
    "timestamp_utc",
    "exchange",
    "currency",
    "frequency",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "amount",
    "adjustment_factor",
    "is_adjusted",
    "source",
    "ingested_at",
)

IDENTITY_FIELDS = (
    "instrument_id",
    "timestamp_utc",
    "exchange",
    "currency",
    "frequency",
)

PRICE_FIELDS = ("open", "high", "low", "close")
NON_NEGATIVE_FIELDS = ("volume", "amount")
TEXT_FIELDS = ("instrument_id", "exchange", "currency", "frequency", "source")
TIMESTAMP_FIELDS = ("timestamp_utc", "ingested_at")
