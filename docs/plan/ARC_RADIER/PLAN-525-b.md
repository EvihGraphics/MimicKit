# PLAN-525-b：MimicKit → UE 真运行时双闭环

## Summary
- 现状已不是 PLAN-525-a 开头描述的“只有 skeletal_visual_pass”：`StopBrain_long01_probe_source_character_closure` 已有同源角色 `USkeletalMesh` 回放、PNG 序列、MP4、`full_visual_parity=true`。
- 当前真正缺口是 runtime gate 过宽：`MimicKitLivePolicyChaosClosure` 只检查 ONNX 文件存在并读取 `ref_actions.jsonl`，trace 写明 `trace_backed_joint_pd_targets`，不能算真实 UE ONNX 推理或 Chaos 接触闭环。
- 本轮目标：保留已通过的同源视觉闭环，把 live closure 改成真 `ONNX → action → joint motor/PD → Chaos physics/contact`，并禁止 trace fallback 被标为 pass。

## Key Changes
- UE runtime closure：
  - 在 `GASPALSShadow` 增加真实 NNE runner，加载 package 内 `StopBrain.onnx`，用 `obs_fixture.jsonl` 或从 runtime actor 采样出的 163 维 observation 调 `RunSync`，输出 31 维 action。
  - `runtime_trace.jsonl` 必须写 `control_mode=live_nne_joint_pd_targets`、`policy_inference_ran=true`、`trace_fallback_used=false`、每帧 action hash/finite/clamp count/inference latency。
  - `live_policy_control_pass=true` 只允许在真实 NNE 推理成功、action 维度匹配、action 有限、且不是 `ref_actions.jsonl` 回放时置 true。
- Chaos/Physics closure：
  - 用 `/Game/MimicKit/SwordShield/SK_MimicKit_SwordShield` + `PA_MimicKit_SwordShield` 创建测试 actor，固定 flat ground、30 Hz policy、240 Hz physics。
  - 将 31 维 action 按 `joint_order.json` / `runtime_control_contract.json` 映射到 source-character joint target；驱动方式优先使用 PhysicsControl，若该 API 在当前工程不可直接编译，则用 `FConstraintInstance` angular drive/PD motor。
  - 采集 root finite/stability、joint target error、right/left foot contact frames、sliding speed；`chaos_contact_validated=true` 只允许在真实物理 body contact/ground overlap 或 Chaos hit/contact query 证据存在时置 true。
- Gate 与报告修正：
  - `runtime_closure_report.json` 增加 `policy_inference_ran`、`trace_fallback_used`、`physics_simulated`、`joint_drive_applied`、`contact_measurement_source`、`max_foot_sliding_mps`。
  - `mimickit_ue_full_closure_report.json` 的 `combined_pass` 必须要求：source-character visual parity、PNG、MP4、真实 NNE 推理、真实 joint drive、真实 contact validation 全部通过。
  - 现有 trace-backed 结果保留为历史 evidence，但标记为 `closure_mode=trace_backed_smoke`，不得再作为 live/Chaos pass。
- Package consistency：
  - 将 UE Saved 中已存在的 `visual_alignment_contract.json v3`、`skeletal_mapping_contract.json`、`mimickit_source_rig_asset_spec.json`、`runtime_control_contract.json` 回写/同步到 MimicKit `ue_export_probe_gate`，让 MimicKit 仓库也保存完整闭环证据。
  - 保持 `output/img/.../render` 为 golden reference；UE 不直接消费 `output/img`，只用于 diff/contact sheet/report。

## Test Plan
- Build：
  - 编译 `GASPALSEditor Win64 Development`，确认 `GASPALSShadow` 可链接 NNE/PhysicsControl 或 constraint-drive fallback。
- Visual parity regression：
  - 重新跑 `GASPALSShadow.MimicKitSourceCharacterReplayCapture`，确认 `capture_meta.json` 仍为 `source_character_skeletalmesh_replay`，`fallback_renderer=""`，`png_ok=true`，`mp4_ok=true`，`full_visual_parity=true`。
- Runtime closure：
  - 跑 `GASPALSShadow.MimicKitLivePolicyChaosClosure`，确认 `runtime_trace.jsonl` 不含 `trace_backed_joint_pd_targets`，报告中 `policy_inference_ran=true`、`trace_fallback_used=false`、`joint_drive_applied=true`、`physics_simulated=true`。
  - 验证 300 policy frames、30/240 Hz、obs dim 163、action dim 31、action finite、root finite、两脚 contact frames 达阈值、sliding 小于 `runtime_control_contract.json` 阈值。
- Final acceptance：
  - `mimickit_ue_full_closure_report.json` 中 `combined_pass=true`。
  - `docs/memory/20260521_amp_ue_visual_diff_log.md` 追加一条新的 live runtime closure 记录，明确它不是 trace-backed smoke。

## Assumptions
- StopBrain long01 probe 继续作为 canary；Walk/Turn/Stop 扩展等真 live/Chaos gate 通过后再做。
- 第一版真实推理使用 UE 已启用的 `NNERuntimeORT`；后续生产化再切 native ONNX Runtime C++。
- source-equivalent generated SkeletalMesh 仍可作为“同源角色”闭环依据，因为它由 MimicKit XML/USD spec deterministic 生成并记录 source hash。
- 场景一致性先锁定 flat ground、same root basis、meters-to-cm、same capture stride/fps/resolution；复杂地形与 gameplay map 接入不纳入本轮。
