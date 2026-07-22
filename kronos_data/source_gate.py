"""Evidence gate for selecting a decision-grade reference market-data source."""

from __future__ import annotations

import json
import math
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from .hashing import hash_configuration

SOURCE_GATE_VERSION = "1.1.0"
REQUIRED_SOURCE_CHECKS = (
    "usage_rights",
    "access_authorization",
    "entitlement_evidence",
    "immutable_snapshot",
    "historical_depth",
    "authoritative_calendar",
    "causal_adjustments",
    "point_in_time_universe",
    "delisting_coverage",
    "instrument_and_currency_identity",
    "revision_policy",
    "primary_evidence",
)
_SHA256 = re.compile(r"[0-9a-f]{64}")


class AccessMode(str, Enum):
    PUBLIC = "public"
    CREDENTIALED_FREE = "credentialed_free"
    PAID = "paid"
    UNAVAILABLE = "unavailable"


class SourceGateError(ValueError):
    """Raised when a source assessment is malformed or cannot be persisted safely."""


@dataclass(frozen=True)
class ReferenceSourceAssessment:
    source_id: str
    provider: str
    data_product: str
    evaluated_at: str | datetime
    terms_url: str
    licence_or_entitlement: str
    usage_rights_confirmed: bool | None
    access_mode: AccessMode | str
    paid_access_authorized: bool
    snapshot_locator: str
    snapshot_sha256: str | None
    raw_snapshot_retained: bool
    coverage_start: str
    coverage_end: str
    frequency: str
    exchange_calendar_reference: str
    calendar_sessions_retained: bool
    adjustment_policy: str
    corporate_action_events_retained: bool
    adjustment_availability_timestamps: bool
    universe_reference: str
    point_in_time_membership: bool
    membership_availability_timestamps: bool
    delistings_retained: bool
    stable_instrument_ids: bool
    currency_metadata: bool
    revision_policy: str
    evidence_references: tuple[str, ...]
    source_limitations: tuple[str, ...] = ()
    entitlement_artifact_sha256: str | None = None

    def __post_init__(self) -> None:
        for name in (
            "source_id",
            "provider",
            "data_product",
            "terms_url",
            "licence_or_entitlement",
            "snapshot_locator",
            "coverage_start",
            "coverage_end",
            "frequency",
            "exchange_calendar_reference",
            "adjustment_policy",
            "universe_reference",
            "revision_policy",
        ):
            _non_empty(getattr(self, name), name)
        _utc_timestamp(self.evaluated_at, "evaluated_at")
        try:
            AccessMode(self.access_mode)
        except ValueError as exc:
            raise SourceGateError("access_mode is invalid") from exc
        if not isinstance(self.paid_access_authorized, bool):
            raise TypeError("paid_access_authorized must be a boolean")
        if self.usage_rights_confirmed is not None and not isinstance(
            self.usage_rights_confirmed, bool
        ):
            raise TypeError("usage_rights_confirmed must be true, false, or unknown")
        for name in (
            "raw_snapshot_retained",
            "calendar_sessions_retained",
            "corporate_action_events_retained",
            "adjustment_availability_timestamps",
            "point_in_time_membership",
            "membership_availability_timestamps",
            "delistings_retained",
            "stable_instrument_ids",
            "currency_metadata",
        ):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be a boolean")
        if self.snapshot_sha256 is not None and (
            not isinstance(self.snapshot_sha256, str)
            or _SHA256.fullmatch(self.snapshot_sha256) is None
        ):
            raise SourceGateError("snapshot_sha256 must be a SHA-256 digest or unknown")
        if self.entitlement_artifact_sha256 is not None and (
            not isinstance(self.entitlement_artifact_sha256, str)
            or _SHA256.fullmatch(self.entitlement_artifact_sha256) is None
        ):
            raise SourceGateError(
                "entitlement_artifact_sha256 must be a SHA-256 digest or unknown"
            )
        start = _date(self.coverage_start, "coverage_start")
        end = _date(self.coverage_end, "coverage_end")
        if start >= end:
            raise SourceGateError("coverage_start must precede coverage_end")
        for values, name in (
            (self.evidence_references, "evidence_references"),
            (self.source_limitations, "source_limitations"),
        ):
            if not isinstance(values, tuple) or not all(
                isinstance(item, str) and item.strip() for item in values
            ):
                raise SourceGateError(f"{name} must be a tuple of non-empty strings")
        if len(self.evidence_references) != len(set(self.evidence_references)):
            raise SourceGateError("evidence_references must be unique")
        if not self.terms_url.startswith("https://") or any(
            not reference.startswith("https://") for reference in self.evidence_references
        ):
            raise SourceGateError("terms and primary evidence references must use HTTPS")

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "provider": self.provider,
            "data_product": self.data_product,
            "evaluated_at": _utc_timestamp(self.evaluated_at, "evaluated_at"),
            "terms_url": self.terms_url,
            "licence_or_entitlement": self.licence_or_entitlement,
            "usage_rights_confirmed": self.usage_rights_confirmed,
            "access_mode": AccessMode(self.access_mode).value,
            "paid_access_authorized": self.paid_access_authorized,
            "snapshot_locator": self.snapshot_locator,
            "snapshot_sha256": self.snapshot_sha256,
            "raw_snapshot_retained": self.raw_snapshot_retained,
            "coverage_start": _date(self.coverage_start, "coverage_start").date().isoformat(),
            "coverage_end": _date(self.coverage_end, "coverage_end").date().isoformat(),
            "frequency": self.frequency,
            "exchange_calendar_reference": self.exchange_calendar_reference,
            "calendar_sessions_retained": self.calendar_sessions_retained,
            "adjustment_policy": self.adjustment_policy,
            "corporate_action_events_retained": self.corporate_action_events_retained,
            "adjustment_availability_timestamps": self.adjustment_availability_timestamps,
            "universe_reference": self.universe_reference,
            "point_in_time_membership": self.point_in_time_membership,
            "membership_availability_timestamps": self.membership_availability_timestamps,
            "delistings_retained": self.delistings_retained,
            "stable_instrument_ids": self.stable_instrument_ids,
            "currency_metadata": self.currency_metadata,
            "revision_policy": self.revision_policy,
            "evidence_references": list(self.evidence_references),
            "entitlement_artifact_sha256": self.entitlement_artifact_sha256,
            "source_limitations": list(self.source_limitations),
        }


