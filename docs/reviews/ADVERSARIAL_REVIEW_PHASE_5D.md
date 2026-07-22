# Adversarial review — Phase 5D audit-gated runner

Date: 2026-07-22  
Scope: `evaluation/audit-gated-runner`

## Decision

The runner is suitable for binding synthetic or real development-fold inputs after
cross-version and package gates pass. It closes silent comparator omission and basic
audit/boundary bypass paths. It does not produce evidence by itself. Kronos remains
`RESEARCH ONLY`.

## How this could produce false confidence

### A passed audit object could be forged

Severity: critical. Typed input is not authentication; code can manually construct a
`passed=True` result without executing provenance checks.

Control: the runner revalidates audit fields, required checks, failures, and identities
and hashes the complete audit. The future registry must link the audit to its source
provenance artifact and code. Cryptographic identity proves consistency, not truth.

### Equal hashes can still describe a dishonest adapter

Severity: critical. An adapter can hash future-contaminated history consistently for
all models or falsely label scales/regimes as causal.

Control: the runner requires equality and passed audit attachment but cannot establish
data truth. Raw hashes, point-in-time source records, training-only scale provenance,
regime availability, and adapter tests remain promotion blockers.

### Missing baselines could make Kronos look stronger

Severity: critical. A failed or unfavorable comparator can disappear from a result.

Control: exactly all eleven mandatory baselines plus one candidate are required and
baseline labels are fixed. The runner fails before scoring an incomplete suite.

### Models could be scored on different targets

Severity: critical. Different instruments, reference values, target outcomes, scale
denominators, or regime labels invalidate comparison even if dates overlap.

Control: a deterministic truth hash covers every such field and must be identical
across all submissions. Forecast-specific values remain separate.

### The final holdout could leak into development artifacts

Severity: critical. Final outcomes could influence model/baseline choice or report
framing before confirmation.

Control: development targets and paper realizations must fall inside the audited test
boundary and are checked against the final-holdout start. No final-run API exists in
this phase. Filesystem/data-access isolation is still required before a real run.

### Undefined metrics can create an incomplete comparison grid

Severity: high. Precision, recall, tail recall, CRPS, or ranking metrics may be missing
for only one model, then fail later or be selectively ignored.

Control: comparable output includes a metric only when defined for every model. Full
scorecards retain every undefined value and warning for interpretation.

### Forecast artifacts are referenced but not byte-verified

Severity: high. A supplied artifact hash may be syntactically valid but not match any
persisted file, or the file may later disappear.

Control: hashes are bound into the run identity. The experiment registry must verify,
copy/link, and reconstruct every artifact before decision-grade status.

### Optional costs can be omitted

Severity: critical for economic claims. A forecast-only fold could be reported as
strategy evidence even though no target weights or costs were evaluated.

Control: absence creates an explicit warning and no economic result. Benchmark
promotion requires separately declared signal/risk logic and cost paths for every
required scenario.

### One reference baseline can be weak

Severity: high. The runner records one predeclared reference but does not prove it was
chosen fairly or is the best conventional method.

Control: all baselines are retained. Multi-fold aggregation and the benchmark report
must compare with the pre-registered best development baseline and disclose all
baseline results, feature-use differences, and selection provenance.

## Regression evidence

Tests cover passed-audit execution, manual failed/incomplete-audit refusal, exact
baseline completeness and labels, dataset/fold/code identity, shared information,
identical truth rows, test/final boundaries, downstream cost binding, cost-assumption
matching, deterministic identity, canonical JSON without NaN, idempotent immutable
writes, existing-artifact preservation, and timestamp ordering.

No real data, model forecast, audit provenance, cost estimate, fold comparison, or
financial conclusion has been produced.

## Checkpoint compatibility

No model, tokenizer, predictor, sampling, inference tensor, architecture, or checkpoint
changes. Released checkpoint behavior is unaffected.

## Promotion blockers

- Implement the artifact-verifying experiment/model registry.
- Implement source-specific causal scale/regime/forecast adapters.
- Select and approve point-in-time data, calendar, universe, adjustments, and licence.
- Add an evaluation smoke run built from deliberately contaminated/failing inputs.
- Register every development fold before a separately controlled final run.
- Produce the complete zero-shot report and adversarial conclusion.

Passing Phase 5D permits registry and real-adapter integration only. It does not permit
fine-tuning, paper portfolio promotion, live trading, or financial claims.
