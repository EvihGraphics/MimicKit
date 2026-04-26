#!/bin/bash
set -euo pipefail

cd /root/Project/MimicKit
tmux new-session -d -s monitor_ase "/root/miniconda3/envs/mimickit/bin/python scripts/run_ase_dashboard.py \
    --root-out ase_7case_tmux_20260415_013617 \
    --llc-target-samples 13107200000 \
    --hlc-target-samples 1310720000 \
    --host 0.0.0.0 --port 8788"
