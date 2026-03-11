# ASE Dual-4090 大规模强化学习训练 SOP（宏观架构版）

本文档定义当前 `MimicKit` 项目的主目标，不再以“单篇论文案例跑通”或“UE5 首个桥接交付”作为最高优先级，而是以 **双 RTX 4090 上复刻并扩展 ASE（Adversarial Skill Embeddings）大规模训练管线** 为核心目标。

文档定位：

- 这是项目目标与工程路线文档，不是论文导读。
- 这是推荐运行口径，不改写 `args/*.txt` 当前的默认后端事实。
- `docs/methods/README_ASE.md` 继续负责 ASE 方法和参数解释；本文负责“为什么这样组织系统，以及当前仓库离目标还有哪些差距”。

## 1. 当前主目标

目标重述：

- 在双 RTX 4090 主机上，以 `MimicKit` 现有 ASE 主干为基础，完成 ASE 训练 SOP 的工程化收敛路线。
- 让物理角色经历 billion-scale 级别的无监督试错，学习连续、可复用、可插值的技能潜变量空间。
- 在保持物理动作自然度的前提下，为后续高层任务控制预留明确分层接口。
- 训练主线必须对 mode collapse、技能切换断裂、CPU-GPU 往返瓶颈三类问题有明确防线。

成功口径：

- 阶段一完成后，角色在无 task reward 下也能依靠 style reward 学出稳定自然动作。
- 阶段二完成后，不同 latent 会诱发可辨识且可复测的技能差异，且技能切换不大面积摔倒。
- 阶段三完成后，高层网络只输出 latent，底层技能网络负责动作解码；底层网络默认冻结或仅极小学习率微调。
- 阶段四完成后，双卡训练以 GPU 常驻张量通路为主，环境与策略更新形成可持续的大规模吞吐。

## 2. 后端决策：当前主推荐使用 Newton

当前仓库支持三类后端：

- `data/engines/isaac_gym_engine.yaml`
- `data/engines/isaac_lab_engine.yaml`
- `data/engines/newton_engine.yaml`

当前主推荐后端：`newton`

决策依据是仓库现状，而不是论文默认口径：

1. `mimickit/run.py`、`mimickit/envs/env_builder.py`、`mimickit/engines/engine_builder.py` 已实现后端解耦，运行时可直接覆盖 `--engine_config`。
2. `docs/benchmarks/README_MimicKit_GPUCaseBenchmark.md` 记录了 Newton 双卡基准最终 `25/25` trainable case 可运行，包含 `ase` 两例。
3. `docs/benchmarks/README_MimicKit_GPUUtilizationPatterns.md` 将 `ase_humanoid*` 归类为 compute-heavy，双卡 Newton 下已有较高利用率实证。
4. `mimickit/engines/newton_engine.py` 通过 `warp`/`torch` 张量桥接持有 GPU 常驻仿真状态，符合“尽量减少 CPU-GPU 往返”的目标。
5. `data/engines/newton_engine.yaml` 使用 `sim_freq: 240`，更贴近当前项目希望保住的高频物理控制基线。

说明：

- 这只是“当前主推荐运行后端”。
- `args/*.txt` 里多数 case 仍默认写着 `isaac_gym_engine.yaml`，这是现状记录，不是本文推荐口径。
- 本轮不修改任何代码 API、YAML schema 或 CLI 参数，只统一文档目标。

## 3. 当前仓库已具备的 ASE 主干能力

代码入口已经具备 ASE 预训练核心链路：

- 后端切换：`mimickit/run.py`、`mimickit/envs/env_builder.py`、`mimickit/engines/engine_builder.py`
- ASE 模型：`mimickit/learning/ase_model.py`
- ASE agent：`mimickit/learning/ase_agent.py`
- ASE agent 配置：`data/agents/ase_humanoid_agent.yaml`
- ASE 环境配置：
  - `data/envs/ase_humanoid_env.yaml`
  - `data/envs/ase_humanoid_sword_shield_env.yaml`
- ASE 入口参数：
  - `args/ase_humanoid_args.txt`
  - `args/ase_humanoid_sword_shield_args.txt`

