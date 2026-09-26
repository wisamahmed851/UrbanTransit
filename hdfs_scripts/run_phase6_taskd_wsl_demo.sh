#!/usr/bin/env bash
# Reproducible launcher for the Phase 6 Task D WSL/HDFS demo.
set -euo pipefail

PROJECT_DIR="/mnt/e/Projects/Techwizz7/UrbanTransit"
VENV_DIR="/home/wisam/venvs/urbantransit"

export HADOOP_HOME="${HADOOP_HOME:-/opt/hadoop-3.4.3}"
export HADOOP_CONF_DIR="${HADOOP_CONF_DIR:-$HADOOP_HOME/etc/hadoop}"
export SPARK_HOME="${SPARK_HOME:-$VENV_DIR/lib/python3.12/site-packages/pyspark}"
export PYSPARK_PYTHON="$VENV_DIR/bin/python"
export PYTHONPATH="$PROJECT_DIR${PYTHONPATH:+:$PYTHONPATH}"

cd "$PROJECT_DIR"
mkdir -p reports/processing_logs
"$VENV_DIR/bin/spark-submit" spark_jobs/phase6_taskD_wsl_demo.py \
  2>&1 | tee reports/processing_logs/phase6_taskD_wsl.log
