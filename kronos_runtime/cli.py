"""Command-line diagnostics and performance probes for a local Kronos checkout."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch

from model import Kronos, KronosPredictor, KronosTokenizer, get_released_model

from .device import device_report, resolve_device


def _write_report(report: dict[str, Any], output: Path | None) -> None:
    encoded = json.dumps(report, indent=2, sort_keys=True)
    print(encoded)
    if output is not None:
        output = output.expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x", encoding="utf-8") as handle:
            handle.write(encoded + "\n")


def _synchronize(device: torch.device) -> None:
    if device.type == "cuda":
        torch.cuda.synchronize(device)
    elif device.type == "mps" and hasattr(torch, "mps"):
        torch.mps.synchronize()


def _market_frame(
    context: int, horizon: int
) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    all_times = pd.Series(
        pd.date_range("2024-01-01", periods=context + horizon, freq="h", tz="UTC")
    )
    phase = np.arange(context, dtype=np.float32)
    midpoint = 100.0 + phase * 0.02 + np.sin(phase / 8.0).astype(np.float32)
    open_price = midpoint - 0.05
    close_price = midpoint + 0.05
    frame = pd.DataFrame(
        {
            "open": open_price,
            "high": np.maximum(open_price, close_price) + 0.2,
            "low": np.minimum(open_price, close_price) - 0.2,
            "close": close_price,
            "volume": 1000.0 + phase,
            "amount": (1000.0 + phase) * midpoint,
        }
    )
    return frame, all_times.iloc[:context].reset_index(drop=True), all_times


def _predict_once(
    predictor: KronosPredictor,
    frame: pd.DataFrame,
    historical_times: pd.Series,
    all_times: pd.Series,
    horizon: int,
    samples: int,
    seed: int,
) -> None:
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    future_times = all_times.iloc[
        len(historical_times) : len(historical_times) + horizon
    ].reset_index(drop=True)
    result = predictor.predict(
        frame,
        historical_times,
        future_times,
        pred_len=horizon,
        T=1.0,
        top_k=1,
        top_p=1.0,
        sample_count=samples,
        verbose=False,
    )
    if result.shape != (horizon, 6):
        raise RuntimeError(f"unexpected benchmark output shape: {result.shape}")
    if not np.isfinite(result.to_numpy(dtype=float)).all():
        raise RuntimeError("benchmark output contains a non-finite value")


def _doctor(args: argparse.Namespace) -> int:
    report = device_report(args.device)
    _write_report(report, args.output)
    if args.require_accelerator and not report["accelerated"]:
        print("No supported accelerator was selected.", file=sys.stderr)
        return 2
    return 0


def _smoke(args: argparse.Namespace) -> int:
    device = resolve_device(args.device)
    torch.manual_seed(args.seed)
    tokenizer = KronosTokenizer(
        d_in=6,
        d_model=16,
        n_heads=2,
        ff_dim=32,
        n_enc_layers=2,
        n_dec_layers=2,
        ffn_dropout_p=0.1,
        attn_dropout_p=0.1,
        resid_dropout_p=0.1,
        s1_bits=4,
        s2_bits=4,
        beta=0.1,
        gamma0=0.1,
        gamma=0.1,
        zeta=0.1,
        group_size=4,
    )
    model = Kronos(
        s1_bits=4,
        s2_bits=4,
        n_layers=2,
        d_model=16,
        n_heads=2,
        ff_dim=32,
        ffn_dropout_p=0.1,
        attn_dropout_p=0.1,
        resid_dropout_p=0.1,
        token_dropout_p=0.1,
        learn_te=False,
    )
    predictor = KronosPredictor(model, tokenizer, device=str(device), max_context=32)
    frame, historical_times, all_times = _market_frame(16, 2)
    _synchronize(device)
    started = time.perf_counter()
    _predict_once(
        predictor,
        frame,
        historical_times,
        all_times,
        horizon=2,
        samples=1,
        seed=args.seed,
    )
    _synchronize(device)
    report = device_report(str(device))
    report.update(
        {
            "smoke_passed": True,
            "smoke_seconds": time.perf_counter() - started,
            "model_eval_mode": not predictor.model.training,
            "tokenizer_eval_mode": not predictor.tokenizer.training,
        }
    )
    _write_report(report, args.output)
    return 0


def _benchmark(args: argparse.Namespace) -> int:
    definition = get_released_model(args.model)
    if args.context > definition.context_length:
        raise ValueError(
            f"context {args.context} exceeds {definition.key} limit "
            f"{definition.context_length}"
        )
    if args.horizon > 512:
        raise ValueError("horizon must not exceed 512")
    if args.samples > 20:
        raise ValueError("samples must not exceed 20")
    if args.runs > 20:
        raise ValueError("runs must not exceed 20")
    device = resolve_device(args.device)
    load_started = time.perf_counter()
    tokenizer = KronosTokenizer.from_pretrained(
        definition.tokenizer_id,
        revision=definition.tokenizer_revision,
    )
    model = Kronos.from_pretrained(
        definition.model_id,
        revision=definition.model_revision,
    )
    predictor = KronosPredictor(
        model,
        tokenizer,
        device=str(device),
        max_context=definition.context_length,
        model_version=definition.model_id,
        model_revision=definition.model_revision,
        tokenizer_revision=definition.tokenizer_revision,
    )
    _synchronize(device)
    load_seconds = time.perf_counter() - load_started
    frame, historical_times, all_times = _market_frame(args.context, args.horizon)

    for _ in range(args.warmups):
        _predict_once(
            predictor,
            frame,
            historical_times,
            all_times,
            args.horizon,
            args.samples,
            args.seed,
        )
    _synchronize(device)
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats(device)

    durations: list[float] = []
    for run in range(args.runs):
        _synchronize(device)
        started = time.perf_counter()
        _predict_once(
            predictor,
            frame,
            historical_times,
            all_times,
            args.horizon,
            args.samples,
            args.seed + run,
        )
        _synchronize(device)
        durations.append(time.perf_counter() - started)

    median_seconds = statistics.median(durations)
    report = device_report(str(device))
    report.update(
        {
            "benchmark_kind": "operational synthetic-input latency; not market evidence",
            "model_key": definition.key,
            "model_id": definition.model_id,
            "model_revision": definition.model_revision,
            "tokenizer_id": definition.tokenizer_id,
            "tokenizer_revision": definition.tokenizer_revision,
            "context": args.context,
            "horizon": args.horizon,
            "sample_count": args.samples,
            "warmups": args.warmups,
            "runs": args.runs,
            "load_seconds": load_seconds,
            "run_seconds": durations,
            "median_seconds": median_seconds,
            "generated_path_steps_per_second": (
                args.horizon * args.samples / median_seconds
            ),
            "peak_gpu_memory_bytes": (
                torch.cuda.max_memory_allocated(device) if device.type == "cuda" else None
            ),
            "model_eval_mode": not predictor.model.training,
            "tokenizer_eval_mode": not predictor.tokenizer.training,
        }
    )
    _write_report(report, args.output)
    return 0


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be at least 1")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kronos-runtime",
        description="Inspect and benchmark a local Kronos installation.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor", help="Report runtime and accelerator status")
    doctor.add_argument("--device", default="auto")
    doctor.add_argument("--require-accelerator", action="store_true")
    doctor.add_argument("--output", type=Path)
    doctor.set_defaults(handler=_doctor)

    smoke = subparsers.add_parser("smoke", help="Run offline end-to-end tiny-model inference")
    smoke.add_argument("--device", default="auto")
    smoke.add_argument("--seed", type=int, default=123)
    smoke.add_argument("--output", type=Path)
    smoke.set_defaults(handler=_smoke)

    benchmark = subparsers.add_parser(
        "benchmark", help="Benchmark one exact released checkpoint"
    )
    benchmark.add_argument(
        "--model",
        choices=("kronos-mini", "kronos-small", "kronos-base"),
        default="kronos-small",
    )
    benchmark.add_argument("--device", default="auto")
    benchmark.add_argument("--context", type=_positive_int, default=128)
    benchmark.add_argument("--horizon", type=_positive_int, default=8)
    benchmark.add_argument("--samples", type=_positive_int, default=1)
    benchmark.add_argument("--warmups", type=int, choices=range(0, 11), default=1)
    benchmark.add_argument("--runs", type=_positive_int, default=3)
    benchmark.add_argument("--seed", type=int, default=123)
    benchmark.add_argument("--output", type=Path)
    benchmark.set_defaults(handler=_benchmark)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
