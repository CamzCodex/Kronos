# Adversarial review — quality and security gates

Review date: 2026-07-22  
Decision boundary: engineering merge controls only; no market-performance or production-security claim

## What was challenged

- Could the workflow be green while important executable code is never checked?
- Could dependency auditing miss a vulnerable resolved environment?
- Could secret scanning miss encoded, novel, or runtime-provided credentials?
- Could a mutable third-party Action change after review?
- Could test duplication create confidence without adding a distinct control?
- Could the Web UI remain unsafe despite an all-green dependency audit?
- Could workflow files exist without being required by branch protection?

## Findings and responses

### High — the legacy Web UI remains unsafe to expose

The dependency audit found eight published findings in the pinned Flask 2.3.3 and Flask-CORS
4.0.0 declarations. Those declarations are upgraded and now audit clean. That does not address the
UI's debugger on `0.0.0.0`, unrestricted CORS, caller-supplied file paths, internal error disclosure,
runtime dependency installation, or missing resource bounds. `GAP-011` blocks every network or
production deployment claim until application-level hardening and regression tests land.

### Medium — static analysis is intentionally incomplete

The upstream examples, `finetune_csv`, Web UI source, and older model internals contain substantial
pre-existing Ruff and typing debt. Enabling a whole-tree required gate now would be permanently red
or require unrelated behavioral churn. The workflow therefore gates the maintained data,
evaluation, typed forecast, and safe-archive surfaces and documents every exclusion. Coverage must
expand monotonically; exclusions are not a passing result.

### Medium — scanner success is not proof of absence

`pip-audit` depends on published vulnerability records and declared requirement resolution.
Gitleaks depends on known patterns and accessible Git history. Neither proves that dependencies are
non-malicious, credentials never existed elsewhere, or runtime secrets are governed correctly.
Results are merge controls, not security certification.

### Medium — external action and toolchain trust remains

The Gitleaks Action is pinned to exact commit
`bcfb9cce635345aac9996cedc19b2de8e01b894f`; Ruff, Mypy, and pip-audit are exactly pinned in
`requirements-quality.txt`. Exact pins prevent silent drift but do not prove upstream integrity and
must be deliberately reviewed and refreshed.

### Medium — branch protection is outside workflow evidence

A workflow can pass while administrators retain the ability to merge without requiring it. The
repository must require all four jobs in branch protection when permissions support that setting.
The current PR cannot infer or claim that configuration from workflow existence.

### Low — duplicated tests can obscure distinct coverage

The integrity job deliberately separates archive, leakage/data, and evaluation commands so a
future edit cannot remove an entire control family from a broad test invocation unnoticed. These
tests overlap the Python 3.12 offline matrix by design; Python 3.10 compatibility remains owned by
the existing offline workflow.

## Validation evidence

- 329 non-networked tests passed locally.
- The four networked checkpoint cases failed before download because the sandbox lacks SOCKS proxy
  support; no checkpoint-sensitive code changed. The separate pinned checkpoint workflow remains
  the authoritative control when its path filter applies.
- Ruff passed on the declared maintained surface.
- Mypy passed on 18 maintained source files.
- Core and upgraded Web UI requirement audits reported no known vulnerabilities.
- The sdist and wheel built without the former setuptools license-metadata deprecation.

## Decision

The focused workflow is suitable to become a required merge gate after remote CI passes. It does
not close `GAP-007` completely and does not make the Web UI safe to deploy. Those limitations must
remain visible in status registers and PR language.
