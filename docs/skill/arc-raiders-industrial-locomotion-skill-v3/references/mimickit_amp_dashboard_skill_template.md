---
name: mimickit-amp-dashboard
description: Start and use a dedicated AMP training dashboard for task-specific MimicKit locomotion brains, tracking AMP/style reward, discriminator health, task reward, throughput, checkpoint quality, dual-GPU state, queue progress, and render-viz rollout links. Use this when training ARC-like Walk/Stop/Turn/Stomp/Recover AMP brains and deciding whether a checkpoint is ready for AI4AnimationPy validation or UE5 export.
---

# MimicKit AMP Dashboard

## Goal

Provide a dedicated web dashboard for **AMP training runs** in MimicKit.

This is the AMP sibling of:

```text
docs/skill/mimickit-ase-dashboard-skill/SKILL.md
```

It must also pair with:

```text
docs/skill/mimickit-render-viz-sequence-skill/SKILL.md
```

The page focuses on:

```text
- current AMP run progress to a target sample budget
- task reward vs adversarial style reward
- discriminator reward and discriminator accuracy
- policy/value/entropy/clip_frac health when available
- recent samples/s and ETA
- dual-GPU utilization and memory history
- current ARC-like brain: WalkBrain / StopBrain / TurnBrain / StompBrain / RecoverBrain
- queue state for multi-brain AMP training series
- recent runner / queue / monitor log tails
- render-viz availability for best/current checkpoints
```

## Difference from ASE Dashboard

Do not copy ASE latent metrics blindly.

ASE dashboard may track:

```text
enc_reward_mean
diversity_loss
latent-space quality
ASE pretraining stages
```

AMP dashboard should instead track:

```text
amp/style reward
discriminator health
task reward
policy stability
brain-specific training status
visual rollout quality
```

Only show `enc_reward_mean`, `diversity_loss`, or latent-space charts if this repository's AMP run actually produces them.

## Entry Script

Preferred script:

```text
scripts/run_amp_dashboard.py
```

If the repository has a generalized dashboard script, the AMP skill may point to the actual entry script, but the public command must still be AMP-specific and easy to copy.

## Quick Start

```bash
cd /root/Project/MimicKit
python -u scripts/run_amp_dashboard.py \
  --root-out amp_arc_walk_dual_newton_YYYYMMDD_HHMMSS \
  --monitor-log /tmp/mk_dualgpu_amp_watch.log \
  --queue-log output/train/amp_series_queue_controller_YYYYMMDD_HHMMSS.log \
  --target-samples 1000000000 \
  --brain WalkBrain \
  --host 0.0.0.0 \
  --port 8789
```

Open:

```text
http://127.0.0.1:8789/
http://127.0.0.1:8789/?root=amp_arc_walk_dual_newton_YYYYMMDD_HHMMSS
```

## Key Options

```bash
python scripts/run_amp_dashboard.py --help
```

Expected flags:

```text
--root-out          AMP training root name or absolute path
--monitor-log       explicit GPU monitor log
--queue-log         AMP queue controller log
--target-samples    sample budget for progress and ETA
--brain             WalkBrain|StopBrain|TurnBrain|StompBrain|RecoverBrain
--series-cases      multi-brain AMP series order
--render-root       optional output/img root for rollout renders
--host              bind address
--port              bind port
```

## What The Page Shows

Top cards:

```text
active AMP run
current brain
progress to target samples
ETA
checkpoint health
visual render status
```

AMP sections:

```text
task_reward_mean
amp_reward_mean or style_reward_mean
disc_reward_mean
discriminator agent/demo accuracy
policy_loss
value_loss
entropy
clip_frac
samples_per_second
```

Ops sections:

```text
live dual-GPU utilization bars
GPU memory / temperature
GPU history chart
training metric chart
copied config snapshot from agent/env/engine YAMLs
recent training rows from log.txt
runner / queue / monitor tails
render-viz links
```

## Health Semantics

Use AMP-oriented health labels:

```text
AMP 训练健康          task, style, discriminator, throughput, and GPU checks look usable
风格奖励偏低           adversarial style reward is weak or falling
判别器失衡             discriminator accuracy/reward suggests overpowering or collapse
任务奖励停滞           task reward is not improving after enough samples
吞吐异常偏低           samples/s below usable threshold
疑似动作坍缩           scalar health or render-viz suggests near-static or repetitive motion
可送 Demo 验证         checkpoint should be rendered and inspected in AI4AnimationPy/render-viz
可送 UE5 导出          only after render-viz + ONNX parity + schema lock pass
```

These are heuristics, not proof of convergence.

## Required Render-Viz Pairing

Before judging visual quality, pair this dashboard with:

```bash
/root/miniconda3/envs/mimickit/bin/python tools/ue_bridge/build_mimickit_render_sequences.py \
  --roots <AMP_ROOT> \
  --cases <AMP_CASE> \
  --frames 300 \
  --frame-stride 5 \
  --device cuda:0 \
  --num-envs 1
```

The dashboard should display or link:

```text
output/img/<root>/.../render/frames/
output/img/<root>/.../render/render_meta.json
output/img/<root>/infer_viz_index.tsv
output/img/render_all_roots.tsv
```

If an AMP render appears frozen or jittery, first verify the render used the agent test loop rather than a static policy wrapper.

## Acceptance

```text
[ ] Page starts without extra web framework.
[ ] It auto-detects newest output/train/amp_* root when --root-out is omitted.
[ ] It parses log.txt even when progress.json is absent.
[ ] It shows task/style/discriminator/throughput metrics.
[ ] It shows GPU utilization history.
[ ] It knows which ARC-like brain is being trained.
[ ] It reads queue state for multi-brain AMP series.
[ ] It links render-viz artifacts when present.
[ ] It does not show ASE-only latent metrics unless available.
[ ] It defines checkpoint readiness for AI4AnimationPy and UE5 stages separately.
```

## Troubleshooting

```text
No AMP metrics found:
- Check log.txt keys.
- Add parser aliases for amp_reward/style_reward/disc_reward.
- Do not fake metrics; show unknown.

Discriminator too strong:
- Style reward may collapse.
- Lower discriminator updates or regularize if training config supports it.

Task reward improves but motion looks bad:
- Render rollout before exporting.
- Increase style weight or improve reference motions.

Render path looks frozen:
- Rerun render-viz through the agent test loop.
- Do not judge from a static actor wrapper.

UE5 export requested before schema lock:
- Block export until obs_action_spec, normalization_stats, joint_order, and brain_manifest are synchronized.
```
