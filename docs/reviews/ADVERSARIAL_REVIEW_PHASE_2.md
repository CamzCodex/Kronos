# Adversarial review — Phase 2 canonical market-data contract

Date: 2026-07-22  
Scope: `data/canonical-market-contract`

## Decision

The contract is suitable as the foundation for dataset ingestion after required CI passes. It does not make any existing Qlib dataset valid, does not select a licensed benchmark source, and does not prove point-in-time causality.

## False-confidence risks and controls

### Structured validation can be mistaken for source truth

Severity: high. A bar can satisfy OHLC, timestamp, frequency, and non-negativity invariants while still being revised, incorrectly adjusted, survivorship-biased, or sourced after the prediction timestamp.

Control: reports identify the exact checks performed. Dataset promotion remains blocked behind source provenance, manifest creation, and the separate leakage auditor.

### Built-in calendars do not contain authoritative holiday history

Severity: high. Weekdays and local session hours alone cannot prove full historical exchange alignment.

Control: built-in calendars emit `calendar_holidays_unverified`; evidence-grade ingestion may require `require_authoritative_calendar=True` and a populated calendar supplied by the data lane.

### Adjustment declarations do not prove causal corporate-action knowledge

Severity: critical for research. Positive factors and raw/adjusted consistency do not establish when an adjustment became knowable or whether a back-adjusted series injects future corporate actions.

Control: the manifest records policy, while the Phase 3 auditor must test effective-time causality. An adjustment declaration is not an audit pass.

### Deterministic identity can still bind a flawed dataset

Severity: high. A stable hash proves exact content identity, not correctness.

Control: `build_dataset_manifest` refuses failed validation reports and embeds the structured report. The leakage audit remains a separate mandatory artifact.

### Instrument IDs do not yet establish point-in-time universe membership

Severity: critical for cross-sectional evaluation. Consistent identifiers within a dataset do not prove membership history, delisting treatment, or symbol mapping.

Control: the reference data card leaves these fields Unknown and blocks dataset approval. The leakage auditor and ingestion adapter must bind membership effective times.

## Residual limitations

- Intraday missing-bar checks are strongest within a session; complete session schedules require an authoritative calendar source.
- The dependency-free core does not itself write Parquet or Arrow. The storage policy designates those formats; the first ingestion adapter should add an optional engine based on the selected source and workload.
- Dataset identity is deterministic for the canonical values and implementation rules. It is not a guarantee of byte equivalence across arbitrary future schema versions.
- `created_at` is recorded but excluded from the dataset ID; content, ingestion timestamps, configuration, raw hashes, splits, policy, schema, and code commit determine identity.
- The reference daily dataset remains planned. Provider, licence, universe, coverage, row count, and split boundaries are Unknown.

## Checkpoint compatibility

No model, tokenizer, inference, or checkpoint-sensitive structure changes. Released checkpoint numerical behavior is unaffected.

## Promotion blockers

- Select and licence a reproducible source.
- Supply an authoritative calendar and point-in-time universe history.
- Define causal corporate-action effective-time semantics.
- Implement and pass the leakage auditor.
- Bind a real dataset manifest and data card to an experiment.

Passing this phase permits ingestion-adapter and auditor work only. It does not permit fine-tuning, paper portfolio construction, or financial claims.
