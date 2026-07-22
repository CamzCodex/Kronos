# Adversarial review — Phase 4D streaming archives

Date: 2026-07-22  
Scope: `hardening/phase-4d-stream-archives`

## Decision

Phase 4D is suitable for merge after required CI passes. It changes archive-writing mechanics only. It does not change the released model architecture, checkpoint parameters, archive schema, or reader semantics.

## Findings

### Resolved: script execution bypassed the streaming writer

Severity: high. The original branch redirected `finetune.data_io.save_frame_mapping` by mutating the imported module in `finetune.__init__`. Direct execution of `finetune/data_io.py`, including its trusted legacy-migration CLI, therefore retained the old writer that held every serialized frame payload in memory.

Resolution: `finetune.data_io.save_frame_mapping` is now a lazy compatibility wrapper around `archive_writer.save_frame_mapping`. Tests cover package exports, wrapper delegation, and direct script migration.

### Resolved: replacement occurred without validating the completed temporary ZIP

Severity: high. A successfully closed but corrupted or structurally incomplete temporary archive could have replaced a valid destination.

Resolution: before replacement, the writer reopens the temporary archive, validates member structure and the exact manifest, and streams every member through SHA-256 verification. A forced validation failure test proves that an existing destination remains untouched.

### Residual: JSON serialization still materialises one complete frame

Severity: medium. Peak payload memory is bounded to one serialized DataFrame rather than the entire multi-symbol mapping, but a single extremely large frame can still require substantial memory.

Required follow-up: benchmark representative large frames and consider chunked Arrow/Parquet research storage. The `.kronos.zip` format remains intended for audited snapshots, fixtures, and portable artifacts rather than extremely large historical universes.

### Residual: source DataFrames are not immutable during writing

Severity: low. A caller that mutates a DataFrame concurrently with serialization could produce nondeterministic input semantics.

Required follow-up: document that callers must provide stable frames; dataset manifests in the canonical market-data phase will bind content hashes to experiment identity.

## False-confidence checks

- Passing archive tests establishes storage integrity only; it provides no evidence of forecast accuracy or trading value.
- Byte-for-byte determinism is asserted for identical logical inputs and implementation versions, not across pandas releases.
- This phase does not address survivorship bias, corporate-action causality, dataset splits, or evaluation leakage.
- Checkpoint regression is not triggered because no model or checkpoint-sensitive file changes.

## Promotion blockers

None for the storage implementation after offline tests and package/wheel smoke tests pass on Python 3.10 and 3.12. The research system remains unvalidated and must not be promoted for trading use.
