# 论文配置与案例清单（按 `args/*.txt` 自动整理）

本文档面向“按论文方法复现实验”的使用场景，汇总每个论文对应案例的配置入口与运行字段。

## 1. 使用说明

1. 默认 `args/*.txt` 里的后端多为 `isaac_gym_engine.yaml`。
2. 若你使用 Newton，可在运行时覆盖：`--engine_config data/engines/newton_engine.yaml`。
3. `case_type=trainable` 表示具备完整 `train -> test -> visualize` 流程；`nontrainable` 一般仅用于展示/验证。

通用命令模板：

```bash
# 训练
python mimickit/run.py --arg_file args/<case>.txt --mode train --visualize false --out_dir output/train/<run_name>

# 推理
python mimickit/run.py --arg_file args/<case>.txt --mode test --visualize false --num_envs 1 --model_file output/train/<run_name>/model.pt

# 可视化
python mimickit/run.py --arg_file args/<case>.txt --mode test --visualize true --num_envs 1 --model_file output/train/<run_name>/model.pt
```

## 2. 分组统计

| 论文分组 | 案例数 | trainable | nontrainable |
|---|---:|---:|---:|
| DeepMimic 论文 | 7 | 7 | 0 |
| AMP 论文 | 9 | 9 | 0 |
| ASE 论文 | 8 | 7 | 1 |
| ADD 论文 | 5 | 5 | 0 |
| MimicKit 框架与扩展示例 | 9 | 2 | 7 |

## 3. DeepMimic 论文

- 论文导读：`docs/paper/README_DeepMimic_CN.md`
- 方法文档：`docs/methods/README_DeepMimic.md`

| case (`args/*.txt`) | case_type | mode | env_config | agent_config | default_num_envs | max_samples | default_engine |
|---|---|---|---|---|---:|---:|---|
| `deepmimic_g1_ppo_args.txt` | trainable | `train` | `data/envs/deepmimic_g1_env.yaml` | `data/agents/deepmimic_g1_ppo_agent.yaml` | 4096 | - | `data/engines/isaac_gym_engine.yaml` |
| `deepmimic_go2_ppo_args.txt` | trainable | `train` | `data/envs/deepmimic_go2_env.yaml` | `data/agents/deepmimic_go2_ppo_agent.yaml` | 4096 | - | `data/engines/isaac_gym_engine.yaml` |
| `deepmimic_humanoid_awr_args.txt` | trainable | `train` | `data/envs/deepmimic_humanoid_env.yaml` | `data/agents/deepmimic_humanoid_awr_agent.yaml` | 4096 | - | `data/engines/isaac_gym_engine.yaml` |
| `deepmimic_humanoid_ppo_args.txt` | trainable | `train` | `data/envs/deepmimic_humanoid_env.yaml` | `data/agents/deepmimic_humanoid_ppo_agent.yaml` | 4096 | - | `data/engines/isaac_gym_engine.yaml` |
| `deepmimic_humanoid_sword_shield_ppo_args.txt` | trainable | `train` | `data/envs/deepmimic_humanoid_sword_shield_env.yaml` | `data/agents/deepmimic_humanoid_ppo_agent.yaml` | 4096 | - | `data/engines/isaac_gym_engine.yaml` |
| `deepmimic_pi_plus_ppo_args.txt` | trainable | `train` | `data/envs/deepmimic_pi_plus_env.yaml` | `data/agents/deepmimic_pi_plus_ppo_agent.yaml` | 4096 | 150000000 | `data/engines/isaac_gym_engine.yaml` |
| `deepmimic_smpl_ppo_args.txt` | trainable | `train` | `data/envs/deepmimic_smpl_env.yaml` | `data/agents/deepmimic_smpl_ppo_agent.yaml` | 4096 | - | `data/engines/isaac_gym_engine.yaml` |

## 3. AMP 论文

- 论文导读：`docs/paper/README_AMP_CN.md`
- 方法文档：`docs/methods/README_AMP.md`

