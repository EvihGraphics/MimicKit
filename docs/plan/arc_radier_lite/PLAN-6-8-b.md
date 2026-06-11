# PLAN-6-8：Evih G3→G5 全链路视觉闭环与 Dashboard 验收

## Summary

- 重写 `PLAN-6-8.md`，不再复制 PLAN-6-7，并同步总路线 skill、dashboard skill 与 replay contract。
- 当前状态：
  - G0 Walk/Stop geom baseline snapshot 已通过，继续保持 `mesh_scope=false`。
  - MimicKit white-knight smoke/full 已临时通过：60 RGB PNG、60 silhouette PNG、有效 MP4、完整 package、有效 17-body rigid-node GLB。
  - 当前首个真实 blocker 是 `camera_samples[*].fov_degrees=null` 导致 Evih 崩溃。
  - 临时使用 45° FOV 后，Evih 可生成 60 PNG + MP4，但视觉指标失败：mean silhouette IoU `0.0731`、mean centroid error `0.1674`、bbox p90 `1.9647`，表明 FK、相机和场景应用仍不一致。
- 已锁定路线：
  - Evih 使用确定性离屏渲染器。
  - 自动硬门采用角色轮廓、构图、场景合同和场景掩码指标。
  - RGB 感知差异仅作为报告，由人工 `visual_review.json` 最终确认。

## Interface And Implementation Changes

- **可复现基线**
  - 保留现有 output artifacts 和 baseline hashes，不覆盖旧 Walk/Stop geom roots。
  - 将当前 MimicKit bridge 改动和 Evih replay/build/tests 纳入各自目标分支；旧 dirty source checkout 与损坏的 skeleton-replay worktree保持只读。
  - 所有正式 v3 artifacts 必须从受版本控制的代码重新生成。

- **同源数据与场景合同**
  - 新增严格 `scene_contract_v3.json`；旧 v2 仅用于诊断，不得通过 v3 true-mesh gate。
  - `CaptureFrame` 增加有限有效的 FOV、实际 camera target、projection、near/far、ground mask 和 renderer version。
  - v3 固定 `960x540`、300 frames、stride 5、12 fps、seed 7、45° FOV，并显式应用到 MimicKit 与 Evih。
  - 合同记录 ground/grid、灯光方向和强度、颜色空间、debug overlay 状态；正式参考渲染要求 `debug_overlays=false`。
  - MimicKit 渲染运行同时写出 authoritative replay rows、采样帧 body-world transforms 和媒体，禁止 package 与 render 来自两次独立 simulation。
  - Manifest 记录 `source_replay_sha256`、frame-to-row 映射和 body-pose hash，并要求 `data_binding_ok=true`。

- **角色和 FK 合同**
  - 当前资产明确标记为 `rigid_node_tessellation`，允许作为本轮 source-equivalent true-mesh；不得声明为 skinned mesh。
  - 新增 `mesh_binding_contract.json`：17 个 renderable nodes 必须与 `joint_order.body_order` 一一对应，并记录每个 node 的 body binding 与 bind-local transform。
  - Evih 使用 source-rig、joint order、joint axes 和 bind transforms 做确定性 FK，再用 body-world transform 驱动 rigid GLB nodes；不再依赖 GLB node 名称启发式和重复 root transform。
  - 对采样帧要求 `max_body_pos_error_m<=1e-6`、`max_body_rot_error_rad<=1e-5`。
  - 恢复真正的 skeleton/source-spec geom replay；当前二维加粗骨架不得产生 `character_geom_replay_pass=true`。

- **Evih 场景、媒体和失败语义**
  - Null/非有限 FOV、缺场景字段、hash 不匹配必须返回结构化 blocker，禁止未捕获异常。
  - Evih 输出 RGB、角色 silhouette、ground mask、非零 MP4、applied scene contract、binding/FK/scene/metric reports 和 comparison sheet。
  - `scene_contract_compare_pass` 比较 Evih 实际应用的场景字段与 hash，不得直接复制 source hash。
  - 媒体硬门要求 60 RGB + 60 silhouette + 60 ground-mask PNG，精确 frame IDs，非黑屏、非静态、非 PPM-only；MP4 必须为 H.264、`960x540`、12 fps、60 帧、5 秒。

