#!/usr/bin/env bash
# Phase 7 only: stage clean HDFS Parquet locally for pandas/PyArrow.
# This script deliberately does not call Spark or read /urbantransit/features.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$PROJECT_ROOT/hdfs_scripts/env.sh"
DESTINATION="${1:-$PROJECT_ROOT/python_pipeline/local_clean}"
TABLES=(trips passenger_counts delays vehicles routes route_stops schedules service_calendar)

mkdir -p "$DESTINATION"
for table in "${TABLES[@]}"; do
  rm -rf "$DESTINATION/$table"
  hdfs dfs -copyToLocal "/urbantransit/clean/$table" "$DESTINATION/$table"
done

echo "Staged cleaned HDFS Parquet to $DESTINATION"
