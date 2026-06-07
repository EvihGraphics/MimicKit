---
name: evihanimation-animationtech
description: Use this skill when reproducing MimicKit inference visualization inside or alongside EvihGraphics/EvihAnimation, especially skeleton replay, body-attached character geom replay, or next-stage mesh visual parity from MimicKit visual_replay packages. Trigger on evihanimation, EvihAnimation, AI4AnimationPy, MimicKit visual_replay, pose_dof_replay, joint_order, skeleton replay, character geom replay, mesh parity, MotionGraph/MotionMatching visualization, BVH/FBX/GLB import, or offline animation rendering.
---

# evihanimation EvihAnimation Replay Skill

## Mission

Use `EvihGraphics/EvihAnimation` as the Python animation-runtime target for reproducing MimicKit inference visualization.

The stable base target is skeleton data parity:

```text
MimicKit export package
  -> visual_replay/pose_dof_replay.jsonl
  -> joint_order.json + source rig/MJCF hierarchy
  -> deterministic FK
  -> skeleton-only PNG sequence + MP4 + report
```

The next visual target is character appearance parity in two steps:

```text
current Walk/Stop baselines -> XML geom character replay -> geom-vs-geom visual sheet
exact mesh roots -> shared GLB + scene contract -> mesh-vs-mesh visual sheet
```

Do not claim true mesh parity until a successful MimicKit mesh reference exists.
Current Walk/Stop MimicKit baselines are XML geom renders, not USD mesh renders.

## Source Truth

- Correct source repo: `/mnt/d/AnimationTech-learning/EvihAnimation`
- Remote: `git@github.com:EvihGraphics/EvihAnimation.git`
- The source checkout is dirty and contains useful local demo/render outputs. Treat it as read-only reference.
- Implementation worktree used for this replay path:

```text
/mnt/d/AnimationTech-learning/EvihAnimation-mimickit-bridge
branch: codex/mimickit-bridge
```

Read [evihanimation_source_map.md](references/evihanimation_source_map.md) before changing the EvihAnimation side.

## Non-Negotiables

1. **Do not mutate the dirty source checkout.**
   - Use it as reference only.
   - Work in a separate worktree for implementation.

2. **Do not copy MimicKit internals for their own sake.**
   - Functional parity matters: same replay data, same skeleton timing, same output media shape.
   - Code design may be independent.

3. **Keep mesh claims precise.**
   - Skeleton and XML geom replay still report `mesh_scope=false`.
   - Missing GLB/USD must not fail skeleton or geom replay.
   - True mesh parity requires a structurally valid shared GLB, complete package,
     matching `scene_contract_v2.json`, PNG/silhouette sequences, and valid MP4.

4. **Use exported sidecars as the stable interface.**
   - `pose_dof_replay.jsonl`
   - `pose_dof_meta.json`
   - `joint_order.json`
   - `mimickit_source_rig_asset_spec.json`
   - `visual_alignment_contract.json`
   - `scene_contract_v2.json`
   - MJCF XML fallback is allowed only for geom replay, never true mesh.

5. **Never infer motion from rendered pixels.**
   - Existing MimicKit PNG/MP4 outputs are visual references.
   - The replay driver must consume root pose and DOF data.

## Baselines

Use [mimickit_visual_replay_baseline.md](references/mimickit_visual_replay_baseline.md) for exact paths.

Primary baseline:

```text
output/train/amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637/ue_export
```

Stop canary:

```text
output/train/amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/ue_export_probe_gate
```

## Replay Commands

From the EvihAnimation implementation worktree:

```bash
cd /mnt/d/AnimationTech-learning/EvihAnimation-mimickit-bridge

/root/miniconda3/envs/mimickit/bin/python Demos/MimicKitReplay/replay_skeleton.py \
  --package-dir /root/Project/MimicKit/output/train/amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637/ue_export \
  --mimic-render-dir /root/Project/MimicKit/output/img/amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637/long_train/render \
  --out-dir /tmp/evih_replay_walk \
  --frames 300 \
  --stride 5 \
  --width 960 \
  --height 540 \
  --skeleton-only
```

For body-attached XML geom character replay:

```bash
/root/miniconda3/envs/mimickit/bin/python Demos/MimicKitReplay/replay_skeleton.py \
  --package-dir /root/Project/MimicKit/output/train/amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637/ue_export \
  --mimic-render-dir /root/Project/MimicKit/output/img/amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637/long_train/render \
  --out-dir /tmp/evih_character_geom_walk \
  --frames 300 \
  --stride 5 \
  --width 960 \
  --height 540 \
  --character-geom
```

