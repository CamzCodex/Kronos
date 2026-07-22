# Adversarial review — Phase 7 experiment and model registry

Date: 2026-07-22  
Scope: `kronos_eval.registry` and its local alias policy  
Financial conclusion: unchanged — **RESEARCH ONLY / usefulness Unknown**

## Review questions

### How could this produce false confidence?

An exact record can preserve flawed evidence perfectly. Artifact hashes do not prove that source
bars were point-in-time, adjustments were causal, baselines were fair, costs were conservative,
or the final holdout was untouched. The registry therefore refuses to present reconstruction as
scientific validation.

The `decision_grade` field means only that the initial status was `approved`, the tree was
declared clean, and an approval reference was supplied. It is a mechanical eligibility flag, not
an independent review finding.

### Where could future data enter?

Future information can enter before registration through a source adapter, feature or regime
label, adjustment table, universe membership history, forecast submission, or approval process.
The registry detects changed bytes; it cannot infer whether unchanged bytes are causal. A passed
real leakage audit and source provenance remain mandatory inputs to the benchmark.

### Could this pass tests while being financially invalid?

Yes. Tests use deliberately synthetic metadata and byte fixtures. They validate identity,
copying, reconstruction, tamper detection, and alias policy only. No market prediction or
strategy is exercised.

### Can results be cherry-picked or rewritten?

Experiment records and alias events cannot be replaced through the API. Alias movement remains
possible by design, but its reason, predecessor, time, and target are retained. A user can still
choose which experiment to register or approve, so the experiment/report registers and
predeclared promotion criteria remain necessary.

## Findings

| ID | Severity | Finding | Disposition |
|---|---|---|---|
| R7-001 | High | Git state, environment metadata, and approval references are caller declarations, not independently attested. | Open; the executable launcher must capture these values and resolve evidence references before any promotion. |
| R7-002 | Critical | Exact registered bytes can still contain future-contaminated, survivorship-biased, or unlicensed data. | Open; blocks model promotion until a real source adapter and passed fold audits exist. |
| R7-003 | High | Initial `approved` status can be requested by a caller; v1 checks evidence presence but not reviewer authority or signatures. | Open; no experiment may be promoted solely because this field is set. |
| R7-004 | Medium | Local evidence is tamper-detecting on read but lacks signed/WORM retention and remote replication. | Open; acceptable for the local research phase, not production governance. |
| R7-005 | Medium | Alias writes are atomic but not protected by a cross-process lock. | Open; launch orchestration must serialize writers until locking is added. |
| R7-006 | Low | Artifact filenames contribute to experiment identity even when content is identical. | Accepted for v1 because the logical source name is useful lineage and remains deterministic. |

## Attack-oriented regression evidence

The focused suite covers:

- declared digest mismatch before publication;
- modified registered artifacts;
- modified experiment records;
- symbolic-link artifact inputs;
- dirty or unapproved champion/rollback attempts;
- rejected-to-candidate attempts;
- retroactive alias timestamps;
- alias pointer tampering and immutable event history;
- deterministic identity in independent registry roots;
- dangling supersession identities;
- non-finite metadata and naive timestamps.

## Promotion decision

Unresolved findings R7-001 through R7-003 block any scientific or model promotion. The registry
is suitable as a local evidence-preservation primitive after CI passes; it does not clear the
zero-shot benchmark, fine-tuning, paper-portfolio, or live-trading gates.
