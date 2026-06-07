# Skeleton Replay Contract

## Inputs

Required:

```text
visual_replay/pose_dof_replay.jsonl
visual_replay/pose_dof_meta.json
joint_order.json
```

Preferred:

```text
mimickit_source_rig_asset_spec.json
scene_contract_v2.json
```

Fallback:

```text
visual_alignment_contract.json -> character.resolved_char_file
visual_alignment_contract.json -> character.declared_char_file
```

If neither source rig spec nor MJCF is available, replay may use built-in sword/shield humanoid offsets, but the report must state that source.

## Row Semantics

Each replay row should provide:

```text
frame
episode
time_seconds
root_pos_m[3]
root_rot_xyzw[4]
dof_pos[31]
policy_action[31]
```

The v1 renderer uses `root_pos_m`, `root_rot_xyzw`, and `dof_pos`. `policy_action` is preserved as package evidence but not used to drive v1 replay.

## FK Rules

- `joint_order.json` is authoritative for body order, parent body, joint type, and DOF slices.
- Root transform comes from `root_pos_m + root_rot_xyzw`.
- Spherical 3D DOF slices use source joint axes when available; otherwise they are interpreted as an exponential map.
- Hinge 1D DOF slices use the source joint axis when available; otherwise local Y is the fallback.
- Fixed bodies consume no DOF and inherit parent-space attachment offsets.

## Outputs

Required files:

```text
frames/frame_000000.png
frames/frame_000001.png
...
frames/frame_000059.png
skeleton_replay.mp4
skeleton_replay_meta.json
visual_compare_report.json
```

Official Evih demo visual result packages also include:

```text
mimickit_skeleton_reference/skeleton_trajectory.jsonl
mimickit_skeleton_reference/skeleton_trajectory.npz
mimickit_skeleton_reference/frames/
mimickit_skeleton_reference/skeleton_replay.mp4
mimickit_skeleton_reference/contact_sheet.png
evih_skeleton_replay/skeleton_trajectory.jsonl
evih_skeleton_replay/skeleton_trajectory.npz
evih_skeleton_replay/frames/
evih_skeleton_replay/skeleton_replay.mp4
evih_skeleton_replay/contact_sheet.png
evih_character_geom_replay/frames/
evih_character_geom_replay/character_replay.mp4
evih_character_geom_replay/character_replay_meta.json
evih_character_geom_replay/visual_asset_manifest.json
evih_character_geom_replay/contact_sheet.png
skeleton_data_compare_report.json
mimickit_skeleton_vs_evih_skeleton_sheet.png
skeleton_overlay_contact_sheet.png
visual_character_compare_report.json
mimickit_geom_vs_evih_geom_sheet.png
visual_result_manifest.json
```

Report fields:

```text
skeleton_replay_pass
mesh_scope
skeleton_only
frames_loaded
stride
expected_png_count
png_count
mp4_ok
dof_dim_ok
root_trajectory_ok
root_displacement_m
mean_joint_delta_m
motion_visible
consumed_dofs.consumed_exactly_once
row_validation.all_rows_finite
row_validation.frames_monotonic
```

Skeleton data compare fields:

```text
skeleton_data_compare_pass
body_order_match
source_frame_ids_match
dof_match
max_body_pos_error_m
mean_body_pos_error_m
root_pos_error_m
missing_bodies
extra_bodies
```

Character geom fields:

```text
character_geom_compare_pass
evih_character_geom_replay_pass
current_baseline_is_geom
true_mesh_reference_available
geom_count
geom_type_counts
missing_geom_bodies
key_bodies_without_geom
mimickit_geom_vs_evih_geom_sheet_exists
```

MimicKit mesh reference fields:

```text
mesh_reference_pass
precheck.ok
dry_run.ok
render_summary.visual_kind
render_summary.mesh_detected
render_summary.image_count
render_summary.expected_image_count
render_summary.mp4_ok
render_summary.frame_ids
contact_sheet.ok
blocker
```

True mesh replay outputs:

```text
rgb_frames/frame_*.png
silhouettes/frame_*.png
mesh_replay.mp4
mesh_binding_report.json
scene_contract_compare_report.json
visual_metric_report.json
comparison_sheet.png
visual_review.json
visual_result_manifest.json
```

True mesh replay fields:

```text
evih_mesh_replay_pass
mesh_binding_pass
scene_contract_compare_pass
visual_metric_pass
mesh_scope
source_mesh_sha256
source_scene_contract_sha256
source_replay_sha256
blocker
```

## Pass Gate

For a 300-frame replay at stride 5:

```text
frames_loaded=300
expected_png_count=60
png_count=60
mp4_ok=true
mesh_scope=false
skeleton_replay_pass=true
skeleton_data_compare_pass=true
max_body_pos_error_m<=1e-6
```

For current Walk/Stop character geom visual validation:

```text
character_geom_compare_pass=true
evih_character_geom_png_count=60
evih_character_geom_mp4_size_bytes>0
evih_character_geom_count>0
evih_character_missing_geom_bodies=[]
mimickit_geom_vs_evih_geom_sheet_exists=true
mesh_scope=false
true_mesh_reference_available=false
```

The skeleton gate is a functional parity gate. The character geom gate proves body-attached MJCF/source-spec geometry rides on the verified skeleton trajectory. Neither gate claims true USD mesh parity, UE parity, Chaos contact validation, or live policy control.

For true USD/white-knight mesh reference validation:

```text
mesh_reference_pass=true
precheck.ok=true
render_summary.visual_kind=mesh
render_summary.mesh_detected=true
render_summary.image_count=60
render_summary.frame_ids=[0,5,...,295]
render_summary.mp4_ok=true
contact_sheet.ok=true
```

If `precheck.ok=false` or `blocker=isaaclab_precheck_failed`, the correct next action is to repair the Isaac Lab environment or run the native Windows helper. Do not mark XML geom outputs as mesh reference success.

For v2 true mesh replay:

```text
evih_mesh_replay_pass=true
mesh_binding_pass=true
scene_contract_compare_pass=true
visual_metric_pass=true
mesh_scope=true
mean_silhouette_iou>=0.90
p10_silhouette_iou>=0.80
mean_centroid_error_diag_ratio<=0.02
p95_centroid_error_diag_ratio<=0.04
bbox_area_ratio_p10>=0.85
bbox_area_ratio_p90<=1.15
```

Any PPM-only output, missing/black/static PNG sequence, invalid MP4, hash
mismatch, scene mismatch, unbound renderable node, missing sword/shield, or XML
geom compatibility fallback is a hard failure.
