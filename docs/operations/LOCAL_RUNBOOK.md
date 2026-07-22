# Local installation, verification, and performance runbook

Status date: 2026-07-22

This runbook makes the repository reproducible on a local workstation. Passing it proves that the
software installs, the pinned checkpoint executes, and the local machine's latency is measured. It
does **not** prove that Kronos predicts markets profitably.

## Recommended path for Cam's Windows 11 / Radeon RX 9070 workstation

AMD currently lists the RX 9070 as supported by its Windows PyTorch 2.9 / ROCm 7.2.1 build on
Python 3.12. AMD also states that the Windows stack is inference-only (no backward pass), so use it
for local forecasts and benchmarking—not fine-tuning.

The public PyTorch 2.9 version is below this repository's generic 2.11 security floor. The Windows
marker preserves compatibility with AMD's current vendor build, but `kronos-runtime doctor` reports
the exception. Until AMD supports a 2.11+ build, load only the exact pinned Kronos safetensors in a
single-user local environment; never load an untrusted `.pth`/pickle checkpoint, and upgrade the AMD
runtime as soon as the support matrix permits it.

1. Install Python 3.12 and the current AMD graphics driver required by the official guide.
2. Follow AMD's current [PyTorch on Windows installation instructions](https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/install/installrad/windows/install-pytorch.html) inside a new virtual environment. Do this before the repository install so pip retains the compatible AMD PyTorch build.
3. Pull and install this repository:

   ```powershell
   git clone https://github.com/CamzCodex/Kronos.git
   cd Kronos
   py -3.12 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   # Install AMD PyTorch here using the current official AMD command.
   python -m pip install --upgrade pip
   python -m pip install -e ".[dev,webui]"
   ```

4. Prove that PyTorch sees the Radeon accelerator:

   ```powershell
   kronos-runtime doctor --device auto --require-accelerator
   ```

   The report should select `cuda:0`, name the Radeon GPU, and normally show a non-null
   `torch_rocm_runtime`. PyTorch deliberately exposes ROCm devices through its `cuda` API. On AMD's
   current 2.9 build, `torch_meets_generic_security_floor` will be false for the documented reason
   above; do not reinterpret that as a clean generic dependency audit.

5. Run the offline end-to-end smoke and full repository gates:

   ```powershell
   kronos-runtime smoke --device auto
   python scripts/verify_local.py --full --device auto --require-accelerator
   ```

6. Download and benchmark the exact validated default checkpoint:

   ```powershell
   kronos-runtime benchmark `
     --model kronos-small `
     --device auto `
     --context 400 `
     --horizon 32 `
     --samples 1 `
     --warmups 1 `
     --runs 3 `
     --output outputs/benchmarks/rx9070-small.json
   ```

   The generated JSON is an operational latency record. Compare `kronos-mini`, `kronos-small`, and
   `kronos-base` using identical context/horizon/sample settings before choosing a local default.

7. Place a strict CSV in a local data directory and start the loopback-only UI:

   ```powershell
   kronos-web --data-dir .\data
   ```

   Open `http://127.0.0.1:7070`. Do not expose this server through Tailscale, a tunnel, LAN binding,
   or reverse proxy; it has no remote authentication boundary.

## One-command CPU fallback

The included bootstrap creates `.venv`, installs the development/Web UI dependencies, and runs the
offline verification path using the generic PyTorch package:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap.ps1 -Full -Device cpu
```

Do not use this bootstrap after creating an AMD environment unless the AMD PyTorch build is already
installed in `.venv` and `kronos-runtime doctor` confirms it remains selected.

## Pulling updates safely

From a clean local `master`:

```powershell
git fetch origin
git switch master
git pull --ff-only origin master
python -m pip install -e ".[dev,webui]"
python scripts/verify_local.py --full --device auto
```

`--ff-only` prevents a surprise local merge. If `git status --short` is not empty, preserve or commit
those changes before pulling.

## Verification levels

- `kronos-runtime doctor`: environment and accelerator discovery only.
- `kronos-runtime smoke`: tiny offline model/tokenizer inference; no network or checkpoint download.
- `python scripts/verify_local.py`: all maintained offline and Web UI regressions.
- `python scripts/verify_local.py --full`: offline suite plus Ruff, Mypy, compilation, and package build.
- `python scripts/verify_local.py --checkpoint`: downloads the exact pinned Kronos-small/tokenizer
  revisions and runs the numerical regression.
- `kronos-runtime benchmark`: measures pinned released-checkpoint loading and inference latency on
  the selected local device; it never creates a market-performance claim.

## Operational expectations

- The first checkpoint load downloads files from Hugging Face and is slower than later cached runs.
- Increasing horizon and sample count increases autoregressive work; compare machines/settings with
  identical inputs.
- The runtime forces both model and tokenizer into evaluation mode and uses PyTorch inference mode.
- Web UI model selections are pinned to exact 40-character model and tokenizer revisions.
- Windows ROCm limitations can change. Re-check AMD's [Windows support matrix](https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/compatibility/compatibilityrad/windows/windows_compatibility.html) before upgrading Python, PyTorch, ROCm, or the graphics driver.

## Scientific boundary

The real baseline comparison remains blocked until a licensed point-in-time market dataset passes
the repository source gate. Local runtime success must not open fine-tuning, paper-portfolio, or live
trading gates.