| case (`args/*.txt`) | case_type | mode | env_config | agent_config | default_num_envs | max_samples | default_engine |
|---|---|---|---|---|---:|---:|---|
| `amp_g1_args.txt` | trainable | `train` | `data/envs/amp_g1_env.yaml` | `data/agents/amp_g1_agent.yaml` | 4096 | - | `data/engines/isaac_gym_engine.yaml` |
| `amp_go2_args.txt` | trainable | `train` | `data/envs/amp_go2_env.yaml` | `data/agents/amp_go2_agent.yaml` | 4096 | - | `data/engines/isaac_gym_engine.yaml` |
| `amp_humanoid_args.txt` | trainable | `train` | `data/envs/amp_humanoid_env.yaml` | `data/agents/amp_humanoid_agent.yaml` | 4096 | - | `data/engines/isaac_gym_engine.yaml` |
| `amp_location_humanoid_args.txt` | trainable | `train` | `data/envs/amp_location_humanoid_env.yaml` | `data/agents/amp_task_humanoid_agent.yaml` | 4096 | - | `data/engines/isaac_gym_engine.yaml` |
| `amp_location_humanoid_sword_shield_args.txt` | trainable | `train` | `data/envs/amp_location_humanoid_sword_shield_env.yaml` | `data/agents/amp_task_humanoid_agent.yaml` | 4096 | - | `data/engines/isaac_gym_engine.yaml` |
| `amp_pi_plus_args.txt` | trainable | `train` | `data/envs/amp_pi_plus_env.yaml` | `data/agents/amp_pi_plus_agent.yaml` | 4096 | 120000000 | `data/engines/isaac_gym_engine.yaml` |
| `amp_smpl_args.txt` | trainable | `train` | `data/envs/amp_smpl_env.yaml` | `data/agents/amp_smpl_agent.yaml` | 4096 | - | `data/engines/isaac_gym_engine.yaml` |
| `amp_steering_humanoid_args.txt` | trainable | `train` | `data/envs/amp_steering_humanoid_env.yaml` | `data/agents/amp_task_humanoid_agent.yaml` | 4096 | - | `data/engines/isaac_gym_engine.yaml` |
| `amp_steering_humanoid_sword_shield_args.txt` | trainable | `train` | `data/envs/amp_steering_humanoid_sword_shield_env.yaml` | `data/agents/amp_task_humanoid_agent.yaml` | 4096 | - | `data/engines/isaac_gym_engine.yaml` |

## 3. ASE 论文

- 论文导读：`docs/paper/README_ASE_CN.md`
- 方法文档：`docs/methods/README_ASE.md`

| case (`args/*.txt`) | case_type | mode | env_config | agent_config | default_num_envs | max_samples | default_engine |
|---|---|---|---|---|---:|---:|---|
| `ase_humanoid_args.txt` | trainable | `train` | `data/envs/ase_humanoid_env.yaml` | `data/agents/ase_humanoid_agent.yaml` | 4096 | - | `data/engines/isaac_gym_engine.yaml` |
| `ase_humanoid_sword_shield_args.txt` | trainable | `train` | `data/envs/ase_humanoid_sword_shield_env.yaml` | `data/agents/ase_humanoid_agent.yaml` | 4096 | - | `data/engines/isaac_gym_engine.yaml` |
| `ase_getup_humanoid_sword_shield_args.txt` | trainable | `train` | `data/envs/ase_getup_humanoid_sword_shield_env.yaml` | `data/agents/ase_humanoid_agent.yaml` | 4096 | - | `data/engines/isaac_gym_engine.yaml` |
| `ase_heading_humanoid_sword_shield_args.txt` | trainable | `train` | `data/envs/ase_heading_humanoid_sword_shield_env.yaml` | `data/agents/ase_hrl_humanoid_agent.yaml` | 4096 | - | `data/engines/isaac_gym_engine.yaml` |
| `ase_location_humanoid_sword_shield_args.txt` | trainable | `train` | `data/envs/ase_location_humanoid_sword_shield_env.yaml` | `data/agents/ase_hrl_humanoid_agent.yaml` | 4096 | - | `data/engines/isaac_gym_engine.yaml` |
| `ase_reach_humanoid_sword_shield_args.txt` | trainable | `train` | `data/envs/ase_reach_humanoid_sword_shield_env.yaml` | `data/agents/ase_hrl_humanoid_agent.yaml` | 4096 | - | `data/engines/isaac_gym_engine.yaml` |
| `ase_strike_humanoid_sword_shield_args.txt` | trainable | `train` | `data/envs/ase_strike_humanoid_sword_shield_env.yaml` | `data/agents/ase_hrl_humanoid_agent.yaml` | 4096 | - | `data/engines/isaac_gym_engine.yaml` |
| `ase_perturb_humanoid_sword_shield_args.txt` | nontrainable | `test` | `data/envs/ase_perturb_humanoid_sword_shield_env.yaml` | `data/agents/ase_humanoid_agent.yaml` | 4096 | - | `data/engines/isaac_gym_engine.yaml` |

