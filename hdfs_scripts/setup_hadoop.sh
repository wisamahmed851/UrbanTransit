#!/usr/bin/env bash
# One-time Hadoop setup for the current (non-root) user inside WSL.
# Prerequisites (as root): openjdk-17-jdk-headless, openssh-server, Hadoop extracted to /opt/hadoop.
set -euo pipefail
source "$(dirname "$0")/env.sh"
CONF_SRC="$(cd "$(dirname "$0")" && pwd)/conf"

# 1) Hadoop config
cp "$CONF_SRC/core-site.xml" "$CONF_SRC/hdfs-site.xml" "$HADOOP_CONF_DIR/"
grep -q '^export JAVA_HOME=' "$HADOOP_CONF_DIR/hadoop-env.sh" \
    || echo "export JAVA_HOME=$JAVA_HOME" >> "$HADOOP_CONF_DIR/hadoop-env.sh"
mkdir -p "$HDFS_DATA_DIR"/{namenode,datanode,tmp}

# 2) Passwordless SSH to localhost (start-dfs.sh needs it)
mkdir -p ~/.ssh && chmod 700 ~/.ssh
[ -f ~/.ssh/id_ed25519 ] || ssh-keygen -t ed25519 -N '' -f ~/.ssh/id_ed25519 -q
grep -qf ~/.ssh/id_ed25519.pub ~/.ssh/authorized_keys 2>/dev/null \
    || cat ~/.ssh/id_ed25519.pub >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
ssh-keyscan -H localhost 0.0.0.0 127.0.0.1 >> ~/.ssh/known_hosts 2>/dev/null
ssh -o BatchMode=yes localhost true && echo "SSH to localhost: OK"

# 3) Shell environment
if ! grep -q 'UrbanTransit IQ env' ~/.bashrc; then
    cat >> ~/.bashrc <<EOF

# ---- UrbanTransit IQ env ----
export JAVA_HOME=$JAVA_HOME
export HADOOP_HOME=$HADOOP_HOME
export HADOOP_CONF_DIR=\$HADOOP_HOME/etc/hadoop
export PATH=\$HADOOP_HOME/bin:\$HADOOP_HOME/sbin:\$JAVA_HOME/bin:\$PATH
EOF
fi
echo "Hadoop setup done: $(hadoop version | head -1)"
