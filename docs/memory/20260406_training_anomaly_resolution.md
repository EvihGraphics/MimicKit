# Training Anomaly & Resolution Archive

Timestamp: `2026-04-06`
Workspace: `/root/Project/MimicKit`

## Incident Summary
- **Issue**: The training for `ase_heading_humanoid_sword_shield` experienced an anomaly. Multiple rogue background processes (`mimickit/run.py` and `run_ase_7case_keepalive.py`) were lingering concurrently, causing overlapping resume sequences (e.g., `resume208`, `resume209`, `resume210`).
- **Symptom 1**: The crontab watchdog (`/tmp/ase_watchdog.log`) was repeatedly attempting to restart `train_ase` because the tmux session was randomly failing, leaving python processes behind.
- **Symptom 2**: The `--strict-dual-gpu` setup catastrophically failed. `nvidia-smi` showed GPU 0 at 99% usage and GPU 1 completely idle (0%).

## Resolution Steps
1. **Pesticide / Process Termination**: 
   - Terminated the broken `train_ase` tmux session: `tmux kill-session -t train_ase`.
   - Force-killed all duplicated supervisor scripts: `pkill -f "run_ase_7case_keepalive.py"`.
   - Force-killed all orphaned worker instances: `pkill -f "mimickit/run.py"`.
2. **Cleanup Verification**: Checked `nvidia-smi` to ensure VRAM on both GPUs dropped back to baseline (no orphaned Python processes holding memory).
3. **Clean Restart**: Executed a fresh detached session:
   ```bash
   tmux new -s train_ase -d "cd /root/Project/MimicKit && conda run -n base python scripts/run_ase_7case_keepalive.py --root-out ase_7case_tmux_20260312_235006 --strict-dual-gpu --llc-target-samples 13107200000 --case-budget-hours 0"
   ```
4. **Post-Flight Check**: Re-ran `nvidia-smi`. The new Python PID (`26992`) is now correctly distributed across both `GPU 0` and `GPU 1`, confirming dual-GPU training is securely re-established.

## Current Status
- **Training Task**: `ase_heading_humanoid_sword_shield`
- **GPU Status**: Dual RTX 4090s correctly active.
- **Watchdog**: Active and monitoring properly.