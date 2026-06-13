# ASE 7-Case L2 参数总表

本文档把 `ASE` 的 `7` 个 trainable case 收敛成一份“可直接执行”的 `L2 可交付` 参数规格。  
目标是：不再从多份文档里拼训练参数，而是固定共享基线、case 专属参数、训练命令模板和验收信号。

说明：

- 本文只覆盖 `7` 个 trainable ASE case：
  - `ase_humanoid`
  - `ase_humanoid_sword_shield`
  - `ase_getup_humanoid_sword_shield`
  - `ase_heading_humanoid_sword_shield`
  - `ase_location_humanoid_sword_shield`
  - `ase_reach_humanoid_sword_shield`
  - `ase_strike_humanoid_sword_shield`
- `perturb` 与 `view_motion` 继续留在验收/资产链路文档，不纳入这份训练参数主表。
- “达到论文效果”在本表中固定解释为：达到 `L2 可交付`，不是 `L3 README/论文级观感`，更不是逐帧复刻视频。

## 1. 共享基线

### 1.1 共享运行参数

| 项目 | 固定值 | 说明 |
|---|---|---|
| Python | `/root/miniconda3/envs/mimickit/bin/python` | 与当前 ASE SOP 保持一致 |
| train engine | `data/engines/newton_engine.yaml` | 训练主口径固定走 Newton |
| train devices | `cuda:0 cuda:1` | 双卡训练基线 |
| train `num_envs` | `4096` | 与 `args/ase_*.txt` 保持一致 |
| `test` | `--num_envs 1 --test_episodes 10` | 指标验证口径 |
| `visualize` | `--num_envs 1 --test_episodes 1` | 视觉验收口径 |
| headless viz | `MIMICKIT_VIEWER_HEADLESS=1` | 统一避免交互式窗口依赖 |
| OpenGL 兼容 | `MESA_GL_VERSION_OVERRIDE=3.3`, `MESA_GLSL_VERSION_OVERRIDE=330` | WSL/headless 建议默认带上 |
| L2 预算 | `8h/case` | 首版规格只锁 `L2`，不混入 `24h` 精修 |

### 1.2 LLC 冻结参数

以下参数固定认 [`data/agents/ase_humanoid_agent.yaml`](/root/Project/MimicKit-ase-fullchain/data/agents/ase_humanoid_agent.yaml)：

| 参数 | 固定值 |
|---|---:|
| `model.latent_dim` | `64` |
| `optimizer.learning_rate` | `2e-5` |
| `steps_per_iter` | `32` |
| `update_epochs` | `5` |
| `batch_size` | `4` |
| `disc_grad_penalty` | `5` |
| `disc_reward_weight` | `0.5` |
| `enc_reward_weight` | `0.5` |
| `task_reward_weight` | `0.0` |
| `enc_loss_weight` | `5.0` |
| `diversity_weight` | `0.01` |
| `diversity_tar` | `1.0` |
| `latent_time_min` | `0.0` |
| `latent_time_max` | `5.0` |

### 1.3 HLC 冻结参数

以下参数固定认 [`data/agents/ase_hrl_humanoid_agent.yaml`](/root/Project/MimicKit-ase-fullchain/data/agents/ase_hrl_humanoid_agent.yaml)：

| 参数 | 固定值 |
|---|---:|
| `model.latent_dim` | `64` |
| `optimizer.learning_rate` | `2e-5` |
| `steps_per_iter` | `32` |
| `update_epochs` | `6` |
| `batch_size` | `4` |
| `llc_steps` | `5` |
| `task_reward_weight` | `0.9` |
| `disc_reward_weight` | `0.1` |

补充规则：

- 所有 HLC case 都必须显式传 `--llc_model_file`。
- HLC 基线统一依赖 sword/shield LLC：
  - `output/train/ase_humanoid_sword_shield_l2/model.pt`

### 1.4 预算执行方式

直接跑单案例时，`run.py` 不会自动在 `8h` 停止，因此本表的 `8h/case` 是墙钟预算口径。  
如果要把预算执行也标准化，优先使用：

```bash
/root/miniconda3/envs/mimickit/bin/python -u scripts/run_case_longcycle.py \
  --engine-config data/engines/newton_engine.yaml \
  --devices-train cuda:0,cuda:1 \
  --long-mode time_budget \
  --long-budget-hours 8 \
  --long-success-policy budget_checkpoint \
  --root-out case_ultralong_8h_<ts>
```

## 2. 7 个案例固定参数

### 2.1 LLC Cases

