# ASE Full-Chain Train / Infer / Visual SOP

本文档是 `MimicKit` 当前 `ASE` 全链路执行口径，主线固定为：

`LLC 训练 -> HLC 训练 -> test -> visualize -> 离线渲染 -> perturb / view_motion 验收`

说明：

- 这是执行型 SOP，不是论文导读。
- 上游对照源固定为 `third_party/ase_upstream`，提交 `6f9b4f1f289603eee6a4f45d082bc6e6d83fecec`。
- submodule 只用于对照 upstream `README / cfg / models / assets`，运行时不要直接 import。
- 本实现已在 `2026-03-12` 完成一轮 `27/27` smoke validation，验证根目录为 `output/train/ase_validation_suite_smoke_20260312_093358`。
- 本实现已在 `2026-03-12` 完成一轮 `24/24` ASE 闭环回归，验证根目录为 `output/train/ase_closure_regression_20260312_145341`，最终汇总见 `results_final.tsv`。
- 白骑士动作库已在 `2026-03-12` 完成一轮 `87/87` per-clip render 验证，训练根目录为 `output/train/case_ase_reallusion_motion_library_smoke_20260312_143511`，图片根目录为 `output/img/case_ase_reallusion_motion_library_smoke_20260312_143511`。
- 官方白骑士剑盾演示在本仓库中归类为 motion-library parity，不额外拆成几十个 ASE task；对应唯一真源是 `data/motions/reallusion/ase_reallusion_sword_shield_manifest.tsv`。
- 当前保留两种 sword/shield 可视化方式：
  - `geom`：默认 `xml` 物理几何体，可视化更稳，保持训练/验收主口径。
  - `mesh`：可选 `usd` 白骑士外观，只建议用于 test / visualize / render，不建议替换训练基线。
- 本文默认解释器统一使用：

```bash
/root/miniconda3/envs/mimickit/bin/python
```

## 1. Upstream 映射

| upstream ASE | MimicKit |
|---|---|
| `HumanoidAMPGetup` | `ase_getup_humanoid_sword_shield_args.txt` |
| `HumanoidPerturb` | `ase_perturb_humanoid_sword_shield_args.txt` |
| `HumanoidViewMotion` | `view_motion_humanoid_sword_shield_args.txt` |
| `HumanoidHeading` | `ase_heading_humanoid_sword_shield_args.txt` |
| `HumanoidLocation` | `ase_location_humanoid_sword_shield_args.txt` |
| `HumanoidReach` | `ase_reach_humanoid_sword_shield_args.txt` |
| `HumanoidStrike` | `ase_strike_humanoid_sword_shield_args.txt` |

## 2. 7-Case 与论文交互 Agent 的关系

当前主线中的 `7` 个 trainable ASE case，已经覆盖论文口径里“可运动、可恢复、可接收高层目标、可与环境交互”的 agent 主干能力。

| case | 能力定位 | 对最终 agent 的作用 |
|---|---|---|
| `ase_humanoid` | 基础 locomotion LLC | 提供无武器 humanoid 的基础动作先验，验证 LLC 训练链可用 |
| `ase_humanoid_sword_shield` | 剑盾 locomotion LLC | 提供后续所有 sword/shield HLC 任务共享的底层技能库 |
| `ase_getup_humanoid_sword_shield` | 恢复 LLC | 让 agent 在跌倒或扰动后能重新站起，而不是一次失败就结束 |
| `ase_heading_humanoid_sword_shield` | 方向控制 HLC | 让 agent 能持续响应方向目标，体现“接收高层控制信号” |
| `ase_location_humanoid_sword_shield` | 导航 HLC | 让 agent 能稳定走向空间目标点，形成基础场景移动能力 |
| `ase_reach_humanoid_sword_shield` | 末端接近 HLC | 让 agent 能把 sword 主动送向 3D 目标，形成定向交互能力 |
| `ase_strike_humanoid_sword_shield` | 攻击交互 HLC | 让 agent 能对 target 产生稳定接触/击倒趋势，构成显式环境交互 |

结论：

- 如果目标是复刻论文里的 `hierarchical interactive agent`，这 `7` 个训练 case 就是主干闭环。
- LLC 负责“怎么动”，HLC 负责“朝哪里动、碰哪里、打哪里”。
- `ase_humanoid_sword_shield` 的 LLC 模型是 `heading/location/reach/strike` 的共享前提，不应跳过。
- `getup` 不是额外装饰项，而是让交互 agent 在真实 rollout 中具备恢复性的关键能力。

