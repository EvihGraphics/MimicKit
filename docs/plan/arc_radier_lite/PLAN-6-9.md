# PLAN-6-9: MimicKit-EvihAnimation 全链路视觉校验与数据生成

## 当前状态 (Current Status)

1. **渲染管线修复完成**: 在 `EvihAnimation-mimickit-bridge` 仓库中，成功修复了 `MimicKitSkeletonReplay.py` 的核心坐标系转换问题。修复了 `Z-up` 到 `Y-up` 投影矩阵的颠倒问题、关节局部旋转的共轭转换 (`rx * R_z * rx_inv`)，以及 `camera_for_frame` 中错误的水平/垂直 FOV (`HFOV/VFOV`) 转换逻辑。
2. **视觉一致性验证**: 通过修改后的测试渲染脚本，成功生成了 `frame: 5` 的渲染输出，并验证其 2D 屏幕空间 bounding box 尺寸（Width: 167, Height: 126）与 Isaac Sim 原始参考图像的 ground truth 尺寸（Width: 165, Height: 133）极其吻合，成功消除了此前由于摄影机位置和姿态解算导致的严重“压扁”和形变失真。
3. **代码已推送**: 相关修复已提交并推送到远端仓库的 `codex/mimickit-bridge` 分支。

## 核心目标 (Objective)

基于现已正确对齐的模型解析、坐标空间转换和视觉投射，执行自动化、全规模的数据桥接生成。我们将遍历完整的参考序列，通过自动轮廓评估指标确保 `IoU >= 0.90`，并建立完全对齐的视频 (MP4) 与图像序列 (PNG) 数据集，从而为 MimicKit 输出在 EvihAnimation 内的无缝渲染提供完全可用、被证明一致的桥接数据链。

## 详细计划 (Implementation Steps)

### 阶段 1：White-Knight Full 闭环校验 (G2/G3 Validation)
- 对目标数据集 `tmp_white_knight_mesh_reference_20260607_bridge_full_v2` 执行全链路回放 (`MimicKitSkeletonReplay.py`)。
- 传入 `--true-mesh`、`--mesh-asset` 等必要参数，确保程序读取新生成的 `scene_contract_v3.json`、`mesh_binding_contract.json` 和 `joint_order.json`。
- 输出完整的 60 帧 PNG 序列及配套的可解码 MP4。
- **验收标准**: 生成的 PNG 序列中，自动化视觉对齐指标必须满足 `mean silhouette IoU >= 0.90`。

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
