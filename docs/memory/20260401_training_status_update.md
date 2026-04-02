# Current Training Status Update

Timestamp: `2026-04-01`
Workspace: `/root/Project/MimicKit`

## Summary
**Update (2026-04-01):** The `ase_getup_humanoid_sword_shield` training was safely resumed under `ase_getup_humanoid_sword_shield_l2_resume52`. The dual GPUs are fully utilized via `--strict-dual-gpu`. Both the training supervisor (`train_ase`) and the ASE pretraining dashboard (`monitor_ase`) are alive in background `tmux` sessions. 

The budget was set explicitly (`--llc-target-samples 13107200000`, `--case-budget-hours 0`) to avoid unintentional time-based limits. 

## Last Active Training Session Details
- **Task**: `ase_getup_humanoid_sword_shield`
- **Location**: `/root/Project/MimicKit/output/train/ase_7case_tmux_20260312_235006/ase_getup_humanoid_sword_shield_l2_resume52/`
- **Log File Path**: `/root/Project/MimicKit/output/train/ase_7case_tmux_20260312_235006/ase_getup_humanoid_sword_shield_l2_resume52/log.txt`
- **Latest Model Path**: `/root/Project/MimicKit/output/train/ase_7case_tmux_20260312_235006/ase_getup_humanoid_sword_shield_l2_resume52/model.pt`

## Monitoring Methodology
The specialized ASE dashboard bounds to `http://0.0.0.0:8788/` locally. Read logs from tmux or access it on `http://127.0.0.1:8788`.

To view historical metrics, run locally:
```bash
tensorboard --logdir output/train/ase_7case_tmux_20260312_235006/ase_getup_humanoid_sword_shield_l2_resume52/ --bind_all
```

## How to Resume If Interrupted

If the training encounters a system fault, crash, or SSH closes unexpectedly and the `tmux` sessions are killed, use these precise scripts to restart. The `run_ase_7case_keepalive.py` logic automatically detects the latest checkpoint and increments the resume count (e.g., to `resume53`).

**Step 1: Restart Training Keepalive**
```bash
tmux new -s train_ase -d "python scripts/run_ase_7case_keepalive.py --root-out ase_7case_tmux_20260312_235006 --strict-dual-gpu --llc-target-samples 13107200000 --case-budget-hours 0"
```

**Step 2: Restart the Dashboard**
```bash
tmux new -s monitor_ase -d "python -u scripts/run_ase_dashboard.py --root-out ase_7case_tmux_20260312_235006 --llc-target-samples 13107200000 --host 0.0.0.0 --port 8788"
```

## Automated Watchdog
To prevent accidental interrupts, a watchdog script was installed at `/root/Project/MimicKit/scripts/watchdog_ase_training.sh`. It checks if `train_ase` and `monitor_ase` are alive, and restarts them automatically. Using `crontab -e` with `* * * * * /bin/bash /root/Project/MimicKit/scripts/watchdog_ase_training.sh` guarantees rapid resume even on hardware reboots.