边界说明：

- `perturb` 和 `view_motion` 不属于这 `7` 个 trainable case。
- `perturb` 用来验收鲁棒性，回答“被打乱后还能不能继续站立/行动”。
- `view_motion` 用来验收动作库与资产呈现，回答“动作素材和可视化是否正确”。
- 白骑士外观复刻属于可视化层，不决定论文口径 agent 是否成立。

## 3. 运行前检查

```bash
cd /root/Project/MimicKit

git submodule update --init --recursive third_party/ase_upstream
git -C third_party/ase_upstream rev-parse HEAD
```

期望输出的提交应为：

```text
6f9b4f1f289603eee6a4f45d082bc6e6d83fecec
```

默认建议：

- 主口径后端：`data/engines/newton_engine.yaml`
- 双卡训练：`--devices cuda:0 cuda:1`
- 训练输出：`output/train/<run_name>`
- 渲染输出：`output/img/<root>/runs/<case>/<variant>/render`

headless 可视化 / 离线渲染统一建议先带上：

```bash
export MIMICKIT_VIEWER_HEADLESS=1
export MESA_GL_VERSION_OVERRIDE=3.3
export MESA_GLSL_VERSION_OVERRIDE=330
```

说明：

- 当前 `MimicKit` 会在 headless viewer 下自动禁用 Newton viewer 的 CUDA-GL interop，并切到 CPU 抓帧 fallback。
- 如果不带 `MESA_*` 环境变量，WSL / headless OpenGL 栈可能报 `GLSL 1.50 is not supported`。

剑盾角色可视化口径：

| mode | asset | 用途 | 入口 |
|---|---|---|---|
| `geom` | `data/assets/sword_shield/humanoid_sword_shield.xml` | 默认训练、默认 test/viz、主验证口径 | 现有 `data/envs/*sword_shield*_env.yaml` |
| `mesh` | `data/assets/sword_shield/humanoid_sword_shield.usd` | 白骑士外观观察、离线图片导出、官网观感对照 | 新增 `data/envs/*sword_shield*_mesh_env.yaml` |

建议：

- 要做训练回归、指标比较、问题定位，先用 `geom`。
- 要确认“是否看到白骑士”，改用对应的 `_mesh_env.yaml`。
- `_mesh_env.yaml` 会把视觉资产切到 `usd`，同时把 `kin_char_file` 保持在 `xml`，避免把运动学解析绑到 `pxr`。
- `mesh` 模式需要 `data/engines/isaac_lab_engine.yaml` 这类支持 `usd` 的 backend；当前 `newton_engine.yaml` 不能直接实例化 `.usd` 资产。

## 3.1 官方停止线

当前仓库中如果直接运行 `mimickit/run.py --mode train`，默认没有硬停止线；必须显式传 `--max_samples` 才会在指定样本预算停下。

官方口径应按 upstream 训练配置推算，而不是按看板里历史上临时使用的 `1e9` 预算线：

| family | case | upstream cfg basis | 官方样本口径 |
|---|---|---|---:|
| LLC | `ase_humanoid` | `numEnvs=4096`, `horizon_length=32`, `max_epochs=100000` | `13,107,200,000` |
| LLC | `ase_humanoid_sword_shield` | 同上 | `13,107,200,000` |
| LLC | `ase_getup_humanoid_sword_shield` | 同上 | `13,107,200,000` |
| HLC | `ase_heading_humanoid_sword_shield` | `numEnvs=4096`, `horizon_length=32`, `max_epochs=10000` | `1,310,720,000` |
| HLC | `ase_location_humanoid_sword_shield` | 同上 | `1,310,720,000` |
| HLC | `ase_reach_humanoid_sword_shield` | 同上 | `1,310,720,000` |
| HLC | `ase_strike_humanoid_sword_shield` | 同上 | `1,310,720,000` |
| tooling | `ase_perturb_humanoid_sword_shield` | nontrainable | 不按 samples 停 |
| tooling | `view_motion_humanoid_sword_shield` | nontrainable | 不按 samples 停 |

说明：

- LLC 的 `13,107,200,000` 来自 `4096 * 32 * 100000`。
- HLC 的 `1,310,720,000` 来自 `4096 * 32 * 10000`。
- 这两个数是“官方配置等价样本预算”；在本仓库里即使 `num_envs` 改成双卡 `2048` 或单卡 `1024`，样本总预算本身不变，只是 wall-clock 和迭代数会变。
- `ase_perturb`、`view_motion` 不属于 trainable case，停止线由 `test_episodes` 或渲染帧数决定。

