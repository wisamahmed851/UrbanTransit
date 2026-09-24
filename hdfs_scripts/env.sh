#!/usr/bin/env bash
# Shared environment for the HDFS scripts. Sourced, not executed.
export JAVA_HOME="${JAVA_HOME:-/usr/lib/jvm/java-17-openjdk-amd64}"
export HADOOP_HOME="${HADOOP_HOME:-/opt/hadoop}"
export HADOOP_CONF_DIR="$HADOOP_HOME/etc/hadoop"
export PATH="$HADOOP_HOME/bin:$HADOOP_HOME/sbin:$JAVA_HOME/bin:$PATH"
export HDFS_DATA_DIR="${HDFS_DATA_DIR:-$HOME/hadoop_data}"

ensure_sshd() {
    # start-dfs.sh launches daemons over ssh to localhost.
    # Ubuntu 24.04 socket-activates sshd, so test a real connection instead of pgrep.
    if ! ssh -o BatchMode=yes -o ConnectTimeout=5 localhost true 2>/dev/null; then
        echo "Cannot ssh to localhost; run: sudo systemctl enable --now ssh" >&2
        return 1
    fi
}
