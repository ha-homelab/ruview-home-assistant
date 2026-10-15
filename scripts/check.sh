#!/bin/sh
# SPDX-License-Identifier: MIT
set -eu
cd "$(dirname "$0")/.."
if [ -z "${RUVIEW_PYTHON:-}" ]; then
    if [ -x .venv/bin/python3 ]; then
        RUVIEW_PYTHON=.venv/bin/python3
    else
        RUVIEW_PYTHON=python3
    fi
fi
PYTHONPATH="$(pwd)/src"
export PYTHONPATH
export PYTHONHASHSEED=0
export PYTHONDONTWRITEBYTECODE=1
"$RUVIEW_PYTHON" -m ruff check src tests scripts/build_release.py scripts/run_tests.py scripts/validate_repository.py
"$RUVIEW_PYTHON" -m ruff format --check src tests scripts/build_release.py scripts/run_tests.py scripts/validate_repository.py
"$RUVIEW_PYTHON" scripts/run_tests.py
"$RUVIEW_PYTHON" scripts/validate_repository.py