## 4. LLC 训练

### 4.1 Locomotion LLC

```bash
/root/miniconda3/envs/mimickit/bin/python mimickit/run.py \
  --arg_file args/ase_humanoid_args.txt \
  --engine_config data/engines/newton_engine.yaml \
  --mode train \
  --visualize false \
  --devices cuda:0 cuda:1 \
  --max_samples 13107200000 \
  --out_dir output/train/ase_humanoid_fullchain
```

### 4.2 Sword / Shield LLC

```bash
/root/miniconda3/envs/mimickit/bin/python mimickit/run.py \
  --arg_file args/ase_humanoid_sword_shield_args.txt \
  --engine_config data/engines/newton_engine.yaml \
  --mode train \
  --visualize false \
  --devices cuda:0 cuda:1 \
  --max_samples 13107200000 \
  --out_dir output/train/ase_humanoid_sword_shield_fullchain
```

### 4.3 Getup LLC

```bash
/root/miniconda3/envs/mimickit/bin/python mimickit/run.py \
  --arg_file args/ase_getup_humanoid_sword_shield_args.txt \
  --engine_config data/engines/newton_engine.yaml \
  --mode train \
  --visualize false \
  --devices cuda:0 cuda:1 \
  --max_samples 13107200000 \
  --out_dir output/train/ase_getup_humanoid_sword_shield_fullchain
```

LLC 训练观察项：

- `disc_reward_mean`
- `enc_reward_mean`
- `Mean Return`
- `model.pt`

LLC 验收：

- 动作不能是纯抖动或长时间原地冻结。
- latent 切换后不能大面积摔倒。
- `ase_getup` 至少能看到明显恢复窗口，不是倒地后直接终止。

### 4.4 LLC 断点续训

```bash
/root/miniconda3/envs/mimickit/bin/python mimickit/run.py \
  --arg_file args/ase_humanoid_sword_shield_args.txt \
  --engine_config data/engines/newton_engine.yaml \
  --mode train \
  --visualize false \
  --devices cuda:0 cuda:1 \
  --max_samples <remaining_samples_for_this_resume_segment> \
  --model_file output/train/ase_humanoid_sword_shield_fullchain/model.pt \
  --out_dir output/train/ase_humanoid_sword_shield_fullchain_resume
```

注意：

- raw `run.py --model_file ... --out_dir new_root` 的 `sample_count` 会从 `0` 重新开始，不会自动继承旧 root 的已训练 samples。
- 所以断点续训时，`--max_samples` 必须传“当前续训段还需要补的剩余 samples”，不能再直接写完整官方预算。
- 如果希望自动按历史 segment 汇总剩余样本，优先用本文后面的 keepalive 口径。

## 5. HLC 训练

`ASEHRL` 必须显式指定 `--llc_model_file`。缺失该参数时应立即报错。

公共模板：

```bash
/root/miniconda3/envs/mimickit/bin/python mimickit/run.py \
  --arg_file args/<hlc_case>.txt \
  --engine_config data/engines/newton_engine.yaml \
  --mode train \
  --visualize false \
  --devices cuda:0 cuda:1 \
  --max_samples 1310720000 \
  --llc_model_file output/train/ase_humanoid_sword_shield_fullchain/model.pt \
  --out_dir output/train/<hlc_run_name>
```

推荐 case：

| HLC case | 说明 |
|---|---|
| `ase_heading_humanoid_sword_shield_args.txt` | 对应 upstream `HumanoidHeading`，落在本地 `task_steering` |
| `ase_location_humanoid_sword_shield_args.txt` | 对应 upstream `HumanoidLocation`，落在本地 `task_location` |
| `ase_reach_humanoid_sword_shield_args.txt` | 对应 upstream `HumanoidReach` |
| `ase_strike_humanoid_sword_shield_args.txt` | 对应 upstream `HumanoidStrike` |

示例：Heading

```bash
/root/miniconda3/envs/mimickit/bin/python mimickit/run.py \
  --arg_file args/ase_heading_humanoid_sword_shield_args.txt \
  --engine_config data/engines/newton_engine.yaml \
  --mode train \
  --visualize false \
  --devices cuda:0 cuda:1 \
  --max_samples 1310720000 \
  --llc_model_file output/train/ase_humanoid_sword_shield_fullchain/model.pt \
  --out_dir output/train/ase_heading_humanoid_sword_shield_fullchain
```

