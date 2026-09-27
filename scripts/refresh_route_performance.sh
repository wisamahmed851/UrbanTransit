#!/usr/bin/env bash
# Rebuild the Phase 5 route-performance output and load only that table into MySQL.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export HADOOP_HOME="${HADOOP_HOME:-/opt/hadoop}"
export PATH="$HADOOP_HOME/bin:$PATH"
export PYTHONPATH=".$(test -n "${PYTHONPATH:-}" && printf ":%s" "$PYTHONPATH")"
PYTHON_BIN="${PYTHON_BIN:-/home/wisam/venvs/urbantransit/bin/python}"

"$PYTHON_BIN" spark_jobs/phase5_analytics.py --only route_performance
MYSQL_HOST="${MYSQL_HOST:-172.17.80.1}" "$PYTHON_BIN" database/load_analytics_to_mysql.py --tables route_performance