## 3. ADD 论文

- 论文导读：`docs/paper/README_ADD_CN.md`
- 方法文档：`docs/methods/README_ADD.md`

| case (`args/*.txt`) | case_type | mode | env_config | agent_config | default_num_envs | max_samples | default_engine |
|---|---|---|---|---|---:|---:|---|
| `add_g1_args.txt` | trainable | `train` | `data/envs/add_g1_env.yaml` | `data/agents/add_g1_agent.yaml` | 4096 | - | `data/engines/isaac_gym_engine.yaml` |
| `add_go2_args.txt` | trainable | `train` | `data/envs/add_go2_env.yaml` | `data/agents/add_go2_agent.yaml` | 4096 | - | `data/engines/isaac_gym_engine.yaml` |
| `add_humanoid_args.txt` | trainable | `train` | `data/envs/add_humanoid_env.yaml` | `data/agents/add_humanoid_agent.yaml` | 4096 | - | `data/engines/isaac_gym_engine.yaml` |
| `add_pi_plus_args.txt` | trainable | `train` | `data/envs/add_pi_plus_env.yaml` | `data/agents/add_pi_plus_agent.yaml` | 4096 | 120000000 | `data/engines/isaac_gym_engine.yaml` |
| `add_smpl_args.txt` | trainable | `train` | `data/envs/add_smpl_env.yaml` | `data/agents/add_smpl_agent.yaml` | 4096 | - | `data/engines/isaac_gym_engine.yaml` |

## 3. MimicKit 框架与扩展示例

- 论文导读：`docs/paper/README_MimicKit_CN.md`
- 方法文档：`docs/methods/README_DeepMimic.md`（vault） / `README.md`（view_motion）

| case (`args/*.txt`) | case_type | mode | env_config | agent_config | default_num_envs | max_samples | default_engine |
|---|---|---|---|---|---:|---:|---|
| `dof_test_humanoid_args.txt` | nontrainable | `train` | `data/envs/dof_test_humanoid_env.yaml` | - | 4 | - | `data/engines/isaac_gym_engine.yaml` |
| `vault_g1_args.txt` | trainable | `train` | `data/envs/vault_g1_env.yaml` | `data/agents/deepmimic_g1_ppo_agent.yaml` | 4096 | - | `data/engines/isaac_gym_engine.yaml` |
| `vault_humanoid_args.txt` | trainable | `train` | `data/envs/vault_humanoid_env.yaml` | `data/agents/deepmimic_humanoid_ppo_agent.yaml` | 4096 | - | `data/engines/isaac_gym_engine.yaml` |
| `view_motion_g1_args.txt` | nontrainable | `test` | `data/envs/view_motion_g1_env.yaml` | - | 4 | - | `data/engines/isaac_gym_engine.yaml` |
| `view_motion_go2_args.txt` | nontrainable | `test` | `data/envs/view_motion_go2_env.yaml` | - | 4 | - | `data/engines/isaac_gym_engine.yaml` |
| `view_motion_humanoid_args.txt` | nontrainable | `test` | `data/envs/view_motion_humanoid_env.yaml` | - | 4 | - | `data/engines/isaac_gym_engine.yaml` |
| `view_motion_humanoid_sword_shield_args.txt` | nontrainable | `test` | `data/envs/view_motion_humanoid_sword_shield_env.yaml` | - | 4 | - | `data/engines/isaac_gym_engine.yaml` |
| `view_motion_pi_plus_args.txt` | nontrainable | `test` | `data/envs/view_motion_pi_plus_env.yaml` | - | 4 | - | `data/engines/isaac_gym_engine.yaml` |
| `view_motion_smpl_args.txt` | nontrainable | `test` | `data/envs/view_motion_smpl_env.yaml` | - | 4 | - | `data/engines/isaac_gym_engine.yaml` |

## 4. 原论文依据与预期结果（参数 -> 效果 -> 验收信号）

