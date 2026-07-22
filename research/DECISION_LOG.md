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
