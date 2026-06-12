# PLAN-6-9: MimicKit-EvihAnimation 全链路视觉校验与数据生成

## 当前状态 (Current Status)

1. **正式实现 worktree**：
   `/mnt/d/AnimationTech-learning/EvihAnimation-mimickit-bridge-v3`，
   分支 `codex/mimickit-bridge-v3`。旧 dirty checkout 与历史 artifacts
   保持只读。
2. **G0 preserved regressions 通过**：Walk/Stop geom baseline 的 60 PNG、
   MP4 与原始 hashes 未漂移，`baseline_protection_pass=true`。
3. **G1 White-Knight smoke 自动门禁通过**：
   MimicKit 与 Evih 均输出 60 RGB、60 silhouette、60 ground-mask PNG 和
   60 帧 H.264 MP4；v3 禁止再用 `[0,5]` 两帧结果充当动态视觉证据。
   Evih 同时输出 60 帧左右同屏 `mimickit_vs_evih_dynamic.mp4`，并将其
   hash 绑定到人工 review。
   data binding、FK、mesh binding、scene/hash、silhouette 和 ground 指标通过。
   Isaac 捕获每帧执行 8 次 RTX settle update，首帧与后续帧的 ground grid
   均稳定；实际小网格间距已固化为 `0.5m`。Evih 使用合同中的方向光
   投射并柔化 ground shadow，`applied_scene_contract.json` 记录实际参数。
4. **G1 动态与自动指标**：MimicKit unique RGB/silhouette 为 `60/20`，
   Evih 为 `20/20`，两端 MP4 均解码出 `60` 个不同帧，
   `dynamic_sequence_pass=true`；mean silhouette IoU
   `0.924255`、p10 `0.888288`，ground-mask mean IoU `0.980994`、p10
   `0.977996`，RGB report-only MAE `0.021496`。
5. **G1 最终门禁仍失败**：`visual_review.json` 保持默认失败，必须由具名
   reviewer 完成九项 checklist 后才允许 G2。
   Review 模板绑定当前 Mimic manifest、mesh、scene、comparison sheet 和
   两端 RGB frame-set hashes；陈旧 review 会 fail closed。
6. **G2/G3 未启动**：严格编排器拒绝越过未验收 G1，当前 blocker 为
   `previous_gate_not_accepted:white-knight-smoke`。动态 smoke root 仍与最终
   White-Knight full-chain root 分离。

当前证据：

```text
output/train/tmp_white_knight_mesh_reference_20260611_bridge_smoke_v3/bridge_case_manifest.json
output/img/mimickit_evih_bridge_v3/plan_6_9_execution_manifest.json
output/img/mimickit_evih_bridge_v3/full_chain_bridge_manifest.json
/mnt/d/AnimationTech-learning/EvihAnimation-mimickit-bridge-v3/Demos/MimicKitReplay/results/white_knight_mesh_replay_v3_smoke/evih_mesh_replay/comparison_sheet.md
/mnt/d/AnimationTech-learning/EvihAnimation-mimickit-bridge-v3/Demos/MimicKitReplay/results/white_knight_mesh_replay_v3_smoke/evih_mesh_replay/dynamic_sequence_report.json
/mnt/d/AnimationTech-learning/EvihAnimation-mimickit-bridge-v3/Demos/MimicKitReplay/results/white_knight_mesh_replay_v3_smoke/evih_mesh_replay/mimickit_vs_evih_dynamic.mp4
```

严格执行入口：

```bash
PYTHONPATH=tools/ue_bridge python tools/ue_bridge/run_plan_6_9_bridge.py --gate preflight
PYTHONPATH=tools/ue_bridge python tools/ue_bridge/run_plan_6_9_bridge.py --gate status
PYTHONPATH=tools/ue_bridge python tools/ue_bridge/run_plan_6_9_bridge.py --gate white-knight
```

编排器没有 unreviewed-gate bypass。
聚合器还会独立验证 review evidence 是否绑定当前 Mimic manifest 与
comparison sheet，不能复用旧签署。

## 核心目标 (Objective)

基于现已正确对齐的模型解析、坐标空间转换和视觉投射，执行自动化、全规模的数据桥接生成。我们将遍历完整的参考序列，通过自动轮廓评估指标确保 `IoU >= 0.90`，并建立完全对齐的视频 (MP4) 与图像序列 (PNG) 数据集，从而为 MimicKit 输出在 EvihAnimation 内的无缝渲染提供完全可用、被证明一致的桥接数据链。

## 详细计划 (Implementation Steps)

### 阶段 1：White-Knight Full 闭环校验 (G2 Validation)
- G1 人工验收通过后，生成
  `tmp_white_knight_mesh_reference_20260611_bridge_full_v3` 并执行全链路回放。
- 传入 `--true-mesh`、`--mesh-asset` 等必要参数，确保程序读取新生成的 `scene_contract_v3.json`、`mesh_binding_contract.json` 和 `joint_order.json`。
- 输出完整的 60 帧 PNG 序列及配套的可解码 MP4。
- **验收标准**: 60 RGB + 60 silhouette + 60 ground-mask PNG、可解码
  H.264 MP4、`mean silhouette IoU >= 0.90`、ground-mask 指标通过，且
  具名人工 review 通过。

### 阶段 2：指标汇总与可观测性面板 (Metrics & Dashboard)
- 收集生成的 `visual_metric_report.json` 和 `mesh_binding_report.json`。
- 构建包含视觉结果对比矩阵的 `visual_review.json` 和人工审阅 Markdown (`comparison_sheet.md`)，将原图与新渲染的 True-Mesh 图像同屏拼接。
- 将最终的 `full_chain_bridge_manifest.json` 发送至 Dashboard，确保 MimicKit 可以验证 `evih_mesh_replay_pass = true`，不再存在 blocker。

### 阶段 3：推广至 Exact Training Roots (G4/G5 Scale Out)
- 在确认 White-Knight 的所有桥接逻辑无误后，将此管线分别应用于 `amp_WalkBrain` 的 `long_train` 资产及 `amp_StopBrain` 的 `probe_train` 资产。
- 重复上述全链路导出和渲染操作，确保真实的策略网络训练输出在引擎渲染侧的表现达到 1:1 视觉像素级复原。
- 进行最后的 `Full-Chain Closure` 验证，准备合并入 EvihAnimation 主分支。

## 潜在风险与缓解方案 (Risks & Mitigations)
- **多资产兼容性问题**: 目前针对 `humanoid_sword_shield.glb` 进行的 `Y-up/Z-up` 校准，如果未来武器（剑、盾）成为独立绑定节点或使用了不同的局部静止姿态（Rest Pose），可能需要扩展 `mesh_binding_contract` 来定义各部件的具体 `rx_inv` 偏置。
- **视频帧率对齐**: 在渲染 12fps/30fps 或插帧时可能存在的子帧偏差，我们将通过对比首尾关键帧和 `bbox_area_ratio` 来监控帧滑动。