说明：你要求按“原版论文”细化，本节按四篇原文整理，并映射到当前仓库可调参数。  
原论文链接：

1. DeepMimic (TOG 2018): https://arxiv.org/abs/1804.02717
2. AMP (TOG 2021): https://arxiv.org/abs/2104.02180
3. ASE (TOG 2022): https://arxiv.org/abs/2205.01906
4. ADD (SIGGRAPH Asia 2025): https://arxiv.org/abs/2505.04961

验收等级沿用 `docs/guides/README_VisualReproductionAcceptance.md` 的 `L1/L2/L3`。  
本节口径是“可复现预期范围”，不是“逐帧等同论文视频”。

### 4.1 DeepMimic（原论文主张与案例预期）

原论文强调三点（对应用户侧结果）：

1. 可模仿高动态动作（包括翻腾/旋转类动作片段）。
2. 在扰动下具备恢复能力，而非只会离线回放。
3. 支持多技能或多动作片段训练。

机制到参数映射（MimicKit）：

| 论文机制 | 代码/配置入口 | 关键参数 | 用户可见效果 | 主要风险 |
|---|---|---|---|---|
| 模仿奖励分解（pose/vel/root/key） | `data/envs/deepmimic_*_env.yaml` | `reward_pose_w` `reward_vel_w` `reward_root_*` `reward_key_pos_w` | 动作形态更贴近参考轨迹 | 权重失衡会出现“像但不稳” |
| 失败早停（ET） | `data/envs/deepmimic_*_env.yaml` | `pose_termination` `pose_termination_dist` | 训练更快淘汰坏样本，提升稳定性 | 阈值过严会抑制探索 |
| 长周期收敛 | `args/*` 运行时覆盖 | `max_samples` | 更高概率达到 `L3` 连贯性 | 墙钟时长大幅上升 |
| 并行采样 | CLI 覆盖 | `--num_envs` | 吞吐提升，收敛更快 | 过高触发 OOM / 多卡不稳 |

案例级预期（DeepMimic 7 例）：

| case | 参考动作源 | 预期视觉结果（L2/L3） | 日志侧应看到 | 优先调参 |
|---|---|---|---|---|
| `deepmimic_humanoid_ppo_args.txt` | `humanoid_spinkick.pkl` | 主动作用链完整，落地后可继续站立/过渡 | `Mean Return` 上升后趋稳 | `num_envs` -> `pose_termination_dist` |
| `deepmimic_humanoid_awr_args.txt` | `humanoid_spinkick.pkl` | 常见为更平滑但收敛略慢 | 早期回报增长偏慢，后期稳定 | 训练预算、学习率/批量（agent） |
| `deepmimic_humanoid_sword_shield_ppo_args.txt` | `RL_Avatar_Atk_2xCombo01` | 攻击链条连续，重心不过度漂移 | 失败回合比例下降 | `reward_key_pos_w`、`pose_termination_dist` |
| `deepmimic_g1_ppo_args.txt` | `g1_walk.pkl` | 步态稳定、接触节奏一致 | episode 长度稳定提升 | `num_envs`、`reward_root_vel_scale` |
| `deepmimic_go2_ppo_args.txt` | `go2_pace.pkl` | 四足节律清晰，不拖腿 | 回报波动收敛 | `pose_termination_dist`、`action_std`（agent） |
| `deepmimic_pi_plus_ppo_args.txt` | `pi_plus_walk.pkl` | 高扭矩平台上保持稳定步态 | 长训后抖动减少 | `max_samples`、`num_envs` 梯度回退 |
| `deepmimic_smpl_ppo_args.txt` | `smpl_walk.pkl` | 人形步行风格自然，肢体相位合理 | `Mean Return` 持续可复测 | `reward_pose_w`、`reward_key_pos_w` |

### 4.2 AMP（原论文主张与案例预期）

原论文核心：将 `what to do`（任务）与 `how to do`（风格）解耦，风格由判别器从动作数据中学习。  
用户侧直观目标：动作“像数据分布”，而非只完成任务。

机制到参数映射（MimicKit）：

