# ASE 7-Case L2 参数规格化计划

## Summary
可以明确，而且可以明确到“可直接执行”的程度，但口径要固定为 `L2 可交付`，不是“逐帧等同论文视频”。  
本计划会把 `7` 个 ASE 训练主案例的参数拆成两层并一次性定死：

- 共享训练基线：agent 超参、设备、并行度、预算、test/viz 口径
- case 专属参数：每个 `env` 的任务参数、数据源、验收信号

最终输出应是一份集中参数表，来源只认当前仓库配置与文档，不再让实现者在多个文档之间来回拼装。

## Key Changes
- 把共享 LLC 基线固定为当前 [`data/agents/ase_humanoid_agent.yaml`](/root/Project/MimicKit-ase-fullchain/data/agents/ase_humanoid_agent.yaml)：
  - `latent_dim=64`
  - `learning_rate=2e-5`
  - `steps_per_iter=32`
  - `update_epochs=5`
  - `batch_size=4`
  - `disc_grad_penalty=5`
  - `disc_reward_weight=0.5`
  - `enc_reward_weight=0.5`
  - `task_reward_weight=0.0`
  - `enc_loss_weight=5.0`
  - `diversity_weight=0.01`
  - `diversity_tar=1.0`
  - `latent_time_min=0.0`
  - `latent_time_max=5.0`
- 把共享 HLC 基线固定为当前 [`data/agents/ase_hrl_humanoid_agent.yaml`](/root/Project/MimicKit-ase-fullchain/data/agents/ase_hrl_humanoid_agent.yaml)：
  - `latent_dim=64`
  - `learning_rate=2e-5`
  - `steps_per_iter=32`
  - `update_epochs=6`
  - `batch_size=4`
  - `llc_steps=5`
  - `task_reward_weight=0.9`
  - `disc_reward_weight=0.1`
  - 训练必须显式传 `--llc_model_file`
- 把共享运行口径固定为：
  - 训练：`--engine_config data/engines/newton_engine.yaml`
  - 训练设备：`--devices cuda:0 cuda:1`
  - 训练并行：`--num_envs 4096`
  - `test`：`--num_envs 1 --test_episodes 10`
  - `visualize`：`--num_envs 1 --test_episodes 1`
  - headless viz：默认带 `MIMICKIT_VIEWER_HEADLESS=1`、`MESA_GL_VERSION_OVERRIDE=3.3`、`MESA_GLSL_VERSION_OVERRIDE=330`
  - L2 预算：先按 `8h/case` 定义，不把 `24h` 精修混进首版参数表
- 把 7 个 case 的专属参数逐项固化：
  - `ase_humanoid`：`dataset_humanoid_locomotion.yaml`，`episode_length=10`，`default_reset_prob=0.5`
  - `ase_humanoid_sword_shield`：`dataset_humanoid_sword_shield.yaml`，剑盾版 `joint_err_w` 与 `key_bodies`
  - `ase_getup_humanoid_sword_shield`：在 sword/shield LLC 基线上额外固定 `recovery_episode_prob=0.2`、`recovery_steps=60`、`fall_init_prob=0.1`、`fall_state_steps=150`
  - `ase_heading_humanoid_sword_shield`：`task_steering`，固定 `tar_speed_min=1.5`、`tar_speed_max=1.6`、`tar_change_time_[3.3,6.7]`、`reward_steering_tar_w=0.7`、`reward_steering_face_w=0.3`
  - `ase_location_humanoid_sword_shield`：`task_location`，固定 `tar_speed=1.0`、`tar_change_time_[3.3,6.7]`、`tar_dist_max=10.0`
  - `ase_reach_humanoid_sword_shield`：`task_reach`，固定 `tar_speed=1.0`、`tar_change_time_[1.7,3.3]`、`tar_dist_max=1.0`、`tar_height_[0.2,2.0]`、`reach_body_name=sword`
  - `ase_strike_humanoid_sword_shield`：`task_strike`，固定 `strike_body_names=[sword,right_hand,right_lower_arm]`、`tar_dist_min=0.5`、`tar_dist_max=10.0`、`tar_height=0.9`、`near_dist=1.5`、`near_prob=0.5`
- 输出形式默认做成一份新的 ASE 参数总表文档，并从 [`docs/guides/README_ASE_FullChain_TrainInferVisual_SOP.md`](/root/Project/MimicKit-ase-fullchain/docs/guides/README_ASE_FullChain_TrainInferVisual_SOP.md) 和 [`docs/guides/README_Paper_ConfigCaseCatalog.md`](/root/Project/MimicKit-ase-fullchain/docs/guides/README_Paper_ConfigCaseCatalog.md) 链过去，避免参数继续分散。

## Public Interfaces
- 不改训练 CLI，不新增新 schema。
- 保持现有 `args/*.txt`、`--mode train|test`、`--llc_model_file`、`--engine_config` 不变。
- 新增的只是“参数规格说明文档”与 case 级命令模板，不改变代码接口。
- 参数表中要明确区分：
  - `冻结参数`：默认不动，作为论文复现基线
  - `次级调参旋钮`：只有未达 L2 时才动，例如 `enc_reward_weight`、`diversity_weight`、`llc_steps`、`task_reward_weight`

## Test Plan
- 配置一致性检查：
  - 参数表中的共享超参与当前 agent YAML 完全一致
  - case 表中的任务参数与对应 env YAML 完全一致
  - 所有命令模板都落在当前 `run.py` 支持的参数集合内
- L2 验收线固定为：
  - LLC：`train -> test -> visualize` 全通过；无长时间冻结；latent 切换有明显差异；不大面积摔倒
  - Getup：跌倒后出现明显恢复窗口，不是持续躺地抖动
  - Heading：目标方向持续对齐
  - Location：可稳定到点
  - Reach：`sword` 末端能主动逼近 3D 目标
  - Strike：可对 target 产生稳定接触/击倒趋势
- 文档完整性检查：
  - 7 个 case 都要同时给出 `数据源`、`训练命令模板`、`关键参数`、`观察指标`、`L2 通过标准`
  - 不把 `perturb`、`view_motion` 混入这份首版训练参数总表

## Assumptions
- “达到论文效果”在本轮固定解释为：达到 `L2 可交付`，不是 `L3 README/论文级观感`，更不是逐帧复刻视频。
- 首版参数规格优先服务于“训练闭环”，所以预算按 `8h/case` 锁定；`24h` 只留作后续 L3 精修策略。
- 参数来源以当前仓库的 agent/env 配置为准；因为新 worktree 里没有现成训练产物与完整 upstream 运行结果，这份规格是“仓库可执行复现基线”，不是对论文原作者训练日志的逐项回填。
- 首版只覆盖 `7` 个 trainable ASE 主案例；`perturb` 与 `view_motion` 继续留在验收/资产链路文档中，不纳入训练参数主表。
