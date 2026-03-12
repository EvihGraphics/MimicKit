# ASE

![ASE](../../images/ASE_teaser.png)

论文主页："ASE: Large-Scale Reusable Adversarial Skill Embeddings for Physically Simulated Characters"  
https://xbpeng.github.io/projects/ASE/index.html

## 0. RL零基础预备知识（先看这一节）

| 术语 | 一句话解释 |
|---|---|
| latent（潜变量 `z`） | 技能开关向量，不同 `z` 会触发不同风格/技能 |
| 策略（Policy） | 根据观测和 `z` 输出动作 |
| 编码器（Encoder） | 从行为反推 `z`，保证技能可辨识 |
| 多样性（Diversity） | 避免不同 `z` 学成同一个动作 |
| 风格奖励 | 对抗分支给出的“像参考风格”评分 |
| 编码器奖励 | 技能可辨识度评分（互信息近似） |
| 推理 | 固定模型，测试技能是否稳定可复现 |
| 可视化 | 观察不同技能在动作形态上的差异 |

本仓库 3 种常用运行模式：
- 训练：`--mode train`。
- 推理：`--mode test --visualize false`。
- 可视化：`--mode test --visualize true`。

## 1. 论文导读（新手版）

### 1.1 论文核心思想

ASE 在 AMP 的对抗模仿基础上，引入可复用技能向量 `z`：
- 低层策略：`pi(a | s, z)`
- 编码器：从行为中恢复 `z`，形成互信息约束

直观理解：
- AMP 学“像不像动作分布”；
- ASE 进一步学“不同 latent 对应不同可控技能”。

### 1.2 读论文重点

1. 为什么要做 latent 条件策略（技能可组合、可迁移）。  
2. 编码器奖励如何提升技能可辨识度。  
3. 多样性损失如何避免所有 latent 学成同一个动作。

## 2. 代码导读（论文机制 -> 源码位置）

### 2.1 运行主链路

- 参数入口：`mimickit/run.py:22`、`mimickit/run.py:95`、`mimickit/run.py:132`
- 环境分发：`mimickit/envs/env_builder.py:8`
- Agent 分发：`mimickit/learning/agent_builder.py:5`
- 训练/测试循环：`mimickit/learning/base_agent.py:51`、`mimickit/learning/base_agent.py:92`

### 2.2 ASE 核心函数

| 论文机制 | 代码入口 |
|---|---|
| latent 条件 actor | `mimickit/learning/ase_model.py:14` |
| latent 条件 critic | `mimickit/learning/ase_model.py:20` |
| 编码器 `q(z|s,s')` 近似 | `mimickit/learning/ase_model.py:26` |
| 奖励融合（disc + enc） | `mimickit/learning/ase_agent.py:186` |
| 编码器奖励 | `mimickit/learning/ase_agent.py:212` |
| 编码器损失 | `mimickit/learning/ase_agent.py:309` |
| latent reset/update/sample | `mimickit/learning/ase_agent.py:95`, `mimickit/learning/ase_agent.py:116`, `mimickit/learning/ase_agent.py:126` |
| 多样性损失 | `mimickit/learning/ase_agent.py:327` |

更细公式对照：`docs/paper_code/README_ASE_TheoryCode.md`

## 3. 训练参数导读（参数意义）

### 3.1 环境参数（`data/envs/ase*_env.yaml`）

| 参数 | 作用 | 调参建议 |
|---|---|---|
| `motion_file` | 训练技能分布来源（dataset） | ASE 建议用 dataset，不建议只用单 clip |
| `num_disc_obs_steps` | 对抗分支时序窗口 | 默认 `10`，动作变化更快可增加 |
| `default_reset_prob` | 默认重置概率 | 提高可增强状态覆盖，过高会扰动收敛 |
| `joint_err_w` | 关节误差加权 | 武器场景要匹配新增关节重要性 |

### 3.2 Agent 参数（`data/agents/ase_humanoid_agent.yaml`）

| 参数 | 作用 | 调参建议 |
|---|---|---|
| `model.latent_dim` | latent 维度（技能容量） | 默认 `64`；增大可表达更丰富，训练更难 |
| `latent_time_min` / `latent_time_max` | 单个 latent 保持时长 | 太短会抖动，太长会技能切换不灵活 |
| `disc_reward_weight` | 对抗风格奖励权重 | 与 `enc_reward_weight` 共同平衡 |
| `enc_reward_weight` | 编码器互信息奖励权重 | 太低技能不可辨，太高会压策略主目标 |
| `enc_loss_weight` | 编码器监督强度 | 与奖励配合调整，防止编码器欠拟合 |
| `diversity_weight` / `diversity_tar` | 多样性约束强度/目标 | 防 latent collapse 的关键参数 |
| `disc_grad_penalty` | 判别器稳定项 | 默认 `5`，判别器不稳时优先检查 |
| `optimizer.learning_rate` | 学习率 | ASE 默认较低 `2e-5`，更稳但收敛慢 |

执行型全流程请同时参考：

- `docs/guides/README_ASE_FullChain_TrainInferVisual_SOP.md`