| 论文机制 | 代码/配置入口 | 关键参数 | 用户可见效果 | 主要风险 |
|---|---|---|---|---|
| 风格对抗奖励 | `data/agents/amp_*_agent.yaml` | `disc_reward_weight` `disc_reward_scale` | 风格一致性增强 | 过高导致任务性能下降 |
| 任务-风格平衡 | `data/agents/amp_task_humanoid_agent.yaml` | `task_reward_weight` vs `disc_reward_weight` | 任务完成与风格可兼顾 | 失衡会“只像不像”或“只会做任务” |
| 判别器稳定化 | `data/agents/amp_*_agent.yaml` | `disc_grad_penalty` | 训练波动减小 | 过大变慢、过小易震荡 |
| 时序风格观测 | AMP env + agent | `num_disc_obs_steps` | 动作节奏更自然 | 显存与计算开销增大 |

案例级预期（AMP 9 例）：

| case | 数据/任务类型 | 预期视觉结果（L2/L3） | 日志侧应看到 | 优先调参 |
|---|---|---|---|---|
| `amp_humanoid_args.txt` | 单体动作模仿 | 风格自然、动作不僵硬 | `disc_reward_mean` 稳定上行 | `disc_reward_scale` |
| `amp_g1_args.txt` | 机器人步态 | 步态自然、支撑相位一致 | episode 失败率下降 | `num_envs` 与 batch 平衡 |
| `amp_go2_args.txt` | 四足步态 | 节律稳定，转步不突变 | 回报曲线波动收窄 | `disc_reward_weight` |
| `amp_pi_plus_args.txt` | 高扭矩步态 | 视觉风格可用但对预算敏感 | 长训后风格提升明显 | `max_samples`、`num_envs` |
| `amp_smpl_args.txt` | SMPL 动作 | 全身节奏更平滑 | 风格奖励与可视化一致改善 | `disc_reward_scale` |
| `amp_location_humanoid_args.txt` | `task_location` | 到达目标点同时保持动作风格 | 任务指标和风格指标同步可用 | `task_reward_weight` 与 `disc_reward_weight` |
| `amp_location_humanoid_sword_shield_args.txt` | `task_location` + 武器风格 | 目标跟随 + 战斗姿态不塌 | 任务成功率提升且不“僵硬” | 同上 + `disc_grad_penalty` |
| `amp_steering_humanoid_args.txt` | `task_steering` | 转向与速度控制稳定，风格保持自然 | 转向任务指标稳定 | `reward_steering_*` + 任务/风格权重 |
| `amp_steering_humanoid_sword_shield_args.txt` | `task_steering` + 武器风格 | 转向时上肢动作不塌缩 | 任务与风格指标同步可用 | 同上 + `disc_grad_penalty` |

### 4.3 ASE（原论文主张与案例预期）

原论文核心：在 AMP 风格基础上引入技能潜变量 `z`，学习可复用技能嵌入。  
用户侧目标：同一个模型在不同 `z` 下呈现不同技能形态，且可切换。

机制到参数映射（MimicKit）：

| 论文机制 | 代码/配置入口 | 关键参数 | 用户可见效果 | 主要风险 |
|---|---|---|---|---|
| 技能潜变量 | `data/agents/ase_humanoid_agent.yaml` | `model.latent_dim` | 技能表达容量提升 | 维度过大训练变难 |
| 编码器可辨识奖励 | 同上 | `enc_reward_weight` `enc_loss_weight` | 不同 `z` 行为更可区分 | 过高牺牲稳定性 |
| 多样性约束 | 同上 | `diversity_weight` `diversity_tar` | 降低 latent collapse | 过高导致动作发散 |
| 潜变量驻留时间 | 同上 | `latent_time_min` `latent_time_max` | 切换更平滑 | 过短易抖，过长不灵活 |

案例级预期（ASE Full Chain）：

