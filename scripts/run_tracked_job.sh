#!/usr/bin/env bash
# Run any Spark/loader command while exposing its genuine lifecycle in /admin/jobs.
# Usage: bash scripts/run_tracked_job.sh <job-name> <log-path> -- <command> [arguments...]
set -euo pipefail

if [[ $# -lt 4 || "$3" != "--" ]]; then
  echo "Usage: $0 <job-name> <log-path> -- <command> [arguments...]" >&2
  exit 2
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NAME="$1"
LOG_PATH="$2"
shift 3
cd "$ROOT"
mkdir -p "$(dirname "$LOG_PATH")"
PYTHON_BIN="${PYTHON_BIN:-python}"

JOB_ID="$("$PYTHON_BIN" database/job_monitor.py start --name "$NAME" --log "$LOG_PATH")"
finish() {
  local exit_code="$1"
  local status="success"
  [[ "$exit_code" -eq 0 ]] || status="failed"
  "$PYTHON_BIN" database/job_monitor.py finish --id "$JOB_ID" --status "$status" || true
  exit "$exit_code"
}
trap 'finish $?' EXIT

"$@" >"$LOG_PATH" 2>&1
