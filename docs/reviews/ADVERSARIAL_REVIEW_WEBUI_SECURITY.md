# Adversarial review — local Web UI security boundary

Review date: 2026-07-22

Decision boundary: deliberate single-user loopback use only; no remote-deployment or research-evidence claim

## What was challenged

- Can a browser choose an arbitrary local file or escape through a symlink?
- Can a malicious origin invoke expensive model operations?
- Can malformed market rows be silently repaired into apparently valid evidence?
- Can large bodies, files, row sets, sampling controls, or device strings exhaust resources?
- Can a traceback, secret, or absolute path be returned to a client?
- Can the launcher expose a debugger, listen on every interface, or modify the environment?
- Can externally hosted browser scripts change without detection?
- Could all controls pass while the application is still unsafe to publish?

## Findings and responses

### High — remote exposure remains prohibited

The application has no authentication, authorization, TLS termination, rate limiting, user
isolation, production WSGI server, or multi-user model lifecycle. Loopback binding, trusted-host
checking, and origin refusal reduce local browser attack surface but do not create an authenticated
service. An origin header can also be absent from a non-browser client. `GAP-011` therefore remains
open for every tunnel, reverse proxy, LAN bind, hosted deployment, or production claim.

### High — structural input checks are not research-data approval

The loader now refuses missing or ambiguous timestamps, invalid dates, duplicate or decreasing
times, empty or over-limit files, missing/non-finite numeric values, non-positive prices, impossible
OHLC relationships, and negative volume or amount. It never synthesizes timestamps or silently
drops invalid rows. These checks do not prove an authoritative calendar, causal corporate-action
adjustment, point-in-time membership, licensing, freshness, or freedom from leakage. UI outputs
remain demonstration artifacts and cannot enter the experiment registry as decision-grade evidence.

### Resolved medium finding — checkpoint acquisition is revision-pinned

The original hardening phase named Hugging Face model IDs without exact revisions. The local-runtime
phase now binds mini, small, and base model/tokenizer pairs to exact 40-character revisions and
returns those identities when a model loads. The UI must still not be used as the reference
benchmark launcher because its data is not source/leakage approved and its saved results are mutable.

### Medium — browser dependencies remain externally hosted

Plotly and Axios use exact-version URLs and SHA-384 Subresource Integrity hashes, so unexpected
bytes are refused by conforming browsers. Availability and certificate trust still depend on two
CDNs, and the legacy template requires inline script/style allowances in its content policy.
Self-hosted assets and nonce- or hash-based inline controls would be stronger for a future deployable
application.

### Medium — local resource limits are not workload isolation

Bodies, input bytes, rows, horizons, samples, and devices are bounded, and the development server is
single-threaded. A local process can still consume substantial CPU/GPU memory within those bounds,
and there is no per-job cancellation or OS-level quota. This is acceptable only inside the declared
single-user loopback boundary.

### Low — saved predictions are local mutable files

Result names use UTC microseconds and exclusive creation, and stored source identity is reduced to a
basename. The result directory is neither encrypted nor content-addressed and is not an experiment
registry. Twenty-nine pre-existing generated JSON files containing an upstream user's absolute
local paths were removed from the current tree, and the directory is now ignored. Those historical
commits are not rewritten; no credential was observed, but the old paths remain in Git history.
Local users must treat every new result as disposable demonstration output.

## Validation evidence

- 37 Web UI boundary regressions pass locally, including traversal, symlink, format, host, origin, request
  size, parameter, launcher, error-sanitization, SRI, and strict market-input cases.
- Ruff passes the Web UI security helper, launcher, and regressions.
- Mypy passes the security helper and launcher.
- Earlier scans of the final core and Web UI declarations reported no known vulnerabilities under
  the pinned audit tool. A fresh repeat failed before scanning because the sandbox could not
  bootstrap pip in pip-audit's isolated environment; remote CI remains the authoritative audit.
- The maintained repository Ruff and Mypy surfaces remain green.
- Full repository tests cannot run in the local sandbox because PyTorch is absent; the existing
  Python 3.10/3.12 GitHub workflows remain the merge authority.

## Decision

The hardened UI may be used intentionally on `127.0.0.1` by one local researcher. It must not be
published, tunneled, proxied, or described as production-safe. Its data validation and forecast
outputs provide no shortcut around the canonical source, leakage, benchmark, or promotion gates.