| case | 数据类型 | 预期视觉结果（L2/L3） | 日志侧应看到 | 优先调参 |
|---|---|---|---|---|
| `ase_humanoid_args.txt` | `dataset_humanoid_locomotion.yaml` | 不同 `z` 显示明显步态/节奏差异 | 编码器相关奖励长期可用 | `enc_reward_weight`、`diversity_weight` |
| `ase_humanoid_sword_shield_args.txt` | `dataset_humanoid_sword_shield.yaml` | 技能切换时武器动作不应坍缩 | 多个 latent 的视觉差异可复测 | `latent_time_*`、`diversity_weight` |
| `ase_getup_humanoid_sword_shield_args.txt` | `dataset_humanoid_sword_shield.yaml` | 跌倒后应能恢复，不是躺地抖动 | `Mean Episode Length` 与可视化恢复窗口可复测 | `recovery_steps`、`fall_init_prob` |
| `ase_heading_humanoid_sword_shield_args.txt` | `RL_Avatar_Idle_Ready_Motion.pkl` + `ASEHRL` | 朝向与速度控制稳定，LLC 风格不塌 | HLC 可产出 `model.pt`，且需显式 `--llc_model_file` | `llc_steps`、`task_reward_weight` |
| `ase_location_humanoid_sword_shield_args.txt` | `RL_Avatar_Idle_Ready_Motion.pkl` + `ASEHRL` | 到点同时保持 sword/shield 风格 | `Mean Return` 稳定，目标跟随可视化明确 | 同上 |
| `ase_reach_humanoid_sword_shield_args.txt` | `RL_Avatar_Idle_Ready_Motion.pkl` + `ASEHRL` | sword 末端主动追目标点 | 3D reach 目标可持续命中 | `llc_steps`、`task_reward_weight` |
| `ase_strike_humanoid_sword_shield_args.txt` | `RL_Avatar_Idle_Ready_Motion.pkl` + `ASEHRL` | 能对物理 target 施加稳定击倒 | target topple / contact 结果可见 | `llc_steps`、`task_reward_weight` |
| `ase_perturb_humanoid_sword_shield_args.txt` | perturb robustness | projectile 扰动下不应立刻退化 | test/viz 稳定触发 projectile | `perturb_interval`、`projectile_speed_*` |

### 4.4 ADD（原论文主张与案例预期）

原论文核心：用“差分判别器”替代复杂手工多目标加权。  
用户侧目标：减少手工奖励工程后仍保持高保真动作质量。

机制到参数映射（MimicKit）：

| 论文机制 | 代码/配置入口 | 关键参数 | 用户可见效果 | 主要风险 |
|---|---|---|---|---|
| 差分对抗奖励 | `data/agents/add_*_agent.yaml` | `disc_reward_weight` `disc_reward_scale` | 动作更快贴近参考 | 过高压制探索 |
| 判别器平滑与稳定 | 同上 | `disc_grad_penalty` | 训练更稳定 | 过低震荡，过高变慢 |
| 差分归一化 + replay | `mimickit/learning/diff_normalizer.py` 等 | 缓冲大小/采样配置 | 减少训练漂移 | 配置不足会不稳 |
| 长周期精修 | `args/add_pi_plus_args.txt` 等 | `max_samples` | 后期连贯性和稳定性持续提升 | 训练成本高 |

案例级预期（ADD 5 例）：

| case | 参考动作源 | 预期视觉结果（L2/L3） | 日志侧应看到 | 优先调参 |
|---|---|---|---|---|
| `add_humanoid_args.txt` | `humanoid_spinkick.pkl` | 动作完整性高，后期稳定性提升明显 | 风格相关奖励逐步稳定 | `disc_grad_penalty` |
| `add_g1_args.txt` | `g1_walk.pkl` | 步态拟合快，稳定性好 | episode 成功样本占比提升 | `num_envs` 与 `disc_reward_scale` |
| `add_go2_args.txt` | `go2_pace.pkl` | 四足节律保持较好 | 回报曲线中后期更平稳 | `action_std`、`disc_grad_penalty` |
| `add_pi_plus_args.txt` | `pi_plus_walk.pkl` | 对预算敏感，长训后质量提升更明显 | 早期波动，后期收敛 | `max_samples`、`env_ladder` |
| `add_smpl_args.txt` | `smpl_walk.pkl` | 全身动作自然度提升 | 风格奖励与视觉一致改善 | `disc_reward_scale` |

### 4.5 MimicKit 框架扩展示例（vault / view_motion / dof_test）

这组不等同于四篇方法论文的主对比集，定位是流程和资产验证：

| 类型 | case | 预期效果 | 不应误解 |
|---|---|---|---|
| 框架任务扩展 | `vault_g1_args.txt`, `vault_humanoid_args.txt` | 看到接近-起跳-越障-落地链路 | 不是标准论文基准分数对齐 |
| 资产回放 | `view_motion_*` | 稳定回放动作数据与渲染链路 | 不代表策略训练质量 |
| 关节检查 | `dof_test_humanoid_args.txt` | 验证动作空间/关节控制通路 | 不用于评价“论文级观感” |