现有 ASE 配置中，已经有几项和目标直接对齐：

- `task_reward_weight: 0.0`，说明当前预训练主线本来就是无 task reward。
- `disc_reward_weight: 0.5`、`enc_reward_weight: 0.5`，已具备 style reward + encoder reward 的双支路。
- `enc_loss_weight: 5.0`，已把技能可辨识约束显式纳入优化。
- `diversity_weight: 0.01`、`diversity_tar: 1.0`，已具备 mode collapse 抑制项。
- `latent_time_min` / `latent_time_max`，已具备潜变量驻留时间控制。

结论：

- 当前仓库已经具备阶段一和阶段二的主体代码基础。
- 当前仓库还没有把阶段三的高层任务策略作为现成 ASE case 暴露出来。

## 4. 四阶段 SOP

### 阶段一：无监督动作先验构建

目标：

- 先解决“角色如何像人一样自然运动”，不引入外部任务目标。

当前仓库对应：

- `data/agents/ase_humanoid_agent.yaml` 中 `task_reward_weight: 0.0`
- `mimickit/learning/ase_agent.py::_compute_rewards`
- `mimickit/learning/ase_agent.py::_calc_disc_rewards`
- `data/envs/ase_*_env.yaml` 的 dataset 驱动 motion source

执行原则：

- 训练目标由 style reward 主导，禁止把 task reward 提前混入阶段一主线。
- 判别器的目标是把策略状态转移分布压向真实 motion dataset。
- 优先保证风格自然度、站立稳定性、落地恢复和节奏连续性。

阶段完成标准：

- `disc_reward_mean` 可稳定工作，不出现长期塌缩到不可用。
- 可视化时动作不再明显像“抖动控制器”或“只会站住不动”。
- 在无 task reward 下仍能形成稳定 locomotion / weapon 风格动作。

### 阶段二：抗崩溃的潜在技能空间生成

目标：

- 把大规模、无标签、无顺序动作集压缩进连续 latent space，并明确防止 mode collapse。

当前仓库对应：

- `mimickit/learning/ase_model.py::eval_actor`
- `mimickit/learning/ase_model.py::eval_enc`
- `mimickit/learning/ase_agent.py::_calc_enc_rewards`
- `mimickit/learning/ase_agent.py::_compute_enc_loss`
- `mimickit/learning/ase_agent.py::_compute_diversity_loss`
- `data/agents/ase_humanoid_agent.yaml` 中的 `enc_*`、`diversity_*`、`latent_time_*`

硬约束：

- 如果不同 latent 最终诱发相同行为，应视为 mode collapse，不能算训练成功。
- 如果 latent 切换频繁导致明显抖动、硬切或成片摔倒，也不能算技能空间可用。

当前应重点关注的参数：

- `enc_reward_weight`
- `enc_loss_weight`
- `diversity_weight`
- `diversity_tar`
- `latent_time_min`
- `latent_time_max`
- `model.latent_dim`

阶段完成标准：

- `enc_reward_mean` 长期可用，不是短暂抬头后失效。
- `diversity_loss` 受控，训练没有明显收敛到单一动作模板。
- 不同 latent 在可视化上呈现可复测差异，不只是噪声级变化。
- latent reset / 更新后，角色大多数情况下能保持连续重心控制，而不是频繁摔倒。

可视化验收注意：

- ASE 序列渲染必须走 agent 的 test-time latent 更新路径。
- 如果渲染脚本直接拿静态 actor 做前向，而没有经过 latent reset/update，可能出现“蓝色 agent 原地抖动”的假阴性。
- 因此在判定 mode collapse 或技能空间失效前，先确认可视化工具没有绕开 `ase_agent` 的真实测试闭环。

### 阶段三：分层控制与高层任务策略

目标：

- 让已训练好的低层技能网络成为“动作执行器”，让高层网络只输出 latent `z` 去完成任务。

目标架构：

- 高层策略：观察目标与环境，输出连续 latent vector。
- 低层策略：观察自身状态与 latent，输出关节动作。
- 训练高层任务时，低层网络默认冻结，或只允许极小学习率微调。

当前仓库状态：

