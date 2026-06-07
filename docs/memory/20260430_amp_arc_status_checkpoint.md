# AMP / ARC 当前状态 Checkpoint (2026-04-30)

## 最终目标

- 最终目标不是单个 AMP root 跑起来，而是完成 `docs/skill/arc-raiders-industrial-locomotion-skill-v3/SKILL.md` 所定义的 ARC-like 工业化链路：
  - MimicKit AMP 多脑训练
  - render-viz / demo 验证
  - ONNX 与 runtime 数据契约
  - UE5 物理驱动运行时接入
- 当前阶段仍然只处于 **Stage A / MimicKit 学习与单脑长训阶段**。
- 当前最直接的阶段性目标是：
  - 把 `WalkBrain` 的正式长训 root 跑完 `50M probe`
  - 再继续推进到 `1B long_train`
  - 为后续 `TurnBrain` 正式长训与 render-viz 判定打基础

## 目前状态

- snapshot_time: `2026-04-30 22:16:41`
- current_root: `amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637`
- current_brain: `WalkBrain`
- current_case: `amp_location_humanoid_sword_shield`
- current_stage: `probe_train`
- current_stage_status: `running`
- current_probe_progress: `13,172,736 / 50,000,000`
- current_long_progress: `13,172,736 / 1,000,000,000`
- current_checkpoint_health: `warming up`
- current_render_state: `render pending`

当前监测地址：

- local dashboard: `http://127.0.0.1:8789/`
- local pinned root: `http://127.0.0.1:8789/?root=amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637`
- remote pinned root: `http://172.23.99.102:8789/?root=amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637`
- live API: `http://127.0.0.1:8789/api/status`

当前运行态事实：

- tmux sessions:
  - `train_amp`
  - `monitor_amp`
- keepalive root files:
  - `output/train/amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637/keepalive_status.json`
  - `output/train/amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637/keepalive_state.json`
  - `output/train/amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637/runner.log`
  - `output/train/amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637/monitor.log`
- stage artifacts already present:
  - `smoke_train/model.pt`
  - `smoke_train/events.out.tfevents.*`
  - `probe_train/model.pt`
  - `probe_train/events.out.tfevents.*`

本轮之前已经完成的前置成果：

- `docs/plan/ARC_RADIER/AMP_STAGE_A_NEWTON_EXECUTION_20260430.md` 已沉淀：
  - `amp_humanoid`
  - `amp_location_humanoid`
  - `amp_steering_humanoid`
  的 Newton 学习与短训练验证
- AMP 单脑长训配套工具已经落地：
  - `scripts/run_amp_keepalive.py`
  - `scripts/run_amp_dashboard.py`
  - `scripts/watchdog_amp_training.sh`
  - `docs/skill/mimickit-amp-dashboard-skill/SKILL.md`
- `WalkBrain` 正式长训 root 已经启动，不再停留在 validate root

## 和最终目标还差多少

训练侧差距：

- 当前只在 `WalkBrain probe_train`
- 距离完成 `50M probe` 还差 `36,827,264` samples
- 距离完成 `1B long_train` 还差 `986,827,264` samples
- `long_train` 目录和阶段尚未真正开始产出

控制器差距：

- 当前只有 `WalkBrain` 进入正式长训 root
- `TurnBrain` 只有 validate root 验证，不在正式长训中
- `StopBrain`、`StompBrain`、`RecoverBrain` 还未进入正式训练规划

可视化与导出差距：

- 当前是 `render pending`
- 还没有这个 root 自己的 render-viz 产物
- 还没有基于该 root 的 rollout 视觉判定
- 还没有进入 ONNX 导出、schema lock、runtime parity 验证

工业化差距：

- 还未进入多脑 orchestrator / queue 级别的正式训练管理
- 还未固定 `obs_action_spec.yaml`、`normalization_stats.json`、`brain_manifest.json`
- 还未进入 UE5 runtime、Chaos 物理、Behavior Tree / brain switch 的接入验证

## 新会话快速了解与复现入口

文档入口，按优先级阅读：

1. `docs/skill/arc-raiders-industrial-locomotion-skill-v3/SKILL.md`
2. `docs/plan/ARC_RADIER/PLAN-430-a.md`
3. `docs/plan/ARC_RADIER/AMP_STAGE_A_NEWTON_EXECUTION_20260430.md`
4. `docs/skill/mimickit-amp-dashboard-skill/SKILL.md`
5. `docs/methods/README_AMP.md`

skill 入口，按优先级使用：

1. `arc-raiders-industrial-locomotion-skill-v3`
2. `mimickit-amp-dashboard-skill`
3. `mimickit-render-viz-sequence-skill`
4. `mimickit-gpu-efficiency-optimization-skill`

运行态事实入口：

- `output/train/amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637/keepalive_status.json`
- `output/train/amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637/runner.log`
- `output/train/amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637/probe_train/log.txt`
- dashboard API:
  - `http://127.0.0.1:8789/api/status`

最小复现当前状态的操作：

1. 打开 dashboard：
```bash
xdg-open 'http://127.0.0.1:8789/?root=amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637' 2>/dev/null || true
```

2. 查看当前 live 状态：
```bash
curl -s http://127.0.0.1:8789/api/status | /root/miniconda3/envs/mimickit/bin/python -m json.tool | sed -n '1,120p'
```

3. 查看 keepalive 状态文件：
```bash
sed -n '1,220p' output/train/amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637/keepalive_status.json
```

4. 确认后台会话与进程：
```bash
tmux ls
ps -eo pid,ppid,etimes,stat,cmd --sort=etimes | rg 'run_amp_keepalive.py|run_amp_dashboard.py'
```

5. 如果训练中断，用同一 root 重新拉起 keepalive：
```bash
tmux new-session -d -s train_amp \
  '/root/miniconda3/envs/mimickit/bin/python /root/Project/MimicKit/scripts/run_amp_keepalive.py \
  --brain WalkBrain \
  --root-out amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637 \
  --engine-config data/engines/newton_engine.yaml \
  --devices cuda:0 cuda:1 \
  --num-envs 1024 \
  --master-port 40489 \
  --smoke-train-samples 16384 \
  --probe-target-samples 50000000 \
  --long-target-samples 1000000000'
```

6. 如果 dashboard 中断，用同一 root 重新拉起 monitor：
```bash
tmux new-session -d -s monitor_amp \
  '/root/miniconda3/envs/mimickit/bin/python -u /root/Project/MimicKit/scripts/run_amp_dashboard.py \
  --root-out amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637 \
  --brain WalkBrain \
  --target-samples 1000000000 \
  --host 0.0.0.0 \
  --port 8789'
```

## 备注

- 这是一份**短期 checkpoint**，用于新会话快速接手，不替代长期设计文档。
- 如果后续 root 切换、`WalkBrain` 阶段变化、或 `TurnBrain` 正式长训启动，继续新增新的时间戳 memory checkpoint，不覆盖本文件。
