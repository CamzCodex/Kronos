# Adversarial review — reference source gate

Date: 2026-07-22  
Scope: `kronos_data.source_gate` and first-source assessment  
Financial conclusion: unchanged — **RESEARCH ONLY / usefulness Unknown**

## False-confidence paths

### Confirmed terms can still be misinterpreted

Severity: high. A boolean cannot encode every territorial, user-class, storage, redistribution,
publication, or derived-data restriction.

Control: the gate requires terms and entitlement text references, but legal/contract review
remains outside the software. Unknown rights fail. Paid access without separate authorization
fails.

### A raw hash can pin bad data

Severity: critical. Exact bytes may contain vendor errors, future-adjusted values, stale prices,
bad identifiers, or omitted delistings.

Control: source approval is only an entry gate. Canonical validation, source-specific
normalization tests, fold leakage audits, and market-result review remain mandatory.

### “Point-in-time membership” can be asserted without publication timing

Severity: critical. Effective membership intervals reconstructed later can still use information
that was unavailable on the decision date.

Control: the gate separately requires membership intervals and availability timestamps. Both are
required to pass.

### Adjusted history can embed later actions

Severity: critical. A current fully adjusted price series can reflect corporate actions announced
after an earlier prediction timestamp.

Control: the gate requires retained events and their availability timestamps. The adjustment
auditor must reconstruct each as-of view; a vendor’s current adjusted close alone is insufficient.

### Delistings can disappear while membership looks dynamic

Severity: critical. A point-in-time constituent file does not prove that terminal outcomes or
delisted series remain present.

Control: delisting coverage is an independent required check.

### Provider statements can be accurate but incomplete

Severity: high. Marketing documentation may describe depth and adjusted fields without calendar,
revision, membership, or delisting methodology.

Control: at least two primary references are required, and every evidence class has its own gate.
Reference count alone never creates a pass.

## Regression evidence

Synthetic tests cover each required evidence class, unknown rights, unavailable sources,
unapproved paid access, raw-hash retention, explicit history thresholds, deterministic identity,
invalid timestamps/hashes, duplicate evidence, and immutable result writes.

No real provider passes because no complete evidence package or raw snapshot was supplied.

## Findings

| ID | Severity | Finding | Disposition |
|---|---|---|---|
| RSG-001 | Critical | No reviewed candidate has complete licensing, snapshot, calendar, adjustment, universe, and delisting evidence. | Open; blocks benchmark and model promotion. |
| RSG-002 | High | Qlib/Yahoo is reproducible only after exact bytes are retained; its own documentation warns about data and adjustment quality and historical-version instability. | Open; engineering smoke only unless resolved. |
| RSG-003 | High | Plausible alternatives reviewed here require paid access, which is outside current authorization. | Escalation required before acquisition. |
| RSG-004 | Medium | The gate trusts human-entered booleans and references. | The future source adapter must derive/hash evidence automatically where possible. |

## Decision

The gate is suitable for refusing incomplete sources after CI passes. It does not make a source
available. Unresolved critical finding RSG-001 blocks the zero-shot decision benchmark,
fine-tuning, paper portfolio work, and all live-trading work.
