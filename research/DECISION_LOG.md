# Kronos decision log

## DEC-001 — Paper and simulation only

- decision_id: `DEC-001`
- date: 2026-07-22
- decision: All trading-related work remains paper/simulation only. No raw forecast may create a broker order.
- alternatives: Live execution; no trading-layer research.
- evidence: Mission authorization and absence of validated economic evidence.
- reasoning: Model, data, signal, portfolio, risk, and execution controls are incomplete.
- risks: Paper results can still be overstated if costs or causality are weak.
- reversal trigger: Separate explicit authorization after evidence, risk, security, and operational gates.
- related commit: `c94cf3be1af5f57849e67defeb25c82ddd93815d` evidence baseline
- related PR: None

## DEC-002 — Current model classification is research only

- decision_id: `DEC-002`
- date: 2026-07-22
- decision: Kronos remains `RESEARCH ONLY`; incremental forecasting and economic usefulness are Unknown.
- alternatives: Direct forecaster; feature generator; limited-regime approval; rejected.
- evidence: No walk-forward baseline benchmark; critical split contamination and causal-audit gaps.
- reasoning: Engineering tests cannot substitute for out-of-sample financial evidence.
- risks: Delays downstream integration but prevents false confidence.
- reversal trigger: Leakage-audited zero-shot benchmark and untouched holdout support another classification.
- related commit: `c94cf3be1af5f57849e67defeb25c82ddd93815d` evidence baseline
- related PR: None

## DEC-003 — Storage roles remain separated

- decision_id: `DEC-003`
- date: 2026-07-22
- decision: Use Parquet/Arrow for scalable research data and `.kronos.zip` for audited compact snapshots, fixtures, and portable artifacts.
- alternatives: Store all history as JSON-in-ZIP; replace `.kronos.zip` immediately.
- evidence: Phase 4D adversarial review and format characteristics.
- reasoning: The safe archive is deterministic and portable but still materialises one frame payload and is not the preferred large-universe analytical store.
- risks: Multiple formats require clear manifest and lineage rules.
- reversal trigger: Measured workload evidence supports a different canonical storage design.
- related commit: `c94cf3be1af5f57849e67defeb25c82ddd93815d`
- related PR: `#11`

## DEC-004 — Fine-tuning is gated behind zero-shot evaluation

- decision_id: `DEC-004`
- date: 2026-07-22
- decision: Do not begin serious predictor, tokenizer, or joint fine-tuning until canonical data, leakage audit, registry, walk-forward baselines, and the released-checkpoint zero-shot benchmark are complete.
- alternatives: Fine-tune immediately; abandon released checkpoints.
- evidence: Mission sequence and absence of decision-grade baseline evidence.
- reasoning: Training loss cannot establish incremental out-of-sample information and expands the search space for overfitting.
- risks: Zero-shot performance may be weak; that is an informative result, not a reason to bypass the gate.
- reversal trigger: Only a separately documented decision based on new evidence or an unavoidable technical blocker.
- related commit: `c94cf3be1af5f57849e67defeb25c82ddd93815d` evidence baseline
- related PR: None

## DEC-005 — Dataset identity is content- and process-bound

- decision_id: `DEC-005`
- date: 2026-07-22
- decision: Dataset identity binds canonical content, raw source hashes, split declarations, adjustment policy, feature schema, configuration hash, and code commit. Validation reports are cryptographically bound to the supplied input order and canonical content.
- alternatives: Filename identity; timestamp-only identity; provider ID without content hashing.
- evidence: `kronos_data/hashing.py`, `kronos_data/validation.py`, and `kronos_data/manifests.py`.
- reasoning: Reconstructability requires both exact data content and the process semantics that created it.
- risks: A stable identity can still describe flawed or non-causal data; validation and leakage approval remain separate gates.
- reversal trigger: A versioned manifest migration supported by compatibility tests and evidence that a different identity boundary is safer.
- related commit: Introduced by `data/canonical-market-contract`
- related PR: This phase's pull request