HLC 验收：

- `heading/location/reach/strike` 都必须产出 `model.pt`。
- `Heading` 必须走 `task_steering`，`Location` 必须走 `task_location`。
- `Reach/Strike` 必须加载新 task env，而不是 AMP 旧 case。
- LLC trainable params 不应出现在 HLC 优化器中。

### 5.1 官方口径 keepalive 启动

如果要按官方样本口径自动续训、自动计算 remaining samples，推荐直接走：

```bash
cd /root/Project/MimicKit

./scripts/run_ase_7case_keepalive.py \
  --root-out ase_7case_official_budget \
  --engine-config data/engines/newton_engine.yaml \
  --devices-train cuda:0,cuda:1 \
  --strict-dual-gpu \
  --primary-num-envs 2048 \
  --fallback-num-envs 1024,512 \
  --llc-target-samples 13107200000 \
  --hlc-target-samples 1310720000 \
  --case-budget-hours 0
```

说明：

- `--case-budget-hours 0` 表示关闭按小时强截断，避免在达到官方样本预算前被 `8h` 预算提前切断。
- `ase_humanoid`、`ase_humanoid_sword_shield`、`ase_getup` 会自动使用 LLC 口径。
- `heading/location/reach/strike` 会自动使用 HLC 口径。

## 6. Test 与交互可视化

### 6.1 LLC / HLC 通用 test

```bash
/root/miniconda3/envs/mimickit/bin/python mimickit/run.py \
  --arg_file args/ase_strike_humanoid_sword_shield_args.txt \
  --engine_config data/engines/newton_engine.yaml \
  --mode test \
  --visualize false \
  --num_envs 1 \
  --test_episodes 10 \
  --llc_model_file output/train/ase_humanoid_sword_shield_fullchain/model.pt \
  --model_file output/train/ase_strike_humanoid_sword_shield_fullchain/model.pt
```

观察：

- `Mean Return`
- `Mean Episode Length`
- 是否能稳定跑完整 episode

### 6.2 交互可视化

```bash
/root/miniconda3/envs/mimickit/bin/python mimickit/run.py \
  --arg_file args/ase_humanoid_sword_shield_args.txt \
  --engine_config data/engines/newton_engine.yaml \
  --mode test \
  --visualize true \
  --num_envs 1 \
  --test_episodes 1 \
  --model_file output/train/ase_humanoid_sword_shield_fullchain/model.pt
```

白骑士 mesh 版：

```bash
/root/miniconda3/envs/mimickit/bin/python mimickit/run.py \
  --arg_file args/ase_humanoid_sword_shield_args.txt \
  --env_config data/envs/ase_humanoid_sword_shield_mesh_env.yaml \
  --engine_config data/engines/isaac_lab_engine.yaml \
  --mode test \
  --visualize true \
  --num_envs 1 \
  --test_episodes 1 \
  --model_file output/train/ase_humanoid_sword_shield_fullchain/model.pt
```

说明：

- `geom` 版继续用 `data/engines/newton_engine.yaml`。
- `mesh` 版改用 `data/engines/isaac_lab_engine.yaml`；如果当前环境没有 Isaac Lab / USD 运行时，只能先用 `geom` 版。

LLC 看：

- 不同 latent 是否有可辨识差异
- 技能切换是否连续
- sword / shield 上肢是否协调

HLC 看：

- `heading` 是否能持续对齐目标方向
- `location` 是否能稳定到点
- `reach` 是否能主动把 sword 送向目标
- `strike` 是否能对 target 产生稳定击倒/扰动

### 6.3 Getup 专项 test

```bash
/root/miniconda3/envs/mimickit/bin/python mimickit/run.py \
  --arg_file args/ase_getup_humanoid_sword_shield_args.txt \
  --env_config data/envs/ase_getup_humanoid_sword_shield_test_env.yaml \
  --engine_config data/engines/newton_engine.yaml \
  --mode test \
  --visualize true \
  --num_envs 1 \
  --test_episodes 3 \
  --model_file output/train/ase_getup_humanoid_sword_shield_fullchain/model.pt
```

白骑士 mesh 版把 `--env_config` 改为：

```text
data/envs/ase_getup_humanoid_sword_shield_test_mesh_env.yaml
```

并把 `--engine_config` 改为：

```text
data/engines/isaac_lab_engine.yaml
```

