# PLAN-6-9：MimicKit → EvihAnimation v3 全链路视觉闭环

## Summary

- 当前证据：MimicKit v2 full 已有 60 RGB PNG、60 silhouette PNG、有效 MP4；v3 full 尚不存在，且两端均未生成 ground mask。
- 当前 Evih v3 smoke 仅 2 帧，`mean_silhouette_iou=0.1332`；姿态、场景与角色投影仍明显不一致，不能按 bbox 接近宣告通过。
- 新建干净 worktree `/mnt/d/AnimationTech-learning/EvihAnimation-mimickit-bridge-v3`，分支 `codex/mimickit-bridge-v3`。现有 dirty bridge worktree、旧 geom baselines 和历史 artifacts 保持只读。
- `PLAN-6-9` 覆盖 White-Knight、Walk exact、Stop exact、完整 manifest、Dashboard 和人工视觉验收。

## Interface And Implementation Changes

- 扩展 `CaptureFrame/capture_frame()`：
  - 输出 RGB、角色 silhouette、ground mask、实际 eye/target、FOV 与 FOV axis、projection、near/far、renderer version。
  - IsaacLab 使用语义分割分别提取角色和地面；缺失、空白或全屏 mask 均失败。

- 固化严格 `scene_contract_v3.json`：
  - 固定 `960x540`、300 frames、stride 5、12 fps、seed 7。
  - 包含逐帧相机、地面/grid、灯光、颜色空间、debug overlay、renderer 和 source hash。
  - 禁止 null/非有限 FOV；Evih 必须输出实际应用的 `applied_scene_contract.json`，不得复制 source hash 冒充通过。

- 新增 `visual_replay/body_world_replay.jsonl`：
  - 按 `joint_order.body_order` 保存采样帧 authoritative body-world transforms。
  - Evih 仍从 root pose、DOF、source-rig 和 binding contract 计算 FK，再与该 sidecar 比较。
  - 要求 `max_body_pos_error_m<=1e-6`、`max_body_rot_error_rad<=1e-5`、`data_binding_ok=true`。

- 整理 Evih replay：
  - 移植并跟踪正式 replay/build/tests，排除现有 debug 脚本和实验输出。
  - 修复 frame-to-row 映射、坐标系转换、bind-local/FK、相机投影；禁止当前 `frame_id + 1` 隐式偏移。
  - 删除 scene/hash gate bypass；缺场景、hash、binding、剑盾或媒体时 fail closed。
  - 输出 RGB、silhouette、ground-mask PNG、H.264 MP4、FK/binding/scene/metric reports 和 comparison sheet。

- 统一 manifest 与 Dashboard：
  - `bridge_case_manifest.json` 使用稳定 `bridge_case_id` 和 `case_acceptance_pass`。
  - `full_chain_bridge_manifest.json` 使用 `full_chain_bridge_pass`，聚合三个 true-mesh 案例和两个 preserved geom regressions。
  - 修复 Dashboard 当前读取 `bridge_pass` 的字段错误；仅 `case_acceptance_pass/full_chain_bridge_pass=true` 显示 ready。
  - Evih results root 改为可配置，并显示所有 blocker、媒体、报告和人工 review。
  - 自动生成默认失败的 `visual_review.json` 模板；人工确认后才允许最终通过。

## Delivery Gates

1. **G0 可复现性与回归保护**
   - 保持 `output/img/mimickit_evih_bridge_v2/baseline_snapshot.json` 通过。
   - Walk/Stop geom baselines 保持 `mesh_scope=false`、60 PNG、非零 MP4 和原始 hashes。

2. **G1 White-Knight v3 Smoke**
   - Mimic root：`tmp_white_knight_mesh_reference_20260611_bridge_smoke_v3`。
   - Evih result：`white_knight_mesh_replay_v3_smoke`。
   - 精确验证帧 `[0,5]` 的数据绑定、FK、场景、RGB/silhouette/ground mask 和 MP4。

3. **G2 White-Knight v3 Full**
   - Mimic root：`tmp_white_knight_mesh_reference_20260611_bridge_full_v3`。
   - Evih result：`white_knight_mesh_replay_v3`。
   - 60 RGB + 60 silhouette + 60 ground-mask PNG，非零可解码 MP4。
   - `mean silhouette IoU>=0.90`、`p10>=0.80`、mean centroid error `<=0.02`、bbox p10/p90 位于 `[0.85,1.15]`。
   - ground-mask mean IoU `>=0.95`、p10 `>=0.90`；人工 review 通过。

4. **G3 Exact Training Roots**
   - Walk：独立 root `amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637_long_train_exact_mesh_v3`。
   - Stop：独立 root `amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01_probe_train_exact_mesh_v3`。
   - 两者重复 G2 全部门禁，不覆盖原训练 root 或 geom baseline。

5. **G4 Full-Chain And Dashboard**
   - 输出 `output/img/mimickit_evih_bridge_v3/full_chain_bridge_manifest.json`。
   - White-Knight、Walk、Stop 的 `case_acceptance_pass=true`，人工 review 全部通过，Dashboard 显示 ready 且无 blocker。

## Test Plan

- MimicKit：覆盖 ground-mask capture、完整 v3 合同、null FOV、body-world sidecar/hash、黑屏/静帧/PPM-only、MP4规格和 Dashboard manifest 字段。
- Evih：修复现有 5 个测试漂移，并新增 frame mapping、FK golden transforms、scene/hash fail-closed、ground mask、错误 binding、缺剑盾和媒体负向测试。
- 每个 gate 先 smoke 后 full；前序 manifest 未通过时不得进入下一 gate。
- 所有正式 artifact 必须由受版本控制代码重新生成；历史 v2/v3 artifacts 只作为诊断证据。

## Assumptions

- 当前 `rigid_node_tessellation` 作为本轮 source-equivalent true-mesh 接受，但不得宣称为 skinned mesh。
- White-Knight 始终先于 Walk/Stop exact roots。
- 人工 `visual_review.json` 是最终 hard gate，自动流程不得自行将其标记为通过。
- Evih 必须使用 MimicKit 导出的同一 GLB、sidecars 和场景合同；禁止 XML geom fallback 和 PPM-only 成功。
