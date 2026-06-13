#!/bin/bash
set -euo pipefail

export PATH=/root/miniconda3/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

ROOT_DIR="/root/Project/MimicKit"
AMP_TRAIN_SESSION="${AMP_TRAIN_SESSION:-train_amp}"
AMP_DASH_SESSION="${AMP_DASH_SESSION:-monitor_amp}"
AMP_WATCHDOG_LOG="${AMP_WATCHDOG_LOG:-/tmp/amp_watchdog.log}"
AMP_PAUSE_FLAG="${AMP_PAUSE_FLAG:-/tmp/amp_watchdog.pause}"
AMP_TRAIN_CMD="${AMP_TRAIN_CMD:-}"
AMP_DASHBOARD_CMD="${AMP_DASHBOARD_CMD:-}"
AMP_IDLE_COUNT_FILE="${AMP_IDLE_COUNT_FILE:-/tmp/amp_gpu_idle_count.txt}"
AMP_IDLE_LIMIT="${AMP_IDLE_LIMIT:-0}"
AMP_REQUIRE_DUAL="${AMP_REQUIRE_DUAL:-1}"

if [ -f "$AMP_PAUSE_FLAG" ]; then
    exit 0
fi

timestamp() {
    date '+%Y-%m-%d %H:%M:%S'
}

log() {
    echo "$(timestamp) - $*" >> "$AMP_WATCHDOG_LOG"
}

if [ -z "$AMP_TRAIN_CMD" ]; then
    log "AMP_TRAIN_CMD is empty; watchdog noop."
    exit 0
fi

if ! /usr/bin/tmux has-session -t "$AMP_TRAIN_SESSION" 2>/dev/null; then
    log "session $AMP_TRAIN_SESSION missing; restarting train command."
    /usr/bin/tmux new-session -d -s "$AMP_TRAIN_SESSION" "$AMP_TRAIN_CMD" || log "failed to start $AMP_TRAIN_SESSION"
fi

if [ -n "$AMP_DASHBOARD_CMD" ] && ! /usr/bin/tmux has-session -t "$AMP_DASH_SESSION" 2>/dev/null; then
    log "session $AMP_DASH_SESSION missing; restarting dashboard command."
    /usr/bin/tmux new-session -d -s "$AMP_DASH_SESSION" "$AMP_DASHBOARD_CMD" || log "failed to start $AMP_DASH_SESSION"
fi

if [ "${AMP_IDLE_LIMIT}" -le 0 ]; then
    exit 0
fi

GPU_UTILS="$(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits 2>/dev/null || true)"
g0="$(echo "$GPU_UTILS" | sed -n '1p' | tr -d ' ')"
g1="$(echo "$GPU_UTILS" | sed -n '2p' | tr -d ' ')"

if [ ! -f "$AMP_IDLE_COUNT_FILE" ]; then
    echo "0" > "$AMP_IDLE_COUNT_FILE"
fi

idle="0"
if [ -z "$g0" ] || [ "$g0" = "0" ]; then
    idle="1"
fi
if [ "$AMP_REQUIRE_DUAL" = "1" ] && { [ -z "$g1" ] || [ "$g1" = "0" ]; }; then
    idle="1"
fi

if [ "$idle" = "1" ]; then
    count="$(cat "$AMP_IDLE_COUNT_FILE")"
    count="$((count + 1))"
    echo "$count" > "$AMP_IDLE_COUNT_FILE"
    if [ "$count" -ge "$AMP_IDLE_LIMIT" ]; then
        log "GPU idle limit reached (g0=${g0:-?}, g1=${g1:-?}); restarting $AMP_TRAIN_SESSION."
        /usr/bin/tmux kill-session -t "$AMP_TRAIN_SESSION" 2>/dev/null || true
        echo "0" > "$AMP_IDLE_COUNT_FILE"
    fi
else
    echo "0" > "$AMP_IDLE_COUNT_FILE"
fi
