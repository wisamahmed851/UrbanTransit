#!/usr/bin/env bash
# Keeps an attached WSL/tmux session active during long Spark workloads.
set -euo pipefail

while true; do
    date -Is >> /tmp/keepalive.log
    sleep 60
done
