# Task A retraining handoff

Use this guide on a separate Linux/WSL machine to produce new, independently
evaluated Task A (delay-severity) candidates. The runner deliberately retrains
only Task A. Task B already meets the SRS through test accuracy; Task C beats its
baseline; Task D is valid clustering evidence.

## What this run does

`scripts/run_task_a_full_retraining.sh` runs two pipelines sequentially:

1. **Python / Phase 7:** Logistic Regression, Random Forest and XGBoost using the
   complete chronological training split and strictly prior route-hour delay
   features.
2. **Spark / Phase 6:** class-weighted Random Forest with validation-only depth
   selection. `occupancy_pct` is explicitly excluded because it is known only
   after a trip has run.

Validation chooses a candidate; the July-August 2026 test split is evaluated
only after that choice. This produces valid evidence, but no hardware or script
can guarantee an SRS score: the task may remain limited by class imbalance and
the predictive signal in the labels.

## Source-machine export

Copy the project source tree, excluding `node_modules`, virtual environments,
and old model binaries unless you want them for comparison. Do not copy `.env`;
create it from `.env.example` on the new device.

The Python pipeline also needs its independently staged clean data:

```bash
# Copy this directory with the project archive or external drive.
python_pipeline/local_clean/
```

The Spark pipeline needs these HDFS feature directories. On the source machine:

```bash
mkdir -p portable_hdfs_features
hdfs dfs -get /urbantransit/features/trip_features portable_hdfs_features/
hdfs dfs -get /urbantransit/features/route_features portable_hdfs_features/
```

Copy `portable_hdfs_features/` with the project. The necessary Python input
folders are `trips`, `passenger_counts`, `delays`, `vehicles`, `routes`, and
`schedules` below `python_pipeline/local_clean/`.

## New-machine setup

The recommended baseline is Linux or WSL Ubuntu with Java 17, Hadoop/HDFS,
Spark 4.2, Python 3.12, 16 GB or more system RAM, and ample temporary disk.
The available 1.5 GB GPU is not used by Spark MLlib Random Forest and is too
small to rely on for full-data GPU training; the runner uses CPU cores safely.

```bash
cd UrbanTransit
python3.12 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

Configure `.env` for that device's HDFS URI, Hadoop/Spark paths, and local
Spark temporary directory. Start HDFS, then restore the copied feature folders:

```bash
hdfs dfs -mkdir -p /urbantransit/features
hdfs dfs -put -f portable_hdfs_features/trip_features /urbantransit/features/
hdfs dfs -put -f portable_hdfs_features/route_features /urbantransit/features/

hdfs dfs -test -d /urbantransit/features/trip_features
hdfs dfs -test -d /urbantransit/features/route_features
```

## Single execution command

Run this from the repository root. It keeps output names versioned and does
not overwrite the existing served `v1` files.

```bash
PYTHON_BIN="$PWD/.venv/bin/python" \
SPARK_SUBMIT="$PWD/.venv/bin/spark-submit" \
VERSION=full_v3 \
bash scripts/run_task_a_full_retraining.sh
```

The two jobs run sequentially. On a CPU-focused machine, allow several hours;
the Spark stage is normally the slower one. Keep the terminal or tmux session
running until the script prints `Completed`.

## Files to send back after completion

Send these small evidence files and the final log sections, not the large model
binaries initially:

```bash
ls -lh models/python/metrics/*full_v3*.json
ls -lh models/spark/metrics/*clean_full_v3*.json
tail -80 reports/processing_logs/taskA_python_full_v3.log
tail -80 reports/processing_logs/taskA_spark_clean_full_v3.log
```

Also provide the contents of the new Python and Spark metrics JSON files. If a
candidate is both valid and better on the untouched test split, its model and
preprocessor folders can then be copied back under `models/` for a separate
serving-config review. Do not change `config/serving.yaml` before that review.
