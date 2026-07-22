# Adversarial review — local runtime and performance readiness

Review date: 2026-07-22

Decision boundary: local installation, checkpoint identity, operational latency measurement, and
single-user loopback behavior only; no financial usefulness or production-deployment approval

## What was challenged

- Can a clean Python environment install the repository and invoke supported commands?
- Does predictor behavior depend on a caller remembering `eval()` or `no_grad()`?
- Can the Web UI silently move to a different Hugging Face checkpoint?
- Does its “latest” comparison actually use the latest evaluable rows?
- Can a user distinguish a device/latency smoke from a market benchmark?
- Will generic PyTorch installation use Cam's Radeon RX 9070 on Windows?
- Are packaged console scripts and Web UI templates present in the wheel?
- Does local verification rely on downloading a second build toolchain?

## Findings and controls

### High — the UI previously used stale rows while labelling them latest

With no selected start date, the route took the first `lookback + pred_len` rows. It also reported
forecast timestamps beyond the end of the file while comparing against old in-file observations.
The route now selects the last complete historical/realized window, passes the immediately following
timestamps to the predictor, and uses those exact timestamps for predictions, truth, and charts.
Regression tests prove the selected target begins strictly after history.

### High — interactive checkpoint identities were mutable

The Web UI previously loaded every model and tokenizer from the mutable default branch. A central
catalog now binds mini, small, and base to exact 40-character model and tokenizer revisions. The UI
and benchmark command use that catalog and return the revisions in model metadata. Pinning bytes
does not establish training-data provenance; GAP-008 remains open.

### Medium — inference mode depended on caller discipline

Examples usually called `eval()`, but `KronosPredictor` did not enforce it. The predictor now puts
both modules into evaluation mode and the autoregressive path uses `torch.inference_mode()`. Tensor
construction avoids redundant NumPy copies. Defaults remain float32 and the pinned numerical
checkpoint workflow remains the compatibility gate; no unverified mixed precision or compilation is
enabled automatically.

### Medium — AMD acceleration needs a vendor-specific PyTorch build

A generic `pip install` can select a CPU or unsuitable wheel. The local runbook requires installing
AMD's current Windows PyTorch build first and then verifies device discovery mechanically. AMD's
current documentation lists RX 9070 Windows inference support but no backward pass, so the supported
use is forecast/benchmark only. The repository does not automate mutable vendor wheel URLs.

The first remote audit also identified that public PyTorch 2.9.1 is inside newly published affected
ranges, including a malicious-checkpoint path fixed in 2.10 and a separate affected range ending at
2.10. Generic Linux/macOS installs therefore require PyTorch 2.11 or newer. The Windows marker keeps
AMD's current 2.9 vendor build installable but the doctor reports that it is below the generic floor;
only exact pinned safetensors are permitted until AMD publishes a compatible 2.11+ runtime.

### Medium — operational latency can be mistaken for alpha

`kronos-runtime benchmark` records device, exact revisions, load time, per-run latency, throughput,
and peak GPU memory using deterministic synthetic input. Every report labels itself non-market
evidence. It cannot enter the experiment registry as a zero-shot market result or open promotion
gates.

### Low — isolated local build bootstrap can fail before packaging

This sandbox could install declared dependencies but could not let the build tool create a second
networked environment for setuptools. The local verifier therefore builds with its already-installed
declared backend. GitHub's Python 3.10/3.12 package workflow continues to create clean isolated
builds, install the wheel without source-tree imports, check the packaged template, and invoke the
installed runtime entry point.

## Validation evidence

- Clean editable install under Python 3.12 with PyTorch 2.9.1 CPU.
- `kronos-runtime doctor --device cpu` passed.
- Offline end-to-end `kronos-runtime smoke --device cpu` passed with model/tokenizer evaluation mode
  asserted.
- 62 focused runtime/split/catalog/predictor/Web UI regressions passed.
- 384 maintained offline and Web UI tests passed through `scripts/verify_local.py`.
- Ruff passed and Mypy passed across 25 maintained files.
- Compilation, patch hygiene, sdist, wheel, packaged Web UI template, and console-entry declarations
  passed locally; external wheel import and cross-version isolation remain remote merge gates.

## Residual risks

- No RX 9070 benchmark has run in this environment; real latency, driver stability, and memory use
  remain machine-specific.
- No KV cache, mixed precision, `torch.compile`, or quantization is enabled; those require separate
  numerical and hardware evidence before becoming defaults.
- The local Flask UI remains prohibited for every remote exposure.
- Exact checkpoints can still carry unknown pretraining overlap or preprocessing history.
- The real market benchmark remains blocked by the source/licence gate.

## Decision

Approve this phase for local pull, installation, CPU/GPU discovery, offline verification, pinned
checkpoint execution, operational benchmarking, and single-user loopback use after CI passes. Keep
fine-tuning, market-performance, paper-portfolio, remote UI, and live-trading gates closed.
