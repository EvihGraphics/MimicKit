# ARC Skill 并行 Subagent 执行计划

## Summary
- 可以并行，但**不是所有步骤都该并行**。按当前仓库现实，最合理的是把这条链拆成 **1 条 GPU 训练主线 + 3 条外围并行线**。
- 训练主线仍然保持单脑串行推进，因为 `/root/Project/MimicKit` 现有 AMP 编排是 `run_amp_keepalive.py + dashboard + autofinish`，没有现成 `run_amp_series_queue.py`，而且同一台双卡主机上不适合并行跑多个脑训练。
- 真正适合 subagent 并行的是：
  - MimicKit 导出/契约线
  - AI4AnimationPy Demo/Parity 线
  - UE `GASPALS` Shadow/Runtime 线
- 目录锚点已明确：
  - MimicKit：`/root/Project/MimicKit`
  - AI4AnimationPy：`/mnt/d/WorldModel/place_holder/ai4animationpy`
  - UE 工程：`/mnt/d/UE/COLMM/GASPALS`

## Parallel Workstreams
1. **主控 Agent：总编排，不写业务实现**
   - 负责跨阶段依赖、里程碑切换、契约锁定、最终集成判断。
   - 不直接承包某一条实现线，避免和 worker 写同一片文件。

2. **Worker A：Stage A 训练主线，单独占有 MimicKit 训练编排**
   - 所有权：`scripts/run_amp_keepalive.py`、`run_amp_dashboard.py`、`run_amp_autofinish_watch.py`、训练 root、render-viz 判定。
   - 只负责当前活跃脑的训练与验收，例如 `Walk -> Turn -> Stop`。
   - 这条线**不与其他训练 worker 并跑第二个脑**；它是 GPU 临界路径。

3. **Worker B：MimicKit 导出/契约线，可与 Worker A 并行**
   - 所有权：`tools/ue_bridge/*` 与导出包约定。
   - 立即可做：
     - 固化导出包结构
     - 统一 `ONNX + schema + fixture + manifest` 打包入口
     - 用现有稳定 checkpoint（先用 WalkBrain）验证导出链
   - 目标接口固定为一套可复用 package，而不是每个脑临时拼文件。
   - 这条线可以在 `TurnBrain` 训练时同步推进，因为它不抢训练 GPU，也不依赖 `TurnBrain` 最终收敛才开工。

4. **Worker C：AI4AnimationPy Demo/Parity 线，可与 A/B 并行**
   - 所有权：`/mnt/d/WorldModel/place_holder/ai4animationpy`
   - 立即可做：
     - 在现有 `Demos/Locomotion` / `scripts` 体系里确定 ARC locomotion demo 的落点
     - 搭 viewer / runner / trace harness 骨架
     - 先接入 WalkBrain 的稳定导出包，打通最小 ONNX 推理与轨迹回放
   - 必须等待契约锁定后再做：
     - 最终 parity 测试
     - 多脑切换的正式 trace 规范
     - 与 UE 对齐的 deterministic validation trace

5. **Worker D：UE Shadow/Runtime 线，可与 A/B/C 并行**
   - 所有权：`/mnt/d/UE/COLMM/GASPALS`
   - 当前现实：
     - 宿主工程有 `Docs/RuntimeInsertionPoints.md`
     - 已有 `Plugins/GASPALSShadow`，而且是只读观察型插件
     - 还没有文档里那种 `ArcNeuralLocomotion` inference/runtime 插件
   - 立即可做：
     - 扩展 `GASPALSShadow` 的观察字段、日志格式、session manifest
     - 把宿主蓝图/AnimBP/Traversal/Overlay 观测面补齐
     - 先做“只读 Shadow Mode”，不碰正式 locomotion 输出链
   - 必须等待契约锁定后再做：
     - ONNX runner
     - observation builder 的精确维度绑定
     - `brain_manifest` / `normalization_stats` / `obs_action_spec` 的 runtime 消费
     - 真正的 brain selection 与 motor application 接入

## Serial Gates
- **Gate 1：训练主线保持单脑串行**
  - 当前 AMP 侧没有现成多脑串列控制器，`queue-log` 还是 forward-compat 占位。
  - 因此 `Walk / Turn / Stop` 的正式训练不拆给多个训练 subagent 并跑。

- **Gate 2：导出契约由 Worker B 独占**
  - 以下文件集合必须由同一条线定义，不允许 B/C/D 各自发明版本：
    - `policy_actor.onnx`
    - `schema.json`
    - `onnx_export_meta.json`
    - obs fixture / reference actions
    - `obs_action_spec.yaml`
    - `normalization_stats.json`
    - `brain_manifest.json`
    - `joint_order.json`
  - B 锁定后，C 和 D 只能消费，不再各自改格式。

- **Gate 3：Stage B / C 可先做骨架，不能先做最终绑定**
  - C、D 可以在 WalkBrain 稳定产物基础上先做骨架与宿主接入。
  - 但所有“精确维度 / 精确 joint order / 精确 normalization”绑定，都要等 B 的契约锁定。

- **Gate 4：多脑 runtime 切换要等至少 3 脑可用**
  - `Behavior Tree / brain_manifest` 的正式多脑切换，以 `Walk + Turn + Stop` 为第一批。
  - `Stomp / Recover` 可以在 manifest 中预留，但不阻塞前三脑接入。

## Test Plan
- **Worker A**
  - dashboard 能显示当前脑、阶段、samples/s、render 状态
  - autofinish 能产出 render 与 post-train summary
- **Worker B**
  - 同一 checkpoint 可稳定导出 ONNX、schema、fixture、manifest
  - ONNX 与 PyTorch 输出误差在阈值内
- **Worker C**
  - AI4AnimationPy 能加载导出包并复现至少一个脑的推理
  - 能输出 deterministic trace，供 UE 消费
- **Worker D**
  - `GASPALSShadow` 能稳定写 `Saved/Logs/...` 会话数据
  - 不替换 AnimBP 主图，不改宿主 locomotion 输出
  - 在契约锁定后，runtime 层能读取同一套 schema/manifest

## Assumptions
- 默认继续把 `TurnBrain`/`StopBrain` 训练视为同一台双卡机器上的串行主线，不尝试同机并行双脑训练。
- 默认 AI4AnimationPy 与 GASPALS 目录后续实现时都可作为独立 write scope，由独立 subagent 持有。
- 默认先做 UE `Shadow Mode`，后做真正的 neural runtime plugin；不跳过观察/日志阶段直接上 inference 接管。
- 默认不实现 `run_amp_series_queue.py` 作为这轮并行化前提；它可以作为后续可选子任务，但不阻塞现在的四线并行方案。