## DEC-006 — Failed leakage audits invalidate experiments

- decision_id: `DEC-006`
- date: 2026-07-22
- decision: Any error-severity leakage or causality finding sets `passed=False` and makes the associated evaluation ineligible for experiment approval, report promotion, fine-tuning decisions, or paper-portfolio use.
- alternatives: Treat findings as non-blocking warnings; permit manual result promotion without a persisted audit.
- evidence: `kronos_data/leakage.py` and deliberately contaminated fixtures.
- reasoning: Leakage can create apparently strong but financially meaningless performance and cannot be averaged away by later metrics.
- risks: Incomplete provenance will block runs until adapters and evaluators emit the required records.
- reversal trigger: None for error-severity causal failures; only correction and a new audit may reverse the result.
- related commit: Introduced by `data/leakage-auditor`
- related PR: This phase's pull request

## DEC-007 — Raw forecast samples remain primary evidence

- decision_id: `DEC-007`
- date: 2026-07-22
- decision: Preserve every requested decoded sample before validation; never overwrite raw output; make candle projection opt-in and cell-accounted; compute published path summaries only from explicitly identified valid raw or projected paths.
- alternatives: Continue returning only the mean; silently repair all candles; discard invalid paths without reporting; treat token sample frequency as a calibrated probability.
- evidence: `model/forecast.py`, forecast API regression tests, and the Phase 4 adversarial review.
- reasoning: Calibration, dispersion, invalid-generation rate, and repair sensitivity cannot be audited after samples are averaged or overwritten.
- risks: Conditioning summaries on valid paths can bias the distribution, while projection can mask model failure. Every evaluation must report raw/output validity, generated/summary counts, repair rate, and calibration.
- reversal trigger: A versioned forecast-contract change supported by backward-compatibility tests and stronger evidence-preservation guarantees.
- related commit: Introduced by `inference/probabilistic-forecast-api`
- related PR: This phase's pull request

## DEC-008 — Walk-forward target roles cannot be reused

- decision_id: `DEC-008`
- date: 2026-07-22
- decision: Build folds from the validated observation index; prevent validation, calibration, purge, or test observations from being reused in those roles across folds; allow later training to expand or roll through a fully observed prior test; reserve one fixed embargoed final holdout; and classify truncated or single-fold plans as non-decision-grade.
- alternatives: Arbitrary date strings; overlapping rolling test windows; one favorable fold; a moving final holdout; silent fold truncation.
- evidence: `kronos_eval/walk_forward.py`, walk-forward regression tests, and the Phase 5A adversarial review.
- reasoning: Reused evaluation targets and movable holdouts create correlated evidence and selection opportunities that can look like robustness without independent periods.
- risks: Conservative stepping produces fewer folds, and observation-count purge can still be too short for the actual horizon/feature availability. The configured gap and sensitivity must be justified by each benchmark.
- reversal trigger: A versioned alternative resampling protocol with explicit dependence correction, contamination tests, and evidence that it strengthens rather than inflates inference.
- related commit: Introduced by `evaluation/walk-forward-engine`
- related PR: This phase's pull request

## DEC-009 — Mandatory baselines share one frozen information contract

- decision_id: `DEC-009`
- date: 2026-07-22
- decision: Run all eleven required v1 forecast baselines from one validated OHLCVA frame and timestamp set; hash the exact common information set and frozen method controls; refuse partial-suite execution; and label deterministic one-path summaries as degenerate rather than calibrated probabilities.
- alternatives: Give each method independently loaded data; silently omit failing baselines; tune controls on test/final periods; report deterministic signs as forecast probabilities.
- evidence: `kronos_eval/baselines.py`, baseline regression tests, the baseline-suite specification, and the Phase 5B adversarial review.
- reasoning: Identical observation availability and immutable controls are necessary for fair attribution. All-or-nothing execution prevents weak or failed comparators from disappearing after results are observed, while explicit degeneracy prevents false calibration claims.
- risks: Most simple methods use close only even though Kronos can use all OHLCVA fields; point-forecast baselines do not test distribution calibration; frozen defaults may not be the strongest conventional comparator; recursive tree/AR paths can amplify error.
- reversal trigger: A versioned baseline-suite contract with pre-registered controls and tests that strengthens fairness without using evaluation or final-holdout outcomes.
- related commit: Introduced by `evaluation/baseline-suite`
- related PR: This phase's pull request

