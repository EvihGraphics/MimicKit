# ASE New Round Started (2026-04-15)

## New root
- root_out: ase_7case_tmux_20260415_013617
- start_time: 2026-04-15 01:37:42

## Launch actions completed
- Updated launcher root in start_train.sh
- Updated dashboard root in start_dashboard.sh
- Updated watchdog root in scripts/watchdog_ase_training.sh
- Restarted tmux sessions: train_ase, monitor_ase

## Initial verification
- current_case.txt: ase_humanoid
- keepalive_status.json: current_case=ase_humanoid, status=running
- dashboard API root switched to ase_7case_tmux_20260415_013617
- Short GPU sampling shows both GPUs observed activity (GPU1 intermittent during warmup)

## Notes
- watchdog idle threshold remains 15 ticks to avoid warmup false positives.
- Old inference root remains available at output/img/ase_7case_tmux_20260312_235006.