| case | 数据源 | 固定 env 参数 | 观察指标 | 次级调参旋钮 | L2 通过标准 |
|---|---|---|---|---|---|
| `ase_humanoid_args.txt` | `data/datasets/dataset_humanoid_locomotion.yaml` | `episode_length=10.0`, `default_reset_prob=0.5`, `num_disc_obs_steps=10`, `key_bodies=[head,right_hand,left_hand,right_foot,left_foot]` | `disc_reward_mean`, `enc_reward_mean`, `Mean Return` | `enc_reward_weight`, `diversity_weight` | `train -> test -> visualize` 全通过；不同 latent 有明显步态/节奏差异；无长时间冻结 |
| `ase_humanoid_sword_shield_args.txt` | `data/datasets/dataset_humanoid_sword_shield.yaml` | `episode_length=10.0`, `default_reset_prob=0.5`, `num_disc_obs_steps=10`, `key_bodies` 额外包含 `sword`，使用 sword/shield 版 `joint_err_w` | `disc_reward_mean`, `enc_reward_mean`, `Mean Return` | `latent_time_*`, `diversity_weight` | 武器动作不坍缩；技能切换平滑；test/viz 无大面积摔倒 |
| `ase_getup_humanoid_sword_shield_args.txt` | `data/datasets/dataset_humanoid_sword_shield.yaml` | 在 sword/shield LLC 基线上额外固定 `recovery_episode_prob=0.2`, `recovery_steps=60`, `fall_init_prob=0.1`, `fall_state_steps=150` | `Mean Return`, `Mean Episode Length`, 恢复窗口可视化 | `recovery_steps`, `fall_init_prob` | 跌倒后有明显恢复窗口；不是持续躺地抖动或刚倒就终止 |

### 2.2 HLC Cases

| case | 数据源 | 任务 | 固定 env 参数 | 观察指标 | 次级调参旋钮 | L2 通过标准 |
|---|---|---|---|---|---|---|
| `ase_heading_humanoid_sword_shield_args.txt` | `data/motions/reallusion/RL_Avatar_Idle_Ready_Motion.pkl` | `task_steering` | `tar_speed_min=1.5`, `tar_speed_max=1.6`, `tar_change_time_min=3.3`, `tar_change_time_max=6.7`, `reward_steering_tar_w=0.7`, `reward_steering_face_w=0.3`, `reward_steering_vel_scale=2.0` | `Mean Return`, `Mean Episode Length`, 朝向/速度可视化 | `llc_steps`, `task_reward_weight` | 目标方向持续对齐；速度控制稳定；LLC 风格不塌 |
| `ase_location_humanoid_sword_shield_args.txt` | `data/motions/reallusion/RL_Avatar_Idle_Ready_Motion.pkl` | `task_location` | `tar_speed=1.0`, `tar_change_time_min=3.3`, `tar_change_time_max=6.7`, `tar_dist_max=10.0` | `Mean Return`, `Mean Episode Length`, 到点可视化 | `llc_steps`, `task_reward_weight` | 能稳定到点；战斗姿态不明显塌缩 |
| `ase_reach_humanoid_sword_shield_args.txt` | `data/motions/reallusion/RL_Avatar_Idle_Ready_Motion.pkl` | `task_reach` | `tar_speed=1.0`, `tar_change_time_min=1.7`, `tar_change_time_max=3.3`, `tar_dist_max=1.0`, `tar_height_min=0.2`, `tar_height_max=2.0`, `reach_body_name=sword` | `Mean Return`, `Mean Episode Length`, 目标点命中可视化 | `llc_steps`, `task_reward_weight` | `sword` 末端能持续逼近 3D 目标点 |
| `ase_strike_humanoid_sword_shield_args.txt` | `data/motions/reallusion/RL_Avatar_Idle_Ready_Motion.pkl` | `task_strike` | `strike_body_names=[sword,right_hand,right_lower_arm]`, `tar_dist_min=0.5`, `tar_dist_max=10.0`, `tar_height=0.9`, `near_dist=1.5`, `near_prob=0.5` | `Mean Return`, `Mean Episode Length`, target contact/topple 可视化 | `llc_steps`, `task_reward_weight` | 对 target 有稳定接触/击倒趋势，不是纯随机挥砍 |

## 3. 训练命令模板

### 3.1 LLC

#### `ase_humanoid_args.txt`

```bash
/root/miniconda3/envs/mimickit/bin/python mimickit/run.py \
  --arg_file args/ase_humanoid_args.txt \
  --engine_config data/engines/newton_engine.yaml \
  --mode train \
  --visualize false \
  --devices cuda:0 cuda:1 \
  --num_envs 4096 \
  --out_dir output/train/ase_humanoid_l2
```

#### `ase_humanoid_sword_shield_args.txt`

```bash
/root/miniconda3/envs/mimickit/bin/python mimickit/run.py \
  --arg_file args/ase_humanoid_sword_shield_args.txt \
  --engine_config data/engines/newton_engine.yaml \
  --mode train \
  --visualize false \
  --devices cuda:0 cuda:1 \
  --num_envs 4096 \
  --out_dir output/train/ase_humanoid_sword_shield_l2
```

