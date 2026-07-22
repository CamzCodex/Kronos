#!/usr/bin/env python3
"""Start the local-only Kronos Web UI without mutating the environment."""

from __future__ import annotations

import importlib.util
import sys
import webbrowser

REQUIRED_MODULES = ("flask", "pandas", "numpy", "plotly")


def missing_dependencies() -> list[str]:
    return [name for name in REQUIRED_MODULES if importlib.util.find_spec(name) is None]


def main() -> int:
    missing = missing_dependencies()
    if missing:
        print(f"Missing Web UI dependencies: {', '.join(missing)}")
        print('Install them explicitly with: python -m pip install -e ".[webui]"')
        return 1

    if __package__:
        from .app import app
    else:
        from app import app

    url = "http://127.0.0.1:7070"
    print(f"Starting the local-only Kronos Web UI at {url}")
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
