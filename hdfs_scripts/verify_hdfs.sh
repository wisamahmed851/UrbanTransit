#!/usr/bin/env bash
# Phase 0 check: create a dir, upload a file, list it, read it back, clean up.
# Leaves /urbantransit/verify/spark_input.txt in place for spark_jobs/verify_spark.py.
set -euo pipefail
source "$(dirname "$0")/env.sh"

TEST_DIR=/urbantransit/verify_tmp
LOCAL_FILE=$(mktemp)
EXPECTED="UrbanTransit IQ HDFS check $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "$EXPECTED" > "$LOCAL_FILE"

echo "1) mkdir $TEST_DIR"
hdfs dfs -mkdir -p "$TEST_DIR"

echo "2) upload"
hdfs dfs -put -f "$LOCAL_FILE" "$TEST_DIR/hello.txt"

echo "3) list"
hdfs dfs -ls "$TEST_DIR"

echo "4) read back"
ACTUAL=$(hdfs dfs -cat "$TEST_DIR/hello.txt")
echo "   $ACTUAL"

echo "5) clean up"
hdfs dfs -rm -r -skipTrash "$TEST_DIR" >/dev/null
rm -f "$LOCAL_FILE"

# Persistent input for the Spark-reads-HDFS check
hdfs dfs -mkdir -p /urbantransit/verify
printf 'route_id,stop_id,passengers\nR1,S1,12\nR1,S2,30\nR2,S3,7\n' \
    | hdfs dfs -put -f - /urbantransit/verify/spark_input.txt

if [ "$ACTUAL" = "$EXPECTED" ]; then
    echo "VERIFY_HDFS: PASS"
else
    echo "VERIFY_HDFS: FAIL (content mismatch)"
    exit 1
fi