- 这是 **目标架构 / 下一阶段实现方向**。
- 仓库当前没有独立的 ASE 高层任务 args 入口。
- `task_location` / `task_steering` 现成案例主要在 AMP 路线，说明任务环境模式存在，但尚未被整理为 ASE 高层技能调用范式。

文档边界：

- 本文明确把阶段三写成工程目标，不把它写成“仓库已经交付完成”的能力。
- 后续若实现该阶段，推荐复用现有任务环境模式，并在 ASE 上新增高层 `z` 输出链路，而不是把 task reward 重新灌进阶段一预训练主线。

### 阶段四：极限并行吞吐量与算力榨取

目标：

- 在双 RTX 4090 上尽量把 rollouts、replay、PPO 更新、disc/enc 训练保持在 GPU 张量通路内，避免不必要同步。

当前仓库对应：

- 多设备入口：`mimickit/run.py` 的 `--devices cuda:0 cuda:1`
- 后端抽象：`mimickit/envs/env_builder.py` + `mimickit/engines/engine_builder.py`
- Newton GPU 张量桥接：`mimickit/engines/newton_engine.py`

主推荐运行契约：

```bash
python mimickit/run.py \
  --arg_file args/ase_humanoid_args.txt \
  --engine_config data/engines/newton_engine.yaml \
  --mode train \
  --visualize false \
  --devices cuda:0 cuda:1
```

执行原则：

- 环境层必须继续保持“同一 env/agent 抽象，运行时切后端”的结构，不把训练逻辑绑死到单一仿真器。
- 双卡主线优先看稳定持续吞吐，而不是只看瞬时 util。
- 4096+ 独立 agent 是架构目标；实际单机运行档位以 benchmark ladder 和显存稳定性为准。
- 当前仓库已有 Newton 双卡 benchmark 证据；ASE 现有记录属于高利用率类别，可作为主线优先方法。

阶段完成标准：

- 训练主线可以长期双卡运行，不因常见 OOM/NCCL 问题频繁中断。
- rollout 数据与 PPO/disc/enc 更新保持 GPU 常驻张量路径为主。
- 文档与执行层都不引入额外 CPU 同步依赖作为常态路径。

## 5. 当前推荐入口与使用边界

推荐直接复用的 ASE 入口：

- `args/ase_humanoid_args.txt`
- `args/ase_humanoid_sword_shield_args.txt`
- `data/agents/ase_humanoid_agent.yaml`
- `data/envs/ase_humanoid_env.yaml`
- `data/envs/ase_humanoid_sword_shield_env.yaml`

推荐阅读顺序：

1. 先读本文，明确项目目标与阶段边界。
2. 再读 `docs/methods/README_ASE.md`，理解参数和代码映射。
3. 再看 `docs/paper_code/README_ASE_TheoryCode.md`，核对论文到实现的具体落点。
4. 最后结合 `docs/benchmarks/README_MimicKit_GPUCaseBenchmark.md` 与 `docs/benchmarks/README_MimicKit_GPUUtilizationPatterns.md` 选稳定运行档位。

## 6. 当前缺口与禁止误读项

当前缺口：

- 尚无独立 ASE hierarchical task policy 训练 case。
- 尚无面向 latent 连续插值的专用可视化/验收工具文档。
- `args/*.txt` 默认后端仍多为 Isaac Gym，推荐运行口径与默认文件值存在差异，需要在命令行显式覆盖。

禁止误读：

- 不要把“已有 ASE 预训练主干”理解为“已经完成了 ASE 分层任务策略”。
- 不要把“当前推荐后端是 Newton”理解为“仓库默认后端已经全部切成 Newton”。
- 不要把“支持 4096+ agent 的架构目标”理解为“任意角色与任意任务都已经在当前主机上实测通过该规模”。

## 7. 本轮文档更新不做什么

- 不修改代码 API。
- 不修改 agent / env / engine YAML schema。
- 不改写 `docs/guides/README_Paper_ConfigCaseCatalog.md` 里的默认 case 事实表。
- 不把 `docs/guides/BaselineConfig.md` 改造成 ASE 主文档。
- 不把 `docs/memory/` 变成长期项目目标目录。
