#!/bin/bash
set -euo pipefail

cd /root/Project/MimicKit
tmux new-session -d -s train_ase "/root/miniconda3/envs/mimickit/bin/python scripts/run_ase_7case_keepalive.py \
    --root-out ase_7case_tmux_20260415_013617 \
    --llc-target-samples 13107200000 \
    --hlc-target-samples 1310720000 \
    --case-budget-hours 0 \
    --primary-num-envs 2048 \
    --fallback-num-envs 1024,512 \
    --strict-dual-gpu"
