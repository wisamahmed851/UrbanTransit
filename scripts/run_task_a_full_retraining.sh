#!/usr/bin/env bash
# Reproducible Task A recovery: independent Python + leakage-free Spark MLlib.
# Prerequisites: local_clean Parquet for Python, HDFS /urbantransit/features for Spark,
# and a configured Python environment with the project dependencies.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
SPARK_SUBMIT="${SPARK_SUBMIT:-spark-submit}"
VERSION="${VERSION:-full_v3}"

cd "$ROOT"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p reports/processing_logs

test -d python_pipeline/local_clean || {
  echo "Missing python_pipeline/local_clean. Stage the cleaned Parquet before running." >&2
  exit 2
}
command -v hdfs >/dev/null || { echo "HDFS client is required for the Spark run." >&2; exit 2; }
hdfs dfs -test -d /urbantransit/features/trip_features || {
  echo "Missing HDFS /urbantransit/features/trip_features." >&2
  exit 2
}

echo "[1/2] Python Task A: full chronological training split; strictly-prior history only"
"$PYTHON_BIN" python_pipeline/phase7_python_models.py \
  --task a --enhanced-delay --full-train --version "$VERSION" \
  2>&1 | tee "reports/processing_logs/taskA_python_${VERSION}.log"

echo "[2/2] Spark Task A: full chronological training split; occupancy_pct explicitly excluded"
"$SPARK_SUBMIT" spark_jobs/phase6_retrain_ab_wsl.py \
  --task a --trees 200 --depths 8,10,12 --enhanced --weight-power 0.5 \
  --run-name "clean_${VERSION}" \
  2>&1 | tee "reports/processing_logs/taskA_spark_clean_${VERSION}.log"

echo "Completed. Compare the new untouched-test JSON metrics before changing config/serving.yaml."
