#!/usr/bin/env bash
# Phase 3 pipeline (one WSL session so HDFS stays up). Logs: reports/processing_logs/.
#   main dataset : profile -> data quality -> evaluation -> cleaning -> rerun cleaning (idempotency) -> reports
#   hidden_like  : upload to its own namespace -> ingest -> profile -> data quality -> cleaning -> evaluation -> readiness report
# The pipeline jobs (profile_data, data_quality, clean_data) are wrapped by no_manifest_guard.py, which makes
# any attempt to open a generator manifest fail - proof that the pipeline does not read it.
# Stop immediately if a guarded Spark stage or its filtered completion check fails.
# Without `-e`, a failed/unfinished stage can let the next phase start concurrently.
set -euo pipefail
cd "$(dirname "$0")/.."
source hdfs_scripts/env.sh
source ~/venvs/urbantransit/bin/activate
# `start-dfs.sh` exits non-zero when daemons already exist; the status check below
# is authoritative and lets the pipeline safely run with a healthy existing HDFS.
bash hdfs_scripts/start_hdfs.sh >/dev/null 2>&1 || true
# Display only; `head` can close early and trigger SIGPIPE in the status script.
bash hdfs_scripts/status_hdfs.sh | head -4 || true
G="python spark_jobs/no_manifest_guard.py"
step() { echo "=== $1 $(date +%H:%M:%S)"; }

MODE=${1:-all}
step guard_selftest   # negative control: the evaluation script DOES read the manifest, so the guard must block it
# Intentional negative-control preview; `head` may produce SIGPIPE after it has shown the proof.
$G spark_jobs/dq_evaluate.py --mode full 2>&1 | grep -E "BLOCKED|no_manifest_guard" | head -3 || true
if [ "$MODE" = all ] || [ "$MODE" = full ]; then
  step profile_full;   $G spark_jobs/profile_data.py --mode full    2>&1 | grep -E "INFO .*wrote|no_manifest_guard|BLOCKED|Error"
  step dq_full;        $G spark_jobs/data_quality.py --mode full    2>&1 | grep -E "INFO DQ done|no_manifest_guard|BLOCKED|Error"
  step evaluate_full;  python spark_jobs/dq_evaluate.py --mode full  2>&1 | grep -E "extra findings"
  step clean_full;     $G spark_jobs/clean_data.py --mode full      2>&1 | grep -E "INFO .*(reconciled|CLEANING)|no_manifest_guard|BLOCKED|Error"
  cp reports/cleaning_metrics_full.json reports/cleaning_metrics_full_run1.json
  step clean_full_rerun; $G spark_jobs/clean_data.py --mode full    2>&1 | grep -E "INFO CLEANING|no_manifest_guard|BLOCKED|Error"
  step idempotency;    python spark_jobs/check_idempotency.py --mode full
  python spark_jobs/cleaning_report.py --mode full
fi
if [ "$MODE" = all ] || [ "$MODE" = hidden ]; then
  step upload_hidden;  bash hdfs_scripts/upload_raw.sh hidden_like > reports/processing_logs/hdfs_upload_hidden_like_$(date +%Y%m%d_%H%M%S).log 2>&1; echo "upload exit=$?"
  step ingest_hidden;  python spark_jobs/ingest_raw.py --mode hidden_like 2>&1 | grep -E "INFO INGESTION|Error"
  step profile_hidden; $G spark_jobs/profile_data.py --mode hidden_like 2>&1 | grep -E "INFO .*wrote|no_manifest_guard|BLOCKED|Error"
  step dq_hidden;      $G spark_jobs/data_quality.py --mode hidden_like 2>&1 | grep -E "INFO DQ done|no_manifest_guard|BLOCKED|Error"
  step clean_hidden;   $G spark_jobs/clean_data.py --mode hidden_like   2>&1 | grep -E "INFO CLEANING|no_manifest_guard|BLOCKED|Error"
  python spark_jobs/cleaning_report.py --mode hidden_like
  step evaluate_hidden; python spark_jobs/dq_evaluate.py --mode hidden_like 2>&1 | grep -E "extra findings"
  step readiness;      python spark_jobs/hidden_readiness.py 2>&1 | grep -E "INFO .*wrote|Error"
fi
step done
