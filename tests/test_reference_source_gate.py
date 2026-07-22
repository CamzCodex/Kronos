from __future__ import annotations

import json

import pytest

from kronos_data import (
    REQUIRED_SOURCE_CHECKS,
    ReferenceSourceAssessment,
    SourceGateError,
    assess_reference_source,
    write_source_gate_result,
)


def _assessment(**overrides) -> ReferenceSourceAssessment:
    values = {
        "source_id": "licensed-fixture-v1",
        "provider": "Fixture Exchange",
        "data_product": "Point-in-time daily equities",
        "evaluated_at": "2026-07-22T06:00:00+00:00",
        "terms_url": "https://example.test/terms",
        "licence_or_entitlement": "internal research fixture grant",
        "usage_rights_confirmed": True,
        "access_mode": "credentialed_free",
        "paid_access_authorized": False,
        "snapshot_locator": "fixture://daily-v1.tar",
        "snapshot_sha256": "a" * 64,
        "raw_snapshot_retained": True,
        "coverage_start": "2010-01-01",
        "coverage_end": "2025-12-31",
        "frequency": "1D",
        "exchange_calendar_reference": "fixture://calendar-v1.csv",
        "calendar_sessions_retained": True,
        "adjustment_policy": "effective-time split and dividend events",
        "corporate_action_events_retained": True,
        "adjustment_availability_timestamps": True,
        "universe_reference": "fixture://membership-v1.csv",
        "point_in_time_membership": True,
        "membership_availability_timestamps": True,
        "delistings_retained": True,
        "stable_instrument_ids": True,
        "currency_metadata": True,
        "revision_policy": "new immutable snapshot and hash for every revision",
        "evidence_references": (
            "https://example.test/methodology",
            "https://example.test/terms",
        ),
        "source_limitations": ("synthetic fixture; not real market data",),
    }
    values.update(overrides)
    return ReferenceSourceAssessment(**values)


def test_complete_source_evidence_passes_with_deterministic_identity() -> None:
    first = assess_reference_source(_assessment())
    second = assess_reference_source(_assessment())

    assert first.passed
    assert first.assessment_id == second.assessment_id
    assert set(first.checks) == set(REQUIRED_SOURCE_CHECKS)
    assert not first.failures
    assert "not real market data" in first.warnings[0]


@pytest.mark.parametrize(
    ("overrides", "check"),
    [
        ({"usage_rights_confirmed": None}, "usage_rights"),
        ({"snapshot_sha256": None}, "immutable_snapshot"),
        ({"calendar_sessions_retained": False}, "authoritative_calendar"),
        ({"adjustment_availability_timestamps": False}, "causal_adjustments"),
        ({"adjustment_policy": "unknown"}, "causal_adjustments"),
        ({"point_in_time_membership": False}, "point_in_time_universe"),
        ({"universe_reference": "unknown"}, "point_in_time_universe"),
        ({"delistings_retained": False}, "delisting_coverage"),
        ({"stable_instrument_ids": False}, "instrument_and_currency_identity"),
        ({"revision_policy": "unknown"}, "revision_policy"),
        ({"evidence_references": ("https://example.test/terms",)}, "primary_evidence"),
    ],
)
def test_each_missing_evidence_class_blocks_source(overrides, check) -> None:
    result = assess_reference_source(_assessment(**overrides))

    assert not result.passed
    assert not result.checks[check]
    assert check in {failure.check for failure in result.failures}


def test_paid_source_requires_authorization_and_hashed_entitlement() -> None:
    blocked = assess_reference_source(
        _assessment(access_mode="paid", paid_access_authorized=False)
    )
    authorized_but_unbound = assess_reference_source(
        _assessment(access_mode="paid", paid_access_authorized=True)
    )
    bound = assess_reference_source(
        _assessment(
            access_mode="paid",
            paid_access_authorized=True,
            entitlement_artifact_sha256="b" * 64,
        )
    )

    assert not blocked.checks["access_authorization"]
    assert authorized_but_unbound.checks["access_authorization"]
    assert not authorized_but_unbound.checks["entitlement_evidence"]
    assert bound.checks["entitlement_evidence"]
    assert bound.passed
    assert bound.assessment_id != authorized_but_unbound.assessment_id
    assert bound.to_dict()["assessment"]["entitlement_artifact_sha256"] == "b" * 64


def test_unavailable_source_is_refused_even_when_other_metadata_is_complete() -> None:
    result = assess_reference_source(_assessment(access_mode="unavailable"))

    assert not result.passed
    assert any("unavailable" in failure.message for failure in result.failures)


def test_minimum_history_is_explicit_and_identity_bound() -> None:
    assessment = _assessment(coverage_start="2020-01-01", coverage_end="2025-12-31")
    strict = assess_reference_source(assessment, minimum_history_years=8)
    permissive = assess_reference_source(assessment, minimum_history_years=5)

    assert not strict.checks["historical_depth"]
    assert permissive.checks["historical_depth"]
    assert strict.assessment_id != permissive.assessment_id


def test_result_write_is_immutable_and_idempotent(tmp_path) -> None:
    result = assess_reference_source(_assessment())
    path = tmp_path / "source-assessment.json"

    assert write_source_gate_result(result, path) == path
    assert write_source_gate_result(result, path) == path
    assert json.loads(path.read_text(encoding="utf-8"))["assessment_id"] == result.assessment_id

    path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(FileExistsError, match="immutable source assessment"):
        write_source_gate_result(result, path)


def test_invalid_dates_hashes_and_naive_evaluation_time_are_refused() -> None:
    with pytest.raises(SourceGateError, match="SHA-256"):
        _assessment(snapshot_sha256="bad")
    with pytest.raises(SourceGateError, match="entitlement_artifact_sha256"):
        _assessment(entitlement_artifact_sha256="bad")
    with pytest.raises(SourceGateError, match="must precede"):
        _assessment(coverage_start="2025-01-01", coverage_end="2024-01-01")
    with pytest.raises(SourceGateError, match="timezone-aware"):
        _assessment(evaluated_at="2026-07-22T06:00:00")
    with pytest.raises(TypeError, match="true, false, or unknown"):
        _assessment(usage_rights_confirmed=1)


def test_empty_or_duplicate_primary_evidence_is_refused() -> None:
    with pytest.raises(SourceGateError, match="must be unique"):
        _assessment(
            evidence_references=(
                "https://example.test/terms",
                "https://example.test/terms",
            )
        )
    with pytest.raises(SourceGateError, match="tuple of non-empty"):
        _assessment(evidence_references=("",))
    with pytest.raises(SourceGateError, match="must use HTTPS"):
        _assessment(evidence_references=("not-a-url", "https://example.test/terms"))


def test_gate_requires_positive_minimum_history() -> None:
    with pytest.raises(SourceGateError, match="must be positive"):
        assess_reference_source(_assessment(), minimum_history_years=0)
    with pytest.raises(SourceGateError, match="must be positive"):
        assess_reference_source(_assessment(), minimum_history_years=float("nan"))
