# Kronos report register

Register date: 2026-07-22  
Current register baseline: `577af114c2fdae7fde5dfc4f89475ebcda06e074`

No zero-shot, walk-forward, baseline-comparison, or economic benchmark report exists yet.

| Report name | Description | Date | Dataset ID | Model revision | Git commit | Confidence | Supersedes | Status | File paths |
|---|---|---|---|---|---|---|---|---|---|
| Kronos implementation status | Reconciled engineering, branch, CI, blocker, and critical-path status | 2026-07-22 | N/A | N/A | `c94cf3be1af5f57849e67defeb25c82ddd93815d` evidence baseline | High | None | Current | `docs/status/KRONOS_IMPLEMENTATION_STATUS.md` |
| Kronos research status | Separates software validation from absent financial evidence and records the current research-only decision | 2026-07-22 | Unknown | Pinned regression revisions only | `c94cf3be1af5f57849e67defeb25c82ddd93815d` evidence baseline | High for status; no confidence in alpha | None | Current | `docs/status/KRONOS_RESEARCH_STATUS.md` |
| Phase 4D adversarial review | Reviews streaming archive failure modes, script compatibility, and residual memory limits | 2026-07-22 | N/A | N/A | `c94cf3be1af5f57849e67defeb25c82ddd93815d` | High | None | Current | `docs/reviews/ADVERSARIAL_REVIEW_PHASE_4D.md` |
| Phase 0 adversarial review | Challenges repository state, split integrity, evidence claims, and CI coverage | 2026-07-22 | Unknown | Pinned regression revisions only | `c94cf3be1af5f57849e67defeb25c82ddd93815d` evidence baseline | High for repository findings | None | Current | `docs/reviews/ADVERSARIAL_REVIEW_PHASE_0.md` |
| Phase 2 adversarial review | Challenges the canonical market-data contract, calendar authority, dataset identity, adjustment causality, and universe controls | 2026-07-22 | No real dataset | N/A | Introduced by `data/canonical-market-contract` | High for contract findings | None | Current | `docs/reviews/ADVERSARIAL_REVIEW_PHASE_2.md` |
| Phase 3 adversarial review | Challenges leakage-audit provenance completeness, hidden holdout access, normalization coverage, adjustment timing, and universe evidence | 2026-07-22 | No real dataset | N/A | Introduced by `data/leakage-auditor` | High for auditor behavior; no market validation | None | Current | `docs/reviews/ADVERSARIAL_REVIEW_PHASE_3.md` |
| Quality/security adversarial review | Challenges CI scope, scanner completeness, supply-chain trust, dependency evidence, and repository-setting enforcement | 2026-07-22 | N/A | N/A | Introduced by the quality/security gate branch | High for stated local controls; no production-security claim | None | Current | `docs/reviews/ADVERSARIAL_REVIEW_QUALITY_SECURITY.md` |

Future benchmark entries must identify a deterministic dataset ID, model/checkpoint revision, code commit, confidence, supersession relation, and immutable result paths.
