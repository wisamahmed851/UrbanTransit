#!/usr/bin/env bash
# Start single-node HDFS (NameNode, DataNode, SecondaryNameNode).
set -euo pipefail
source "$(dirname "$0")/env.sh"

ensure_sshd

if [ ! -d "$HDFS_DATA_DIR/namenode/current" ]; then
    echo "NameNode not formatted yet - formatting $HDFS_DATA_DIR/namenode"
    hdfs namenode -format -nonInteractive -force
fi

start-dfs.sh
hdfs dfsadmin -safemode wait
echo "HDFS started. NameNode UI: http://localhost:9870"