当前实现备注：

- `2026-03-12` 已完成一轮 `27/27` ASE smoke validation，覆盖 `LLC/HLC/test/viz/perturb/view_motion`。
- `2026-03-12` 已完成一轮 `24/24` ASE closure regression，汇总文件：`output/train/ase_closure_regression_20260312_145341/results_final.tsv`
- 白骑士 sword/shield 资产已单独固化为 manifest-driven motion library parity，不和 task case 混写。
- `2026-03-12` 已完成一轮 `87/87` 白骑士 per-clip render 验证，索引文件：`output/img/case_ase_reallusion_motion_library_smoke_20260312_143511/infer_viz_index.tsv`
- headless 可视化与离线渲染推荐统一带：
  - `MIMICKIT_VIEWER_HEADLESS=1`
  - `MESA_GL_VERSION_OVERRIDE=3.3`
  - `MESA_GLSL_VERSION_OVERRIDE=330`
- `view_motion` 直接走 `run.py` 时，建议显式加 `--num_envs 1 --test_episodes 1`，并保持默认设备 `cuda:0`

## 4. 任务案例 vs 动作素材

官方 `ASE` 任务口径仍是：

- `Getup`
- `Perturb`
- `ViewMotion`
- `Heading`
- `Location`
- `Reach`
- `Strike`

官网里“白色骑士拿剑盾的很多动作”在本仓库中不解读成额外 task，而是解读成 Reallusion 动作素材库的 coverage。当前 source of truth：

- manifest：`data/motions/reallusion/ase_reallusion_sword_shield_manifest.tsv`
- helper：`tools/ue_bridge/build_ase_reallusion_motion_render_root.py`

当前覆盖口径：

| coverage | 说明 |
|---|---|
| `7` 个官方 task family | 对应本仓库 `ASE` Full Chain |
| `87` 个白骑士动作条目 | `82` 个 train-enabled + `5` 个 fall view-only |

动作来源归类：

| source_pack | 作用 |
|---|---|
| `sword_shield_stunts` | combo / counter / kill / dodge / fall / special_attack |
| `sword_shield_moves` | slash / stab / locomotion / idle / taunt / block / parry |

## 5. 案例覆盖（ASE Full Chain）

| case | env_config | agent_config | motion_file | 参数导读（意义） |
|---|---|---|---|---|
| `ase_humanoid_args.txt` | `data/envs/ase_humanoid_env.yaml` | `data/agents/ase_humanoid_agent.yaml` | `data/datasets/dataset_humanoid_locomotion.yaml` | locomotion 技能集，`disc_reward_weight=0.5`, `enc_reward_weight=0.5` 平衡风格与可辨识技能 |
| `ase_humanoid_sword_shield_args.txt` | `data/envs/ase_humanoid_sword_shield_env.yaml` | `data/agents/ase_humanoid_agent.yaml` | `data/datasets/dataset_humanoid_sword_shield.yaml` | 武器技能集，`joint_err_w` 覆盖 sword 相关关节，保持同一 latent 配置迁移 |
| `ase_getup_humanoid_sword_shield_args.txt` | `data/envs/ase_getup_humanoid_sword_shield_env.yaml` | `data/agents/ase_humanoid_agent.yaml` | `data/datasets/dataset_humanoid_sword_shield.yaml` | LLC getup 预训练，重点看 `recovery_*` 与 `fall_init_prob` |
| `ase_heading_humanoid_sword_shield_args.txt` | `data/envs/ase_heading_humanoid_sword_shield_env.yaml` | `data/agents/ase_hrl_humanoid_agent.yaml` | `data/motions/reallusion/RL_Avatar_Idle_Ready_Motion.pkl` | HLC heading，运行时必须提供 `--llc_model_file` |
| `ase_location_humanoid_sword_shield_args.txt` | `data/envs/ase_location_humanoid_sword_shield_env.yaml` | `data/agents/ase_hrl_humanoid_agent.yaml` | `data/motions/reallusion/RL_Avatar_Idle_Ready_Motion.pkl` | HLC location，对应 upstream `HumanoidLocation` |
| `ase_reach_humanoid_sword_shield_args.txt` | `data/envs/ase_reach_humanoid_sword_shield_env.yaml` | `data/agents/ase_hrl_humanoid_agent.yaml` | `data/motions/reallusion/RL_Avatar_Idle_Ready_Motion.pkl` | HLC reach，3D target + sword-body reward |
| `ase_strike_humanoid_sword_shield_args.txt` | `data/envs/ase_strike_humanoid_sword_shield_env.yaml` | `data/agents/ase_hrl_humanoid_agent.yaml` | `data/motions/reallusion/RL_Avatar_Idle_Ready_Motion.pkl` | HLC strike，target topple / contact / velocity reward |
| `ase_perturb_humanoid_sword_shield_args.txt` | `data/envs/ase_perturb_humanoid_sword_shield_env.yaml` | `data/agents/ase_humanoid_agent.yaml` | `data/datasets/dataset_humanoid_sword_shield.yaml` | test-only robustness case，不进入 trainable 主线 |