### 4.6 分阶段观测模板（建议直接用于复盘）

| 训练进度（按样本或时间预算） | 典型状态 | 可视化应看到 | 若不符合先查 |
|---|---|---|---|
| 0% -> 10% | 探索期，波动大 | 动作可能不稳但不应完全僵死 | 学习率、`num_envs`、OOM/NCCL |
| 10% -> 40% | 结构形成期 | 主动作链出现，失败率下降 | 奖励权重平衡、判别器过强/过弱 |
| 40% -> 80% | 质量提升期 | 连贯性显著改善，抖动减少 | `disc_grad_penalty`、终止阈值 |
| 80% -> 100% | 精修期 | 细节稳定性提升，接近 `L3` | 是否需要更长预算与更小步长 |

## 5. 复现实操建议（按论文）

1. DeepMimic/AMP/ASE/ADD 的主论文案例优先使用各自前缀 `args`（`deepmimic_*` / `amp_*` / `ase_*` / `add_*`）。
2. `view_motion_*` 是“动作数据可视化案例”，用于检查 motion 数据与渲染，不代表策略训练质量。
3. `vault_*` 属于框架扩展示例（任务环境扩展），可用于验证方法泛化与障碍交互。
4. 若目标是论文/README 视觉复现，请结合：`docs/guides/README_VisualReproductionAcceptance.md`。
5. 训练预算建议使用“两阶段”：
   - 先全量 `8h/case` 获取首轮结果与失败清单。
   - 再对未达标案例补到 `24h/case`（重点关注 `pi_plus` 与通信敏感案例）。

推荐命令模板（全案例）：

```bash
# pass-1: 8h
python -u scripts/run_case_longcycle.py \
  --engine-config data/engines/newton_engine.yaml \
  --devices-train cuda:0,cuda:1 \
  --include-nontrainable \
  --long-mode time_budget \
  --long-budget-hours 8 \
  --long-success-policy budget_checkpoint \
  --root-out case_ultralong_8h_<ts>

# pass-2: 同 root 补到 24h
python -u scripts/run_case_longcycle.py \
  --engine-config data/engines/newton_engine.yaml \
  --devices-train cuda:0,cuda:1 \
  --include-nontrainable \
  --long-mode time_budget \
  --long-budget-hours 24 \
  --long-success-policy budget_checkpoint \
  --root-out case_ultralong_8h_<ts> \
  --resume-skip-status ok
```

## 6. 维护方式

当 `args/*.txt` 新增或修改后，建议重新生成本文档，保证案例清单与配置字段同步。

## 7. 论文图示主题对照（Figure-Level）

说明：本节基于原论文 arXiv 源码（`e-print`）中的图注主题，映射到当前仓库 `args/*.txt`。  
对齐等级定义：

1. `Direct`：同方法、同任务族、同类型角色可直接对照。
2. `Partial`：方法一致但任务/角色/数据集不完全一致。
3. `Gap`：当前仓库缺少对应任务或角色，不建议硬对齐。

### 7.1 DeepMimic（1804.02717）图示对照

| 原论文图示主题（caption 摘要） | 对应仓库 case | 对齐等级 | 复现时重点 |
|---|---|---|---|
| “various skills” 多技能模仿快照 | `deepmimic_humanoid_ppo_args.txt`, `deepmimic_humanoid_awr_args.txt` | Direct | 重点看高动态动作链是否连续、落地后能恢复 |
| “different morphologies” 多形体角色 | `deepmimic_g1_ppo_args.txt`, `deepmimic_go2_ppo_args.txt`, `deepmimic_smpl_ppo_args.txt` | Partial | 可验证跨形体可训练性，但不是论文原角色全集 |
| “traversing terrains / stepping stones” 地形交互 | `vault_humanoid_args.txt`, `vault_g1_args.txt` | Partial | 验证障碍交互链路，不是论文完全同场景 |
| “with vs without RSI/ET learning curves” | `deepmimic_*` 全系 | Direct | 通过 `pose_termination*` 与初始化策略对比训练稳定性 |
| “throw task without imitation reward” | 当前无直接 case | Gap | 需新增任务环境与纯任务奖励配置 |