- **Manifest 与 Dashboard**
  - 每个案例生成稳定 `bridge_case_id` 和 `bridge_case_manifest.json`。
  - `case_acceptance_pass` 必须同时满足：
    `capture_ok && media_ok && asset_ok && package_ok && data_binding_ok && mesh_binding_pass && fk_compare_pass && scene_contract_compare_pass && scene_visual_metric_pass && visual_metric_pass && visual_review_pass && blocker==""`。
  - `full_chain_bridge_manifest.json` 聚合 white-knight、Walk exact、Stop exact；Walk/Stop geom baseline 作为独立回归矩阵，不计入 true-mesh closure。
  - Dashboard 仅以 case/full-chain manifest 判定 `render ready`，删除当前 OR-ready 逻辑。
  - Evih results root 改为可配置；使用 `bridge_case_id + source hashes` 关联结果，并分别链接 MimicKit、Evih、Compare 的 frames、silhouettes、ground masks、MP4、reports 和 reviews。

## Delivery Gates

1. **G0 Reproducibility**
   - 保持 `output/img/mimickit_evih_bridge_v2/baseline_snapshot.json` 通过。
   - 完成代码跟踪、合同负向测试和旧 geom baseline hash 保护。

2. **G1 White-Knight v3 Smoke**
   - Mimic root：`tmp_white_knight_mesh_reference_20260608_bridge_smoke_v3`。
   - Evih result：`white_knight_mesh_replay_v3_smoke`。
   - 精确验证 `[0,5]`，先通过数据绑定、FK、FOV、场景和媒体门。

3. **G2 White-Knight v3 Full**
   - Mimic root：`tmp_white_knight_mesh_reference_20260608_bridge_full_v3`。
   - Evih result：`white_knight_mesh_replay_v3`。
   - 60 帧全部通过；mean silhouette IoU `>=0.90`、p10 `>=0.80`、mean centroid error `<=0.02`、p95 `<=0.04`、bbox p10/p90 位于 `[0.85,1.15]`。
   - Ground-mask mean IoU `>=0.95`、p10 `>=0.90`、horizon error `<=2%` 图像高度。

4. **G3 Exact Training Roots**
   - Walk：从 `amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637/long_train` 建立独立 exact-mesh v3 root。
   - Stop：从 `amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/probe_train` 建立独立 exact-mesh v3 root。
   - 两者重复 white-knight full gate，不覆盖旧 geom roots。

5. **G4 Full-Chain And Dashboard**
   - 输出 `output/img/mimickit_evih_bridge_v3/full_chain_bridge_manifest.json`。
   - 三个 true-mesh 案例、两个 preserved geom baseline、dashboard artifact matrix 全部可见且无 blocker。

## Test Plan

- 扩展 MimicKit 与 Evih 单元测试：null FOV、scene 字段缺失、错误 applied-scene hash、数据/media hash 不匹配、缺 body binding、重复 root transform、假 geom pass、黑屏/静帧/PPM-only、错误 MP4 fps/尺寸/时长。
- 保留并扩展现有 3 个 MimicKit validator tests 和 5 个 Evih true-mesh tests。
- 每个 gate 均先 smoke 再 full；前序 manifest 未通过时不得进入下一阶段。
- Dashboard 测试覆盖：普通 render、geom baseline 或单侧 mesh pass 均不得显示 `render ready`。

## Assumptions

- 当前 MimicKit sword/shield USD 是 rigid-body primitive source；本轮接受完整绑定的 `rigid_node_tessellation`，但不宣称 skinned mesh。
- RGB 感知指标不作为自动硬门；角色、剑盾、姿态、镜头、地面、灯光和明显漂移仍必须通过人工 review。
- 当前 white-knight G1/G2 产物作为有效证据保留，但正式 closure 必须使用 v3 合同从受版本控制状态重新生成。
