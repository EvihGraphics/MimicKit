# PLAN-525-d：MimicKit → UE 真渲染 + 真 Chaos 接触闭环

## Summary
- 当前桥接已经具备：StopBrain ONNX、UE NNE 推理、UE physics actor observation、FConstraintInstance joint drive、PNG/MP4 媒体链路、source-character package。
- 当前失败点很集中：`MimicKitLivePolicyChaosClosure` 最新报告为 `live_policy_control_pass=true`，但 `contact_events=0`、`chaos_contact_validated=false`、`combined_pass=false`。
- 本轮目标改为补齐两个硬门：UE 视觉必须来自真实 UE SceneCapture/RenderTarget，不再用自绘骨架图冒充 full parity；Chaos 接触必须来自真实 foot body 与 flat ground 的碰撞/查询证据。

## Key Changes
- 视觉门升级：
  - 将 `CaptureSourceCharacterReplay` 的 full-parity 输出改为真实 UE transient world 渲染：`/Game/MimicKit/SwordShield/SK_MimicKit_SwordShield` + flat ground + camera/stride/fps 与 MimicKit render 对齐。
  - `RenderSkeletalFrame` 只能保留为 `procedural_skeletal_debug`，不得写 `full_visual_parity=true`。
  - UE 端继续直接输出 PNG sequence；`finalize_ue_visual_capture.py` 生成 MP4；PPM 只允许 legacy/debug sidecar。
- Live runtime 修正：
  - 修正 `BuildUePhysicsObservation`，按 MimicKit `compute_char_obs` 契约组满 163 维：root height、heading-local root rot/vel、joint rot tan-norm、31 维 dof_vel、6 个 key body 相对位置。
  - 初始化 physics actor 时应用 `visual_replay` 第 0 帧 root/pose 作为初始状态，并在报告中写 `initial_state_source=visual_replay_frame0_only`；后续控制不得读 `ref_actions.jsonl` 或 replay action。
  - 修正 foot contact：用 foot body collision/overlap 或 shape sweep against ground 作为主证据，line trace 只能作为诊断字段；记录左右脚 body name、ground distance、contact method、contact frames。
- 契约与报告：
  - 将 UE Saved package 中完整的 `visual_alignment_contract.json`、`skeletal_mapping_contract.json`、`mimickit_source_rig_asset_build_report.json` 回写到本地 `ue_export_probe_gate`。
  - `mimickit_ue_full_closure_report.json` 的 `combined_pass=true` 只允许在 source-character true UE render、PNG、MP4、UE ONNX inference、UE obs、joint drive、Chaos simulated、real foot contact 全部为真时出现。

## Public Interfaces
- `capture_meta.json` 新增/强制：
  - `capture_mode=source_character_skeletalmesh_replay`
  - `render_source=ue_scene_capture_render_target`
  - `target_mesh=/Game/MimicKit/SwordShield/SK_MimicKit_SwordShield`
  - `frame_format=png`
  - `legacy_ppm_written=false`
- `runtime_trace.jsonl` 每帧必须包含：
  - `observation_dim=163`
  - `observation_source=ue_physics_actor_state`
  - `control_mode=live_nne_joint_pd_targets`
  - `policy_inference_ran=true`
  - `trace_fallback_used=false`
  - `joint_drive_applied`
  - `physics_substeps`
  - `contact_events`
  - `contact_query_method`
  - `action_hash`
- `runtime_closure_report.json` 必须包含：
  - `observation_filled_dim=163`
  - `obs_layout_contract=compute_char_obs`
  - `initial_state_source=visual_replay_frame0_only`
  - `contact_measurement_source=chaos_contact_query`
  - `right_foot_contact_frames`
  - `left_foot_contact_frames`
  - `max_foot_sliding_mps_raw`
  - `max_foot_sliding_mps_scored`
  - `chaos_contact_validated`

## Test Plan
- Build `GASPALSEditor Win64 Development`，确认 `GASPALSShadow` 链接 `NNE`、`PhysicsCore`、`ImageWrapper`。
- 运行 `GASPALSShadow.MimicKitSourceRigAssetBuild`，确认 source mesh、skeleton、physics asset 均存在。
- 运行 `GASPALSShadow.MimicKitSourceCharacterReplayCapture`，然后执行 `finalize_ue_visual_capture.py` 和 `build_ue_visual_contact_sheet.py`；验收 `png_ok=true`、`mp4_ok=true`、`source_was_ppm_only=false`、`render_source=ue_scene_capture_render_target`、`full_visual_parity=true`。
- 运行 `GASPALSShadow.MimicKitLivePolicyChaosClosure`；验收 300 policy frames、2400 physics substeps、obs/action 为 163/31、NNE 推理、无 trace fallback、joint drive applied、左右脚 contact frames 均大于 0。
- Negative gate：确认 `kinematic_proxy_report.json` 永远 `combined_pass=false`，自绘/procedural capture 也不能写 full parity。
- 最终在 `docs/memory/20260521_amp_ue_visual_diff_log.md` 追加新记录，明确本次是 true UE render + live NNE + Chaos contact closure。

## Assumptions
- Canary 固定为 `amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01 / StopBrain_long01_probe`。
- UE package 固定为 `/mnt/d/UE/COLMM/GASPALS/Saved/MimicKitPackages/StopBrain_long01_probe`。
- Golden reference 固定为 `output/img/amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/probe_train/render`。
- 本轮继续用 `FConstraintInstance angular SLERP drive`；PhysicsControl 可后续替换，但不阻塞本轮闭环。
