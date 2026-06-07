---
name: mimickit-amp-dashboard
description: Start and use a dedicated AMP training dashboard for task-specific MimicKit locomotion brains, tracking AMP/style reward, discriminator health, task reward proxies, throughput, checkpoint quality, dual-GPU state, single-brain keepalive progress, and render-viz artifact links. Use this when training ARC-like WalkBrain, TurnBrain, or StopBrain AMP roots and deciding whether a checkpoint is ready for render-viz inspection or later UE5 export work.
---

# MimicKit AMP Dashboard

## Goal

Provide a dedicated web page for **AMP single-brain training runs** in MimicKit.

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
- current AMP run progress to smoke/probe/long targets
- task return proxy vs adversarial style reward
- discriminator reward and discriminator accuracy
- policy/value/entropy/clip_frac when available
- recent samples/s and ETA
- dual-GPU utilization and memory history
- current brain: WalkBrain / TurnBrain / StopBrain
- single-brain keepalive stage state
- checkpoint health and best scalar candidate
- render-viz availability for best/current checkpoints
```

## Difference From ASE Dashboard

Do not copy ASE latent metrics blindly.

ASE dashboard may track:

```text
enc_reward_mean
diversity_loss
latent-space quality
multi-case ASE pretraining SOP
```

AMP dashboard should instead track:

```text
disc/style reward
task return proxy
discriminator health
throughput stability
brain-specific training status
visual rollout readiness
```

Only show `enc_reward_mean` or `diversity_loss` if an AMP run actually produces them.

## Entry Scripts

Preferred scripts:

```text
scripts/run_amp_dashboard.py
scripts/run_amp_keepalive.py
scripts/watchdog_amp_training.sh
```

No extra web framework is required. The dashboard uses stdlib HTTP serving.

## Quick Start

Start a new single-brain AMP keepalive root:

```bash
cd /root/Project/MimicKit

/root/miniconda3/envs/mimickit/bin/python scripts/run_amp_keepalive.py \
  --brain WalkBrain \
  --root-out amp_WalkBrain_dual_newton_hiutil_e1024_$(date +%Y%m%d_%H%M%S) \
  --engine-config data/engines/newton_engine.yaml \
  --devices cuda:0 cuda:1 \
  --num-envs 1024 \
  --master-port 40489
```

Start the AMP dashboard:

```bash
cd /root/Project/MimicKit

/root/miniconda3/envs/mimickit/bin/python -u scripts/run_amp_dashboard.py \
  --root-out amp_WalkBrain_dual_newton_hiutil_e1024_YYYYMMDD_HHMMSS \
  --target-samples 1000000000 \
  --brain WalkBrain \
  --host 0.0.0.0 \
  --port 8789
