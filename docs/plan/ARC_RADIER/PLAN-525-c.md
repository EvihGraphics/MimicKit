# PLAN-525-c：MimicKit → UE 真视觉一致 + 真 Chaos 闭环

## Summary
- 保留已通过的视觉闭环：`StopBrain_long01_probe` 使用 `/Game/MimicKit/SwordShield/SK_MimicKit_SwordShield`、PNG 序列、MP4、`source_character_skeletalmesh_replay`，以 `output/img/.../render` 作为 golden reference。
- 修正当前最大风险：现有 `MimicKitLivePolicyChaosClosure` 的 `physics_simulated/contact` 仍是 kinematic proxy，且 clamp sliding 到阈值；它不能再产生 `combined_pass=true`。
- 本轮目标改为：`UE NNE/ONNX 推理 -> UE 物理 actor observation -> joint motor/PD -> Chaos simulate -> real contact query -> PNG/MP4/report`，禁止 trace、ref action、proxy contact 被标为真闭环。

## Key Changes
- UE runtime gate：
  - 将 `EvaluateRuntimePhysicsProxy` 降级为 `kinematic_contact_proxy`，报告字段只能写 `closure_mode=kinematic_proxy_smoke`，不得设置 `physics_simulated=true`、`chaos_contact_validated=true` 或 `combined_pass=true`。
  - 新建真实 runtime path：spawn source SkeletalMesh + PhysicsAsset actor，启用 physics simulation，在固定 flat ground 中以 `30 Hz policy / 240 Hz physics` 运行 10 秒。
  - NNE runner 加载 package 内 `StopBrain.onnx`，每个 policy tick 从 UE actor body state 组包 163 维 observation，输出 31 维 action，映射到 `joint_order.json` 的 joint drive target。
- 物理与接触：
  - 优先使用 PhysicsControl；若当前 UE 工程编译不可用，则使用 `FConstraintInstance` angular drive/PD motor，且报告写明 `joint_drive_backend`。
  - 接触必须来自真实 UE/Chaos 证据：body overlap、hit/contact query、或 foot collision against ground；不能用 replay foot height 推断。
  - `max_foot_sliding_mps_raw` 和 `max_foot_sliding_mps_scored` 分开记录；不得 clamp raw 值后用于伪装 pass。
- 视觉/媒体：
  - UE capture 必须直接产出 PNG sequence，并由 `tools/ue_bridge/finalize_ue_visual_capture.py` 生成 MP4；PPM 只能作为 legacy sidecar，不能作为 full parity 输入。
  - `mimickit_ue_full_closure_report.json` 的 `combined_pass` 只在以下全部为真时通过：source-character visual parity、PNG、MP4、UE ONNX inference、UE observation source、joint drive applied、Chaos simulated、real contact validated、no trace fallback。
- 契约回写：
  - 将 UE Saved 中最新 `visual_alignment_contract.json`、`skeletal_mapping_contract.json`、`mimickit_source_rig_asset_spec.json`、`runtime_control_contract.json` 回写到 `output/train/.../ue_export_probe_gate/`。
  - 升级 `runtime_control_contract` 到 v2，新增 `observation_source=ue_physics_actor_state`、`contact_measurement_source=chaos_contact_query`、`joint_drive_backend`、`proxy_gate_allowed=false`。

## Public Interfaces
- `runtime_trace.jsonl` 每帧必须包含：`frame`、`observation_dim`、`action_dim`、`observation_source`、`control_mode=live_nne_joint_pd_targets`、`policy_inference_ran=true`、`trace_fallback_used=false`、`joint_drive_applied`、`physics_substeps`、`contact_events`、`action_hash`、`inference_latency_ms`。
- `runtime_closure_report.json` 必须包含：`policy_inference_ran`、`trace_fallback_used`、`physics_simulated`、`joint_drive_backend`、`contact_measurement_source`、`right/left_foot_contact_frames`、`max_foot_sliding_mps_raw`、`max_foot_sliding_mps_scored`、`live_policy_control_pass`、`chaos_contact_validated`。
- `combined_pass=true` 只能出现在 `closure_mode=source_character_visual_parity_plus_live_nne_joint_pd_chaos_contact`，不能出现在任何 `*_proxy_*` 或 `trace_backed_*` mode。

## Test Plan
- Build：编译 `GASPALSEditor Win64 Development`，确认 `GASPALSShadow` 可链接 NNE 与选定 joint drive backend。
- Visual parity regression：重跑 `GASPALSShadow.MimicKitSourceCharacterReplayCapture`，确认 capture mode、source mesh、PNG、MP4、`full_visual_parity=true` 不回退。
- Negative gate：保留/新增 proxy runtime 测试，确认 kinematic proxy 可以生成诊断报告，但 `combined_pass=false`。
- Live closure：跑 `GASPALSShadow.MimicKitLivePolicyChaosClosure`，确认 300 policy frames、obs 163、action 31、30/240 Hz、无 `ref_actions.jsonl` replay、无 trace fallback、真实 joint drive、真实 Chaos contact。
- Final evidence：`mimickit_ue_full_closure_report.json` 为 `combined_pass=true` 后，在 `docs/memory/20260521_amp_ue_visual_diff_log.md` 追加新记录，明确它是真 live/Chaos closure，不是 kinematic proxy。

## Assumptions
- StopBrain `amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01 / StopBrain_long01_probe` 继续作为 canary。
- 第一版 runtime inference 使用当前工程已有 `NNERuntimeORTCpu`；生产化 native ONNX Runtime C++ 后续再切。
- 角色一致性以现有 MimicKit source-equivalent SkeletalMesh 为准：`/Game/MimicKit/SwordShield/SK_MimicKit_SwordShield`，其来源 hash 和 build report 必须保留。
- 场景一致性本轮锁定 flat ground、相同单位换算、相同 root basis、相同 capture stride/fps/resolution；复杂地形和 gameplay map 不纳入本轮。
