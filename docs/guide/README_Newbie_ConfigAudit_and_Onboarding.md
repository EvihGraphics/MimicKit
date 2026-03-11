# MimicKit 零基础上手与配置审计手册（2026-03-05）

面向人群：
- 没有计算机基础、没有深度学习基础的新手
- 想按论文案例跑通 MimicKit 的同学
- 想知道“为什么命令跑不动/跑不完/跑很慢”的同学

本文做两件事：
1. 用最小步骤带你从 0 跑通 `可视化 -> 推理 -> 训练`
2. 基于仓库当前文档与配置，给出“有证据的问题清单 + 修复建议”

---

## 1. 先看结论（新手最重要）

如果你只记 5 条，请记这 5 条：

1. **测试命令一定要加 `--test_episodes`**，否则可能长时间不结束。
2. **训练先把 `--num_envs` 从 4096 降下来**（例如 32/64），否则很容易爆显存。
3. **每次训练都改 `--out_dir`**，否则模型和日志会互相覆盖。
4. **不要把 `--visualize true` 用在训练**，先 `false` 训练，再 `true` 可视化。
5. **默认 `args/*.txt` 都是 Isaac Gym**，而 Isaac Gym 官方已标注 deprecated；新装机优先考虑 Newton 或 Isaac Lab。

---

## 2. 在线论文与资料核对（README 相关）

以下是 README 关联的核心论文与资料（已在线核对）：

### 2.1 核心论文

1. MimicKit（框架论文）
- 题目：MimicKit: A Reinforcement Learning Framework for Motion Imitation and Control
- arXiv：<https://arxiv.org/abs/2510.13794>
- arXiv 页面显示：2025-10-15 提交，2026-01-18 更新到 v4。

2. DeepMimic
- 题目：DeepMimic: Example-Guided Deep Reinforcement Learning of Physics-Based Character Skills
- arXiv：<https://arxiv.org/abs/1804.02717>

3. AMP
- 题目：AMP: Adversarial Motion Priors for Stylized Physics-Based Character Control
- arXiv：<https://arxiv.org/abs/2104.02180>

4. ASE
- 题目：ASE: Large-Scale Reusable Adversarial Skill Embeddings for Physically Simulated Characters
- arXiv：<https://arxiv.org/abs/2205.01906>

5. ADD
- 题目：Physics-Based Motion Imitation with Adversarial Differential Discriminators
- arXiv：<https://arxiv.org/abs/2505.04961>

6. PPO（项目中常用算法）
- 题目：Proximal Policy Optimization Algorithms
- arXiv：<https://arxiv.org/abs/1707.06347>

7. AWR（DeepMimic AWR case 用到）
- 题目：Advantage-Weighted Regression: Simple and Scalable Off-Policy Reinforcement Learning
- arXiv：<https://arxiv.org/abs/1910.00177>

### 2.2 引擎官方资料（安装与选型）

1. Isaac Gym（NVIDIA 页面）
- <https://developer.nvidia.com/isaac-gym>
- 页面明确写了 `Isaac Gym - Now Deprecated`，并提示这是 legacy software，建议考虑 Isaac Lab。

2. Isaac Lab（官方安装文档）
- <https://isaac-sim.github.io/IsaacLab/main/source/setup/installation/index.html>
- 文档页面更新时间：2026-03-05。
- 文档给出系统要求（示例：Ubuntu 22.04 / Windows 11，建议 16GB+ VRAM）。

3. Newton（官方仓库）
- <https://github.com/newton-physics/newton>
- README 有 Quickstart（`pip install "newton[examples]"`）。

### 2.3 新手补充资料（建议）

1. PPO 参数直觉（Spinning Up）
- <https://spinningup.openai.com/en/latest/algorithms/ppo.html>

2. PyTorch 初学入口（官方教程）
- <https://docs.pytorch.org/tutorials/>

3. W&B 快速开始（若你用 `--logger wandb`）
- <https://docs.wandb.ai/quickstart>

---

## 3. 当前仓库配置与文档问题清单（有证据）

以下按严重程度分级：
- `P0`：高概率直接卡住/误判
- `P1`：高概率导致新手失败或结果很差
- `P2`：信息不一致或易误导

## 3.1 P0：测试命令未限制 episode，可能“看起来像卡死”

证据：
- `README.md:86` 示例测试命令没有 `--test_episodes`
- `mimickit/run.py:124` 默认 `test_episodes = np.iinfo(np.int64).max`
- `mimickit/learning/base_agent.py:300` 测试循环 `while True`，直到达到 episode 门槛才退出

影响：
- 新手常以为程序死机，实际是测试在持续跑。

建议：
- 所有测试命令都加：`--test_episodes 1`（看画面）或 `--test_episodes 10`（看指标）。

---

## 3.2 P1：训练示例命令与文字建议互相矛盾

证据：
- `README.md:64` 训练示例写了 `--visualize true`
- `README.md:71` 同一段又说训练应关闭渲染以提速

影响：
- 新手会复制粘贴 `visualize=true` 去训练，速度慢很多，远程无图形环境还可能报错。

