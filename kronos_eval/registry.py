"""Content-addressed experiment evidence and governed model aliases."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from kronos_data.hashing import canonical_json, hash_configuration, sha256_file

EXPERIMENT_REGISTRY_VERSION = "1.0.0"
APPROVAL_STATUSES = frozenset({"unreviewed", "approved", "research-only", "rejected"})
MODEL_ALIASES = frozenset({"candidate", "champion", "rollback", "research-only", "rejected"})
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
_GIT_COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}")
_EXPERIMENT_ID_PATTERN = re.compile(r"kexp-[0-9a-f]{24}")


class ExperimentRegistryError(ValueError):
    """Raised when experiment evidence is incomplete, mutable, or inconsistent."""


@dataclass(frozen=True)
class ArtifactInput:
    """A local artifact whose expected bytes must be registered."""

    role: str
    path: str | os.PathLike[str]
    expected_sha256: str
    media_type: str = "application/octet-stream"

    def __post_init__(self) -> None:
        _non_empty(self.role, "artifact role")
        _non_empty(self.media_type, "artifact media_type")
        if _SHA256_PATTERN.fullmatch(self.expected_sha256) is None:
            raise ExperimentRegistryError("artifact expected_sha256 must be a SHA-256 digest")
        source = Path(self.path)
        if source.is_symlink():
            raise ExperimentRegistryError("artifact inputs cannot be symbolic links")
        if not source.is_file():
            raise ExperimentRegistryError(f"artifact input is not a regular file: {source}")


@dataclass(frozen=True)
class RegisteredArtifact:
    """Portable identity and content-addressed location for registered bytes."""

    role: str
    filename: str
    sha256: str
    size_bytes: int
    media_type: str
    storage_path: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "filename": self.filename,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "media_type": self.media_type,
            "storage_path": self.storage_path,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> RegisteredArtifact:
        return cls(
            role=str(value["role"]),
            filename=str(value["filename"]),
            sha256=str(value["sha256"]),
            size_bytes=int(value["size_bytes"]),
            media_type=str(value["media_type"]),
            storage_path=str(value["storage_path"]),
        )


@dataclass(frozen=True)
class ExperimentRegistrationRequest:
    """Complete lineage supplied when an experiment is first registered."""

    git_commit: str
    dirty_tree: bool
    dataset_id: str
    configuration: Mapping[str, Any]
    configuration_hash: str
    feature_schema_version: str
    model_identifier: str
    checkpoint_revision: str
    seed: int
    fold_definitions: tuple[Mapping[str, Any], ...]
    hardware: Mapping[str, Any]
    library_versions: Mapping[str, str]
    metrics: Mapping[str, Any]
    artifacts: tuple[ArtifactInput, ...]
    approval_status: str
    approval_evidence: tuple[str, ...]
    created_at: str | datetime
    supersedes_experiment_id: str | None = None

    def __post_init__(self) -> None:
        if _GIT_COMMIT_PATTERN.fullmatch(self.git_commit) is None:
            raise ExperimentRegistryError("git_commit must be a full lowercase commit SHA")
        if not isinstance(self.dirty_tree, bool):
            raise TypeError("dirty_tree must be a boolean")
        for value, name in (
            (self.dataset_id, "dataset_id"),
            (self.feature_schema_version, "feature_schema_version"),
            (self.model_identifier, "model_identifier"),
            (self.checkpoint_revision, "checkpoint_revision"),
        ):
            _non_empty(value, name)
        if _SHA256_PATTERN.fullmatch(self.configuration_hash) is None:
            raise ExperimentRegistryError("configuration_hash must be a SHA-256 digest")
        _validate_json_mapping(self.configuration, "configuration")
        if not self.configuration:
            raise ExperimentRegistryError("configuration cannot be empty")
        if hash_configuration(self.configuration) != self.configuration_hash:
            raise ExperimentRegistryError("configuration_hash does not match configuration")
        if not isinstance(self.seed, int) or isinstance(self.seed, bool) or self.seed < 0:
            raise ExperimentRegistryError("seed must be a non-negative integer")
        if not isinstance(self.fold_definitions, tuple) or not self.fold_definitions:
            raise ExperimentRegistryError("fold_definitions must be a non-empty tuple")
        for index, fold in enumerate(self.fold_definitions):
            _validate_json_mapping(fold, f"fold_definitions[{index}]")
        _validate_json_mapping(self.hardware, "hardware")
        if not self.hardware:
            raise ExperimentRegistryError("hardware cannot be empty")
        _validate_json_mapping(self.library_versions, "library_versions")
        if not self.library_versions:
            raise ExperimentRegistryError("library_versions cannot be empty")
        if not all(
            isinstance(name, str) and name and isinstance(version, str) and version
            for name, version in self.library_versions.items()
        ):
            raise ExperimentRegistryError("library_versions must map names to non-empty versions")
        _validate_json_mapping(self.metrics, "metrics")
        if not self.metrics:
            raise ExperimentRegistryError("metrics cannot be empty")
        if not isinstance(self.artifacts, tuple) or not self.artifacts:
            raise ExperimentRegistryError("artifacts must be a non-empty tuple")
        if not all(isinstance(artifact, ArtifactInput) for artifact in self.artifacts):
            raise TypeError("every artifact must be an ArtifactInput")
        roles = [artifact.role for artifact in self.artifacts]
        if len(roles) != len(set(roles)):
            raise ExperimentRegistryError("artifact roles must be unique")
        if self.approval_status not in APPROVAL_STATUSES:
            raise ExperimentRegistryError(
                f"approval_status must be one of {sorted(APPROVAL_STATUSES)}"
            )
        if not isinstance(self.approval_evidence, tuple) or not all(
            isinstance(item, str) and item.strip() for item in self.approval_evidence
        ):
            raise ExperimentRegistryError(
                "approval_evidence must be a tuple of non-empty references"
            )
        if self.approval_status in {"approved", "rejected"} and not self.approval_evidence:
            raise ExperimentRegistryError(
                "approved and rejected experiments require approval_evidence"
            )
        _utc_timestamp(self.created_at, "created_at")
        if self.supersedes_experiment_id is not None:
            _experiment_id(self.supersedes_experiment_id)


@dataclass(frozen=True)
class ExperimentRecord:
    """Immutable, reconstructable identity for one registered experiment."""

    registry_version: str
    experiment_id: str
    created_at: str
    git_commit: str
    dirty_tree: bool
    dataset_id: str
    configuration: dict[str, Any]
    configuration_hash: str
    feature_schema_version: str
    model_identifier: str
    checkpoint_revision: str
    seed: int
    fold_definitions: tuple[dict[str, Any], ...]
    hardware: dict[str, Any]
    library_versions: dict[str, str]
    metrics: dict[str, Any]
    artifacts: tuple[RegisteredArtifact, ...]
    approval_status: str
    approval_evidence: tuple[str, ...]
    decision_grade: bool
    supersedes_experiment_id: str | None
    warnings: tuple[str, ...]

    def identity_payload(self) -> dict[str, Any]:
        value = self.to_dict()
        value.pop("experiment_id")
        return value

    def to_dict(self) -> dict[str, Any]:
        return {
            "registry_version": self.registry_version,
            "experiment_id": self.experiment_id,
            "created_at": self.created_at,
            "git_commit": self.git_commit,
            "dirty_tree": self.dirty_tree,
            "dataset_id": self.dataset_id,
            "configuration": self.configuration,
            "configuration_hash": self.configuration_hash,
            "feature_schema_version": self.feature_schema_version,
            "model_identifier": self.model_identifier,
            "checkpoint_revision": self.checkpoint_revision,
            "seed": self.seed,
            "fold_definitions": list(self.fold_definitions),
            "hardware": self.hardware,
            "library_versions": self.library_versions,
            "metrics": self.metrics,
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "approval_status": self.approval_status,
            "approval_evidence": list(self.approval_evidence),
            "decision_grade": self.decision_grade,
            "supersedes_experiment_id": self.supersedes_experiment_id,
            "warnings": list(self.warnings),
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(), ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False
        ) + "\n"

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> ExperimentRecord:
        return cls(
            registry_version=str(value["registry_version"]),
            experiment_id=str(value["experiment_id"]),
            created_at=str(value["created_at"]),
            git_commit=str(value["git_commit"]),
            dirty_tree=bool(value["dirty_tree"]),
            dataset_id=str(value["dataset_id"]),
            configuration=dict(value["configuration"]),
            configuration_hash=str(value["configuration_hash"]),
            feature_schema_version=str(value["feature_schema_version"]),
            model_identifier=str(value["model_identifier"]),
            checkpoint_revision=str(value["checkpoint_revision"]),
            seed=int(value["seed"]),
            fold_definitions=tuple(dict(item) for item in value["fold_definitions"]),
            hardware=dict(value["hardware"]),
            library_versions={str(key): str(item) for key, item in value["library_versions"].items()},
            metrics=dict(value["metrics"]),
            artifacts=tuple(RegisteredArtifact.from_dict(item) for item in value["artifacts"]),
            approval_status=str(value["approval_status"]),
            approval_evidence=tuple(str(item) for item in value["approval_evidence"]),
            decision_grade=bool(value["decision_grade"]),
            supersedes_experiment_id=value.get("supersedes_experiment_id"),
            warnings=tuple(str(item) for item in value["warnings"]),
        )


@dataclass(frozen=True)
class AliasEvent:
    """Immutable history entry for a mutable model alias pointer."""

    event_id: str
    alias: str
    experiment_id: str
    previous_experiment_id: str | None
    updated_at: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "alias": self.alias,
            "experiment_id": self.experiment_id,
            "previous_experiment_id": self.previous_experiment_id,
            "updated_at": self.updated_at,
            "reason": self.reason,
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(), ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False
        ) + "\n"

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> AliasEvent:
        return cls(
            event_id=str(value["event_id"]),
            alias=str(value["alias"]),
            experiment_id=str(value["experiment_id"]),
            previous_experiment_id=value.get("previous_experiment_id"),
            updated_at=str(value["updated_at"]),
            reason=str(value["reason"]),
        )


class ExperimentRegistry:
    """Filesystem registry with immutable records and content-addressed artifacts."""

    def __init__(self, root: str | os.PathLike[str]) -> None:
        self.root = Path(root)

    def register(self, request: ExperimentRegistrationRequest) -> ExperimentRecord:
        if not isinstance(request, ExperimentRegistrationRequest):
            raise TypeError("request must be an ExperimentRegistrationRequest")
        if request.supersedes_experiment_id is not None:
            self.get(request.supersedes_experiment_id, verify_artifacts=True)
        artifacts = tuple(
            sorted((self._store_artifact(item) for item in request.artifacts), key=lambda x: x.role)
        )
        created_at = _utc_timestamp(request.created_at, "created_at")
        decision_grade = (
            request.approval_status == "approved"
            and not request.dirty_tree
            and bool(request.approval_evidence)
        )
        warnings = []
        if request.dirty_tree:
            warnings.append("dirty-tree experiments are not decision-grade")
        if request.approval_status != "approved":
            warnings.append("experiment has not been approved for decision use")
        payload = {
            "registry_version": EXPERIMENT_REGISTRY_VERSION,
            "created_at": created_at,
            "git_commit": request.git_commit,
            "dirty_tree": request.dirty_tree,
            "dataset_id": request.dataset_id,
            "configuration": _normalized_mapping(request.configuration),
            "configuration_hash": request.configuration_hash,
            "feature_schema_version": request.feature_schema_version,
            "model_identifier": request.model_identifier,
            "checkpoint_revision": request.checkpoint_revision,
            "seed": request.seed,
            "fold_definitions": [
                _normalized_mapping(item) for item in request.fold_definitions
            ],
            "hardware": _normalized_mapping(request.hardware),
            "library_versions": _normalized_mapping(request.library_versions),
            "metrics": _normalized_mapping(request.metrics),
            "artifacts": [item.to_dict() for item in artifacts],
            "approval_status": request.approval_status,
            "approval_evidence": list(request.approval_evidence),
            "decision_grade": decision_grade,
            "supersedes_experiment_id": request.supersedes_experiment_id,
            "warnings": warnings,
        }
        experiment_id = f"kexp-{hash_configuration(payload)[:24]}"
        record = ExperimentRecord.from_dict({"experiment_id": experiment_id, **payload})
        path = self.root / "experiments" / f"{experiment_id}.json"
        _write_immutable(path, record.to_json().encode("utf-8"))
        return self.get(experiment_id, verify_artifacts=True)

    def get(self, experiment_id: str, *, verify_artifacts: bool = True) -> ExperimentRecord:
        _experiment_id(experiment_id)
        path = self.root / "experiments" / f"{experiment_id}.json"
        if not path.is_file():
            raise FileNotFoundError(f"unknown experiment {experiment_id}")
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            record = ExperimentRecord.from_dict(value)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ExperimentRegistryError(f"invalid experiment record {experiment_id}") from exc
        self._validate_record(record, expected_id=experiment_id)
        if verify_artifacts:
            for artifact in record.artifacts:
                self._verify_artifact(artifact)
        return record

    def set_alias(
        self,
        alias: str,
        experiment_id: str,
        *,
        reason: str,
        updated_at: str | datetime,
    ) -> AliasEvent:
        if alias not in MODEL_ALIASES:
            raise ExperimentRegistryError(f"alias must be one of {sorted(MODEL_ALIASES)}")
        _non_empty(reason, "alias reason")
        record = self.get(experiment_id, verify_artifacts=True)
        self._validate_alias_policy(alias, record)
        pointer_path = self.root / "aliases" / f"{alias}.json"
        previous = None
        previous_event = None
        if pointer_path.exists():
            previous_event = self._load_alias_pointer(alias)
            previous = previous_event.experiment_id
        timestamp = _utc_timestamp(updated_at, "updated_at")
        if previous_event is not None and timestamp <= previous_event.updated_at:
            raise ExperimentRegistryError("alias updated_at must increase monotonically")
        event_payload = {
            "alias": alias,
            "experiment_id": experiment_id,
            "previous_experiment_id": previous,
            "updated_at": timestamp,
            "reason": reason,
        }
        event = AliasEvent(
            event_id=f"kae-{hash_configuration(event_payload)[:24]}", **event_payload
        )
        event_path = self.root / "alias-events" / alias / f"{event.event_id}.json"
        _write_immutable(event_path, event.to_json().encode("utf-8"))
        _write_atomic(pointer_path, event.to_json().encode("utf-8"))
        return event

    def resolve_alias(self, alias: str, *, verify_artifacts: bool = True) -> ExperimentRecord:
        event = self._load_alias_pointer(alias)
        return self.get(event.experiment_id, verify_artifacts=verify_artifacts)

    def alias_history(self, alias: str) -> tuple[AliasEvent, ...]:
        if alias not in MODEL_ALIASES:
            raise ExperimentRegistryError(f"alias must be one of {sorted(MODEL_ALIASES)}")
        directory = self.root / "alias-events" / alias
        if not directory.exists():
            return ()
        events = []
        for path in directory.glob("kae-*.json"):
            try:
                event = AliasEvent.from_dict(json.loads(path.read_text(encoding="utf-8")))
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                raise ExperimentRegistryError(f"invalid alias event {path.name}") from exc
            self._validate_alias_event(event, alias)
            if path.stem != event.event_id:
                raise ExperimentRegistryError("alias event filename and identity disagree")
            events.append(event)
        ordered = tuple(sorted(events, key=lambda event: (event.updated_at, event.event_id)))
        previous = None
        for event in ordered:
            if event.previous_experiment_id != previous:
                raise ExperimentRegistryError("alias event history chain is incomplete")
            previous = event.experiment_id
        return ordered

    def _store_artifact(self, artifact: ArtifactInput) -> RegisteredArtifact:
        source = Path(artifact.path)
        if source.is_symlink() or not source.is_file():
            raise ExperimentRegistryError("artifact input changed before registration")
        destination = (
            self.root
            / "artifacts"
            / "sha256"
            / artifact.expected_sha256[:2]
            / artifact.expected_sha256
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if not destination.is_file() or sha256_file(destination) != artifact.expected_sha256:
                raise ExperimentRegistryError(
                    f"stored artifact is corrupt: {artifact.expected_sha256}"
                )
        else:
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{artifact.expected_sha256}.", suffix=".tmp", dir=destination.parent
            )
            temporary = Path(temporary_name)
            digest = hashlib.sha256()
            size = 0
            try:
                with source.open("rb") as input_handle, os.fdopen(descriptor, "wb") as output_handle:
                    for chunk in iter(lambda: input_handle.read(1024 * 1024), b""):
                        digest.update(chunk)
                        size += len(chunk)
                        output_handle.write(chunk)
                    output_handle.flush()
                    os.fsync(output_handle.fileno())
                if digest.hexdigest() != artifact.expected_sha256:
                    raise ExperimentRegistryError(
                        f"artifact bytes do not match expected_sha256 for role {artifact.role}"
                    )
                try:
                    os.link(temporary, destination)
                except FileExistsError:
                    if sha256_file(destination) != artifact.expected_sha256:
                        raise ExperimentRegistryError(
                            f"stored artifact is corrupt: {artifact.expected_sha256}"
                        )
                temporary.unlink(missing_ok=True)
            except Exception:
                temporary.unlink(missing_ok=True)
                raise
        size_bytes = destination.stat().st_size
        return RegisteredArtifact(
            role=artifact.role,
            filename=source.name,
            sha256=artifact.expected_sha256,
            size_bytes=size_bytes,
            media_type=artifact.media_type,
            storage_path=str(destination.relative_to(self.root).as_posix()),
        )

    def _verify_artifact(self, artifact: RegisteredArtifact) -> None:
        expected_path = Path("artifacts") / "sha256" / artifact.sha256[:2] / artifact.sha256
        if Path(artifact.storage_path) != expected_path:
            raise ExperimentRegistryError(
                f"artifact storage path is not content-addressed for role {artifact.role}"
            )
        path = self.root / expected_path
        if not path.is_file():
            raise ExperimentRegistryError(f"registered artifact is missing for role {artifact.role}")
        if path.stat().st_size != artifact.size_bytes or sha256_file(path) != artifact.sha256:
            raise ExperimentRegistryError(f"registered artifact is corrupt for role {artifact.role}")

    def _validate_record(self, record: ExperimentRecord, *, expected_id: str) -> None:
        if record.registry_version != EXPERIMENT_REGISTRY_VERSION:
            raise ExperimentRegistryError("unsupported experiment registry version")
        if record.experiment_id != expected_id:
            raise ExperimentRegistryError("experiment record filename and identity disagree")
        calculated = f"kexp-{hash_configuration(record.identity_payload())[:24]}"
        if calculated != expected_id:
            raise ExperimentRegistryError("experiment record identity hash is invalid")
        if record.decision_grade != (
            record.approval_status == "approved"
            and not record.dirty_tree
            and bool(record.approval_evidence)
        ):
            raise ExperimentRegistryError("decision_grade is inconsistent with approval and tree state")
        if record.configuration_hash != hash_configuration(record.configuration):
            raise ExperimentRegistryError("stored configuration hash is invalid")
        roles = [artifact.role for artifact in record.artifacts]
        if not roles or len(roles) != len(set(roles)):
            raise ExperimentRegistryError("stored artifact roles must be non-empty and unique")
        if record.approval_status not in APPROVAL_STATUSES:
            raise ExperimentRegistryError("stored approval status is invalid")
        if record.approval_status in {"approved", "rejected"} and not record.approval_evidence:
            raise ExperimentRegistryError("stored approval evidence is incomplete")

    def _validate_alias_policy(self, alias: str, record: ExperimentRecord) -> None:
        if alias in {"champion", "rollback"} and not record.decision_grade:
            raise ExperimentRegistryError(
                f"{alias} requires an approved, clean-tree, artifact-verified experiment"
            )
        if alias == "candidate" and record.approval_status == "rejected":
            raise ExperimentRegistryError("a rejected experiment cannot be a candidate")
        if alias == "research-only" and record.approval_status not in {
            "unreviewed",
            "research-only",
        }:
            raise ExperimentRegistryError(
                "research-only alias requires unreviewed or research-only status"
            )
        if alias == "rejected" and record.approval_status != "rejected":
            raise ExperimentRegistryError("rejected alias requires rejected approval status")

    def _load_alias_pointer(self, alias: str) -> AliasEvent:
        if alias not in MODEL_ALIASES:
            raise ExperimentRegistryError(f"alias must be one of {sorted(MODEL_ALIASES)}")
        path = self.root / "aliases" / f"{alias}.json"
        if not path.is_file():
            raise FileNotFoundError(f"alias is not assigned: {alias}")
        try:
            event = AliasEvent.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ExperimentRegistryError(f"invalid alias pointer {alias}") from exc
        self._validate_alias_event(event, alias)
        event_path = self.root / "alias-events" / alias / f"{event.event_id}.json"
        if not event_path.is_file() or event_path.read_bytes() != path.read_bytes():
            raise ExperimentRegistryError("alias pointer is not backed by immutable history")
        return event

    @staticmethod
    def _validate_alias_event(event: AliasEvent, expected_alias: str) -> None:
        if event.alias != expected_alias or event.alias not in MODEL_ALIASES:
            raise ExperimentRegistryError("alias event identity is invalid")
        _experiment_id(event.experiment_id)
        if event.previous_experiment_id is not None:
            _experiment_id(event.previous_experiment_id)
        _utc_timestamp(event.updated_at, "updated_at")
        _non_empty(event.reason, "alias reason")
        payload = event.to_dict()
        payload.pop("event_id")
        calculated = f"kae-{hash_configuration(payload)[:24]}"
        if calculated != event.event_id:
            raise ExperimentRegistryError("alias event hash is invalid")


def _validate_json_mapping(value: Mapping[str, Any], name: str) -> None:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    try:
        canonical_json(value)
    except (TypeError, ValueError) as exc:
        raise ExperimentRegistryError(f"{name} must contain finite canonical JSON values") from exc


def _normalized_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    return json.loads(canonical_json(value))


def _utc_timestamp(value: str | datetime, name: str) -> str:
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    except (TypeError, ValueError) as exc:
        raise ExperimentRegistryError(f"{name} must be a valid timestamp") from exc
    if not isinstance(timestamp, datetime) or timestamp.tzinfo is None:
        raise ExperimentRegistryError(f"{name} must be timezone-aware")
    return timestamp.astimezone(timezone.utc).isoformat()


def _experiment_id(value: str) -> None:
    if not isinstance(value, str) or _EXPERIMENT_ID_PATTERN.fullmatch(value) is None:
        raise ExperimentRegistryError("experiment_id is invalid")


def _non_empty(value: object, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ExperimentRegistryError(f"{name} must be a non-empty string")


def _write_immutable(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.is_file() and path.read_bytes() == payload:
            return
        raise FileExistsError(f"refusing to replace immutable registry evidence {path}")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            if path.read_bytes() != payload:
                raise FileExistsError(f"immutable registry evidence changed concurrently: {path}")
        temporary.unlink(missing_ok=True)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _write_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


__all__ = [
    "APPROVAL_STATUSES",
    "EXPERIMENT_REGISTRY_VERSION",
    "MODEL_ALIASES",
    "AliasEvent",
    "ArtifactInput",
    "ExperimentRecord",
    "ExperimentRegistrationRequest",
    "ExperimentRegistry",
    "ExperimentRegistryError",
    "RegisteredArtifact",
]
