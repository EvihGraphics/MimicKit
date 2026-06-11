# MimicKit AMP Stage A 执行记录（Newton / baseline -> task AMP）

## 1. 本轮完成了什么

- 按 `docs/plan/ARC_RADIER/PLAN-430-a.md` 的 Stage A 路线，实际跑通了 `amp_humanoid`、`amp_location_humanoid`、`amp_steering_humanoid`。
- 统一使用 `data/engines/newton_engine.yaml` 和 `/root/miniconda3/envs/mimickit/bin/python`。
- 三个 case 都完成了：
  - pretrained `test`
  - headless `visualize true`
  - 短训练产物验证
- 额外补了两个“一迭代自然退出”训练，用来确认 `location` 和 `steering` 的 TensorBoard 事件文件不是 0 字节。

本轮没有改训练代码、环境代码、配置代码，只做了运行验证和学习沉淀。

## 2. 运行约定

- 入口：`mimickit/run.py:22-38`, `mimickit/run.py:96-126`, `mimickit/run.py:137-163`
- headless 可视化环境变量：
  - `MIMICKIT_VIEWER_HEADLESS=1`
  - `MESA_GL_VERSION_OVERRIDE=3.3`
  - `MESA_GLSL_VERSION_OVERRIDE=330`
- 训练输出目录由 `mimickit/run.py:58-69` 和 `mimickit/run.py:123-126` 复制：
  - `engine_config.yaml`
  - `env_config.yaml`
  - `agent_config.yaml`
  - `log.txt`
  - `model.pt`
  - TensorBoard `events.out.tfevents.*`

## 3. 实际执行结果

| case | pretrained test | headless visualize | 训练产物 | 关键结论 |
|---|---|---|---|---|
| `amp_humanoid` | `Mean Return=0.0`, `EpLen=31` | `Mean Return=0.0`, `EpLen=39` | `output/train/amp_learn_humanoid_newton_20260430_170334/`，含非零 `events` | 纯 AMP 风格模仿基线可在 Newton 上稳定加载、测试、可视化、启动训练 |
| `amp_location_humanoid` | `Mean Return=10.27`, `EpLen=21` | `Mean Return=0.0947`, `EpLen=32` | 主验证目录 `output/train/amp_learn_location_newton_20260430_171023/`；完整 flush 目录 `output/train/amp_learn_location_newton_complete_20260430_171426/` | 任务奖励和风格奖励共存，`motion_file` 已从单 clip 变成 locomotion dataset |
| `amp_steering_humanoid` | `Mean Return=45.01`, `EpLen=51` | `Mean Return=23.17`, `EpLen=73` | 主验证目录 `output/train/amp_learn_steering_newton_20260430_171210/`；完整 flush 目录 `output/train/amp_learn_steering_newton_complete_20260430_171426/` | steering 任务链路真实生效，适合作为后续 ARC-like TurnBrain 前置模板 |

补充说明：

- `location` 和 `steering` 的第一次长命令验证运行是“运行到验证点后收束”，因此 `model.pt`、`log.txt`、配置快照都已生成，但 TensorBoard writer 没有自然退出 flush。
- 为了把产物链路补完整，后续增加了 `max_samples=16384` 的一迭代自然退出烟测，所以 `*_complete_*` 目录里的 `events.out.tfevents.*` 为非零字节。

## 4. 短训练观测到的 AMP 指标

### 4.1 `amp_humanoid`

- 配置上是纯 AMP：
  - `data/agents/amp_humanoid_agent.yaml:42-43`
  - `task_reward_weight: 0.0`
  - `disc_reward_weight: 1.0`
- 环境上是单 clip：
  - `data/envs/amp_humanoid_env.yaml:24`
  - `motion_file: data/motions/humanoid/humanoid_spinkick.pkl`
- 已验证训练目录：
  - `output/train/amp_learn_humanoid_newton_20260430_170334/`
- `Iteration 0` 记录到：
  - `Disc_Reward_Mean = 0.284`
  - `Disc_Agent_Acc = 0.819`
  - `Disc_Demo_Acc = 0.884`

这说明 baseline case 的学习重心就是“像 reference style”，而不是完成外部任务。

### 4.2 `amp_location_humanoid`

