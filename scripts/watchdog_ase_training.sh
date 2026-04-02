#!/bin/bash
# script: /root/Project/MimicKit/scripts/watchdog_ase_training.sh

export PATH=/root/miniconda3/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

if ! /usr/bin/tmux has-session -t train_ase 2>/dev/null; then
    echo "$(date) - train_ase session not found. Starting training and monitor..." >> /tmp/ase_watchdog.log
    
    /usr/bin/tmux new -s train_ase -d "cd /root/Project/MimicKit && conda run -n base python scripts/run_ase_7case_keepalive.py --root-out ase_7case_tmux_20260312_235006 --strict-dual-gpu --llc-target-samples 13107200000 --case-budget-hours 0"
    
    /usr/bin/tmux new -s monitor_ase -d "cd /root/Project/MimicKit && conda run -n base python -u scripts/run_ase_dashboard.py --root-out ase_7case_tmux_20260312_235006 --llc-target-samples 13107200000 --host 0.0.0.0 --port 8788"
fi