#### `ase_getup_humanoid_sword_shield_args.txt`

```bash
/root/miniconda3/envs/mimickit/bin/python mimickit/run.py \
  --arg_file args/ase_getup_humanoid_sword_shield_args.txt \
  --engine_config data/engines/newton_engine.yaml \
  --mode train \
  --visualize false \
  --devices cuda:0 cuda:1 \
  --num_envs 4096 \
  --out_dir output/train/ase_getup_humanoid_sword_shield_l2
```

### 3.2 HLC

#### `ase_heading_humanoid_sword_shield_args.txt`

```bash
/root/miniconda3/envs/mimickit/bin/python mimickit/run.py \
  --arg_file args/ase_heading_humanoid_sword_shield_args.txt \
  --engine_config data/engines/newton_engine.yaml \
  --mode train \
  --visualize false \
  --devices cuda:0 cuda:1 \
  --num_envs 4096 \
  --llc_model_file output/train/ase_humanoid_sword_shield_l2/model.pt \
  --out_dir output/train/ase_heading_humanoid_sword_shield_l2
```

#### `ase_location_humanoid_sword_shield_args.txt`

```bash
/root/miniconda3/envs/mimickit/bin/python mimickit/run.py \
  --arg_file args/ase_location_humanoid_sword_shield_args.txt \
  --engine_config data/engines/newton_engine.yaml \
  --mode train \
  --visualize false \
  --devices cuda:0 cuda:1 \
  --num_envs 4096 \
  --llc_model_file output/train/ase_humanoid_sword_shield_l2/model.pt \
  --out_dir output/train/ase_location_humanoid_sword_shield_l2
```

#### `ase_reach_humanoid_sword_shield_args.txt`

```bash
/root/miniconda3/envs/mimickit/bin/python mimickit/run.py \
  --arg_file args/ase_reach_humanoid_sword_shield_args.txt \
  --engine_config data/engines/newton_engine.yaml \
  --mode train \
  --visualize false \
  --devices cuda:0 cuda:1 \
  --num_envs 4096 \
  --llc_model_file output/train/ase_humanoid_sword_shield_l2/model.pt \
  --out_dir output/train/ase_reach_humanoid_sword_shield_l2
```

#### `ase_strike_humanoid_sword_shield_args.txt`

```bash
/root/miniconda3/envs/mimickit/bin/python mimickit/run.py \
  --arg_file args/ase_strike_humanoid_sword_shield_args.txt \
  --engine_config data/engines/newton_engine.yaml \
  --mode train \
  --visualize false \
  --devices cuda:0 cuda:1 \
  --num_envs 4096 \
  --llc_model_file output/train/ase_humanoid_sword_shield_l2/model.pt \
  --out_dir output/train/ase_strike_humanoid_sword_shield_l2
```

## 4. Test / Visualize 固定口径

### 4.1 通用 test

```bash
/root/miniconda3/envs/mimickit/bin/python mimickit/run.py \
  --arg_file args/<case>.txt \
  --engine_config data/engines/newton_engine.yaml \
  --mode test \
  --visualize false \
  --num_envs 1 \
  --test_episodes 10 \
  --model_file output/train/<run_name>/model.pt
```

HLC case 额外补：

```text
--llc_model_file output/train/ase_humanoid_sword_shield_l2/model.pt
```

### 4.2 通用 visualize

```bash
export MIMICKIT_VIEWER_HEADLESS=1
export MESA_GL_VERSION_OVERRIDE=3.3
export MESA_GLSL_VERSION_OVERRIDE=330

/root/miniconda3/envs/mimickit/bin/python mimickit/run.py \
  --arg_file args/<case>.txt \
  --engine_config data/engines/newton_engine.yaml \
  --mode test \
  --visualize true \
  --num_envs 1 \
  --test_episodes 1 \
  --model_file output/train/<run_name>/model.pt
```

HLC case 同样额外补：

```text
--llc_model_file output/train/ase_humanoid_sword_shield_l2/model.pt
```

## 5. 复盘顺序

如果某个 case 未达到 `L2`，按以下顺序排查，不要一上来同时改很多参数：

1. 先确认运行口径没有偏离本表：
   - engine 仍是 `newton_engine.yaml`
   - train `num_envs` 仍是 `4096`
   - HLC 已显式传 `--llc_model_file`
2. 再查共享冻结参数是否被改动：
   - LLC 先查 `enc_reward_weight`、`diversity_weight`
   - HLC 先查 `llc_steps`、`task_reward_weight`
3. 最后才动 case 专属旋钮：
   - getup 先查 `recovery_steps`、`fall_init_prob`
   - heading/location/reach/strike 先查各自 target 采样参数

如果目标升级到 `L3`，再在这份 `L2` 规格之上追加 `24h/case` 精修，不回头修改首版基线定义。
