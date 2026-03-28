# ASE Status Checkpoint

Timestamp: `2026-03-29 00:08:20 CST`
Branch: `feat/ase-prework`

## Current State

- `7-case` supervisor root: `/root/Project/MimicKit/output/train/ase_7case_tmux_20260312_235006`
- Active case when training stalled: `ase_getup_humanoid_sword_shield`
- Latest reliable dual-GPU checkpoint:
  - model: `/root/Project/MimicKit/output/train/ase_7case_tmux_20260312_235006/ase_getup_humanoid_sword_shield_l2_resume11/model.pt`
  - log: `/root/Project/MimicKit/output/train/ase_7case_tmux_20260312_235006/ase_getup_humanoid_sword_shield_l2_resume11/log.txt`
- Latest reliable new samples after resume:
  - `Iteration 2200`
  - `Samples 36061184`
- Global dashboard sample count remained stuck at:
  - `3961954304`

## Training Status

- Dual-GPU recovery for `ase_getup_humanoid_sword_shield` repeatedly failed after `resume11`.
- Later keepalive retries (`resume23` and onward) did not produce valid new samples.
- Observed failure modes included:
  - `Segmentation fault (core dumped)` with `rc=139`
  - earlier `NCCL` and Warp CUDA related recovery failures

## Dashboard Status

- Dashboard service itself is healthy.
- WSL-side `nvidia-smi` is broken on this host and can fail with:
  - `cannot apply additional memory protection after relocation: Cannot allocate memory`
- `scripts/run_ase_dashboard.py` now falls back to Windows-side `nvidia-smi.exe`, so the website can still show GPU telemetry.
- After the fallback change, the site should no longer show `GPU 不可用` when the Windows binary is reachable.

## Relevant Logs

- keepalive session log:
  - `/root/Project/MimicKit/output/train/ase_7case_tmux_20260312_235006/session_logs/ase_getup_humanoid_sword_shield.log`
- dashboard log:
  - `/tmp/ase_dashboard_8789.log`

## Handoff Notes

- Next debugging step should focus on making dual-GPU `ase_getup` resume stable again, not on dashboard display.
- Do not treat `3961954304` as live progress unless the current segment log is actively growing.