建议：
- 训练统一用 `--visualize false`。
- 只在 `mode=test` 且 `num_envs=1` 时开 `--visualize true`。

---

## 3.3 P1：`args/*.txt` 默认 `num_envs=4096`，对新手机器风险很高

证据：
- 绝大多数训练 case 都是 `--num_envs 4096`（如 `args/deepmimic_humanoid_ppo_args.txt:1`, `args/amp_humanoid_args.txt:1`）

影响：
- 显存不足直接 OOM；即使不 OOM，也会因为调度压力导致吞吐不稳定。

建议：
- 新手从 `32` 或 `64` 起步，稳定后再上调。
- 不要一开始追求论文速度，先跑通闭环。

---

## 3.4 P1：`args/*.txt` 默认 `out_dir=output/`，容易覆盖实验结果

证据：
- 全量 args 基本都写 `--out_dir output/`（如 `args/deepmimic_humanoid_ppo_args.txt:7`）

影响：
- 新手连续跑多个实验，模型和日志可能互相覆盖，最后无法复盘。

建议：
- 每次训练都显式设置唯一目录：
  - `--out_dir output/train/<日期_方法_案例_备注>`

---

## 3.5 P1：默认引擎指向 Isaac Gym，但官方已标记 deprecated

证据：
- `args/*.txt` 全部默认 `--engine_config data/engines/isaac_gym_engine.yaml`
- NVIDIA Isaac Gym 页面明确标注 deprecated，并建议 Isaac Lab

影响：
- 新装机用户按默认配置走，可能在安装环节踩坑较多。

建议：
- 新手优先选 Newton 或 Isaac Lab。
- 如保留 Isaac Gym，请在文档中明确“legacy/归档安装路径”。

---

## 3.6 P1：README 让你用 TensorBoard，但依赖里没有 `tensorboard`

证据：
- `README.md:123` 给出 `tensorboard --logdir=...`
- `requirements.txt` 只有 `tensorboardX`，没有 `tensorboard`

影响：
- 新手执行 `tensorboard` 可能提示命令不存在。

建议：
- 在环境中补装：`pip install tensorboard`
- 或把 `tensorboard` 加进 `requirements.txt`

---

## 3.7 P2：动作数据数量文档过时

证据：
- `docs/guides/README_Newbie_TrainInferVisual_PaperCases.md:143` 写 `145` 个 `.pkl`
- 当前仓库统计（2026-03-05）：`find data/motions -name '*.pkl' | wc -l` 为 `387`

影响：
- 新手按文档估算数据规模会误判训练覆盖范围。

建议：
- 把“固定数字”改为“命令实时统计结果”。

---

## 3.8 P2：`docs/ops/tmux-keepalive-guide.md` 示例与本仓库不一致

证据：
- `docs/ops/tmux-keepalive-guide.md` 使用 `scripts/full_train.py` 与 `configs/training.yaml`
- 本仓库不存在 `scripts/full_train.py`、`configs/` 目录

影响：
- 新手照抄命令会直接报“文件不存在”。

建议：
- 在该文档开头明确“这是通用模板，不是 MimicKit 现成命令”。
- 或替换为 `python mimickit/run.py ...` / `scripts/run_case_*.py` 的真实命令。

---

## 4. 零基础上手路径（从 0 到能复盘）

## 4.1 第 0 步：先理解 8 个词

1. 环境（Env）：仿真世界
2. 智能体（Agent）：学习算法（PPO/AMP/ASE/ADD）
3. 策略（Policy）：观测 -> 动作 的神经网络
4. 观测（Obs）：模型输入
5. 动作（Action）：模型输出
6. 奖励（Reward）：每一步好坏分数
7. 训练（Train）：更新模型参数
8. 推理（Test）：不更新参数，只评估

你可以把它理解成：
- 环境出题（给观测）
- 智能体答题（给动作）
- 奖励打分
- 训练阶段不断改进答题方法

---

## 4.2 第 1 步：选一个引擎（别一上来纠结）

推荐优先级（新手）：
1. Newton（快速验证链路）
2. Isaac Lab（新官方路线，要求更高）
3. Isaac Gym（legacy，仅在你已有现成环境时考虑）

注意：
- MimicKit 的 args 默认写的是 Isaac Gym。
- 不换引擎参数，命令就会走 Isaac Gym。

---

## 4.3 第 2 步：基础环境准备（最小集合）

```bash
# 1) 新建环境（示例）
conda create -n mimickit python=3.10 -y
conda activate mimickit

# 2) 安装基础依赖
pip install -r requirements.txt
pip install tensorboard

# 3) 验证 PyTorch 和 GPU（可选）
python3 -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.device_count())"
```

如果你的系统没有 `python` 命令，请统一使用 `python3`。

---

## 4.4 第 3 步：先跑“纯动作可视化”（不涉及训练）

目的：确认引擎 + 资源 + 渲染链路是通的。

```bash
python3 mimickit/run.py \
  --arg_file args/view_motion_humanoid_args.txt \
  --engine_config data/engines/newton_engine.yaml \
  --mode test \
  --visualize true \
  --num_envs 1 \
  --test_episodes 1
```

