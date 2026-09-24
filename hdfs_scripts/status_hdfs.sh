#!/usr/bin/env bash
# Show HDFS daemon status and a short cluster report.
set -uo pipefail
source "$(dirname "$0")/env.sh"

echo "== Java processes =="
jps | grep -Ev '^[0-9]+ Jps$' || echo "(none)"

echo "== HDFS report =="
if hdfs dfsadmin -report 2>/dev/null | head -n 12; then
    exit 0
else
    echo "HDFS is not running."
    exit 1
fi
