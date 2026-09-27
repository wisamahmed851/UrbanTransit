#!/usr/bin/env bash
# Train the independent Phase 7 numeric occupancy model and record the run in the dashboard.
# Usage: PYTHON_BIN=/home/wisam/venvs/urbantransit/bin/python bash scripts/run_occupancy_forecast.sh [--full-train]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

cd "$ROOT"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
exec bash scripts/run_tracked_job.sh phase7_occupancy_forecast \
  reports/processing_logs/phase7_occupancy_forecast.log -- \
  "$PYTHON_BIN" python_pipeline/phase7_python_models.py --task e "$@"
