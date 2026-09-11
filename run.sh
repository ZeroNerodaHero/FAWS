#!/usr/bin/env bash
# Run FAWS. Creates the venv and installs deps the first time; after that just launches.
#   ./run.sh                              default example project
#   ./run.sh examples/pinwheel.faws.json  any project file
set -euo pipefail

cd "$(dirname "$0")"

PY=.venv/bin/python

if [ ! -x "$PY" ]; then
    echo "creating .venv ..."
    python3 -m venv .venv
fi

if ! "$PY" -c "import PySide6" 2>/dev/null; then
    echo "installing requirements ..."
    "$PY" -m pip install --quiet -r requirements.txt
fi

exec "$PY" -m app.main "$@"
