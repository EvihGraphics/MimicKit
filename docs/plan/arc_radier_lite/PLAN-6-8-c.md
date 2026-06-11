# PLAN 6-8-c: MimicKit & EvihAnimation 全链路视觉对齐 (Camera Scale & FOV)

## 当前状态与已达成目标
1. **数据桥接完成**：`pose_dof_replay.jsonl`，`scene_contract_v3.json`，以及 `glb` 资产导出均已连通。
2. **真正的 GLB 骨骼绑定修复**：
   - 彻底修复了 IsaacLab 导出 `spherical` 关节 `dof_slice` 缺失导致的 A-pose Bug。
   - 修正了 `local_rest` 和 `joint_rot` 的变换层级顺序，确保所有的骨骼旋转均围绕子物体的局部坐标系原点（也就是骨骼端点）进行 Pivot，这与 Mujoco XML 的物理定义完全一致。
3. **消除坐标系错误**：去除了临时添加的 90 度 Z 轴人工校正，将渲染相机和渲染目标统一到真实的 Isaac Sim World Space 中，模型姿态已在视觉上表现出正确性。

## 当前存在的问题 (Blocker)
尽管模型的动作与 MimicKit 训练参考已经一致，但 **EvihAnimation 的渲染结果在尺寸上几乎是 MimicKit 参考的两倍大**：
- Mimic BBox Height 约 `134px`
- Evih BBox Height 约 `289px`

这说明我们在 **摄像机投影 (Camera Projection) 或者 渲染管线的缩放处理 (FOV / Scale / Aspect Ratio)** 方面依然存在参数映射误差。主要嫌疑在于：
- Isaac Sim 输出的 `fov_degrees` 可能代表 Horizontal FOV，而目前的 Python Rasterizer 强制将其视为 Vertical FOV 或者处理逻辑相反。
- 或者相机的 `target` 和 `eye` 在两端坐标系上存在着固定的拉长系数（比如单位长度从 cm 转换到了 meters，但在相机距离上有截断）。

## 核心任务目标
**使得两者的渲染结果最终 Bounding Box 以及像素重叠达到 $\text{IoU} \ge 0.9$。**

## 下一步执行计划 (Execution Path)

### Phase 1: 摄像机 FOV 与投影体系排查 (Camera Projection Debugging)
- **校对 FOV 定义**：查阅 IsaacLab / Isaac Sim 对于摄像机配置（特别是 Horizontal vs Vertical FOV）的底层定义，对比 `scene_contract_v3.json` 中的参数。
- **校对 Rasterizer 逻辑**：在 `MimicKitSkeletonReplay.py` 的 `camera_for_frame` 和 `rasterize_triangles` 函数中，重构 Perspective Matrix 构建算法，保证 Aspect Ratio (960x540, 16:9) 和 Focal Length 与物理引擎严格 1:1 对齐。

### Phase 2: 空间尺度校验 (Spatial Scale Alignment)
- 验证 Isaac Sim World Space (Z-up) 下相机的相对距离（`eye - target`）是否与 `glb` 模型的 `1.8m` 身高尺度对齐。
- 如果存在尺度差异，查明是否需要在载入 `.glb` 模型时应用一个缩放常数（例如 `metersPerUnit`）。

### Phase 3: 指标跑分与结果固化 (Metrics Validation & Wrapping)
- 运行 `bbox_check_multi.py` 和 `test_sweep.py` 对比最终修正后的坐标。
- 生成一套完整的 `.png` 序列和合成 `.mp4` 视频，确认 IoU 满足目标（$\ge 0.9$）。
- 输出最终验证报告，宣告 EvihAnimation 到 MimicKit 的 "True-Mesh Replay" 桥接链路全面打通。
