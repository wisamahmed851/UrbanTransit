#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec /home/wisam/venvs/urbantransit/bin/python "$PROJECT_ROOT/python_pipeline/phase7_python_models.py" "$@"