`view_motion` 资产验收入口：

- 单动作：`data/envs/view_motion_humanoid_sword_shield_env.yaml`
- dataset yaml：`data/envs/view_motion_humanoid_sword_shield_dataset_env.yaml`
- per-clip motion library：`tools/ue_bridge/build_ase_reallusion_motion_render_root.py`

## 6. 训练/推理/可视化模板

```bash
# 训练
/root/miniconda3/envs/mimickit/bin/python mimickit/run.py \
  --arg_file args/ase_humanoid_args.txt \
  --mode train \
  --engine_config data/engines/newton_engine.yaml \
  --visualize false \
  --out_dir output/train/<run_name>

# 推理（无渲染）
/root/miniconda3/envs/mimickit/bin/python mimickit/run.py \
  --arg_file args/ase_humanoid_args.txt \
  --mode test \
  --engine_config data/engines/newton_engine.yaml \
  --visualize false \
  --num_envs 1 \
  --test_episodes 10 \
  --model_file output/train/<run_name>/model.pt

# 策略可视化
/root/miniconda3/envs/mimickit/bin/python mimickit/run.py \
  --arg_file args/ase_humanoid_args.txt \
  --mode test \
  --engine_config data/engines/newton_engine.yaml \
  --visualize true \
  --num_envs 1 \
  --test_episodes 1 \
  --model_file output/train/<run_name>/model.pt
```

HLC 额外模板：

```bash
/root/miniconda3/envs/mimickit/bin/python mimickit/run.py \
  --arg_file args/ase_heading_humanoid_sword_shield_args.txt \
  --mode train \
  --engine_config data/engines/newton_engine.yaml \
  --visualize false \
  --llc_model_file output/train/<llc_run>/model.pt \
  --out_dir output/train/<hlc_run_name>
```

## 7. 每个案例推理与可视化讲解

统一命令（将 `<case_args>` 替换为下表对应案例）：

```bash
# 推理（指标验证）
/root/miniconda3/envs/mimickit/bin/python mimickit/run.py \
  --arg_file args/<case_args>.txt \
  --mode test \
  --engine_config data/engines/newton_engine.yaml \
  --visualize false \
  --num_envs 1 \
  --test_episodes 10 \
  --model_file output/train/<run_name>/model.pt

# 可视化（技能质检）
/root/miniconda3/envs/mimickit/bin/python mimickit/run.py \
  --arg_file args/<case_args>.txt \
  --mode test \
  --engine_config data/engines/newton_engine.yaml \
  --visualize true \
  --num_envs 1 \
  --test_episodes 1 \
  --model_file output/train/<run_name>/model.pt
```

| case | 推荐 `run_name` | 推理讲解（看什么） | 可视化讲解（看什么） |
|---|---|---|---|
| `ase_humanoid_args.txt` | `ase_humanoid` | 看总回报、风格奖励、编码器奖励是否同时稳定 | 观察同一模型下不同技能是否有明显差异 |
| `ase_humanoid_sword_shield_args.txt` | `ase_humanoid_sword_shield` | 看武器动作场景下是否稳定完成完整回合 | 观察持武器动作是否自然、技能切换是否平滑 |
| `ase_getup_humanoid_sword_shield_args.txt` | `ase_getup_humanoid_sword_shield` | 看跌倒初始化后能否恢复 | 观察恢复窗口是否连续、不是地面抖动 |
| `ase_heading_humanoid_sword_shield_args.txt` | `ase_heading_humanoid_sword_shield` | 需加 `--llc_model_file`，看 heading 任务达成 | 看角色速度和朝向是否持续对齐 |
| `ase_location_humanoid_sword_shield_args.txt` | `ase_location_humanoid_sword_shield` | 需加 `--llc_model_file`，看到点成功率 | 看战斗姿态下的目标跟随 |
| `ase_reach_humanoid_sword_shield_args.txt` | `ase_reach_humanoid_sword_shield` | 需加 `--llc_model_file`，看 sword 是否主动逼近目标 | 看 3D 目标点和 sword 末端关系 |
| `ase_strike_humanoid_sword_shield_args.txt` | `ase_strike_humanoid_sword_shield` | 需加 `--llc_model_file`，看 target topple / hit 率 | 看 strike 动作是否能稳定击倒 target |
| `ase_perturb_humanoid_sword_shield_args.txt` | `ase_perturb_humanoid_sword_shield` | robustness test，不做 trainable 主线评价 | 看 projectile 扰动下是否迅速退化 |

## Citation

```bibtex
@article{
	2022-TOG-ASE,
	author = {Peng, Xue Bin and Guo, Yunrong and Halper, Lina and Levine, Sergey and Fidler, Sanja},
	title = {ASE: Large-scale Reusable Adversarial Skill Embeddings for Physically Simulated Characters},
	journal = {ACM Trans. Graph.},
	issue_date = {August 2022},
	volume = {41},
	number = {4},
	month = jul,
	year = {2022},
	articleno = {94},
	publisher = {ACM},
	address = {New York, NY, USA},
	keywords = {motion control, physics-based character animation, reinforcement learning}
}
```
