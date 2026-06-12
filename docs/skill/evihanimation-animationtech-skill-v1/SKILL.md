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
- Implementation worktree used for the strict v3 replay path:

```text
/mnt/d/AnimationTech-learning/EvihAnimation-mimickit-bridge-v3
branch: codex/mimickit-bridge-v3
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
     matching `scene_contract_v3.json`, RGB/silhouette/ground-mask PNG sequences,
     valid H.264 MP4, and a passing manual `visual_review.json`.

4. **Use exported sidecars as the stable interface.**
   - `pose_dof_replay.jsonl`
   - `body_world_replay.jsonl`
   - `body_world_contract.json`
   - `pose_dof_meta.json`
   - `joint_order.json`
   - `mimickit_source_rig_asset_spec.json`
   - `visual_alignment_contract.json`
   - `scene_contract_v3.json`
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
cd /mnt/d/AnimationTech-learning/EvihAnimation-mimickit-bridge-v3

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
/mnt/d/AnimationTech-learning/EvihAnimation-mimickit-bridge-v3/Demos/MimicKitReplay/results/
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
  --frames 300 \
  --frame-stride 5 \
  --force-root
```

The workflow uses `view_motion_humanoid_sword_shield_mesh_env.yaml`, `isaac_lab_engine.yaml`, and `RL_Avatar_Atk_2xCombo01_Motion` by default. It writes `mesh_reference_manifest.json` under both `output/train/<root>/` and `output/img/<root>/`.
PLAN-6-9 v3 never accepts a two-frame smoke as visual evidence: it requires
the full 60-frame sampled dynamic sequence and a 60-frame MP4.

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
software_geometry_replay_pass=true
framework_api_used=true
evih_framework_api_replay_pass=true
framework_scene_contract_compare_pass=true
framework_visual_metric_pass=true
framework_scene_visual_metric_pass=true
framework_dynamic_sequence_pass=true
framework_media_ok=true
framework_renderer_provenance=<non-empty>
data_binding_ok=true
mesh_binding_pass=true
fk_compare_pass=true
scene_contract_compare_pass=true
scene_visual_metric_pass=true
visual_metric_pass=true
dynamic_sequence_pass=true
comparison_mp4_pass=true
visual_review_pass=true
media_ok=true
mesh_scope=true
source_was_ppm_only=false
rgb_png_count=expected_count
silhouette_png_count=expected_count
ground_mask_png_count=expected_count
rgb_png_count=60
mp4_frame_count=60
```

The strict v3 final renderer is EvihAnimation Framework API, not the stdlib
software rasterizer. Use the dedicated Python 3.12 environment:

```text
/root/miniconda3/envs/evihanimation-mimickit-bridge
```

`AI4Animation.Mode.CAPTURE` must initialize `Actor`, `RigidNodeMesh`, and
`RenderPipeline` without entering the interactive loop. The accepted exported
GLB is `rigid_node`; never claim it is skinned. Framework capture must record
the same GLB, pose/body-world sidecars, binding contract, source scene hash,
applied camera/FOV/near/far/ground/light/shadow values, and renderer
provenance. Missing Python 3.12, raylib, einops, pygltflib, or display context
fails with `evih_framework_environment_unavailable`.

For `rigid_node`, bind every non-skinned mesh to its corresponding Actor body
entity and update its dynamic vertex/normal buffer from the entity's applied
world transform. Keep all 17 models registered through `RenderPipeline`.
Framework silhouette is a dedicated RenderPipeline semantic pass with Ground
as the depth occluder; ground-mask is the complement of that semantic
silhouette. Record both derivations and the rigid-node update mode in renderer
provenance.

For v3 scene parity, require `capture.settle_updates_per_attempt` and strict
per-frame camera samples in the source contract. The current Isaac default grid
uses `ground.grid_spacing_m=0.5`; do not silently substitute `1.0`.
Apply the contract's distant-light direction and ground shadow, and record the
actual shadow opacity and blur settings in `applied_scene_contract.json`.
V3 always consumes 300 source frames at stride 5 and requires 60 output frames
with at least 6 distinct RGB and silhouette frames; a two-frame smoke fails.
It also requires a 60-frame side-by-side `mimickit_vs_evih_dynamic.mp4`
(MimicKit left, Evih right). Its hash is part of `visual_review.json.evidence`.

Manual approval is artifact-bound. `visual_review.json.evidence` must match the
current Mimic manifest, mesh, scene contract, comparison sheet, and both RGB
frame sets. A named checklist also requires a non-empty `reviewed_at_utc`.
Missing timestamps fail closed; stale evidence must fail with
`visual_review_evidence_mismatch`.

Use the PLAN-6-9 orchestrator from MimicKit to preserve gate order:

```bash
PYTHONPATH=tools/ue_bridge python tools/ue_bridge/run_plan_6_9_bridge.py --gate preflight
PYTHONPATH=tools/ue_bridge python tools/ue_bridge/run_plan_6_9_bridge.py --gate framework-preflight
PYTHONPATH=tools/ue_bridge python tools/ue_bridge/run_plan_6_9_bridge.py --gate status
PYTHONPATH=tools/ue_bridge python tools/ue_bridge/run_plan_6_9_bridge.py --gate white-knight-smoke
PYTHONPATH=tools/ue_bridge python tools/ue_bridge/run_plan_6_9_bridge.py --gate promote-review --case white-knight-smoke
PYTHONPATH=tools/ue_bridge python tools/ue_bridge/run_plan_6_9_bridge.py --gate white-knight
PYTHONPATH=tools/ue_bridge python tools/ue_bridge/run_plan_6_9_bridge.py --gate framework-render --case white-knight
```

The orchestrator has no unreviewed-gate bypass. It writes
`output/img/mimickit_evih_bridge_v3/plan_6_9_execution_manifest.json`.
`promote-review` reruns only the Evih evidence validation for an existing case;
it never rebuilds or overwrites the MimicKit source root.
After each final case's automatic gates, stop for a named human review before
promotion. Do not automatically continue to the next case.

## Response Style

When helping with this skill:

- State which package is being replayed.
- State whether source rig spec or MJCF fallback was used.
- Report PNG count, MP4 status, DOF consumption, root displacement, and `skeleton_replay_pass`.
- For character geom work, report geom count, missing geom bodies, `character_geom_compare_pass`, and whether the MimicKit baseline is geom or mesh.
- For true mesh work, first verify that a MimicKit mesh reference exists; otherwise state that mesh parity is blocked pending a successful mesh baseline.
