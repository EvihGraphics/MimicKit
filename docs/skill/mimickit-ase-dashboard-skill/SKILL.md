---
name: mimickit-ase-dashboard
description: Start and use a dedicated ASE training dashboard for single-run pretraining, billion-sample ETA tracking, latent-space health, queue state, and dual-GPU monitoring.
---

# MimicKit ASE Dashboard

## Goal

Provide a dedicated web page for ASE training runs that focuses on:

- current ASE run progress to a target sample budget such as `1B`
- `disc_reward_mean`, `enc_reward_mean`, `diversity_loss`, `clip_frac`
- dual-GPU utilization and monitor history
- current ASE SOP stage (`Stage 1-2` pretraining)
- serial queue state for `ase_humanoid -> ase_humanoid_sword_shield`
- recent runner / queue / monitor log tails

This is for ASE-specific pretraining. It is not the generic longcycle/e2e dashboard.

## Entry Script

- `scripts/run_ase_dashboard.py`

No extra web framework is required. The script uses stdlib HTTP serving.

## When To Use

Use this skill when:

1. You are running `ase_humanoid` or `ase_humanoid_sword_shield`.
2. You care about latent-space quality, style reward, or mode-collapse risk.
3. The generic progress dashboard is too tied to `progress.json` / `attempts.json`.

## Quick Start

```bash
cd /root/Project/MimicKit

python -u scripts/run_ase_dashboard.py \
  --root-out ase_humanoid_dual_newton_hiutil_e1024_20260308_015844 \
  --monitor-log /tmp/mk_dualgpu_follow_until_high_20260308_015844.log \
  --queue-log output/train/ase_series_queue_controller_20260308_111243.log \
  --target-samples 1000000000 \
  --host 0.0.0.0 \
  --port 8788
```

Open:

- local: `http://127.0.0.1:8788/`
- direct root pin: `http://127.0.0.1:8788/?root=ase_humanoid_dual_newton_hiutil_e1024_20260308_015844`

## Key Options

```bash
python scripts/run_ase_dashboard.py --help
```

Important flags:

- `--root-out`: ASE training root name or absolute path
- `--monitor-log`: explicit GPU monitor log
- `--queue-log`: explicit ASE queue controller log
- `--target-samples`: budget target for ETA and progress bar
- `--series-cases`: ASE series order, default is `ase_humanoid_args.txt,ase_humanoid_sword_shield_args.txt`
- `--host`, `--port`: bind address

## What The Page Shows

Top cards:

- active ASE run
- progress to target samples
- ETA to current target
- ASE health summary

ASE-specific sections:

- `disc_reward_mean`
- `enc_reward_mean`
- `diversity_loss`
- `clip_frac`
- discriminator agent/demo accuracy
- SOP stage and serial queue state

Ops sections:

- live dual-GPU utilization bars
- GPU history chart
- ASE metrics chart
- copied config snapshot from `agent_config.yaml`, `env_config.yaml`, `engine_config.yaml`
- recent training rows from `log.txt`
- runner / queue / monitor tails

## Health Semantics

The dashboard labels are intentionally ASE-oriented:

- `ASE 训练健康`: style, latent, throughput, and GPU checks are all in a good state
- `风格奖励偏低`: discriminator reward is weaker than expected
- `潜空间需观察`: encoder reward or diversity loss suggests latent quality needs watching
- `疑似 latent 风险`: encoder reward too low or diversity loss too high
- `吞吐异常偏低`: recent samples/s is below a usable threshold

These are monitoring heuristics, not proof of convergence.

## Operational Notes

- The page is read-only.
- It parses `log.txt` by converting carriage-return updates into row history, so it works for single ASE runs without `progress.json`.
- If `--root-out` is empty, the script auto-picks the newest `output/train/ase_*` directory.
- The queue card can read `output/train/ase_series_queue_controller_*.log` and show whether the next ASE case is armed or has started.
