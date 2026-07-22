#!/usr/bin/env python3
"""Run the same local-operability gates expected before a Kronos PR is merged."""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OFFLINE_TESTS = (
    "tests/test_modules.py",
    "tests/test_tokenizer.py",
    "tests/test_predictor.py",
    "tests/test_model_catalog.py",
    "tests/test_runtime_cli.py",
    "tests/test_forecast_api.py",
    "tests/test_sampling.py",
    "tests/test_finetune_csv_normalization.py",
    "tests/test_finetune_config.py",
    "tests/test_data_io.py",
    "tests/test_archive_paths.py",
    "tests/test_backtest_io.py",
    "tests/test_market_data_validation.py",
    "tests/test_dataset_manifests.py",
    "tests/test_leakage_auditor.py",
    "tests/test_walk_forward.py",
    "tests/test_baselines.py",
    "tests/test_evaluation_metrics.py",
    "tests/test_evaluation_costs.py",
    "tests/test_fold_aggregation.py",
    "tests/test_evaluation_runner.py",
    "tests/test_experiment_registry.py",
    "tests/test_reference_source_gate.py",
    "tests/webui/test_security.py",
)
RUFF_PATHS = (
    "kronos_data",
    "kronos_eval",
    "kronos_runtime",
    "model/catalog.py",
    "model/forecast.py",
    "finetune/archive_writer.py",
    "finetune/config.py",
    "finetune/data_io.py",
    "webui/security.py",
    "webui/run.py",
    "scripts/verify_local.py",
)


def _run(command: Sequence[str]) -> None:
    print(f"\n> {' '.join(command)}", flush=True)
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", action="store_true", help="Add lint, typing, and build")
    parser.add_argument(
        "--checkpoint",
        action="store_true",
        help="Download and run the pinned released-checkpoint regression",
    )
    parser.add_argument("--device", default="auto")
    parser.add_argument("--require-accelerator", action="store_true")
    args = parser.parse_args(argv)

    python = sys.executable
    doctor = [python, "-m", "kronos_runtime", "doctor", "--device", args.device]
    if args.require_accelerator:
        doctor.append("--require-accelerator")
    _run(doctor)
    _run([python, "-m", "kronos_runtime", "smoke", "--device", args.device])
    _run([python, "-m", "pytest", "-q", *OFFLINE_TESTS])

    if args.full:
        _run([python, "-m", "ruff", "check", *RUFF_PATHS])
        _run([python, "-m", "mypy"])
        _run([python, "-m", "compileall", "-q", *RUFF_PATHS[:-1]])
        # The development install already provides the declared build backend.
        # Avoid a second network-dependent bootstrap in local/offline verification;
        # GitHub's package matrix independently proves isolated clean builds.
        _run([python, "-m", "build", "--no-isolation"])
    if args.checkpoint:
        _run([python, "-m", "pytest", "-q", "tests/test_kronos_regression.py"])

    print("\nLocal verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
