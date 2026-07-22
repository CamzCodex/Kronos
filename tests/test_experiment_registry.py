from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from kronos_data.hashing import hash_configuration
from kronos_eval.registry import (
    MODEL_ALIASES,
    ArtifactInput,
    ExperimentRegistrationRequest,
    ExperimentRegistry,
    ExperimentRegistryError,
)


def _artifact(path: Path, payload: bytes = b'{"run":"evidence"}\n') -> ArtifactInput:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return ArtifactInput(
        role="evaluation-result",
        path=path,
        expected_sha256=hashlib.sha256(payload).hexdigest(),
        media_type="application/json",
    )


def _request(
    tmp_path: Path,
    *,
    approval_status: str = "research-only",
    dirty_tree: bool = False,
    created_at: str = "2026-07-22T05:00:00+00:00",
    payload: bytes = b'{"run":"evidence"}\n',
) -> ExperimentRegistrationRequest:
    configuration = {
        "frequency": "1d",
        "horizons": [1, 3, 5],
        "paper_only": True,
    }
    return ExperimentRegistrationRequest(
        git_commit="1b5000cf22247ae28de7e4e04cb6fdba5f854f4d",
        dirty_tree=dirty_tree,
        dataset_id="kds-reference-fixture",
        configuration=configuration,
        configuration_hash=hash_configuration(configuration),
        feature_schema_version="canonical-bars-v1",
        model_identifier="NeoQuasar/Kronos-small",
        checkpoint_revision="0123456789abcdef0123456789abcdef01234567",
        seed=17,
        fold_definitions=(
            {
                "fold_id": "fold-001",
                "train_end": "2024-12-31T00:00:00+00:00",
                "test_end": "2025-03-31T00:00:00+00:00",
            },
        ),
        hardware={"device": "cpu", "processor": "test-fixture"},
        library_versions={"python": "3.12.0", "torch": "2.7.0"},
        metrics={"mae": 1.25, "financial_conclusion": "unknown"},
        artifacts=(_artifact(tmp_path / "result.json", payload),),
        approval_status=approval_status,
        approval_evidence=("test://synthetic-review",)
        if approval_status in {"approved", "rejected"}
        else (),
        created_at=created_at,
    )


def test_registers_content_addressed_artifact_and_reconstructs_without_source(
    tmp_path: Path,
) -> None:
    registry = ExperimentRegistry(tmp_path / "registry")
    request = _request(tmp_path)

    record = registry.register(request)
    Path(request.artifacts[0].path).unlink()
    reconstructed = registry.get(record.experiment_id)

    assert reconstructed == record
    assert record.experiment_id.startswith("kexp-")
    assert record.configuration_hash == hash_configuration(request.configuration)
    assert record.approval_status == "research-only"
    assert record.decision_grade is False
    stored = registry.root / record.artifacts[0].storage_path
    assert stored.read_bytes() == b'{"run":"evidence"}\n'


def test_identical_evidence_has_deterministic_identity_across_roots(tmp_path: Path) -> None:
    request_a = _request(tmp_path / "a")
    request_b = _request(tmp_path / "b")

    record_a = ExperimentRegistry(tmp_path / "registry-a").register(request_a)
    record_b = ExperimentRegistry(tmp_path / "registry-b").register(request_b)

    assert record_a.experiment_id == record_b.experiment_id
    assert record_a.to_json() == record_b.to_json()


def test_registration_is_idempotent_but_record_replacement_is_refused(tmp_path: Path) -> None:
    registry = ExperimentRegistry(tmp_path / "registry")
    request = _request(tmp_path)
    record = registry.register(request)

    assert registry.register(request) == record
    record_path = registry.root / "experiments" / f"{record.experiment_id}.json"
    record_path.write_text("{}\n", encoding="utf-8")

    with pytest.raises(FileExistsError, match="refusing to replace immutable"):
        registry.register(request)


def test_expected_digest_mismatch_does_not_publish_artifact_or_record(tmp_path: Path) -> None:
    registry = ExperimentRegistry(tmp_path / "registry")
    request = _request(tmp_path)
    bad_artifact = replace(request.artifacts[0], expected_sha256="0" * 64)

    with pytest.raises(ExperimentRegistryError, match="do not match expected_sha256"):
        registry.register(replace(request, artifacts=(bad_artifact,)))

    assert not (registry.root / "artifacts" / "sha256" / "00" / ("0" * 64)).exists()
    assert not (registry.root / "experiments").exists()


def test_corrupt_or_missing_registered_artifact_invalidates_reconstruction(
    tmp_path: Path,
) -> None:
    registry = ExperimentRegistry(tmp_path / "registry")
    record = registry.register(_request(tmp_path))
    stored = registry.root / record.artifacts[0].storage_path
    stored.write_bytes(b"corrupt")

    with pytest.raises(ExperimentRegistryError, match="artifact is corrupt"):
        registry.get(record.experiment_id)

    assert registry.get(record.experiment_id, verify_artifacts=False) == record


def test_configuration_hash_and_non_finite_metadata_are_refused(tmp_path: Path) -> None:
    request = _request(tmp_path)

    with pytest.raises(ExperimentRegistryError, match="does not match configuration"):
        replace(request, configuration_hash="0" * 64)
    with pytest.raises(ExperimentRegistryError, match="finite canonical JSON"):
        replace(request, metrics={"mae": float("nan")})
    with pytest.raises(ExperimentRegistryError, match="require approval_evidence"):
        replace(request, approval_status="approved", approval_evidence=())


