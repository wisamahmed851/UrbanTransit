#!/usr/bin/env bash
# Usage: bash hdfs_scripts/run_phase6_retrain_ab.sh a|b
set -euo pipefail

TASK="${1:?Usage: run_phase6_retrain_ab.sh a|b}"
shift
PROJECT_DIR="/mnt/e/Projects/Techwizz7/UrbanTransit"
VENV_DIR="/home/wisam/venvs/urbantransit"
export HADOOP_HOME="${HADOOP_HOME:-/opt/hadoop-3.4.3}"
export HADOOP_CONF_DIR="${HADOOP_CONF_DIR:-$HADOOP_HOME/etc/hadoop}"
export SPARK_HOME="${SPARK_HOME:-$VENV_DIR/lib/python3.12/site-packages/pyspark}"
export PYSPARK_PYTHON="$VENV_DIR/bin/python"
export PYTHONPATH="$PROJECT_DIR${PYTHONPATH:+:$PYTHONPATH}"
# WSL has 7.8 GB available; use most of it for RF while leaving headroom for HDFS.
export SPARK_DRIVER_MEMORY="${SPARK_DRIVER_MEMORY:-6g}"
export SPARK_SHUFFLE_PARTITIONS="${SPARK_SHUFFLE_PARTITIONS:-32}"

cd "$PROJECT_DIR"
mkdir -p reports/processing_logs
exec "$VENV_DIR/bin/spark-submit" spark_jobs/phase6_retrain_ab_wsl.py --task "$TASK" --trees 80 --depths 6,8 \
  "$@" 2>&1 | tee "reports/processing_logs/phase6_task${TASK^^}_full_rf.log"
