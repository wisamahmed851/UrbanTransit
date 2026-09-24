#!/usr/bin/env bash
# Stop single-node HDFS.
set -euo pipefail
source "$(dirname "$0")/env.sh"

ensure_sshd
stop-dfs.sh
echo "HDFS stopped."