- 配置上是 task AMP：
  - `data/agents/amp_task_humanoid_agent.yaml:42-43`
  - `task_reward_weight: 0.5`
  - `disc_reward_weight: 0.5`
- 环境改成 location task：
  - `data/envs/amp_location_humanoid_env.yaml:1`
  - `data/envs/amp_location_humanoid_env.yaml:22-27`
- 一迭代完整退出目录：
  - `output/train/amp_learn_location_newton_complete_20260430_171426/`
- `Iteration 0` 记录到：
  - `Test_Return = 3.79`
  - `Train_Return = 3.46`
  - `Disc_Reward_Mean = 1.84`
  - `Disc_Agent_Acc = 0.849`
  - `Disc_Demo_Acc = 0.893`

这说明 location case 不是纯风格克隆，而是在“向目标点移动”和“保持动作风格”之间做 5:5 融合。

### 4.3 `amp_steering_humanoid`

- 配置上仍是 task AMP：
  - `data/agents/amp_task_humanoid_agent.yaml:42-43`
- 环境改成 steering task：
  - `data/envs/amp_steering_humanoid_env.yaml:1`
  - `data/envs/amp_steering_humanoid_env.yaml:22-29`
  - `data/envs/amp_steering_humanoid_env.yaml:43-46`
- 一迭代完整退出目录：
  - `output/train/amp_learn_steering_newton_complete_20260430_171426/`
- `Iteration 0` 记录到：
  - `Test_Return = 2.94`
  - `Train_Return = 2.64`
  - `Disc_Reward_Mean = 6.58`
  - `Disc_Agent_Acc = 0.760`
  - `Disc_Demo_Acc = 0.811`

这说明 steering case 的策略已经同时接收“去哪儿、朝哪儿看、以多快速度走”的任务约束，不再只是朝一个固定目标点移动。

## 5. 代码链路解释

### 5.1 `AMPEnv` 在做什么

`AMPEnv` 负责把 reference motion 和在线 rollout 都转换成判别器可吃的时序观测。

- demo 侧：
  - `mimickit/envs/amp_env.py:29-61`
  - 从 motion 库里采样时间点，然后拼成判别器 demo obs
- demo 数据展开：
  - `mimickit/envs/amp_env.py:63-86`
  - 以 `num_disc_obs_steps` 为时间窗口，取 root/joint/body 时序状态
- 在线缓存：
  - `mimickit/envs/amp_env.py:88-154`
  - 为 root pos/rot/vel、joint rot、dof vel、body pos 建 circular buffers
- 在线更新：
  - `mimickit/envs/amp_env.py:156-242`
  - 每步把当前角色状态推入历史缓存，再拼成当前 `disc_obs`

一句话总结：

- `AMPEnv` 的职责不是算最终奖励。
- 它的职责是维护“判别器看见的 reference 序列”和“判别器看见的 agent 序列”。

### 5.2 `AMPAgent` 在做什么

`AMPAgent` 负责把 PPO 的任务训练和 AMP 的对抗风格训练绑在一起。

- 读取 AMP 参数：
  - `mimickit/learning/amp_agent.py:15-29`
- 建立判别器 replay buffer：
  - `mimickit/learning/amp_agent.py:36-42`
- 建立判别器 normalizer：
  - `mimickit/learning/amp_agent.py:44-50`
- 每步记录在线 `disc_obs`：
  - `mimickit/learning/amp_agent.py:52-60`
- 训练前补充 demo obs + replay：
  - `mimickit/learning/amp_agent.py:67-99`
- 奖励融合：
  - `mimickit/learning/amp_agent.py:101-116`
  - 核心公式是：
    - `r = task_reward_weight * task_r + disc_reward_weight * disc_r`
- 判别器损失：
  - `mimickit/learning/amp_agent.py:118-190`
  - 包含：
    - agent/demo BCE
    - grad penalty
    - logit regularization
    - weight decay
- 风格奖励：
  - `mimickit/learning/amp_agent.py:209-217`

一句话总结：

- `AMPEnv` 提供“判别器输入”。
- `AMPAgent` 决定“任务奖励和风格奖励怎么合起来训练 policy”。

### 5.3 task env 比 baseline 多了什么

