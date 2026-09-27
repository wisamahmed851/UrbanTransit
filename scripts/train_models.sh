#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "=== Ensuring HDFS is running ==="
bash hdfs_scripts/start_hdfs.sh

echo "=== Training Spark models ==="
bash scripts/run_tracked_job.sh phase6_spark_models reports/processing_logs/phase6_spark.log -- python spark_jobs/phase6_spark_models.py

echo "=== Training Python models ==="
bash scripts/run_tracked_job.sh phase7_python_models reports/processing_logs/phase7_python.log -- python python_pipeline/phase7_python_models.py --task all --enhanced-delay --full-train

echo "=== Evaluating and loading models ==="
bash scripts/run_tracked_job.sh evaluate_saved_models reports/processing_logs/evaluate.log -- python database/evaluate_saved_models.py
bash scripts/run_tracked_job.sh load_model_outputs reports/processing_logs/load_model.log -- python database/load_model_outputs.py
