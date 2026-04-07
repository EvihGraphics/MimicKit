# 2026-04-08 ASE Dashboard GPU Visibility and Recovery

## Summary
- `ase_heading_humanoid_sword_shield` has been resumed on the existing root:
  `output/train/ase_7case_tmux_20260312_235006`.
- The dual-GPU HLC startup bug was fixed by rebinding the global arg parser in
  spawned workers, so `--llc_model_file` is now visible to every rank.
- The ASE dashboard was cleaned up so GPU visibility no longer depends on a
  stale `/tmp/mk_dualgpu_follow_until_high_*.log`.

## What Was Fixed
- `mimickit/run.py`
  - Rebind `ArgParser.global_parser` inside `run()` so spawned workers can read
    `llc_model_file` and other CLI-only overrides.
- `scripts/run_ase_dashboard.py`
  - Resume chains are aggregated by `base + ordered resume*` segments instead of
    following only `resume_context.tsv` successors.
  - For keepalive-supervised ASE roots, the dashboard no longer auto-binds an
    unrelated historical monitor log from `/tmp`.
  - The server now keeps a live GPU history in memory from fresh `nvidia-smi`
    snapshots, so the page can render current GPU status and GPU history even
    without an external monitor log.
- `scripts/watchdog_ase_training.sh`
  - `monitor_ase` is restarted independently from `train_ase`.
  - The 15-tick deadlock threshold is documented correctly.
  - Visualization handoff retries safely if `viz_ase` fails to launch.
  - Added `/tmp/ase_watchdog.pause` so maintenance can temporarily stop cron
    from fighting manual recovery.

## Current State
- `train_ase` and `monitor_ase` are both running in tmux.
- `keepalive_status.json` now reports `hlc_target_samples = 1310720000`.
- The active heading resume has advanced beyond `39,452,672` aggregate samples.
- The dashboard API returns live dual-GPU data directly and no longer reports
  zero samples for the active heading chain.
