# Audit-gated development-fold runner

Status: executable development-fold binding contract; no real evaluation result

## Entry gate

`run_evaluation_fold` accepts only `AuditedWalkForwardFold`. It revalidates that:

- the leakage audit passed and has no failures;
- every required leakage check is present;
- dataset, code, split, and audit identities match; and
- result creation occurs after both the test boundary and audit timestamp.

Manually constructing the wrapper cannot bypass these checks.

## Fair forecast suite

Every development fold must contain exactly:

- the eleven versioned mandatory baselines; and
- one non-baseline candidate, normally the released Kronos checkpoint.

Every submission carries an information-set hash, forecast-configuration hash, and
forecast-artifact hash. The runner requires one shared information-set hash and
identical instrument/as-of/target/horizon, reference, realized value, training scale,
market regime, and volatility regime rows across every model. A missing, extra,
failed, or mislabeled comparator invalidates the fold.

Target timestamps must stay within the audited test boundary. The development runner
explicitly refuses final-holdout timestamps.

## Comparable scores

The runner executes the common scorer for every model and emits a complete long-form
comparison grid for metrics defined across the entire suite. Undefined metrics are
omitted for every model rather than producing an incomplete comparison. Interval
coverage is compared as absolute error from the declared nominal interval, not as a
misleading higher-is-better percentage.

The runner records but does not automatically use the predeclared reference baseline.
Paired multi-fold aggregation remains a separate step after all development folds are
registered.

## Optional economic path

Cost requests are optional because forecast evaluation must not invent a strategy.
When externally produced paper target weights are supplied, their dataset/fold/code,
realization boundary, and core commission/spread/slippage assumptions must match the
audited fold. Cost accounting remains downstream and creates no signal or order.

## Immutable artifact

`EvaluationFoldResult` binds:

- dataset, fold, split, code, and audit identity;
- candidate and reference-baseline declarations;
- shared information and truth identities;
- upstream forecast/configuration/artifact hashes;
- all scorecard inputs/configurations;
- optional paper-cost input/assumption identities; and
- the complete scorecards, ledgers, comparable scores, and warnings.

`write_evaluation_fold_result` writes canonical JSON through a temporary file and
atomic replacement. An identical artifact is idempotent; a changed artifact at the
same path is refused and the existing evidence remains untouched.

## Remaining integration boundary

This runner does not load a model, derive a baseline, calculate training-only MASE
scales, assign regimes, transform forecasts into signals, select hyperparameters, or
open the final holdout. Adapters must construct and hash those inputs causally. The
experiment registry must verify referenced artifact bytes before any result becomes
decision-grade.