## DEC-010 — Final-holdout scores never enter development aggregation

- decision_id: `DEC-010`
- date: 2026-07-22
- decision: Require a complete paired model/fold/metric grid and one predeclared reference baseline; remove the named final-holdout fold before calculating development means, fold wins, or bootstrap intervals; and report final values separately without automatically pooling or selecting a model.
- alternatives: Pool final and development folds; choose the best baseline after observing all scores; report only an aggregate mean; omit failed model/fold cells.
- evidence: `kronos_eval/aggregation.py`, final-isolation regression tests, the evaluation protocol, and the Phase 5C adversarial review.
- reasoning: Final pooling and ex-post comparator choice convert confirmation data into model selection. Complete paired grids prevent failures or unfavorable comparators from disappearing.
- risks: Fold resampling does not remove market dependence, a predeclared baseline may not be the strongest comparator, and multiple metric/model comparisons can still inflate confidence.
- reversal trigger: A versioned, pre-registered inference protocol that demonstrably strengthens final isolation and dependence handling without using final outcomes for selection.
- related commit: Introduced by `evaluation/metrics-and-costs`
- related PR: This phase's pull request

## DEC-011 — Over-limit paper trades invalidate cost evaluation

- decision_id: `DEC-011`
- date: 2026-07-22
- decision: Apply commission, half spread, slippage, and participation-dependent impact to every absolute target-weight change; require complete-universe zero targets; and fail the evaluation when any simulated trade exceeds the declared participation ceiling rather than silently clipping, filling, or omitting it.
- alternatives: Ignore liquidity; assume full fills at fixed costs; drop rejected trades; carry omitted positions without explicit exits.
- evidence: `kronos_eval/costs.py`, cost/causality/liquidity regression tests, the evaluation protocol, and the Phase 5C adversarial review.
- reasoning: Silent fill assumptions and missing exits systematically understate turnover and costs. A failed scenario is more honest than a portfolio return that could not satisfy its own liquidity assumptions.
- risks: Dollar volume and impact parameters can still be wrong, a hard ceiling does not model partial fills or delay, and paper costs are not execution evidence.
- reversal trigger: A versioned execution simulator with explicit rejected/partial/delayed fills and evidence that it is at least as conservative.
- related commit: Introduced by `evaluation/metrics-and-costs`
- related PR: This phase's pull request

## DEC-012 — Development folds require a complete audited comparator suite

- decision_id: `DEC-012`
- date: 2026-07-22
- decision: Execute a development fold only from a revalidated passed audit; require exactly the eleven mandatory baselines plus one named candidate on one shared information identity and identical target/reference/scale/regime rows; refuse test-boundary and final-holdout violations; and persist the complete result as an immutable atomic JSON artifact.
- alternatives: Trust a wrapper without revalidation; permit partial comparator sets; score models on independently supplied targets; allow final rows in development results; persist chat-only or mutable outputs.
- evidence: `kronos_eval/runner.py`, runner regression tests, the audit-gated runner specification, and the Phase 5D adversarial review.
- reasoning: A strong model can appear superior if audits are bypassed, weak baselines disappear, truth rows differ, or final data enters development. One identity-bound complete artifact makes these failures observable and blocks silent substitution.
- risks: Valid hashes do not prove honest source provenance, upstream artifact bytes are not verified until the registry exists, optional costs can be omitted, and filesystem-level final-data isolation remains absent.
- reversal trigger: A versioned runner/registry protocol that provides stronger source authentication, artifact verification, comparator completeness, and final isolation with compatibility evidence.
- related commit: Introduced by `evaluation/audit-gated-runner`
- related PR: This phase's pull request
