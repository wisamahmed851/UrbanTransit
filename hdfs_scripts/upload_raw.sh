#!/usr/bin/env bash
# Upload a generated dataset to HDFS and verify it.
#
# Layout (full mode):            (other modes use /urbantransit_<mode>/...)
#   /urbantransit/raw/<table>/        raw CSV / JSON / JSON Lines files, exactly as generated
#   /urbantransit/parquet/<table>/    Parquet written by spark_jobs/ingest_raw.py
#   /urbantransit/quarantine/<table>/ rows that failed type parsing (written by Spark)
#
# Verification per table: number of files, data rows (lines minus one header per CSV file)
# and bytes must be identical locally and in HDFS; rows are counted by reading the files
# back out of HDFS (hdfs dfs -cat), not from metadata.
#
# Usage: bash hdfs_scripts/upload_raw.sh [full|sample|hidden_like]
set -euo pipefail
source "$(dirname "$0")/env.sh"
MODE="${1:-full}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
LOCAL="$REPO/raw_data/$MODE"
BASE=/urbantransit; [ "$MODE" != "full" ] && BASE="/urbantransit_$MODE"
TABLES="stops routes route_stops service_calendar schedules vehicles passengers trips passenger_counts tickets delays gps_events"

[ -d "$LOCAL" ] || { echo "No local data at $LOCAL - run the generator first"; exit 1; }
hdfs dfs -test -d / || { echo "HDFS is not running - run hdfs_scripts/start_hdfs.sh"; exit 1; }

echo "== 1) layout under $BASE"
hdfs dfs -mkdir -p "$BASE/raw" "$BASE/parquet" "$BASE/quarantine"

echo "== 2) upload (overwrite)"
start=$(date +%s)
for t in $TABLES; do
    hdfs dfs -rm -r -f -skipTrash "$BASE/raw/$t" >/dev/null 2>&1 || true
    hdfs dfs -mkdir -p "$BASE/raw/$t"
    hdfs dfs -put -f "$LOCAL/$t"/* "$BASE/raw/$t/"
    echo "   $t: $(ls "$LOCAL/$t" | wc -l) file(s) uploaded"
done
echo "   upload took $(( $(date +%s) - start )) s"

echo "== 3) listing"
hdfs dfs -ls -R "$BASE/raw" | awk '{print $5, $8}' | sed "s#$BASE/raw/##" | column -t | head -80

echo "== 4) verification (local vs HDFS)"
printf "%-17s %6s %6s %12s %12s %14s %14s %s\n" table l_files h_files local_rows hdfs_rows local_bytes hdfs_bytes status
all_ok=1
for t in $TABLES; do
    lf=$(ls "$LOCAL/$t" | wc -l)
    hf=$(hdfs dfs -count "$BASE/raw/$t" | awk '{print $2}')
    lb=$(du -cb "$LOCAL/$t"/* | tail -1 | cut -f1)
    hb=$(hdfs dfs -du -s "$BASE/raw/$t" | awk '{print $1}')
    if [ "$t" = "service_calendar" ]; then           # one JSON array: count objects, not lines
        lr=$(python3 -c "import json,sys;print(len(json.load(open(sys.argv[1]))))" "$LOCAL/$t/service_calendar.json")
        hr=$(hdfs dfs -cat "$BASE/raw/$t/service_calendar.json" | python3 -c "import json,sys;print(len(json.load(sys.stdin)))")
    elif [ "$t" = "gps_events" ]; then               # JSON Lines: one record per line, no header
        lr=$(cat "$LOCAL/$t"/* | wc -l)
        hr=$(hdfs dfs -cat "$BASE/raw/$t/*" | wc -l)
    else                                             # CSV: lines minus one header per file
        lr=$(( $(cat "$LOCAL/$t"/* | wc -l) - lf ))
        hr=$(( $(hdfs dfs -cat "$BASE/raw/$t/*" | wc -l) - hf ))
    fi
    st=OK; { [ "$lf" = "$hf" ] && [ "$lr" = "$hr" ] && [ "$lb" = "$hb" ]; } || { st=MISMATCH; all_ok=0; }
    printf "%-17s %6s %6s %12s %12s %14s %14s %s\n" "$t" "$lf" "$hf" "$lr" "$hr" "$lb" "$hb" "$st"
done
hdfs dfs -du -s -h "$BASE/raw"
[ "$all_ok" = 1 ] && echo "UPLOAD_VERIFY: PASS" || { echo "UPLOAD_VERIFY: FAIL"; exit 1; }
