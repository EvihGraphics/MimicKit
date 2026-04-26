#!/bin/bash
# script: /root/Project/MimicKit/scripts/watchdog_ase_training.sh

export PATH=/root/miniconda3/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

ROOT_DIR="/root/Project/MimicKit"
ROOT_OUT="ase_7case_tmux_20260415_013617"
OUT_DIR="${ROOT_DIR}/output/train/${ROOT_OUT}"
PYTHON_BIN="/root/miniconda3/envs/mimickit/bin/python"
BEST_BY_CASE_TSV="${OUT_DIR}/best_by_case.tsv"
VIZ_INDEX_TSV="${ROOT_DIR}/output/img/${ROOT_OUT}/infer_viz_index.tsv"
IDLE_COUNT_FILE="/tmp/gpu_idle_count.txt"
VIZ_FLAG="/tmp/viz_ase_complete"
WATCHDOG_LOG="/tmp/ase_watchdog.log"
PAUSE_FLAG="/tmp/ase_watchdog.pause"
TRAIN_START_SCRIPT="${ROOT_DIR}/start_train.sh"
DASHBOARD_START_SCRIPT="${ROOT_DIR}/start_dashboard.sh"
BUILD_BEST_CMD="cd ${ROOT_DIR} && ${PYTHON_BIN} scripts/build_best_by_case_from_keepalive.py --root-out ${ROOT_OUT}"
VIZ_CMD="cd ${ROOT_DIR} && ${PYTHON_BIN} tools/ue_bridge/build_mimickit_render_sequences.py --roots ${ROOT_OUT} --frames 300 --frame-stride 5 --device cuda:0 --num-envs 1"

if [ -f "$PAUSE_FLAG" ]; then
    exit 0
fi

# 1. Completion Sequence
if [ -f "$OUT_DIR/current_case.txt" ] && grep -q "COMPLETE" "$OUT_DIR/current_case.txt"; then
    if [ ! -s "$BEST_BY_CASE_TSV" ]; then
        echo "$(date) - Training COMPLETE. Missing best_by_case.tsv; generating from keepalive status..." >> "$WATCHDOG_LOG"
        if ! /bin/bash -lc "$BUILD_BEST_CMD" >> "$WATCHDOG_LOG" 2>&1; then
            echo "$(date) - Failed to generate best_by_case.tsv; will retry on next watchdog tick." >> "$WATCHDOG_LOG"
            exit 0
        fi
    fi

    if [ -f "$VIZ_INDEX_TSV" ] && [ "$(wc -l < "$VIZ_INDEX_TSV")" -gt 1 ]; then
        if [ ! -f "$VIZ_FLAG" ]; then
            echo "$(date) - Visualization index detected; marking viz handoff complete." >> "$WATCHDOG_LOG"
            touch "$VIZ_FLAG"
        fi
        exit 0
    fi

    if /usr/bin/tmux has-session -t viz_ase 2>/dev/null; then
        exit 0
    fi

    rm -f "$VIZ_FLAG"
    echo "$(date) - Training COMPLETE. Spawning visualization tmux session..." >> "$WATCHDOG_LOG"
    if ! /usr/bin/tmux new -s viz_ase -d "$VIZ_CMD"; then
        echo "$(date) - Failed to start viz_ase; will retry on next watchdog tick." >> "$WATCHDOG_LOG"
    fi
    exit 0
fi

# 2. Watchdog Restart & Process Pruning
if ! /usr/bin/tmux has-session -t train_ase 2>/dev/null; then
    echo "$(date) - train_ase session not found. Force cleaning zombies and restarting..." >> "$WATCHDOG_LOG"
    
    pkill -9 -f "run_ase_7case_keepalive" 2>/dev/null
    pkill -9 -f "mimickit/run.py" 2>/dev/null
    echo "0" > "$IDLE_COUNT_FILE"
    
    if ! /bin/bash "$TRAIN_START_SCRIPT" >> "$WATCHDOG_LOG" 2>&1; then
        echo "$(date) - Failed to restart train_ase via ${TRAIN_START_SCRIPT}." >> "$WATCHDOG_LOG"
    fi
fi

if ! /usr/bin/tmux has-session -t monitor_ase 2>/dev/null; then
    echo "$(date) - monitor_ase session not found. Restarting dashboard..." >> "$WATCHDOG_LOG"
    if ! /bin/bash "$DASHBOARD_START_SCRIPT" >> "$WATCHDOG_LOG" 2>&1; then
        echo "$(date) - Failed to restart monitor_ase via ${DASHBOARD_START_SCRIPT}." >> "$WATCHDOG_LOG"
    fi
fi

if ! /usr/bin/tmux has-session -t train_ase 2>/dev/null; then
    exit 0
fi

# 3. GPU Idle Spin and Deadlock Monitoring (Dual GPU)
GPU_UTILS=$(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits)
g0=$(echo "$GPU_UTILS" | sed -n '1p')
g1=$(echo "$GPU_UTILS" | sed -n '2p')

if [ ! -f "$IDLE_COUNT_FILE" ]; then
    echo "0" > "$IDLE_COUNT_FILE"
fi

# Dual-GPU training requires both devices to come alive. If either is 0 for
# 15 watchdog ticks, treat it as a deadlock/zombie and let tmux respawn.
if [ -z "$g0" ] || [ -z "$g1" ] || [ "$g0" -eq 0 ] || [ "$g1" -eq 0 ]; then
    count=$(cat "$IDLE_COUNT_FILE")
    count=$((count + 1))
    echo "$count" > "$IDLE_COUNT_FILE"
    if [ "$count" -ge 15 ]; then
        echo "$(date) - GPU 0 ($g0%) or GPU 1 ($g1%) idle for 15 ticks (15 mins). Deadlock detected, killing train_ase to respawn..." >> "$WATCHDOG_LOG"
        /usr/bin/tmux kill-session -t train_ase 2>/dev/null
        pkill -9 -f "run_ase_7case_keepalive" 2>/dev/null
        pkill -9 -f "mimickit/run.py" 2>/dev/null
        echo "0" > "$IDLE_COUNT_FILE"
    fi
else
    echo "0" > "$IDLE_COUNT_FILE"
fi