如果这一步都跑不通，不要进训练。

---

## 4.5 第 4 步：跑预训练模型推理（先看结果）

```bash
python3 mimickit/run.py \
  --arg_file args/deepmimic_humanoid_ppo_args.txt \
  --engine_config data/engines/newton_engine.yaml \
  --mode test \
  --visualize true \
  --num_envs 1 \
  --test_episodes 1 \
  --model_file data/models/deepmimic_humanoid_spinkick_model.pt
```

目标：
- 你能看到“可用动作效果”
- 这样后面训练效果有对照组

---

## 4.6 第 5 步：跑一个超短训练（先验证闭环）

```bash
python3 mimickit/run.py \
  --arg_file args/deepmimic_humanoid_ppo_args.txt \
  --engine_config data/engines/newton_engine.yaml \
  --mode train \
  --visualize false \
  --num_envs 64 \
  --max_samples 200000 \
  --out_dir output/train/quickcheck_deepmimic_humanoid
```

然后测试：

```bash
python3 mimickit/run.py \
  --arg_file args/deepmimic_humanoid_ppo_args.txt \
  --engine_config data/engines/newton_engine.yaml \
  --mode test \
  --visualize false \
  --num_envs 1 \
  --test_episodes 10 \
  --model_file output/train/quickcheck_deepmimic_humanoid/model.pt
```

---

## 4.7 第 6 步：看日志（不要只看一段视频）

```bash
tensorboard --logdir output/ --port 6006 --samples_per_plugin scalars=999999
```

最低检查项：
1. 程序能正常结束（不是中途异常退出）
2. `Mean Return` 是否总体上升
3. 可视化是否比随机动作更稳定

---

## 5. 论文方法和本项目案例怎么对应

## 5.1 一张表看懂

1. DeepMimic：`args/deepmimic_*`
2. AMP：`args/amp_*`
3. ASE：`args/ase_*`
4. ADD：`args/add_*`
5. 扩展示例：`args/vault_*`
6. 工具型非训练：`args/view_motion_*`、`args/dof_test_*`

说明：
- `view_motion_*` 是数据/渲染检查，不代表策略好坏。
- `vault_*` 是扩展任务，不是原论文主 benchmark。

---

## 6. 新手最常见报错与处理

## 6.1 OOM（显存不足）

先做这 3 个动作：
1. `--num_envs` 直接减半（64 -> 32）
2. 训练时确认 `--visualize false`
3. 关闭其他占 GPU 程序

## 6.2 测试一直不结束

检查是否忘了 `--test_episodes`。

## 6.3 看不到图形窗口

1. 先用 `--visualize false` 验证逻辑链路
2. 再用本地桌面/可用图形环境开 `--visualize true`

## 6.4 命令 `tensorboard` 不存在

执行：

```bash
pip install tensorboard
```

## 6.5 模型找不到

1. 先确认训练输出目录是否唯一且正确
2. 常见路径是：`output/train/<run_name>/model.pt`

---

## 7. 给维护者的最小修正文档建议（可选）

建议优先改这几处：

1. `README.md` 测试示例补 `--test_episodes 10`
2. `README.md` 训练示例改为 `--visualize false`
3. `requirements.txt` 加 `tensorboard`
4. 在 `README.md` 或 `docs/README.md` 明确：默认 args=Isaac Gym（legacy）
5. 更新 `docs/guides/README_Newbie_TrainInferVisual_PaperCases.md` 的动作数量统计口径
6. 给 `docs/ops/tmux-keepalive-guide.md` 加“通用模板”声明，避免误抄

---

## 8. 你现在可以直接复制的“安全模板”

## 8.1 训练模板

```bash
python3 mimickit/run.py \
  --arg_file args/<case>.txt \
  --engine_config data/engines/newton_engine.yaml \
  --mode train \
  --visualize false \
  --num_envs 64 \
  --max_samples 500000 \
  --out_dir output/train/<run_name>
```

## 8.2 测试模板

```bash
python3 mimickit/run.py \
  --arg_file args/<case>.txt \
  --engine_config data/engines/newton_engine.yaml \
  --mode test \
  --visualize false \
  --num_envs 1 \
  --test_episodes 10 \
  --model_file output/train/<run_name>/model.pt
```

## 8.3 可视化模板

```bash
python3 mimickit/run.py \
  --arg_file args/<case>.txt \
  --engine_config data/engines/newton_engine.yaml \
  --mode test \
  --visualize true \
  --num_envs 1 \
  --test_episodes 1 \
  --model_file output/train/<run_name>/model.pt
```

---

## 9. 审计范围说明

本手册基于以下范围整理：

1. 项目文档：`README.md`、`docs/**`
2. 参数配置：`args/*.txt`、`data/envs/*.yaml`、`data/agents/*.yaml`、`data/engines/*.yaml`
3. 关键代码：`mimickit/run.py`、`mimickit/learning/base_agent.py`、`mimickit/util/arg_parser.py`
4. 在线资料核对时间：2026-03-05

