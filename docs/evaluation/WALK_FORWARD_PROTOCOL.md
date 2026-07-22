# Walk-forward evaluation protocol

Status: split-planning and audit-binding contract; no financial result

## Purpose

`kronos_eval` constructs immutable expanding- or rolling-window fold plans from the
ordered timestamps of a validated dataset. It does not forecast, score, trade, or
touch the final holdout. The later evaluation runner must accept only
`AuditedWalkForwardFold` objects produced by `attach_leakage_audit`.

## Required identity

Every plan and fold records:

- dataset ID;
- code commit;
- feature-schema version;
- model/checkpoint revision;
- canonical cost assumptions and their SHA-256;
- seed;
- split configuration and hash; and
- exact inclusive start/end timestamps, positions, and observation counts.

The deterministic plan ID binds the full timestamp-index hash, split configuration,
and research context. `created_at` is audit metadata and does not change the plan ID.
It must be timezone-aware and cannot precede the latest dataset timestamp.

## Split construction

`WalkForwardConfig` requires positive train, validation, test, and final-holdout
sizes. Calibration is optional. Purge and embargo sizes are counts of observations in
the supplied validated timestamp index, not calendar durations.

For each fold, target roles are ordered:

1. training;
2. purge;
3. validation;
4. optional purge and calibration;
5. purge;
6. test.

The next fold cannot begin its new validation period until the prior fold's entire
validation/calibration/test sequence is observable. The minimum step therefore
equals all post-training roles and purges. This prevents the same observation from
serving as a selection or test target in multiple folds. In expanding mode, training
starts at the first timestamp and grows through the prior test. In rolling mode, the
training window retains a fixed size and advances through the prior test.

The final holdout is one fixed suffix shared by every fold. A dedicated embargo
immediately precedes it. No development train, validation, calibration, test, or
purge boundary may enter either final interval.

## Multiple-period gate

`minimum_folds` defaults to two. A one-fold plan is available only when explicitly
configured for debugging and is marked non-decision-grade. `maximum_folds` selects
the most recent candidate folds for bounded smoke tests; any truncation is recorded
and makes `decision_grade_protocol=False` because a restricted period can be
cherry-picked.

Two folds are a mechanical minimum, not sufficient scientific evidence. Promotion
still requires a meaningful majority of folds, regime/instrument breadth,
perturbation, uncertainty, and a single untouched final evaluation.

## Leakage-audit binding

Leakage results now include:

- `audit_id`, binding split declarations, sample windows, feature provenance,
  normalization probes, universe membership, corporate actions, selection events,
  policy controls, dataset ID, code commit, and audit time; and
- `split_hash`, binding exact target-role boundaries.

`attach_leakage_audit` rejects a result when it failed or its dataset, code commit,
split hash, or audit identity does not match the fold. Optional calibration must be
explicitly disabled in both the plan and leakage specification.

An attached audit establishes that the supplied specification passed the implemented
checks. It does not prove that a source adapter reported every event or that arbitrary
code never accessed a holdout.

## Immutable plan artifacts

`write_walk_forward_plan` writes one canonical JSON artifact atomically. Repeating an
identical write is allowed. Replacing an existing path with different bytes is
refused. This makes split plans suitable inputs to the experiment registry.

## Required later enforcement

The evaluation runner must:

- consume only attached passed audits;
- derive context from verified manifests and registry state, not manual labels;
- derive purge size from maximum lookback/label overlap risk;
- keep final observations inaccessible until configuration freeze;
- record every selection and final-evaluation event;
- apply the recorded costs rather than merely persisting them;
- run identical timestamps/information through Kronos and all baselines; and
- write metrics/artifacts under an immutable experiment identity.

No real dataset, forecast, baseline, metric, or economic result is produced by this
phase.
