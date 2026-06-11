# 修正骨骼对照通道：MimicKit Skeleton Reference vs Evih Skeleton Replay

## Summary

你指出的问题成立：当前 `mimickit_evih_compare_sheet.png` 是 MimicKit geom/UE 渲染对 Evih stick skeleton，不是同类骨骼通道对比。下一步要把 MimicKit baseline 先转成“骨骼动画参考通道”，同时保存数据和视觉结果，再让 Evih replay 与这个 skeleton reference 做数据级和视觉级对照。

目标从“看起来跟 MimicKit render 同步”改为“同一套 skeleton trajectory 是否被 Evih 正确复现”。

## Key Changes

- 在每个结果包下新增 MimicKit skeleton reference：
  - `mimickit_skeleton_reference/skeleton_trajectory.jsonl`
  - `mimickit_skeleton_reference/skeleton_trajectory.npz`
  - `mimickit_skeleton_reference/frames/frame_000000.png ... frame_000059.png`
  - `mimickit_skeleton_reference/skeleton_replay.mp4`
  - `mimickit_skeleton_reference/contact_sheet.png`
- Evih replay 也输出同构数据：
  - `evih_skeleton_replay/skeleton_trajectory.jsonl`
  - `evih_skeleton_replay/skeleton_trajectory.npz`
  - 现有 Evih frames/MP4 可迁入或镜像到 `evih_skeleton_replay/`
- 统一 trajectory 数据字段：
  - `frame`
  - `source_frame_id`
  - `time_seconds`
  - `body_order`
  - `root_pos_m`
  - `root_rot_xyzw`
  - `dof_pos`
  - `global_body_pos_m[body_count,3]`
  - `global_body_rot_xyzw[body_count,4]` 若当前 FK 可稳定导出，否则 v1 先只验 position
- 新增真正的同类 compare 输出：
  - `skeleton_data_compare_report.json`
  - `mimickit_skeleton_vs_evih_skeleton_sheet.png`
  - `skeleton_overlay_contact_sheet.png`
- 旧的 `mimickit_evih_compare_sheet.png` 保留但降级命名/语义为 geom sanity：
  - 重命名或新增 manifest 字段标注为 `geom_render_sanity_sheet`
  - 不再作为 skeleton parity 证据
- 更新 skill 文档：
  - 明确 MimicKit geom render 不是骨骼对照组
  - skeleton parity 必须以 MimicKit skeleton trajectory reference 为基准
  - visual acceptance 使用 skeleton-vs-skeleton sheet，而不是 geom-vs-skeleton sheet

## Data Compare Rules

- MimicKit skeleton reference 只从 sidecars 生成，不从 PNG/MP4 反推：
  - `visual_replay/pose_dof_replay.jsonl`
  - `pose_dof_meta.json`
  - `joint_order.json`
  - `mimickit_source_rig_asset_spec.json` 或 MJCF fallback
- Evih replay 使用同一输入 sidecars，但比较对象是 Evih 实际渲染/导出的 skeleton transforms。
- 对每个 sampled frame 和 body 计算：
  - `max_body_pos_error_m`
  - `mean_body_pos_error_m`
  - `root_pos_error_m`
  - `dof_max_abs_error`
  - `missing_bodies`
  - `extra_bodies`
- v1 pass gate：
  - `body_order_match=true`
  - `source_frame_ids_match=true`
  - `dof_match=true`
  - `max_body_pos_error_m <= 1e-6` 当前直接 FK 路径
  - 若后续切到 Evih Motion/ECS runtime，可放宽到 `1e-4`
  - `skeleton_visual_compare_sheet_exists=true`
  - `skeleton_data_compare_pass=true`

## Visual Results Layout

每个 case 的正式结果包改为：

```text
Demos/MimicKitReplay/results/<case>/
  mimickit_skeleton_reference/
    skeleton_trajectory.jsonl
    skeleton_trajectory.npz
    frames/
    skeleton_replay.mp4
    contact_sheet.png

  evih_skeleton_replay/
    skeleton_trajectory.jsonl
    skeleton_trajectory.npz
    frames/
    skeleton_replay.mp4
    contact_sheet.png

  skeleton_data_compare_report.json
  mimickit_skeleton_vs_evih_skeleton_sheet.png
  skeleton_overlay_contact_sheet.png
  visual_result_manifest.json
```

Walk case:

```text
Demos/MimicKitReplay/results/walkbrain_skeleton_replay/
```

Stop case:

```text
Demos/MimicKitReplay/results/stopbrain_skeleton_replay/
```

## Test Plan

- Rebuild WalkBrain visual results from sidecars:
  - MimicKit skeleton reference data exists
  - Evih skeleton replay data exists
  - `skeleton_data_compare_pass=true`
  - 60 MimicKit skeleton PNGs and 60 Evih skeleton PNGs exist
  - skeleton-vs-skeleton sheet exists
- Rebuild StopBrain visual results with the same checks.
- Verify reports:
  - `source_frame_ids=[0,5,...,295]`
  - `body_order_match=true`
  - `dof_match=true`
  - `max_body_pos_error_m <= 1e-6`
  - `mesh_scope=false`
- Keep geom render sheet only as optional sanity context, never as skeleton parity acceptance.
- Confirm original `/mnt/d/AnimationTech-learning/EvihAnimation` remains untouched.

## Assumptions

- “骨骼动画一致”以 sidecar-derived skeleton trajectory 为真值，而不是 MimicKit PNG/MP4。
- v1 先比较 skeleton positions；rotation comparison only 在导出格式稳定后加入 pass gate。
- 结果继续保存到 Evih clean worktree，不写回 MimicKit `output/`。
