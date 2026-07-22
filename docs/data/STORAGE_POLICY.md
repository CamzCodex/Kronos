# Research data storage policy

## Decision

- Use Parquet or Arrow as the primary scalable representation for research bars.
- Use DuckDB or Polars optionally for local analytical queries when justified by workload evidence.
- Use versioned `.kronos.zip` archives for bounded audited snapshots, regression fixtures, prepared compatibility artifacts, and portable experiment evidence.
- Do not store extremely large historical universes solely as JSON-in-ZIP.

## Identity boundary

Storage format does not define dataset identity. The deterministic dataset manifest binds source, content hash, raw hashes, universe, adjustment policy, split boundaries, code commit, feature schema, and configuration hash.

## Immutability

Evidence-grade manifests are write-once. A changed dataset, split, configuration, adjustment policy, or code commit receives a new dataset ID. Existing manifests are never silently replaced.