`location` 和 `steering` 都继承 task AMP 路线，但增加的是“任务 obs + 任务 reward”，不是替换掉 AMP。

#### `TaskLocationEnv`

- 目标点状态：
  - `mimickit/envs/task_location_env.py:53-60`
- 目标点重置逻辑：
  - `mimickit/envs/task_location_env.py:101-125`
- 新增 obs：
  - `mimickit/envs/task_location_env.py:127-143`
  - 本质是“角色朝向坐标系里的目标点二维向量”
- 新增 reward：
  - `mimickit/envs/task_location_env.py:145-156`
  - 具体公式在 `mimickit/envs/task_location_env.py:200-243`
  - 奖励由：
    - 接近目标点
    - 朝目标方向移动
    - 面向目标方向
    组成

#### `TaskSteeringEnv`

- steering 任务状态：
  - `mimickit/envs/task_steering_env.py:75-87`
  - 核心变量：
    - `tar_speed`
    - `tar_dir`
    - `face_dir`
- steering 任务重置逻辑：
  - `mimickit/envs/task_steering_env.py:168-200`
- 新增 obs：
  - `mimickit/envs/task_steering_env.py:202-220`
  - 公式在 `mimickit/envs/task_steering_env.py:250-267`
  - obs 结构是：
    - local target dir
    - target speed
    - local face dir
- 新增 reward：
  - `mimickit/envs/task_steering_env.py:222-237`
  - 公式在 `mimickit/envs/task_steering_env.py:270-297`
  - 奖励由：
    - 速度方向跟随目标
    - 角色朝向贴近 face dir
    组成

## 6. 三个 case 的学习对照表

| case | motion source | task reward 角色 | ARC 映射 |
|---|---|---|---|
| `amp_humanoid` | 单 clip：`humanoid_spinkick.pkl` | 无外部任务，只有风格主导 | 学 AMP 本体，理解 style prior 和 discriminator |
| `amp_location_humanoid` | dataset：`dataset_humanoid_locomotion.yaml` | 到点移动 | 后续 WalkBrain / MoveTo 任务前置模板 |
| `amp_steering_humanoid` | dataset：`dataset_humanoid_locomotion.yaml` | 方向、朝向、速度联合控制 | 后续 TurnBrain / heading control 前置模板 |

## 7. 验收结论

- `amp_humanoid`
  - `test` 通过
  - `visualize true` 通过
  - 短训练产物通过
- `amp_location_humanoid`
  - 任务目标点逻辑通过
  - task reward + AMP 指标同时出现
  - dataset 驱动 locomotion 含义已验证
- `amp_steering_humanoid`
  - `tar_dir / face_dir / tar_speed` 已进入 obs/reward 链路
  - task reward + AMP 指标同时出现
  - 适合作为后续 ARC-like TurnBrain 前置模板

本轮已经可以清楚回答：

- `AMPEnv` 在做什么：维护判别器时序观测
- `AMPAgent` 在做什么：融合 PPO 任务训练和 AMP 风格训练
- task env 比 baseline 多了什么：多了任务观测和任务奖励，但不替换 AMP 判别器链路

## 8. 下一阶段建议

下一阶段建议从下面这个入口继续，而不是直接自定义 ARC 机器人：

- 首选入口：`args/amp_location_humanoid_sword_shield_args.txt`

原因：

- 它仍然沿用你这轮已经学会的 task AMP 结构
- 但角色和数据分布更接近“有装备、有战斗语境的角色 locomotion”
- 比直接新造 ARC 资产更容易定位问题来源

建议顺序：

1. `amp_location_humanoid_sword_shield`
2. `amp_steering_humanoid_sword_shield`
3. 再进入自定义 ARC locomotion case

## 9. 备注

- `iters_per_output` 在 `data/agents/amp_humanoid_agent.yaml:19` 和 `data/agents/amp_task_humanoid_agent.yaml:19` 都是 `100`。
- 这意味着长训练在未到 `100` 次输出前，`log.txt` 只会稳定写入 `Iteration 0`。
- 因此本轮主验证策略是：
  - 先用长命令确认真实训练链路、实时指标、产物目录
  - 再用一迭代自然退出烟测补齐非零 TensorBoard 事件文件
