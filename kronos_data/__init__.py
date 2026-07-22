"""Canonical market-data contracts for reproducible Kronos research."""

from .adjustments import AdjustmentPolicy
from .calendars import CalendarSpec, calendar_for
from .hashing import hash_configuration, hash_dataframe, sha256_file
from .leakage import (
    REQUIRED_LEAKAGE_CHECKS,
    AuditFinding,
    AuditSeverity,
    LeakageAuditResult,
    LeakageAuditSpec,
    NormalizationProbe,
    SplitBoundary,
    SplitRole,
    UniversePolicy,
    audit_leakage,
    hash_split_boundaries,
)
from .manifests import DatasetManifest, build_dataset_manifest, write_manifest
from .schema import CANONICAL_BAR_FIELDS, FEATURE_SCHEMA_VERSION
from .source_gate import (
    REQUIRED_SOURCE_CHECKS,
    SOURCE_GATE_VERSION,
    AccessMode,
    ReferenceSourceAssessment,
    SourceGateError,
    SourceGateFinding,
    SourceGateResult,
    assess_reference_source,
    write_source_gate_result,
)
from .validation import (
    IssueSeverity,
    ValidationConfig,
    ValidationIssue,
    ValidationReport,
    validate_bars,
)

__all__ = [
    "AdjustmentPolicy",
    "AuditFinding",
    "AuditSeverity",
    "CANONICAL_BAR_FIELDS",
    "CalendarSpec",
    "DatasetManifest",
    "FEATURE_SCHEMA_VERSION",
    "IssueSeverity",
    "LeakageAuditResult",
    "LeakageAuditSpec",
    "NormalizationProbe",
    "REQUIRED_LEAKAGE_CHECKS",
    "REQUIRED_SOURCE_CHECKS",
    "SOURCE_GATE_VERSION",
    "SplitBoundary",
    "SplitRole",
    "AccessMode",
    "ReferenceSourceAssessment",
    "SourceGateError",
    "SourceGateFinding",
    "SourceGateResult",
    "UniversePolicy",
    "ValidationConfig",
    "ValidationIssue",
    "ValidationReport",
    "audit_leakage",
    "assess_reference_source",
    "hash_split_boundaries",
    "build_dataset_manifest",
    "calendar_for",
    "hash_configuration",
    "hash_dataframe",
    "sha256_file",
    "validate_bars",
    "write_manifest",
    "write_source_gate_result",
]