```

Open:

```text
http://127.0.0.1:8789/
http://127.0.0.1:8789/?root=amp_WalkBrain_dual_newton_hiutil_e1024_YYYYMMDD_HHMMSS
```

Optional tmux watchdog:

```bash
export AMP_TRAIN_CMD='/root/miniconda3/envs/mimickit/bin/python /root/Project/MimicKit/scripts/run_amp_keepalive.py --brain WalkBrain --root-out amp_WalkBrain_dual_newton_hiutil_e1024_YYYYMMDD_HHMMSS --engine-config data/engines/newton_engine.yaml --devices cuda:0 cuda:1 --num-envs 1024 --master-port 40489'
export AMP_DASHBOARD_CMD='/root/miniconda3/envs/mimickit/bin/python /root/Project/MimicKit/scripts/run_amp_dashboard.py --root-out amp_WalkBrain_dual_newton_hiutil_e1024_YYYYMMDD_HHMMSS --brain WalkBrain --port 8789'
/bin/bash scripts/watchdog_amp_training.sh
```

## Key Options

```bash
python scripts/run_amp_dashboard.py --help
python scripts/run_amp_keepalive.py --help
```

Important dashboard flags:

```text
--root-out
--monitor-log
--queue-log
--target-samples
--brain
--series-cases
--render-root
--host
--port
```

Important keepalive flags:

```text
--brain             WalkBrain|TurnBrain|StopBrain
--root-out          keepalive root
--engine-config     default newton_engine.yaml
--devices           default cuda:0 cuda:1
--num-envs          default 1024
--master-port       default 40489
--smoke-train-samples
--probe-target-samples
--long-target-samples
--stop-after-stage  smoke_test|smoke_visualize|smoke_train|probe_train|long_train|complete
```

## What The Page Shows

Top cards:

```text
current run
current brain
progress to current target
ETA
checkpoint health
render status
```

AMP sections:

```text
task return proxy
disc_reward_mean
disc_agent_acc / disc_demo_acc
policy_loss
value_loss
entropy
clip_frac
samples_per_second
```

Ops sections:

```text
live dual-GPU utilization bars
GPU history chart
AMP metrics chart
copied config snapshot from current train segment
recent training rows from log.txt
recent keepalive events
artifact links for render_meta / mp4 / index files
```

## Health Semantics

Use AMP-oriented labels:

```text
warming up          no valid training rows yet
throughput healthy  recent samples/s is above the configured floor
throughput low      recent samples/s is below the configured floor
判别器可用           discriminator accuracy remains inside the healthy band
判别器失衡           discriminator is likely overpowering the policy
判别器塌陷           discriminator signal is likely unusable
scalar ready        best scalar checkpoint passed metric thresholds
Demo-ready          scalar-ready plus render-viz artifacts exist
render pending      no render-viz artifacts found yet
render blocked      a discovered manifest failed and exposes a blocker
render incomplete   files exist but required manifest gates are absent
```

These are monitoring heuristics, not proof of convergence.

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

For MimicKit -> Evih v2 bridge results, the dashboard also links:

```text
MimicKit RGB/silhouette PNG and MP4
mesh_reference_manifest.json
Evih RGB/silhouette PNG and MP4
visual_result_manifest.json
scene_contract_compare_report.json
visual_metric_report.json
comparison_sheet.png
visual_review.json
full_chain_bridge_manifest.json
```

`render ready` is manifest-driven. File existence alone is never sufficient.
Failed manifests must show their blocker; incomplete manifests must not be
promoted to ready.

If an AMP render appears frozen or jittery, first verify the render used the agent test loop rather than a static policy wrapper.

## Acceptance

```text
[ ] docs/skill/mimickit-amp-dashboard-skill/SKILL.md exists.
[ ] The metadata name is mimickit-amp-dashboard.
[ ] The skill references scripts/run_amp_dashboard.py.
[ ] It explains the AMP vs ASE difference.
[ ] It does not require progress.json.
[ ] It tracks style/discriminator/task-proxy/throughput metrics.
[ ] It explains the single-brain keepalive flow.
[ ] It pairs explicitly with mimickit-render-viz-sequence-skill.
[ ] It defines visual acceptance through rollout renders, not scalar rewards alone.
```

## Troubleshooting

```text
No AMP metrics found:
- Check the active train segment's log.txt.
- A fresh run may still be warming up because iters_per_output=100.

Location sword-shield smoke test has no exact pretrained model:
- The keepalive script tries a reasonable fallback candidate if present.
- If none exists, smoke test still runs without --model_file and records that fact.

Dashboard opens but render links are empty:
- This only means render-viz has not produced artifacts yet.
- Run the render-viz sequence workflow before judging visual quality.

Need to validate only part of the flow:
- Use --stop-after-stage on run_amp_keepalive.py to stop after smoke_train or probe_train.

Need watchdog restarts:
- Set AMP_TRAIN_CMD and optionally AMP_DASHBOARD_CMD, then run scripts/watchdog_amp_training.sh.
- The watchdog is read-only with respect to checkpoints; it only manages tmux sessions.
```