The same entrypoint should pass on StopBrain by swapping the package and render paths.

## Official Visual Results

For reviewable Evih demo artifacts, write results under:

```text
/mnt/d/AnimationTech-learning/EvihAnimation-mimickit-bridge/Demos/MimicKitReplay/results/
```

Expected v1 packages:

```text
walkbrain_skeleton_replay/
stopbrain_skeleton_replay/
```

Each package should include a MimicKit skeleton reference channel and an Evih skeleton replay channel:

```text
mimickit_skeleton_reference/
evih_skeleton_replay/
evih_character_geom_replay/
skeleton_data_compare_report.json
mimickit_skeleton_vs_evih_skeleton_sheet.png
skeleton_overlay_contact_sheet.png
visual_character_compare_report.json
mimickit_geom_vs_evih_geom_sheet.png
visual_result_manifest.json
```

MimicKit geom/UE render frames are optional sanity context for skeleton replay, but they are the current character-geom visual reference. The skeleton parity reference remains sidecar-derived skeleton trajectory data, not rendered pixels.

Use the visual result builder to rerun replay from baseline sidecars and build the sheets:

```bash
/root/miniconda3/envs/mimickit/bin/python Demos/MimicKitReplay/build_visual_results.py \
  --label WalkBrain \
  --package-dir /root/Project/MimicKit/output/train/amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637/ue_export \
  --mimic-render-dir /root/Project/MimicKit/output/img/amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637/long_train/render \
  --out-dir Demos/MimicKitReplay/results/walkbrain_skeleton_replay
```

The skeleton parity gate is `skeleton_data_compare_report.json`, backed by `mimickit_skeleton_vs_evih_skeleton_sheet.png`. The optional `geom_render_sanity_sheet.png` is not a pass/fail gate.

The character geom gate is `visual_character_compare_report.json`, backed by `mimickit_geom_vs_evih_geom_sheet.png`. This gate proves Evih is carrying the MimicKit XML character geoms on the verified skeleton trajectory. It does not prove true USD mesh parity.

## Mesh Reference Workflow

True mesh parity starts by producing a MimicKit white-knight reference, isolated from the current Walk/Stop geom baselines:

```bash
/root/miniconda3/envs/mimickit/bin/python tools/ue_bridge/build_mimickit_mesh_reference.py \
  --root-name tmp_white_knight_mesh_reference_smoke \
  --frames 10 \
  --frame-stride 5 \
  --force-root
```

The workflow uses `view_motion_humanoid_sword_shield_mesh_env.yaml`, `isaac_lab_engine.yaml`, and `RL_Avatar_Atk_2xCombo01_Motion` by default. It writes `mesh_reference_manifest.json` under both `output/train/<root>/` and `output/img/<root>/`.

Use `build_mimickit_mesh_reference.py --run-native-windows` for the native
white-knight gate. It must use public offscreen capture, reject structurally
empty GLB output, and emit complete package/scene sidecars. Do not switch this
mesh reference path to Newton or XML geom.

## Acceptance

A skeleton replay pass requires:

```text
skeleton_replay_pass=true
mesh_scope=false
frames_loaded=300
png_count=60
mp4_ok=true
dof_dim_ok=true
root_trajectory_ok=true
consumed_dofs.consumed_exactly_once=true
row_validation.all_rows_finite=true
row_validation.frames_monotonic=true
motion_visible=true
```

A character geom pass additionally requires:

```text
character_geom_compare_pass=true
evih_character_geom_replay_pass=true
current_baseline_is_geom=true
true_mesh_reference_available=false
evih_character_geom_png_count=60
evih_character_geom_mp4_size_bytes>0
evih_character_geom_count=21
evih_character_missing_geom_bodies=[]
mimickit_geom_vs_evih_geom_sheet_exists=true
```

See [skeleton_replay_contract.md](references/skeleton_replay_contract.md) for the field contract and validation semantics.

A true mesh replay pass additionally requires:

```text
evih_mesh_replay_pass=true
mesh_binding_pass=true
scene_contract_compare_pass=true
visual_metric_pass=true
mesh_scope=true
source_was_ppm_only=false
```

## Response Style

When helping with this skill:

- State which package is being replayed.
- State whether source rig spec or MJCF fallback was used.
- Report PNG count, MP4 status, DOF consumption, root displacement, and `skeleton_replay_pass`.
- For character geom work, report geom count, missing geom bodies, `character_geom_compare_pass`, and whether the MimicKit baseline is geom or mesh.
- For true mesh work, first verify that a MimicKit mesh reference exists; otherwise state that mesh parity is blocked pending a successful mesh baseline.
