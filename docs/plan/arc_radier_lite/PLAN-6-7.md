# PLAN-6-3 v2：MimicKit → EvihAnimation 全链路视觉一致桥接

## Summary

- 当前真实 blocker 已不是 `carb/omni.kit.usd` import，而是：
  - IsaacLab 渲染路径依赖不存在的私有 `_viewer.get_frame()`，white-knight 当前为 0 PNG、无 MP4。
  - dummy white-knight package 不生成 `joint_order.json`、source rig spec、alignment contract。
  - 当前 380-byte GLB 没有有效 mesh/node，现有 `asset_export.ok=true` 为假阳性。
  - Evih `EvihAnimation-skeleton-replay` worktree 源码和 results 已缺失。
- 新建干净 Evih worktree `/mnt/d/AnimationTech-learning/EvihAnimation-mimickit-bridge`，旧 source checkout 与损坏 worktree均只读保留。
- 保留现有 Walk long、Stop probe geom baseline，始终标记 `mesh_scope=false`；true-mesh 只使用新 exact-mesh roots。
- 最终视觉验收采用自动轮廓/构图指标、感知差异报告和人工 comparison sheet，不采用严格像素相等。

## Interfaces And Implementation

- 在 MimicKit Engine 抽象层新增 `capture_frame(width, height, include_silhouette=True) -> CaptureFrame`：
  - 返回 RGBA、silhouette、实测尺寸、camera eye/target/FOV。
  - IsaacLab 使用 headless Camera/RenderProduct 离屏捕获；render sequence 不再访问 `_viewer`。
  - PNG 必须可解码、非黑屏；MP4 必须通过 `ffprobe`，帧数、fps、时长匹配合同。

- 建立 `scene_contract_v2.json`：
  - 固定 `960x540`、300 frames、stride 5、12 fps、seed 7。
  - 记录逐帧 camera eye/target/FOV、track 规则、坐标系、ground 材质/颜色、灯光、颜色空间和 renderer 版本。
  - MimicKit 与 Evih manifest 均记录同一 source scene-contract SHA256，并要求 `scene_contract_compare_pass=true`。

- 修正 package 与资产 gate：
  - 抽出 policy/dummy 共用 visual-package builder；white-knight dummy 也必须生成 replay、joint order、skeletal mapping、alignment contract 和 source rig spec。
  - White-knight 与 exact builders 均显式运行 source-rig spec builder。
  - 使用结构化 GLB 解析生成 `asset_structure_manifest.json`，要求有效 buffers、nodes、meshes、primitives、顶点和 sword/shield。
  - `skinned` 与完整绑定的 `rigid_node` 均可通过；任何未绑定 renderable node、body compatibility 放行或 XML geom fallback 都失败。

- 在干净 Evih worktree 重建 replay：
  - 提供 `--true-mesh --mesh-asset --mesh-reference-manifest`。
  - 消费同一 replay sidecar、GLB hash 和 scene contract；输出 RGB 与 silhouette PNG、非零 MP4、binding report、scene compare report、visual metric report 和 comparison sheet。
  - 扩展 replay contract，加入 `evih_mesh_replay_pass`、`mesh_binding_pass`、`scene_contract_compare_pass`、`visual_metric_pass` 和明确 blocker。

- Dashboard：
  - 更新 Evih results root 到新 worktree。
  - 仅当对应 manifest pass 时显示 `render ready`；失败 manifest 显示 blocker，不再因文件存在误报 ready。
  - 链接 MimicKit/Evih PNG、MP4、manifest、metric report、人工审查结果和最终聚合 manifest。

## Delivery Gates

1. **G0 Baseline Protection**
   - 快照并保持现有 Walk long、Stop probe geom artifacts hash。
   - 重跑 skeleton/geom regression：60 PNG、可解码 MP4、`max_body_pos_error_m<=1e-6`、`mesh_scope=false`。

2. **G1 White-Knight Smoke**
   - 新 root：`tmp_white_knight_mesh_reference_20260607_bridge_smoke_v2`。
   - 精确生成 frame `[0,5]`、PNG、MP4、完整 package、有效 GLB 和 scene contract。
   - 消除 `viewer not available`、package missing sidecars 和 empty GLB blocker。

3. **G2 White-Knight Full**
   - 新 root：`tmp_white_knight_mesh_reference_20260607_bridge_full_v2`。
   - 60 个精确 PNG、非零可解码 MP4、contact sheet、完整 asset/package，`mesh_reference_pass=true`。

4. **G3 Evih White-Knight**
   - 输出 `results/white_knight_mesh_replay_v2/`。
   - GLB、sidecar、scene hashes 匹配；binding、trajectory、媒体和视觉指标全部通过。

5. **G4 Exact Training Roots**
   - Walk：从 `amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637/long_train` 建立独立 exact-mesh root。
   - Stop：从 `amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/probe_train` 建立独立 exact-mesh root。
   - 两者分别重复 G2-G3；不得覆盖旧 geom roots。

6. **G5 Full-Chain Closure**
   - 生成 `full_chain_bridge_manifest.json`，要求 white-knight、Walk long、Stop probe 全部通过且 blocker 为空。
   - Dashboard 可访问全部最终证据。

## Visual Acceptance

- 自动硬门：
  - 所有对应 frame IDs 存在。
  - mean silhouette IoU `>=0.90`，p10 IoU `>=0.80`。
  - mean centroid error `<=2%` 图像对角线，p95 `<=4%`。
  - bbox area-ratio 的 p10/p90 位于 `[0.85,1.15]`。
  - `motion_visible=true`，无黑屏、重复静帧或 PPM-only。
- RGB 感知差异作为报告和趋势证据，不作为严格像素门。
- 人工 `visual_review.json` 必须确认角色、剑盾、姿态、镜头、地面、灯光、帧配对和明显穿模/漂移均通过。

## Test Plan

- 单元测试覆盖 capture API、dummy visual package、scene-contract compare、GLB 空资产拒绝和 dashboard 状态。
- 负向测试覆盖 PPM-only、空 GLB、缺 joint/weapon、hash 不匹配、scene 不匹配、无 PNG/MP4、compatibility fallback。
- Windows native 依次运行 smoke/full；每阶段通过后才进入 Evih 和 exact roots。
- 更新路线 skill、dashboard skill 和 `PLAN-6-3.md`，使文档与最终 blocker、接口和 gate 一致。

## Assumptions

- 当前闭环范围为 white-knight、Walk long、Stop probe；Stop root 当前没有 `long_train`，不将其虚构为本轮通过项。
- dirty Evih source checkout 与损坏的 skeleton-replay worktree均不修改。
- Evih 必须加载 MimicKit 导出的同一 GLB，不允许 XML geom fallback。
