#!/bin/sh
set -eu

if ! command -v python3 >/dev/null 2>&1; then
    echo "Python 3 is required." >&2
    exit 1
fi

if ! python3 -c "import flask, pandas, numpy, plotly" >/dev/null 2>&1; then
    echo 'Web UI dependencies are missing.' >&2
    echo 'Install them explicitly with: python -m pip install -e ".[webui]"' >&2
    exit 1
fi

exec python3 run.py