专项验收：

- 跌倒初始化后应能进入恢复动作，而不是持续躺地抖动。

## 7. 离线序列渲染

```bash
/root/miniconda3/envs/mimickit/bin/python tools/ue_bridge/build_mimickit_render_sequences.py \
  --roots ase_fullchain_root \
  --cases ase_humanoid_sword_shield \
  --frames 300 \
  --frame-stride 5 \
  --device cuda:0 \
  --num-envs 1
```

输出契约：

- `output/img/<root>/runs/<case>/<variant>/render/frames/frame_000000.png`
- `output/img/<root>/runs/<case>/<variant>/render/render_meta.json`
- `output/img/<root>/infer_viz_index.tsv`

ASE 专属注意：

- 优先信任 agent test loop 路径。
- 不要先用静态 actor 包装结果判断 `ASE` 坍缩。
- 如果看到“蓝色 agent 原地轻微抖动”，先复查渲染路径，再判训练失败。

## 8. Perturb 验收

```bash
/root/miniconda3/envs/mimickit/bin/python mimickit/run.py \
  --arg_file args/ase_perturb_humanoid_sword_shield_args.txt \
  --engine_config data/engines/newton_engine.yaml \
  --mode test \
  --visualize true \
  --num_envs 1 \
  --test_episodes 1 \
  --model_file output/train/ase_humanoid_sword_shield_fullchain/model.pt
```

验收：

- projectile 能持续生成，不是只出现一次。
- 角色受扰动后不应立刻退化成纯抖动或完全失控。

## 9. View Motion 验收

### 9.1 单动作

```bash
/root/miniconda3/envs/mimickit/bin/python mimickit/run.py \
  --arg_file args/view_motion_humanoid_sword_shield_args.txt \
  --engine_config data/engines/newton_engine.yaml \
  --env_config data/envs/view_motion_humanoid_sword_shield_env.yaml \
  --mode test \
  --visualize true \
  --num_envs 1 \
  --test_episodes 1
```

白骑士 mesh 版：

```bash
/root/miniconda3/envs/mimickit/bin/python mimickit/run.py \
  --arg_file args/view_motion_humanoid_sword_shield_args.txt \
  --engine_config data/engines/isaac_lab_engine.yaml \
  --env_config data/envs/view_motion_humanoid_sword_shield_mesh_env.yaml \
  --mode test \
  --visualize true \
  --num_envs 1 \
  --test_episodes 1
```

### 9.2 数据集

```bash
/root/miniconda3/envs/mimickit/bin/python mimickit/run.py \
  --arg_file args/view_motion_humanoid_sword_shield_args.txt \
  --engine_config data/engines/newton_engine.yaml \
  --env_config data/envs/view_motion_humanoid_sword_shield_dataset_env.yaml \
  --mode test \
  --visualize true \
  --num_envs 1 \
  --test_episodes 1
```

白骑士 mesh 版把 `--env_config` 改为：

```text
data/envs/view_motion_humanoid_sword_shield_dataset_mesh_env.yaml
```

并把 `--engine_config` 改为：

```text
data/engines/isaac_lab_engine.yaml
```

验收：

- `view_motion_humanoid_sword_shield` 必须同时支持单 clip 与 dataset yaml。
- `geom` 与 `mesh` 都必须有明确入口；其中 `mesh` 只用于外观观察，不替代训练主口径。
- 这一路径只验证动作资产与渲染，不代表策略质量。
- Newton 下直接跑 `view_motion` 时，建议保持默认设备 `cuda:0`，不要强行切到 `cuda:1`；否则可能触发 Warp `copy_indexed` 的跨设备 launch 报错。
- 当前 `newton_engine.yaml` 不能直接加载 `.usd`，所以白骑士 mesh 版要切到 `data/engines/isaac_lab_engine.yaml`。

## 10. 白骑士动作库全覆盖

官方 `ASE` 官网里最显眼的白骑士剑盾展示，主要来自 Reallusion 的两套动作素材：

- `Sword & Shield Stunts`
- `Sword & Shield Moves`

在 `MimicKit` 中，这部分不作为新的 task family 接入，而是作为 `view_motion_humanoid_sword_shield` 的 manifest-driven 资产覆盖：

- manifest：`data/motions/reallusion/ase_reallusion_sword_shield_manifest.tsv`
- helper：`tools/ue_bridge/build_ase_reallusion_motion_render_root.py`

当前口径：

