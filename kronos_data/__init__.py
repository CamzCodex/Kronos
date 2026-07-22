"""Canonical market-data contracts for reproducible Kronos research."""

from .adjustments import AdjustmentPolicy
from .calendars import CalendarSpec, calendar_for
from .hashing import hash_configuration, hash_dataframe, sha256_file
from .leakage import (
    AuditFinding,
    AuditSeverity,
    LeakageAuditResult,
    LeakageAuditSpec,
    NormalizationProbe,
    SplitBoundary,
    SplitRole,
    UniversePolicy,
    audit_leakage,
)
from .manifests import DatasetManifest, build_dataset_manifest, write_manifest
from .schema import CANONICAL_BAR_FIELDS, FEATURE_SCHEMA_VERSION
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
    "SplitBoundary",
    "SplitRole",
    "UniversePolicy",
    "ValidationConfig",
    "ValidationIssue",
    "ValidationReport",
    "audit_leakage",
    "build_dataset_manifest",
    "calendar_for",
    "hash_configuration",
    "hash_dataframe",
    "sha256_file",
    "validate_bars",
    "write_manifest",
]
