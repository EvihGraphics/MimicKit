# MimicKit -> EvihAnimation 全链路视觉桥接计划

## Summary
- 保留当前已通过的 Walk/Stop skeleton parity 与 XML geom parity，不覆盖旧结果，不把 `visual_kind=geom` 升级声称为 true mesh。
- 分阶段全链路：先打通 white-knight `humanoid_sword_shield.usd` mesh reference，再扩到 WalkBrain/StopBrain exact training roots。
- MimicKit 侧必须输出 PNG 序列、非零 MP4、manifest、GLB asset；Evih 侧必须用同一 replay sidecar、同一 scene contract、同一角色资产输出 PNG、MP4、side-by-side sheet。
- WSL 缺少 `/root/miniconda3/envs/mimickit-isaaclab`，默认使用 Windows native Isaac Lab，然后 ingest 回 `/root/Project/MimicKit/output/...`。

## Key Changes
- MimicKit mesh reference:
  - 使用 `tools/ue_bridge/build_mimickit_mesh_reference.py --run-native-windows` 生成：
    - smoke: `tmp_white_knight_mesh_reference_20260602_bridge_smoke`, `frames=10`, `frame_stride=5`
    - full: `tmp_white_knight_mesh_reference_20260602_bridge_full`, `frames=300`, `frame_stride=5`
  - manifest 必须包含 `mesh_reference_pass`, `render_summary.visual_kind=mesh`, `mesh_detected=true`, `png_count`, `frame_ids`, `mp4_ok`, `source_was_ppm_only=false`, `scene_contract`, `asset_export`.
  - 固定 Evih v1 资产格式为 GLB：`asset_export.format=glb`、`asset_export.glb_file` 非空；GLTF 可保留为工具能力，但不作为 v1 pass 输入。

- Replay package bridge:
  - 为每个 mesh reference root 写出 `ue_export_mesh_reference/`，包含 `visual_replay/pose_dof_replay.jsonl`, `pose_dof_meta.json`, `joint_order.json`, `mimickit_source_rig_asset_spec.json`, `visual_alignment_contract.json`。
  - white-knight 用 `view_motion_humanoid_sword_shield_mesh_env.yaml` + `isaac_lab_engine.yaml` + `RL_Avatar_Atk_2xCombo01_Motion`。
  - Walk/Stop exact roots 另建 mesh reference root，不覆盖旧 root；复制原 stage 的 model/agent/env 配置，只改 `char_file` 为 USD、加入 `kin_char_file` XML、engine 固定 Isaac Lab，并用同 seed 渲染与导出 package。

- Evih mesh replay:
  - 在 `/mnt/d/AnimationTech-learning/EvihAnimation-skeleton-replay` 实现，不修改 dirty source checkout。
  - 扩展 `Demos/MimicKitReplay/replay_skeleton.py`：新增 `--true-mesh --mesh-asset <glb> --mesh-reference-manifest <json>`。
  - 扩展 `ai4animation/Standalone/MimicKitSkeletonReplay.py`：复用现有 FK，新增 GLB mesh renderer；支持 `skinned` 和 `rigid_node` 两种模式，实际模式写入 manifest。
  - 绑定规则：默认 exact body/joint name mapping；缺少 pelvis、DOF body、key bodies、sword/shield 时 fail 为 `mesh_joint_binding_failed`，不回退 XML geom。

- Result/dashboard:
  - 扩展 `Demos/MimicKitReplay/build_visual_results.py`：仅当 `mesh_reference_pass=true` 时生成 `evih_mesh_replay/frames/`, `mesh_replay.mp4`, `mesh_replay_meta.json`, `mimickit_mesh_vs_evih_mesh_sheet.png`。
  - 更新 `scripts/run_amp_keepalive.py::render_summary` 与 `scripts/run_amp_dashboard.py`，扫描并链接 `mesh_reference_manifest.json`, mesh MP4, Evih `visual_result_manifest.json`, comparison sheets；artifact allowlist 加入 Evih results 目录。

## Test Plan
- 先验回归：WalkBrain/StopBrain 现有 `skeleton_data_compare_pass=true`, `character_geom_compare_pass=true`, 60 PNG, MP4 非零。
- MimicKit white-knight smoke：`image_count=2`, `visual_kind=mesh`, `mesh_detected=true`, `mp4_ok=true`, GLB export ok。
- MimicKit white-knight full：60 PNG, `frame_ids=[0,5,...,295]`, nonzero `render.mp4`, contact sheet, `source_was_ppm_only=false`, `mesh_reference_pass=true`。
- Evih white-knight mesh replay：60 PNG, nonzero `mesh_replay.mp4`, `evih_mesh_replay_pass=true`, `mimickit_mesh_vs_evih_mesh_sheet.png` exists。
- Walk/Stop exact mesh roots repeat the full checks; old geom packages remain green and marked `mesh_scope=false`.
- Negative gates: fail if PPM-only, missing GLB, asset export failed, MimicKit mesh reference failed, missing required mesh joints, or Evih PNG/MP4 missing.

## Assumptions
- Scene defaults are `camera_mode=track`, flat ground, root-follow framing, `960x540`, stride `5`, mesh MP4 fps `12`.
- v1 mesh visual acceptance uses mechanical artifact/trajectory gates plus side-by-side sheet review; no pixel-diff pass gate yet.
- Windows native workspace is `/mnt/d/MimicKitNative/workspace/MimicKit`, conda env is `mimickit-isaaclab-win`.
- Existing Walk/Stop `output/img` baselines are XML geom references and remain valid current-baseline evidence, not true mesh references.