def test_symlink_artifact_is_refused(tmp_path: Path) -> None:
    target = tmp_path / "target.json"
    target.write_bytes(b"evidence")
    symlink = tmp_path / "link.json"
    symlink.symlink_to(target)

    with pytest.raises(ExperimentRegistryError, match="symbolic links"):
        ArtifactInput(
            role="result",
            path=symlink,
            expected_sha256=hashlib.sha256(b"evidence").hexdigest(),
        )


def test_dirty_or_unapproved_experiment_cannot_be_champion_or_rollback(
    tmp_path: Path,
) -> None:
    registry = ExperimentRegistry(tmp_path / "registry")
    dirty = registry.register(
        _request(tmp_path / "dirty", approval_status="approved", dirty_tree=True)
    )
    research = registry.register(_request(tmp_path / "research"))

    for experiment_id in (dirty.experiment_id, research.experiment_id):
        for alias in ("champion", "rollback"):
            with pytest.raises(ExperimentRegistryError, match="approved, clean-tree"):
                registry.set_alias(
                    alias,
                    experiment_id,
                    reason="promotion fixture",
                    updated_at="2026-07-22T06:00:00+00:00",
                )


def test_alias_policies_cover_all_declared_aliases(tmp_path: Path) -> None:
    registry = ExperimentRegistry(tmp_path / "registry")
    approved = registry.register(_request(tmp_path / "approved", approval_status="approved"))
    research = registry.register(_request(tmp_path / "research"))
    rejected = registry.register(_request(tmp_path / "rejected", approval_status="rejected"))

    assignments = {
        "candidate": approved,
        "champion": approved,
        "rollback": approved,
        "research-only": research,
        "rejected": rejected,
    }
    for index, (alias, record) in enumerate(assignments.items()):
        registry.set_alias(
            alias,
            record.experiment_id,
            reason=f"policy fixture {alias}",
            updated_at=f"2026-07-22T06:0{index}:00+00:00",
        )
        assert registry.resolve_alias(alias) == record

    assert set(assignments) == set(MODEL_ALIASES)
    with pytest.raises(ExperimentRegistryError, match="rejected experiment cannot"):
        registry.set_alias(
            "candidate",
            rejected.experiment_id,
            reason="invalid fixture",
            updated_at="2026-07-22T07:00:00+00:00",
        )


def test_alias_updates_preserve_immutable_history(tmp_path: Path) -> None:
    registry = ExperimentRegistry(tmp_path / "registry")
    first = registry.register(_request(tmp_path / "first", approval_status="approved"))
    second = registry.register(
        _request(
            tmp_path / "second",
            approval_status="approved",
            created_at="2026-07-22T05:01:00+00:00",
            payload=b'{"run":"second"}\n',
        )
    )

    event_a = registry.set_alias(
        "champion",
        first.experiment_id,
        reason="initial evidence gate",
        updated_at="2026-07-22T06:00:00+00:00",
    )
    event_b = registry.set_alias(
        "champion",
        second.experiment_id,
        reason="superseding evidence gate",
        updated_at="2026-07-22T07:00:00+00:00",
    )

    history = registry.alias_history("champion")
    assert history == (event_a, event_b)
    assert event_b.previous_experiment_id == first.experiment_id
    assert registry.resolve_alias("champion") == second
    assert all(
        (registry.root / "alias-events" / "champion" / f"{event.event_id}.json").is_file()
        for event in history
    )

    with pytest.raises(ExperimentRegistryError, match="increase monotonically"):
        registry.set_alias(
            "champion",
            first.experiment_id,
            reason="retroactive rewrite fixture",
            updated_at="2026-07-22T06:30:00+00:00",
        )


def test_tampered_record_and_alias_pointer_are_detected(tmp_path: Path) -> None:
    registry = ExperimentRegistry(tmp_path / "registry")
    record = registry.register(_request(tmp_path, approval_status="approved"))
    registry.set_alias(
        "candidate",
        record.experiment_id,
        reason="tamper fixture",
        updated_at="2026-07-22T06:00:00+00:00",
    )

    record_path = registry.root / "experiments" / f"{record.experiment_id}.json"
    value = json.loads(record_path.read_text(encoding="utf-8"))
    value["metrics"]["mae"] = 0.0
    record_path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ExperimentRegistryError, match="identity hash is invalid"):
        registry.get(record.experiment_id, verify_artifacts=False)

    pointer = registry.root / "aliases" / "candidate.json"
    pointer.write_text("{}\n", encoding="utf-8")
    with pytest.raises(ExperimentRegistryError, match="invalid alias pointer"):
        registry.resolve_alias("candidate", verify_artifacts=False)


def test_supersedes_reference_and_timezone_are_identity_bound(tmp_path: Path) -> None:
    registry = ExperimentRegistry(tmp_path / "registry")
    first = registry.register(_request(tmp_path / "first"))
    request = _request(
        tmp_path / "second",
        created_at="2026-07-22T14:30:00+09:30",
        payload=b'{"run":"superseding"}\n',
    )
    second = registry.register(
        replace(request, supersedes_experiment_id=first.experiment_id)
    )

    assert second.created_at == "2026-07-22T05:00:00+00:00"
    assert second.supersedes_experiment_id == first.experiment_id
    with pytest.raises(ExperimentRegistryError, match="timezone-aware"):
        replace(request, created_at="2026-07-22T05:00:00")

    with pytest.raises(FileNotFoundError, match="unknown experiment"):
        registry.register(
            replace(request, supersedes_experiment_id="kexp-000000000000000000000000")
        )