@dataclass(frozen=True)
class SourceGateFinding:
    check: str
    message: str
    evidence: str

    def to_dict(self) -> dict[str, str]:
        return {"check": self.check, "message": self.message, "evidence": self.evidence}


@dataclass(frozen=True)
class SourceGateResult:
    gate_version: str
    assessment_id: str
    source_id: str
    passed: bool
    checks: dict[str, bool]
    failures: tuple[SourceGateFinding, ...]
    warnings: tuple[str, ...]
    assessment: ReferenceSourceAssessment

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_version": self.gate_version,
            "assessment_id": self.assessment_id,
            "source_id": self.source_id,
            "passed": self.passed,
            "checks": dict(sorted(self.checks.items())),
            "failures": [finding.to_dict() for finding in self.failures],
            "warnings": list(self.warnings),
            "assessment": self.assessment.to_dict(),
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(), ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False
        ) + "\n"


def assess_reference_source(
    assessment: ReferenceSourceAssessment,
    *,
    minimum_history_years: float = 8.0,
) -> SourceGateResult:
    """Evaluate whether a source may back a decision-grade reference dataset."""

    if not isinstance(assessment, ReferenceSourceAssessment):
        raise TypeError("assessment must be a ReferenceSourceAssessment")
    if (
        not isinstance(minimum_history_years, (int, float))
        or isinstance(minimum_history_years, bool)
        or not math.isfinite(minimum_history_years)
        or minimum_history_years <= 0
    ):
        raise SourceGateError("minimum_history_years must be positive")
    mode = AccessMode(assessment.access_mode)
    start = _date(assessment.coverage_start, "coverage_start")
    end = _date(assessment.coverage_end, "coverage_end")
    history_years = (end - start).days / 365.2425
    checks = {
        "usage_rights": assessment.usage_rights_confirmed is True,
        "access_authorization": mode is not AccessMode.UNAVAILABLE
        and (mode is not AccessMode.PAID or assessment.paid_access_authorized),
        "entitlement_evidence": mode is not AccessMode.PAID
        or bool(assessment.entitlement_artifact_sha256),
        "immutable_snapshot": bool(assessment.snapshot_sha256)
        and assessment.raw_snapshot_retained,
        "historical_depth": history_years >= minimum_history_years,
        "authoritative_calendar": assessment.calendar_sessions_retained,
        "causal_adjustments": assessment.corporate_action_events_retained
        and assessment.adjustment_availability_timestamps
        and assessment.adjustment_policy.strip().lower() not in {"unknown", "none"},
        "point_in_time_universe": assessment.point_in_time_membership
        and assessment.membership_availability_timestamps
        and assessment.universe_reference.strip().lower() not in {"unknown", "none"},
        "delisting_coverage": assessment.delistings_retained,
        "instrument_and_currency_identity": assessment.stable_instrument_ids
        and assessment.currency_metadata,
        "revision_policy": assessment.revision_policy.strip().lower() not in {
            "unknown",
            "none",
            "not documented",
        },
        "primary_evidence": len(assessment.evidence_references) >= 2,
    }
    failures = []
    evidence = ", ".join(assessment.evidence_references) or "None"
    messages = {
        "usage_rights": "usage/licensing rights are unconfirmed or refused",
        "access_authorization": "source is unavailable or requires unapproved paid access",
        "entitlement_evidence": (
            "paid access is not bound to the SHA-256 of a retained entitlement artifact"
        ),
        "immutable_snapshot": "exact raw bytes are not retained and SHA-256 pinned",
        "historical_depth": (
            f"history is {history_years:.2f} years; at least {minimum_history_years:.2f} required"
        ),
        "authoritative_calendar": "authoritative session records are not retained",
        "causal_adjustments": "corporate-action events or availability times are absent",
        "point_in_time_universe": "membership intervals or availability times are absent",
        "delisting_coverage": "delisted instruments/outcomes are not retained",
        "instrument_and_currency_identity": "stable IDs or currency metadata are absent",
        "revision_policy": "provider revision policy is undocumented",
        "primary_evidence": "at least two primary evidence references are required",
    }
    for check in REQUIRED_SOURCE_CHECKS:
        if not checks[check]:
            failures.append(
                SourceGateFinding(check=check, message=messages[check], evidence=evidence)
            )
    warnings = list(assessment.source_limitations)
    warnings.append(
        "source approval does not replace canonical bar validation or a passed leakage audit"
    )
    identity = {
        "gate_version": SOURCE_GATE_VERSION,
        "minimum_history_years": minimum_history_years,
        "assessment": assessment.to_dict(),
        "checks": checks,
    }
    return SourceGateResult(
        gate_version=SOURCE_GATE_VERSION,
        assessment_id=f"ksa-{hash_configuration(identity)[:24]}",
        source_id=assessment.source_id,
        passed=not failures,
        checks=checks,
        failures=tuple(failures),
        warnings=tuple(warnings),
        assessment=assessment,
    )


