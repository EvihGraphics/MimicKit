# ASE：论文-代码精细对照（更新版）

## 1. 论文核心问题与目标
参考论文：ASE (TOG 2022)
- arXiv: https://arxiv.org/abs/2205.01906

ASE的目标是学到可复用的技能嵌入：
- 低层策略：\(\pi(a|s,z)\)
- 高层策略：\(\omega(z|s,g)\)（下游任务调用技能）

论文预训练目标的核心形式：
\[
\max_{\pi}\; -D_{JS}(d_{\pi}, d_M) + \beta I((s,s');z)
\]
其中第一项是对抗模仿，第二项鼓励 latent 与行为可辨识（互信息项）。

论文还给出基于变分近似 \(q(z|s,s')\) 的实现形式，对应 style+MI 奖励：
\[
r_t = -\log(1-D(s_t,s_{t+1})) + \beta \log q(z_t|s_t,s_{t+1})
\]

## 2. 论文机制在 MimicKit 的代码映射

### 2.1 Skill-conditioned actor/critic
- actor：`mimickit/learning/ase_model.py:14` (`eval_actor(obs, z)`)
- critic：`mimickit/learning/ase_model.py:20` (`eval_critic(obs, z)`)

这和论文的 \(\pi(a|s,z)\) 对齐。

### 2.2 编码器与MI相关项
- 编码器：`mimickit/learning/ase_model.py:26` (`eval_enc`)
- 编码器奖励：`mimickit/learning/ase_agent.py:212` (`_calc_enc_rewards`)
- 编码器损失：`mimickit/learning/ase_agent.py:309` (`_compute_enc_loss`)
- 编码误差定义：`mimickit/learning/ase_agent.py:322` (`_calc_enc_error`)

当前实现中，编码器误差是点积形式（`-<z, enc_pred>`），奖励用 `clamp_min(-err, 0)`。
这与论文“通过 \(q(z|s,s')\) 近似MI下界”的思想一致，但具体函数形式更工程化。

### 2.3 对抗模仿分支
ASE复用了AMP的对抗分支：
- 奖励融合入口：`mimickit/learning/ase_agent.py:186` (`_compute_rewards`)
- 其中 `disc_reward` 来自AMP判别器链路。

### 2.4 latent时序调度
- reset latent：`mimickit/learning/ase_agent.py:95`
- update latent：`mimickit/learning/ase_agent.py:116`
- sample latent：`mimickit/learning/ase_agent.py:126`

对应配置：`latent_time_min`, `latent_time_max`。

### 2.5 多样性约束
- 多样性损失：`mimickit/learning/ase_agent.py:327` (`_compute_diversity_loss`)

本质是：同一观测下采样不同latent，鼓励动作分布均值产生可分差异，降低mode collapse。

## 3. 论文项 -> 配置映射

| 论文项 | 作用 | MimicKit 参数 |
|---|---|---|
| \(\beta\)（MI相关权重） | 技能可辨识与可恢复 | `enc_reward_weight`, `enc_loss_weight` |
| adversarial imitation | 贴近参考动作分布 | `disc_reward_weight`, `disc_loss_weight` |
| task项 | 下游任务目标 | `task_reward_weight` |
| latent维度 | 技能容量 | `model.latent_dim` |
| 编码器结构 | 近似 \(q(z|s,s')\) | `model.enc_net` |
| 多样性约束 | 防止技能坍缩 | `diversity_weight`, `diversity_tar` |
| latent切换时间 | 技能片段长度 | `latent_time_min`, `latent_time_max` |

主要配置文件：`data/agents/ase_humanoid_agent.yaml`。

## 4. 与论文一致点与实现差异

一致点：
- latent条件策略 + 对抗模仿 + MI相关项 + 多样性约束都保留。
- 训练结构仍是“PPO主干 + 对抗支路 + 编码器支路”。

实现差异（工程化）：
- 论文中的 \(\log q(z|s,s')\) 在仓库里通过编码器点积误差近似实现，奖励和损失分开注入。
- 判别器损失形式沿用AMP工程实现（BCE-logits链路），并非逐字照搬论文里的每个数学表达。

## 5. 读代码时的核对清单
- `disc_reward_weight` 与 `enc_reward_weight` 是否平衡。
- latent切换时间是否与动作节奏匹配。
- `diversity_weight` 是否足够抑制mode collapse。
- 编码器loss是否稳定下降且不压制主策略学习。

## 6. 从理论到复现的自动化监控落地 (Automated Reproducibility via Code Structure)
1. **持久化与训练崩溃重恢复**：理论的对抗网络（AMP判别器 + PPO主干）极易发生损失不稳定的震荡。为此，项目在 `scripts/watchdog_ase_training.sh` 实现了长周期的无人值守（pkill孤儿进程 + tmux环境隔离）管理。从而通过 `multiprocessing` 重建有效控制高频切换时 `os.killpg()` 漏掉的僵尸Python线程。
2. **论文可视化对照验证**：为确认模型不仅获得了在测试环境的高得分，还要确认视觉生成上的“动作多样性约束”（防止mode collapse），参考 `docs/skill/mimickit-render-viz-sequence-skill`，通过下述代码可以端到端对代码推理质量给出视觉佐证：

```bash
# 生成 ASE 动作推理可视化集 (例: 提取 300 帧, 按 5 stride)
/root/miniconda3/envs/mimickit/bin/python tools/ue_bridge/build_mimickit_render_sequences.py \
  --roots case_ase_fullchain_render_xxx --cases ase_humanoid_args --frames 300 --frame-stride 5
```
生成的 `output/img/render_all_roots.tsv` 文件中将会记录最佳训练权重的所有统计与视觉类别（geom / mesh）。这也标志了当前代码架构全方位匹配并验证了 ASE 论文原文的目标要求。
