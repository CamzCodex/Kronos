#!/usr/bin/env python3
"""Start the local-only Kronos Web UI without mutating the environment."""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys
import webbrowser
from collections.abc import Sequence
from pathlib import Path

REQUIRED_MODULES = ("flask", "pandas", "numpy", "plotly")


def missing_dependencies() -> list[str]:
    return [name for name in REQUIRED_MODULES if importlib.util.find_spec(name) is None]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Start the loopback-only Kronos Web UI")
    parser.add_argument(
        "--data-dir",
        type=Path,
        help="Directory containing local CSV inputs (defaults to repository data/)",
    )
    parser.add_argument("--no-browser", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    missing = missing_dependencies()
    if missing:
        print(f"Missing Web UI dependencies: {', '.join(missing)}")
        print('Install them explicitly with: python -m pip install -e ".[webui]"')
        return 1

    if args.data_dir is not None:
        data_dir = args.data_dir.expanduser().resolve()
        if not data_dir.is_dir():
            print(f"Data directory does not exist or is not a directory: {data_dir}")
            return 2
        os.environ["KRONOS_DATA_DIR"] = str(data_dir)

    if __package__:
        from .app import app
    else:
        from app import app

    url = "http://127.0.0.1:7070"
    print(f"Starting the local-only Kronos Web UI at {url}")
    if not args.no_browser:
        webbrowser.open(url)
    app.run(
        debug=False,
        use_reloader=False,
        host="127.0.0.1",
        port=7070,
        threaded=False,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