def write_source_gate_result(
    result: SourceGateResult, path: str | os.PathLike[str]
) -> Path:
    if not isinstance(result, SourceGateResult):
        raise TypeError("result must be a SourceGateResult")
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = result.to_json().encode("utf-8")
    if destination.exists():
        if destination.is_file() and destination.read_bytes() == payload:
            return destination
        raise FileExistsError(f"refusing to replace immutable source assessment {destination}")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return destination


def _utc_timestamp(value: str | datetime, name: str) -> str:
    try:
        timestamp = (
            datetime.fromisoformat(value.replace("Z", "+00:00"))
            if isinstance(value, str)
            else value
        )
    except (TypeError, ValueError) as exc:
        raise SourceGateError(f"{name} must be a valid timestamp") from exc
    if not isinstance(timestamp, datetime) or timestamp.tzinfo is None:
        raise SourceGateError(f"{name} must be timezone-aware")
    return timestamp.astimezone(timezone.utc).isoformat()


def _date(value: str, name: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError) as exc:
        raise SourceGateError(f"{name} must be an ISO date") from exc


def _non_empty(value: object, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise SourceGateError(f"{name} must be a non-empty string")


__all__ = [
    "REQUIRED_SOURCE_CHECKS",
    "SOURCE_GATE_VERSION",
    "AccessMode",
    "ReferenceSourceAssessment",
    "SourceGateError",
    "SourceGateFinding",
    "SourceGateResult",
    "assess_reference_source",
    "write_source_gate_result",
]