### 7.2 AMP（2104.02180）图示对照

| 原论文图示主题（caption 摘要） | 对应仓库 case | 对齐等级 | 复现时重点 |
|---|---|---|---|
| “single-clip imitation tasks” | `amp_humanoid_args.txt`, `amp_g1_args.txt`, `amp_go2_args.txt`, `amp_smpl_args.txt`, `amp_pi_plus_args.txt` | Direct | 看 `disc_reward_mean` 稳定性与风格自然度 |
| “Target Heading policies” | `amp_steering_humanoid_args.txt`, `amp_steering_humanoid_sword_shield_args.txt` | Direct | 看转向任务达成与风格保持是否同时成立 |
| “various tasks and datasets” | `amp_location_*`, `amp_steering_*` | Direct | 任务与风格双目标是否平衡（`task/disc` 权重） |
| “compare to latent/no-data baselines” | `amp_*` + 以 `deepmimic_*`/scratch 作对照 | Partial | 仓库可做方法对照，但不保证与论文同数据同种子 |
| “T-Rex / Dog non-humanoid results” | `amp_go2_args.txt`（四足近似） | Partial | 方法族一致，角色不一致（Go2 != Dog/T-Rex） |

### 7.3 ASE（2205.01906）图示对照

| 原论文图示主题（caption 摘要） | 对应仓库 case | 对齐等级 | 复现时重点 |
|---|---|---|---|
| “pre-train + transfer framework” | `ase_humanoid_args.txt`, `ase_humanoid_sword_shield_args.txt`, `ase_heading_humanoid_sword_shield_args.txt`, `ase_location_humanoid_sword_shield_args.txt`, `ase_reach_humanoid_sword_shield_args.txt`, `ase_strike_humanoid_sword_shield_args.txt` | Direct | 先验证 LLC latent 技能库，再验证 HLC task transfer |
| “random latent samples produce diverse skills” | `ase_*` 两例 | Direct | 固定模型下切不同 latent，观察行为差异 |
| “tasks with simple rewards” | `ase_heading_humanoid_sword_shield_args.txt`, `ase_location_humanoid_sword_shield_args.txt`, `ase_reach_humanoid_sword_shield_args.txt`, `ase_strike_humanoid_sword_shield_args.txt` | Direct | HLC case 已单独暴露，并要求 `--llc_model_file` |
| “motion transition matrix / frequency analysis” | `ase_*` + 离线日志分析 | Partial | 需要额外脚本统计转移频率，不是开箱即得 |
| “recovery after falling” | `ase_getup_humanoid_sword_shield_args.txt`, `ase_perturb_humanoid_sword_shield_args.txt` | Direct | getup 与 perturb 已拆成单独 case |

### 7.4 ADD（2505.04961）图示对照

| 原论文图示主题（caption 摘要） | 对应仓库 case | 对齐等级 | 复现时重点 |
|---|---|---|---|
| “humanoid skills with ADD” | `add_humanoid_args.txt`, `add_smpl_args.txt` | Direct | 看模仿质量与后期稳定性提升 |
| “compare ADD vs AMP/DeepMimic learning curves” | `add_*` + `amp_*` + `deepmimic_*` 同动作源对照 | Direct | 统一预算下对比收敛速度和稳定性 |
| “gradient penalty ablation” | `add_*` 全系（改 `disc_grad_penalty`） | Direct | 做多档 GP 扫描，观察震荡/收敛速度变化 |
| “Go1 quadruped locomotion” | `add_go2_args.txt` | Partial | 四足任务可复现方法趋势，但角色型号不同 |
| “EVAL / Walker benchmark” | 当前无直接 case | Gap | 需新增对应机器人资产与任务环境 |

### 7.5 最小可执行对照清单（建议）

1. DeepMimic 图示族：`deepmimic_humanoid_ppo_args.txt` + `vault_humanoid_args.txt`
2. AMP 图示族：`amp_humanoid_args.txt` + `amp_steering_humanoid_args.txt`
3. ASE 图示族：`ase_humanoid_args.txt`
4. ADD 图示族：`add_humanoid_args.txt` + `add_go2_args.txt`

若目标是“严格论文图号逐项复现”，先从 `Gap` 项补资产/环境，再跑长周期训练。
