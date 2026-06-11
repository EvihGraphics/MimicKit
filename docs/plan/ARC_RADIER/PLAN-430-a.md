# MimicKit AMP 学习起步计划（Newton / baseline -> task AMP）

## Summary

- 目标：按 `docs/skill/arc-raiders-industrial-locomotion-skill-v3/SKILL.md` 的 Stage A 学习路径，在 **MimicKit 现有 AMP 能力** 上先完成训练侧入门，而不是立刻做 ARC 资产定制或 UE5 部署。
- 本轮范围：学懂并跑通 `amp_humanoid`、`amp_location_humanoid`、`amp_steering_humanoid`，在 `Newton` 引擎下完成阅读、测试、可视化、短训练、对比总结。
- 截止标准：你能清楚解释 AMP 在本仓库里的 `判别器观测 -> 风格奖励 -> 任务奖励融合 -> task env 扩展`，并能把 `location/steering` 映射到后续 ARC-like Walk/Turn 脑的前置能力。
- 本轮不做：自定义机器人/动作数据、Sword+Shield 任务、ONNX 导出、UE5 接入、AMP dashboard skill 新建。

## Key Changes / Learning Path

- 先固定学习底座，不改代码：
  - 引擎固定为 `data/engines/newton_engine.yaml`。
  - Python 固定为 `/root/miniconda3/envs/mimickit/bin/python`。
  - 入口固定为 `mimickit/run.py`。
- 先读文档和核心代码，顺序固定：
  - `docs/methods/README_AMP.md`
  - `mimickit/run.py`
  - `mimickit/envs/amp_env.py`
  - `mimickit/learning/amp_agent.py`
  - `mimickit/envs/task_location_env.py`
  - `mimickit/envs/task_steering_env.py`
- 阅读时只抓 4 件事：
  - AMP demo/disc 观测是怎么从 motion 和在线 rollout 组出来的。
  - `disc_reward_mean` 是怎么算的，和 task reward 如何加权融合。
  - replay / normalizer / discriminator loss 在哪里生效。
  - `location` 和 `steering` 分别额外加了哪些观测和奖励。
- 案例顺序固定，不跳步：
  1. `amp_humanoid`
     - 目的：先学纯 AMP 风格模仿，理解 `task_reward_weight=0.0`、`disc_reward_weight=1.0`。
     - 关注：单动作 clip、判别器、风格奖励、基础可视化。
  2. `amp_location_humanoid`
     - 目的：再学 “任务奖励 + 风格奖励” 共存。
     - 关注：目标点观测、位置任务奖励、dataset 驱动 locomotion。
  3. `amp_steering_humanoid`
     - 目的：最后学面向 ARC-like 转向控制的 task AMP。
     - 关注：目标方向/朝向/速度、转向奖励、面向控制。
- 每个案例都做同一套动作：
  - 先跑 pretrained `test`。
  - 再跑 `visualize true` 看动作。
  - 再跑一次短训练，确认日志、checkpoint、TB 文件都会生成。
  - 最后写出“这个 case 学到了什么、对应 ARC 哪个脑前置能力”。

## Commands / Artifacts

```bash
# 1) 纯 AMP baseline：预训练测试
/root/miniconda3/envs/mimickit/bin/python mimickit/run.py \
  --arg_file args/amp_humanoid_args.txt \
  --mode test \
  --engine_config data/engines/newton_engine.yaml \
  --visualize false \
  --num_envs 1 \
  --test_episodes 1 \
  --model_file data/models/amp_humanoid_spinkick_model.pt

# 2) 纯 AMP baseline：可视化
/root/miniconda3/envs/mimickit/bin/python mimickit/run.py \
  --arg_file args/amp_humanoid_args.txt \
  --mode test \
  --engine_config data/engines/newton_engine.yaml \
  --visualize true \
  --num_envs 1 \
  --test_episodes 1 \
  --model_file data/models/amp_humanoid_spinkick_model.pt

# 3) 纯 AMP baseline：短训练
/root/miniconda3/envs/mimickit/bin/python mimickit/run.py \
  --arg_file args/amp_humanoid_args.txt \
  --mode train \
  --engine_config data/engines/newton_engine.yaml \
  --visualize false \
  --num_envs 512 \
  --max_samples 5000000 \
  --out_dir output/train/amp_learn_humanoid_newton_<ts>

# 4) location task AMP：预训练测试 + 短训练
# model: data/models/amp_location_humanoid_model.pt
# arg_file: args/amp_location_humanoid_args.txt
# out_dir: output/train/amp_learn_location_newton_<ts>

# 5) steering task AMP：预训练测试 + 短训练
# model: data/models/amp_steering_humanoid_model.pt
# arg_file: args/amp_steering_humanoid_args.txt
# out_dir: output/train/amp_learn_steering_newton_<ts>
```

- 这一阶段把以下接口/产物视为稳定学习对象，不改它们：
  - `arg_file -> env_config + agent_config + engine_config`
  - `output/train/<run>/log.txt`
  - `output/train/<run>/model.pt`
  - `output/train/<run>/agent_config.yaml`
  - `output/train/<run>/env_config.yaml`
  - TensorBoard `events` 文件

## Test Plan

- `amp_humanoid` 必须先通过：
  - `test` 不报错。
  - `visualize true` 能看动作。
  - 短训练能产出 `log.txt` 和 `model.pt`。
- `amp_location_humanoid` 必须确认：
  - 任务目标点逻辑跑通。
  - 日志里能看到 AMP 相关指标持续出现。
  - 可解释 `motion_file` 从单 clip 变成 dataset 后的意义。
- `amp_steering_humanoid` 必须确认：
  - 转向相关 obs/reward 路径跑通。
  - 能解释 `tar_dir / face_dir / tar_speed` 分别控制什么。
  - 能说明它为什么是后续 ARC-like TurnBrain 的前置模板。
- 最终验收：
  - 你能口头或文档化回答 “AMPEnv 在做什么、AMPAgent 在做什么、task env 比 baseline 多了什么”。
  - 你能给出一张 3 行对比表：`case / motion source / task reward / ARC 映射`。
  - 你能明确说出下一阶段从哪里进入：`amp_location_humanoid_sword_shield` 或自定义 ARC locomotion case。

## Assumptions / Defaults

- 默认用 `Newton now`，因为当前环境里 `warp` 可用，`isaacgym` 和 `omni` 不可导入；而 `amp_humanoid` 预训练 `test` 已在 `newton_engine.yaml` 下通过 smoke test。
- 默认从 `Humanoid baseline` 开始，不直接进 sword/shield。
- 默认第一阶段止步于 `Through task AMP`，即先学会 baseline、location、steering 三个 case，不延伸到多脑拆分实现。
- 默认单卡 `cuda:0` + `num_envs=512` 做短训练学习；双卡分布式和 hiutil 调优后置。
- 默认本轮不改仓库代码；若后续进入第二阶段，再规划 `mimickit-amp-dashboard-skill`、render-viz 集成、sword/shield、以及 Walk/Turn/Stop 脑拆分。
