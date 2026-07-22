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

## DEC-013 — Experiment artifacts are content-addressed and model aliases are governed

- decision_id: `DEC-013`
- date: 2026-07-22
- decision: Register experiments as immutable canonical records whose declared files are copied and SHA-256 verified in content-addressed storage; reconstruct and reverify every artifact by experiment ID; retain every model-alias movement as an immutable event; and restrict champion/rollback aliases to approved, clean-tree, artifact-verified records with approval references.
- alternatives: Store only paths or caller-declared hashes; overwrite experiment JSON; use mutable aliases without history; introduce a hosted MLflow service immediately.
- evidence: `kronos_eval/registry.py`, registry regression tests, the registry specification, and the Phase 7 adversarial review.
- reasoning: Decision evidence must survive source-file deletion and detect later byte or metadata changes. A lightweight local implementation closes that integrity gap without adding a service before a real benchmark justifies it.
- risks: Caller metadata and approval authority are not independently attested; local storage is not signed or WORM; alias writers are not cross-process locked; exact bytes can still encode causally invalid data.
- reversal trigger: A versioned registry or MLflow-compatible backend that preserves content verification, immutable history, reconstructability, and stricter attestation with migration tests.
- related commit: Introduced by `registry/experiment-and-model-lineage`
- related PR: `#20`

## DEC-014 — No reviewed reference source is approved

- decision_id: `DEC-014`
- date: 2026-07-22
- decision: Refuse to create a decision-grade dataset manifest unless a provider passes explicit usage-rights/access, retained-snapshot hash, historical-depth, calendar, causal-adjustment, point-in-time membership, delisting, instrument/currency, revision, and primary-evidence checks. Do not approve Qlib/Yahoo or reviewed paid alternatives on current evidence.
- alternatives: Treat Qlib/Yahoo as approved despite documented quality/version warnings and unresolved rights; purchase a provider without authorization; use the bundled single-instrument intraday fixture as a daily equity-universe benchmark; invent a snapshot hash and continue.
- evidence: `kronos_data/source_gate.py`, source-gate regression tests, `docs/data/REFERENCE_SOURCE_ASSESSMENT.md`, and its linked primary sources.
- reasoning: A forced benchmark on unlicensed, unavailable, mutable, future-adjusted, or survivorship-biased data would produce precise but non-decision-grade metrics. Unknown is more truthful than an unsupported approval.
- risks: The zero-shot benchmark remains blocked until data authority is supplied; a later approved source may require adapter-specific work and cost.
- reversal trigger: A complete user-supplied licensed evidence package or separately authorized paid-source evaluation passes the versioned source gate and downstream canonical/leakage validation.
- related commit: Introduced by `data/reference-source-gate`
- related PR: `#21`

## DEC-015 — Quality and security gates are scoped and fail closed

- decision_id: `DEC-015`
- date: 2026-07-22
- decision: Require exact-pinned Ruff, Mypy, pip-audit, Gitleaks, archive, leakage, and evaluation checks for the maintained research surface; do not describe excluded legacy code or unverified GitHub repository settings as covered.
- alternatives: Add no gates; lint the entire legacy tree and leave CI permanently red; suppress all existing findings; use mutable security-action tags.
- evidence: `.github/workflows/quality-security.yml`, `requirements-quality.txt`, local Ruff/Mypy/audit results, 329 offline tests, clean sdist/wheel build, and the quality/security adversarial review.
- reasoning: A narrow green gate that names its exclusions creates enforceable forward progress, while a knowingly red or silently suppressed whole-tree gate provides no reliable merge signal.
- risks: Known-vulnerability databases and secret patterns can miss novel threats; pinned tools age; third-party Actions remain a supply-chain dependency; legacy executable code remains outside static coverage; branch protection is not established by a workflow file.
- reversal trigger: Expand the gate monotonically when legacy surfaces are repaired, or replace a tool only with a pinned, tested control that provides equal or stronger evidence.
- related commit: Introduced by the quality/security gate branch
- related PR: This phase's pull request

## DEC-016 — The bundled Web UI is local-only

- decision_id: `DEC-016`
- date: 2026-07-22
- decision: Permit the bundled Flask UI only as a single-user loopback research demonstration; fail closed on untrusted hosts/origins/files, malformed market rows, unbounded request controls, runtime installation, and internal error disclosure; prohibit every remote or production deployment until a separately reviewed access and workload design exists.
- alternatives: Remove the UI; preserve its debugger/all-interface/CORS/path defaults; infer production readiness from dependency-audit success; add ad hoc remote exposure without authentication.
- evidence: `webui/security.py`, hardened launchers/routes, 37 Web UI security regressions, dependency audits, generated-output removal/ignore controls, and the Web UI adversarial review.
- reasoning: A small explicit local trust boundary preserves useful demonstration access while removing avoidable local-file, browser, debugger, and silent-data-repair risks. It does not pretend that a development server is an authenticated service.
- risks: Local model execution remains resource-intensive; checkpoint IDs are not revision-pinned in the UI; external browser assets and inline template code remain; local result files are mutable; structural validation is not canonical data or leakage approval.
- reversal trigger: A separately versioned remote-deployment architecture passes authentication, authorization, TLS, isolation, workload, serving, dependency, and security regression review without weakening the local defaults.
- related commit: Introduced by `security/webui-local-boundary`
- related PR: This phase's pull request

## DEC-017 — Select Norgate conditionally and reject its standard subscription

- decision_id: `DEC-017`
- date: 2026-07-22
- decision: Select Norgate US Stocks Platinum as the preferred conditional technical source, target the USD 346.50 six-month package only after a provider- or counsel-approved signed amendment permits the project, automation/transfer, immutable snapshots, derived evidence, permitted aggregate publication, and indefinite post-expiry retention; otherwise buy nothing and keep the source gate closed.
- alternatives: Purchase Norgate under its standard personal-use/deletion terms; buy a longer or more expensive package before evidence; use Nasdaq under standard deletion terms; run Qlib/Yahoo smoke metrics; lower the source gate; abandon the benchmark.
- evidence: `docs/data/REFERENCE_SOURCE_ACQUISITION_DECISION.md`, the acquisition adversarial review, Norgate's 2026-06-19 EULA, stock-package/content/accessibility pages, and Nasdaq Data Link terms.
- reasoning: Norgate most closely matches historical-constituent, delisting, corporate-action, identity, and history needs at a bounded initial price, but standard deletion/use terms make durable evidence impossible. Contract-first acquisition preserves the scientific and registry requirements without paying for unusable access.
- risks: Custom terms may be unavailable or expensive; public documentation does not prove first-known timestamps; the supported Python path is Windows-oriented; histories and delistings contain qualifications; corrections can change data; legal interpretation requires provider/counsel acceptance.
- reversal trigger: Another provider offers equal or stronger point-in-time technical coverage under accepted durable-retention/publication terms at lower total acquisition risk, or Norgate declines the mandatory amendment/evidence fields.
- related commit: Introduced by `docs/data-acquisition-closeout`
- related PR: This phase's pull request
