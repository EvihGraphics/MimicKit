# PLAN-526-a：MimicKit → UE Source Character + Live Chaos 双脚接触闭环

## Summary
- 当前视觉桥已闭环：`StopBrain_long01_probe` 的 UE source-character capture 是真实 `SceneCapture/RenderTarget`，PNG/MP4 正常，`full_visual_parity=true`。
- 当前唯一硬 blocker 是 live Chaos runtime：最新报告为 `live_policy_control_pass=true`、`contact_events=300`，但全部来自左脚，`right_foot_contact_frames=0`，所以 `chaos_contact_validated=false`、`combined_pass=false`。
- 本轮只修 runtime 接触闭环与契约同步，不降低验收门槛，不允许 proxy/contact height 或 trace fallback 冒充通过。

## Key Changes
- 修 UE live runtime joint/pose mapping：
  - 在 `GASPALSMimicKitVisualReplayCapture.cpp` 中从 `mimickit_source_rig_asset_spec.json` 读取 MJCF joint axis/gear/stiffness/damping。
  - `LocalRotationForJoint` 和 `ActionTargetRotationForJoint` 的 1DOF hinge 不再硬编码 `FVector::RightVector`，改用 source spec 中的真实 joint axis。
  - spherical joint 继续按 `joint_order.json` 的 3D exp-map 映射，action 维度仍为 31。
- 修 Chaos contact evidence：
  - 验证并记录 `right_foot` / `left_foot` 的 `FBodyInstance`、collision shape count、body bounds、foot location、ground distance、query method。
  - ground 不再只用固定 `z=0` 假设；先读取 contract 中显式 ground 字段，若缺失则用 `visual_replay_frame0` 的 foot body bounds 计算 deterministic support plane，并写入 `ground_alignment_source`。
  - 增加 0.25s deterministic pre-policy physics settle：只使用 frame0 初始 pose 和 frame0 joint drive，不读取后续 replay/ref action；正式计数仍为 300 policy frames。
- 保持 gate 严格：
  - `chaos_contact_validated=true` 必须满足：UE NNE 推理、UE physics observation、joint drive、Chaos simulated、左右脚 contact frames 均 `>= runtime_control_contract.contact.min_contact_frames_per_foot`、raw sliding <= threshold。
  - `combined_pass=true` 仍必须同时满足 source-character visual parity、PNG、MP4、live policy、no trace fallback、real Chaos contact。
- 契约同步：
  - 将 UE Saved package 中最新 `visual_alignment_contract.json`、`skeletal_mapping_contract.json`、`runtime_control_contract.json`、`mimickit_source_rig_asset_build_report.json` 回写到 local `output/train/.../ue_export_probe_gate/`。
  - 修正文档中过时表述：最新失败不是 `contact_events=0`，而是 right-foot contact missing。

## Public Interfaces
- `runtime_trace.jsonl` 新增/保留每帧字段：
  - `right_foot_body_name`、`left_foot_body_name`
  - `right_foot_body_instance_found`、`left_foot_body_instance_found`
  - `right_foot_shape_count`、`left_foot_shape_count`
  - `ground_top_z_m`、`ground_alignment_source`
  - `right_foot_lowest_z_m`、`left_foot_lowest_z_m`
  - existing `observation_dim=163`、`control_mode=live_nne_joint_pd_targets`、`policy_inference_ran=true`、`trace_fallback_used=false`
- `runtime_closure_report.json` 新增 aggregate fields：
  - `pre_policy_settle_substeps`
  - `right_foot_body_validated`
  - `left_foot_body_validated`
  - `ground_alignment_source`
  - `right_foot_contact_frames`
  - `left_foot_contact_frames`
  - `max_foot_sliding_mps_raw`
  - `max_foot_sliding_mps_scored`
- `mimickit_ue_full_closure_report.json` 保持最终硬门：
  - `source_character_replay_pass=true`
  - `full_visual_parity=true`
  - `live_policy_control_pass=true`
  - `chaos_contact_validated=true`
  - `png_ok=true`
  - `mp4_ok=true`
  - `combined_pass=true`

## Test Plan
- Build UE:
  - `GASPALSEditor Win64 Development`
  - 确认 `GASPALSShadow` 仍链接 `NNE`、`PhysicsCore`、`ImageWrapper`。
- Regression visual gate:
  - 跑 `GASPALSShadow.MimicKitSourceCharacterReplayCapture`
  - 跑 `tools/ue_bridge/finalize_ue_visual_capture.py`
  - 跑 `tools/ue_bridge/build_ue_visual_contact_sheet.py`
  - 验收 `render_source=ue_scene_capture_render_target`、`legacy_ppm_written=false`、`png_ok=true`、`mp4_ok=true`、`full_visual_parity=true`。
- Live Chaos gate:
  - 跑 `GASPALSShadow.MimicKitLivePolicyChaosClosure`，输出到 `Saved/MimicKitRuntimeClosures/StopBrain_long01_probe_live_chaos`。
  - 验收 300 policy frames、2400 physics substeps、obs/action 为 163/31、`NNERuntimeORTCpu` 推理、无 trace fallback、joint drive applied。
  - 验收 `right_foot_contact_frames > 0` 且 `left_foot_contact_frames > 0`，`chaos_contact_validated=true`，`combined_pass=true`。
- Negative gate:
  - `kinematic_proxy_report.json` 必须继续 `combined_pass=false`。
  - debug/procedural capture 不得写 `full_visual_parity=true`。
- Memory update:
  - 在 `docs/memory/20260521_amp_ue_visual_diff_log.md` 追加 2026-05-26 live policy/Chaos closure 条目。
  - 在 `docs/memory/20260521_amp_arc_status_checkpoint.md` 追加 Follow-up Delta，记录 source-character visual gate + live NNE + two-foot Chaos contact final status。

## Assumptions
- Canary 固定为 `amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01 / StopBrain_long01_probe`。
- UE package 固定为 `/mnt/d/UE/COLMM/GASPALS/Saved/MimicKitPackages/StopBrain_long01_probe`。
- MimicKit golden reference 固定为 `output/img/amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/probe_train/render`。
- 当前角色一致性以 generated source-equivalent asset 为准：`/Game/MimicKit/SwordShield/SK_MimicKit_SwordShield`；preferred USD mesh import 仍是后续生产化增强，不阻塞本闭环。
