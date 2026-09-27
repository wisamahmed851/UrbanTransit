#!/usr/bin/env bash
# Phase 7 only: stage clean HDFS Parquet locally for pandas/PyArrow.
# This script deliberately does not call Spark or read /urbantransit/features.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$PROJECT_ROOT/hdfs_scripts/env.sh"
DESTINATION="${1:-$PROJECT_ROOT/python_pipeline/local_clean}"
# Tickets are required for the independent stop × time-period demand forecast. They
# record real smart-card tap-ins; passenger_counts only identifies a trip's peak load.
TABLES=(trips passenger_counts delays vehicles routes route_stops schedules service_calendar tickets)

mkdir -p "$DESTINATION"
for table in "${TABLES[@]}"; do
  rm -rf "$DESTINATION/$table"
  hdfs dfs -copyToLocal "/urbantransit/clean/$table" "$DESTINATION/$table"
done

echo "Staged cleaned HDFS Parquet to $DESTINATION"
