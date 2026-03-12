# ASE Full-Chain Train / Infer / Visual SOP

本文档是 `MimicKit` 当前 `ASE` 全链路执行口径，主线固定为：

`LLC 训练 -> HLC 训练 -> test -> visualize -> 离线渲染 -> perturb / view_motion 验收`

说明：

- 这是执行型 SOP，不是论文导读。
- 上游对照源固定为 `third_party/ase_upstream`，提交 `6f9b4f1f289603eee6a4f45d082bc6e6d83fecec`。
- submodule 只用于对照 upstream `README / cfg / models / assets`，运行时不要直接 import。
- 本实现已在 `2026-03-12` 完成一轮 `27/27` smoke validation，验证根目录为 `output/train/ase_validation_suite_smoke_20260312_093358`。
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

## 2. 运行前检查

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

## 3. LLC 训练

### 3.1 Locomotion LLC

```bash
/root/miniconda3/envs/mimickit/bin/python mimickit/run.py \
  --arg_file args/ase_humanoid_args.txt \
  --engine_config data/engines/newton_engine.yaml \
  --mode train \
  --visualize false \
  --devices cuda:0 cuda:1 \
  --out_dir output/train/ase_humanoid_fullchain
```

### 3.2 Sword / Shield LLC

```bash
/root/miniconda3/envs/mimickit/bin/python mimickit/run.py \
  --arg_file args/ase_humanoid_sword_shield_args.txt \
  --engine_config data/engines/newton_engine.yaml \
  --mode train \
  --visualize false \
  --devices cuda:0 cuda:1 \
  --out_dir output/train/ase_humanoid_sword_shield_fullchain
```

### 3.3 Getup LLC

```bash
/root/miniconda3/envs/mimickit/bin/python mimickit/run.py \
  --arg_file args/ase_getup_humanoid_sword_shield_args.txt \
  --engine_config data/engines/newton_engine.yaml \
  --mode train \
  --visualize false \
  --devices cuda:0 cuda:1 \
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

### 3.4 LLC 断点续训

```bash
/root/miniconda3/envs/mimickit/bin/python mimickit/run.py \
  --arg_file args/ase_humanoid_sword_shield_args.txt \
  --engine_config data/engines/newton_engine.yaml \
  --mode train \
  --visualize false \
  --devices cuda:0 cuda:1 \
  --model_file output/train/ase_humanoid_sword_shield_fullchain/model.pt \
  --out_dir output/train/ase_humanoid_sword_shield_fullchain_resume
```

## 4. HLC 训练

`ASEHRL` 必须显式指定 `--llc_model_file`。缺失该参数时应立即报错。

公共模板：

```bash
/root/miniconda3/envs/mimickit/bin/python mimickit/run.py \
  --arg_file args/<hlc_case>.txt \
  --engine_config data/engines/newton_engine.yaml \
  --mode train \
  --visualize false \
  --devices cuda:0 cuda:1 \
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
  --llc_model_file output/train/ase_humanoid_sword_shield_fullchain/model.pt \
  --out_dir output/train/ase_heading_humanoid_sword_shield_fullchain
```

HLC 验收：

- `heading/location/reach/strike` 都必须产出 `model.pt`。
- `Heading` 必须走 `task_steering`，`Location` 必须走 `task_location`。
- `Reach/Strike` 必须加载新 task env，而不是 AMP 旧 case。
- LLC trainable params 不应出现在 HLC 优化器中。

## 5. Test 与交互可视化

### 5.1 LLC / HLC 通用 test

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

### 5.2 交互可视化

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

LLC 看：

- 不同 latent 是否有可辨识差异
- 技能切换是否连续
- sword / shield 上肢是否协调

HLC 看：

- `heading` 是否能持续对齐目标方向
- `location` 是否能稳定到点
- `reach` 是否能主动把 sword 送向目标
- `strike` 是否能对 target 产生稳定击倒/扰动

### 5.3 Getup 专项 test

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

专项验收：

- 跌倒初始化后应能进入恢复动作，而不是持续躺地抖动。

## 6. 离线序列渲染

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

## 7. Perturb 验收

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

## 8. View Motion 验收

### 8.1 单动作

```bash
/root/miniconda3/envs/mimickit/bin/python mimickit/run.py \
  --arg_file args/view_motion_humanoid_sword_shield_args.txt \
  --engine_config data/engines/newton_engine.yaml \
  --env_config data/envs/view_motion_humanoid_sword_shield_env.yaml \
  --mode test \
  --visualize true
```

### 8.2 数据集

```bash
/root/miniconda3/envs/mimickit/bin/python mimickit/run.py \
  --arg_file args/view_motion_humanoid_sword_shield_args.txt \
  --engine_config data/engines/newton_engine.yaml \
  --env_config data/envs/view_motion_humanoid_sword_shield_dataset_env.yaml \
  --mode test \
  --visualize true
```

验收：

- `view_motion_humanoid_sword_shield` 必须同时支持单 clip 与 dataset yaml。
- 这一路径只验证动作资产与渲染，不代表策略质量。

## 9. 看板与排障

### 9.1 ASE 看板

```bash
/root/miniconda3/envs/mimickit/bin/python scripts/run_ase_dashboard.py \
  --root-out ase_humanoid_sword_shield_fullchain
```

### 9.2 常见问题

- `python: command not found`
  - 统一改用 `/root/miniconda3/envs/mimickit/bin/python`
- `ModuleNotFoundError: isaacgym`
  - 主线改用 `data/engines/newton_engine.yaml`
- `--llc_model_file` 缺失
  - `ASEHRL` 会直接失败，这是预期保护
- `DISPLAY` / OpenGL / headless 报错
  - 先确认 `MIMICKIT_VIEWER_HEADLESS=1` 与 `MESA_GL_VERSION_OVERRIDE=3.3`、`MESA_GLSL_VERSION_OVERRIDE=330`
  - 再走 headless test 与离线渲染
- `run.py --help` 不可用
  - `run.py` 不是 argparse 风格 CLI，统一从 `args/*.txt` + 显式覆写参数运行
