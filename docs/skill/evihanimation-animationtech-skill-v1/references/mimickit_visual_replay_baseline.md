# MimicKit Visual Replay Baseline

## Primary Walk Baseline

Package:

```text
output/train/amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637/ue_export
```

MimicKit render reference:

```text
output/img/amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637/long_train/render
```

Important package files:

```text
visual_replay/pose_dof_replay.jsonl
visual_replay/pose_dof_meta.json
joint_order.json
obs_action_spec.yaml
visual_alignment_contract.json
```

Expected v1 result:

```text
body_spec_source=/root/Project/MimicKit/data/assets/sword_shield/humanoid_sword_shield.xml
geom_spec_source=/root/Project/MimicKit/data/assets/sword_shield/humanoid_sword_shield.xml
frames_loaded=300
png_count=60
mp4_ok=true
skeleton_replay_pass=true
character_geom_compare_pass=true
true_mesh_reference_available=false
```

## Stop Canary

Package:

```text
output/train/amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/ue_export_probe_gate
```

MimicKit render reference:

```text
output/img/amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/probe_train/render
```

Important package files:

```text
visual_replay/pose_dof_replay.jsonl
visual_replay/pose_dof_meta.json
joint_order.json
mimickit_source_rig_asset_spec.json
runtime_control_contract.json
visual_alignment_contract.json
```

Expected v1 result:

```text
body_spec_source=<package>/mimickit_source_rig_asset_spec.json
geom_spec_source=<package>/mimickit_source_rig_asset_spec.json
frames_loaded=300
png_count=60
mp4_ok=true
skeleton_replay_pass=true
character_geom_compare_pass=true
true_mesh_reference_available=false
```

## Character Visual Baseline Status

The current Walk and Stop render references are XML geom renders:

```text
render_meta.visual_kind=geom
render_meta.mesh_detected=0
```

Use them for `mimickit_geom_vs_evih_geom_sheet.png`. Do not treat them as true mesh references. True mesh parity is blocked until a MimicKit render reference succeeds with `visual_kind=mesh`, `mesh_detected=1`, `image_count=60`, and `status=ok`.

## Mesh Reference Builder

Use this isolated builder for the first MimicKit white-knight reference:

```bash
/root/miniconda3/envs/mimickit/bin/python tools/ue_bridge/build_mimickit_mesh_reference.py \
  --root-name tmp_white_knight_mesh_reference_smoke \
  --frames 10 \
  --frame-stride 5 \
  --force-root
```

For the full 60-frame reference, rerun with:

```bash
--frames 300 --frame-stride 5
```

The generated manifest is:

```text
output/train/<root>/mesh_reference_manifest.json
output/img/<root>/mesh_reference_manifest.json
```

It should only pass when the render is a successful USD mesh render. If WSL lacks `mimickit-isaaclab` or `omni.kit.usd`, the manifest will record `blocker=isaaclab_precheck_failed`.

## Read-Only Rule

The packages under `output/train` and reference media under `output/img` are baselines. Do not write replay output back into those directories during validation. Use `/tmp/...` or a fresh explicit output directory.
