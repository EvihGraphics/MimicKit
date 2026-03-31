# Current Training Status Update

Timestamp: `2026-03-31`
Workspace: `/root/Project/MimicKit`

## Summary
**Update (2026-03-31):** After completing environment repairs, training was successfully resumed from `ase_getup_humanoid_sword_shield_l2_resume49` using dual GPUs (`--strict-dual-gpu`). The keepalive configuration was explicitly adjusted (`--llc-target-samples 13107200000`, `--case-budget-hours 0`) to prevent unintended budget timeouts. The `run_ase_7case_keepalive.py` supervisor and `run_ase_dashboard.py` dashboard are both actively running in background `tmux` sessions (`train_ase` and `monitor_ase` respectively).

## Last Active Training Session Details
- **Task**: `ase_getup_humanoid_sword_shield`
- **Location**: `/root/Project/MimicKit/output/train/ase_7case_tmux_20260312_235006/ase_getup_humanoid_sword_shield_l2_resume49/`
- **Final Progress** (recorded prior to recent resume):
  - **Iteration**: 19600
  - **Samples**: 321,142,784
- **Log File Path**: `/root/Project/MimicKit/output/train/ase_7case_tmux_20260312_235006/ase_getup_humanoid_sword_shield_l2_resume49/log.txt`
- **Latest Model Path**: `/root/Project/MimicKit/output/train/ase_7case_tmux_20260312_235006/ase_getup_humanoid_sword_shield_l2_resume49/model.pt`

## Monitoring Methodology
- We are running an interactive `mimickit-ase-dashboard-skill` internally to track the real-time progress toward the 13.1B scale budget.
- Dashboard bound to `http://0.0.0.0:8788/` (accessible locally as `127.0.0.1:8788`), managed by the `monitor_ase` tmux session.
- To view historical metrics, run locally:
  `tensorboard --logdir output/train/ase_7case_tmux_20260312_235006/ase_getup_humanoid_sword_shield_l2_resume49/ --bind_all`