- 总动作数：`87`
- LLC 训练启用：`82`
- fall 资产：`5`
- fall 只进入 `view / render / index`，不回灌 `data/datasets/dataset_humanoid_sword_shield.yaml`
- 当前已验证根目录：
  - `output/train/case_ase_reallusion_motion_library_smoke_20260312_143511`
  - `output/img/case_ase_reallusion_motion_library_smoke_20260312_143511`

### 10.1 生成 per-clip render root

```bash
ROOT_NAME=case_ase_reallusion_motion_library_$(date +%Y%m%d_%H%M%S)

/root/miniconda3/envs/mimickit/bin/python tools/ue_bridge/build_ase_reallusion_motion_render_root.py \
  --root-name "${ROOT_NAME}" \
  --engine-config data/engines/newton_engine.yaml
```

白骑士 mesh 版：

```bash
/root/miniconda3/envs/mimickit/bin/python tools/ue_bridge/build_ase_reallusion_motion_render_root.py \
  --root-name "${ROOT_NAME}" \
  --engine-config data/engines/isaac_lab_engine.yaml \
  --base-env-config data/envs/view_motion_humanoid_sword_shield_mesh_env.yaml
```

生成结果：

- `output/train/${ROOT_NAME}/best_by_case.tsv`
- `output/train/${ROOT_NAME}/generated_envs/<motion_id>.yaml`

### 10.2 dry-run 检查

```bash
/root/miniconda3/envs/mimickit/bin/python tools/ue_bridge/build_mimickit_render_sequences.py \
  --roots "${ROOT_NAME}" \
  --cases view_motion_humanoid_sword_shield_args \
  --dry-run
```

验收：

- dry-run 必须发现 `87` 个 job。
- variant 必须直接对应 `motion_id`。

### 10.3 全量离线渲染

```bash
/root/miniconda3/envs/mimickit/bin/python tools/ue_bridge/build_mimickit_render_sequences.py \
  --roots "${ROOT_NAME}" \
  --cases view_motion_humanoid_sword_shield_args \
  --frames 300 \
  --frame-stride 5 \
  --device cuda:0 \
  --num-envs 1
```

输出契约：

- `output/img/<root>/runs/view_motion_humanoid_sword_shield_args/<motion_id>/render/frames/frame_000000.png`
- `output/img/<root>/runs/view_motion_humanoid_sword_shield_args/<motion_id>/render/render_meta.json`
- `output/img/<root>/infer_viz_index.tsv`

索引字段至少应包含：

- `motion_id`
- `motion_file`
- `source_pack`
- `category`
- `train_enabled`
- `view_enabled`

抽样验收建议：

- 至少覆盖 `combo / slash / stab / locomotion / idle / taunt / block / parry / fall`。
- `5` 个 fall 动作必须能单独 view / render，但不能被误写成 LLC 训练输入。
- 如果索引里看到 `visual_kind=geom`，说明还在走默认 `xml`；要看白骑士，应改用 `_mesh_env.yaml` 或 `--base-env-config ..._mesh_env.yaml`。
- 如果在 `mesh` 模式下仍使用 `data/engines/newton_engine.yaml`，会直接报 `.usd` asset unsupported；这是当前 Newton 后端的已知边界。

## 11. 看板与排障

### 11.1 ASE 看板

```bash
/root/miniconda3/envs/mimickit/bin/python scripts/run_ase_dashboard.py \
  --root-out ase_humanoid_sword_shield_fullchain
```

### 11.2 常见问题

- `python: command not found`
  - 统一改用 `/root/miniconda3/envs/mimickit/bin/python`
- `ModuleNotFoundError: isaacgym`
  - 主线改用 `data/engines/newton_engine.yaml`
- `--llc_model_file` 缺失
  - `ASEHRL` 会直接失败，这是预期保护
- `DISPLAY` / OpenGL / headless 报错
  - 先确认 `MIMICKIT_VIEWER_HEADLESS=1` 与 `MESA_GL_VERSION_OVERRIDE=3.3`、`MESA_GLSL_VERSION_OVERRIDE=330`
  - 再走 headless test 与离线渲染
- `view_motion` 在 `cuda:1` 上报 `copy_indexed` device mismatch
  - 这是当前 Newton direct-run 的已知限制
  - 直接回到默认设备 `cuda:0`，或改走 render-sequence helper
- `run.py --help` 不可用
  - `run.py` 不是 argparse 风格 CLI，统一从 `args/*.txt` + 显式覆写参数运行
