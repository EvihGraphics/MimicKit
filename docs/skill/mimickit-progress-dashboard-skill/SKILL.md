---
name: mimickit-progress-dashboard
description: Start and use a local web dashboard for MimicKit longcycle/e2e training progress, GPU dual-card utilization, current case attempts, and recent runner/monitor log events.
---

# MimicKit Progress Dashboard

## Goal

Provide a single web page for:
- current pipeline progress (`progress.json`)
- current case attempt state (`runs/<case>/attempts.json`)
- dual-GPU utilization snapshot and recent trend
- recent runner and monitor log tails

This avoids repeated manual terminal polling.

If you are monitoring a single ASE pretraining run rather than longcycle/e2e orchestration, prefer:

- `docs/skill/mimickit-ase-dashboard-skill/SKILL.md`

## Entry Script

- `scripts/run_progress_dashboard.py`

No extra Python dependencies are required (stdlib only).

## Quick Start

```bash
source /root/miniconda3/etc/profile.d/conda.sh
conda activate mimickit
cd /root/Project/MimicKit

python -u scripts/run_progress_dashboard.py \
  --root-out case_ultralong_alloc_full_20260219_154546 \
  --host 0.0.0.0 \
  --port 8787
```

Open:
- local: `http://127.0.0.1:8787/`
- remote via SSH tunnel: `ssh -L 8787:127.0.0.1:8787 <host>`

## Root Switching

You can switch run root in either way:

1. Web input box: enter `root-out` then click `切换 Root`.
2. URL query:

```text
http://127.0.0.1:8787/?root=case_ultralong_alloc_full_20260219_154546
```

If `root` is empty, the script auto-picks latest folder under `output/train/`.

## Useful Options

```bash
python scripts/run_progress_dashboard.py --help
```

Key options:
- `--root-out`: root name or path (optional)
- `--monitor-log`: force a monitor log path (optional)
- `--history-size`: monitor history points returned to page
- `--host`, `--port`: bind address

## Health Semantics

Dashboard health labels:
- `双卡高利用率`: both GPUs are currently `>=60%`
- `双卡负载不均`: recent window shows large imbalance
- `疑似通信异常`: current attempt note includes `long_nccl`
- `利用率偏低`: currently below target

## Operational Notes

- The page is read-only; it does not kill or edit training jobs.
- Runner log is typically `/tmp/<root-out>.log`.
- Monitor log auto-detection prioritizes:
  - `/tmp/mk_dualgpu_follow_until_high_*.log`
  - `/tmp/mk_ultralong_alloc_monitor_*.log`
  - `/tmp/mk_longcycle_monitor_*.log`
