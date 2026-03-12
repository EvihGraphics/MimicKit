# ASE 全链路迁移计划（MimicKit 原生实现）

## Summary

- 本轮目标不再停留在 `ase_humanoid` / `ase_humanoid_sword_shield` 两个低层预训练案例，而是把 upstream `ASE` 的完整链路迁入 `MimicKit`。
- 上游对照源固定为 submodule：`third_party/ase_upstream`，仓库地址 `https://github.com/logic-three-body/ASE`，固定提交 `6f9b4f1f289603eee6a4f45d082bc6e6d83fecec`。
- 本地实现坚持 `MimicKit` 原生抽象：source of truth 在 `args/`、`data/`、`mimickit/`，submodule 只用于对照 README / cfg / assets / 预训练模型文件名，不在运行时直接 import。

## Upstream -> MimicKit Parity

| upstream ASE | upstream role | MimicKit case / path | status |
|---|---|---|---|
| `HumanoidAMPGetup` | LLC getup pretrain | `args/ase_getup_humanoid_sword_shield_args.txt` | 新增 trainable |
| `HumanoidPerturb` | LLC robustness test | `args/ase_perturb_humanoid_sword_shield_args.txt` | 新增 test-only |
| `HumanoidViewMotion` | motion viewer | `args/view_motion_humanoid_sword_shield_args.txt` | 复用 |
| `HumanoidHeading` | HLC heading task | `args/ase_heading_humanoid_sword_shield_args.txt` | 新增 trainable |
| `HumanoidLocation` | HLC location task | `args/ase_location_humanoid_sword_shield_args.txt` | 新增 trainable |
| `HumanoidReach` | HLC reach task | `args/ase_reach_humanoid_sword_shield_args.txt` | 新增 trainable |
| `HumanoidStrike` | HLC strike task | `args/ase_strike_humanoid_sword_shield_args.txt` | 新增 trainable |
| `ase_humanoid.yaml` LLC pretrain | locomotion latent pretrain | `args/ase_humanoid_args.txt` | 已有 |
| `ase_humanoid.yaml` sword/shield LLC pretrain | sword/shield latent pretrain | `args/ase_humanoid_sword_shield_args.txt` | 已有 |

说明：

- `HumanoidHeading` 在本地落在 `task_steering`。
- `HumanoidLocation` 在本地落在 `task_location`。
- `HumanoidReach` / `HumanoidStrike` 使用新的本地 task env。
- `HumanoidPerturb` 只用于 `test -> visualize`，不进入 trainable 主表。

## Key Changes

### 1. 上游对照源

- 新增 `.gitmodules` 条目，把 upstream `ASE` 固定到 `third_party/ase_upstream`。
- 文档中统一声明：
  - submodule 只做对照，不是运行时依赖；
  - 本地 case 不读取 submodule 内的 Python 代码；
  - 需要 1:1 对照时，只参考 upstream `README`、`ase/data/cfg/*`、`ase/data/models/*`。

### 2. 环境能力

- 复用现有：
  - `task_location` 作为 `HumanoidLocation`
  - `task_steering` 作为 `HumanoidHeading`
- 新增：
  - `ase_getup`
  - `ase_perturb`
  - `task_reach`
  - `task_strike`
- `ase_getup` 必须支持：
  - fall-state generation
  - recovery window
  - fall-init reset
  - 独立 getup test env config
- `task_reach` 必须提供：
  - 3D 目标点
  - target marker
  - sword-body reach reward
- `task_strike` 必须提供：
  - 物理 target
  - target reset
  - contact / velocity / topple 相关 reward
  - success termination
- task env 统一暴露 `compute_llc_obs()` / `get_llc_obs_space()`，供冻结的 ASE LLC 使用。

### 3. ASEHRL

- 新增 `agent_name: ASEHRL` 与 `mimickit/learning/ase_hrl_agent.py`、`mimickit/learning/ase_hrl_model.py`。
- 新公共接口：
  - `--llc_model_file`：必填，指定冻结 LLC checkpoint
  - `--llc_agent_config`：选填，默认 `data/agents/ase_humanoid_agent.yaml`
  - `llc_steps`：写在 `data/agents/ase_hrl_humanoid_agent.yaml`，默认 `5`
- 运行契约：
  - 高层 actor 输出 raw latent
  - 进入 LLC 前做 `L2 normalize`
  - 每个高层步执行 `llc_steps` 个低层步
  - 高层 reward 为 `0.9 * task_reward + 0.1 * llc_disc_reward`
  - LLC 参数不进入优化器，也不计入 trainable param count

### 4. 本地 ASE case 集合

- LLC trainable:
  - `ase_humanoid_args.txt`
  - `ase_humanoid_sword_shield_args.txt`
  - `ase_getup_humanoid_sword_shield_args.txt`
- HLC trainable:
  - `ase_heading_humanoid_sword_shield_args.txt`
  - `ase_location_humanoid_sword_shield_args.txt`
  - `ase_reach_humanoid_sword_shield_args.txt`
  - `ase_strike_humanoid_sword_shield_args.txt`
- Test-only:
  - `ase_perturb_humanoid_sword_shield_args.txt`
- Reused tooling:
  - `view_motion_humanoid_sword_shield_args.txt`

## Implementation Order

1. 接入 submodule，并固定提交号。
2. 落 `ASEHRL` agent/model 与 `--llc_model_file` 运行时约定。
3. 新增 `ase_getup / ase_perturb / task_reach / task_strike`，并在 `env_builder` 注册。
4. 补齐 `data/envs/`、`data/agents/`、`args/` 新案例。
5. 新增 full-chain SOP，并更新 ASE 方法文档、docs 索引、case catalog。
6. 做静态检查与最小 smoke validation。

## Acceptance

- `.gitmodules` 与 gitlink 路径正确，submodule 指向固定提交。
- 新增 args/env/agent 全部能被本地解析。
- `heading/location/reach/strike` 缺失 `--llc_model_file` 时立即失败，并给出清晰错误。
- `ASEHRL` 的 trainable params 不包含 LLC。
- docs 中明确区分：
  - submodule 是对照源
  - `Newton` 是主口径
  - `Isaac Gym` 只保留 parity / fallback 说明

## Validation Result

- `2026-03-12` 已完成一轮 `ASE` 全链路 smoke validation。
- 验证根目录：`output/train/ase_validation_suite_smoke_20260312_093358`
- 结果：`27/27 ok`
- 覆盖项：
  - train artifact 存在性：`ase_humanoid`、`ase_humanoid_sword_shield`、`ase_getup`、`ase_heading`、`ase_location`、`ase_reach`、`ase_strike`
  - HLC 缺参保护：`ASEHRL requires --llc_model_file`
  - `test -> visualize`：`ase_humanoid`、`ase_humanoid_sword_shield`、`ase_getup`、`ase_heading`、`ase_location`、`ase_reach`、`ase_strike`
  - `getup` 专项：`ase_getup_humanoid_sword_shield_test_env.yaml`
  - robustness：`ase_perturb_humanoid_sword_shield`
  - motion viewer：`view_motion_humanoid_sword_shield` single clip / dataset yaml
- 本轮为通过验证额外修复的运行时问题：
  - Newton headless viewer 的 CUDA-GL interop fallback
  - `ASEHRL` latent action normalizer shape
  - LLC env adapter 缺失 `set_mode`
  - `ase_getup` fall-state 初始化时的张量别名写回
- `2026-03-12` 已完成一轮 `ASE` 闭环回归：
  - 根目录：`output/train/ase_closure_regression_20260312_145341`
  - 最终汇总：`results_final.tsv`
  - 结果：`24/24 ok`

## White-Knight Motion Library Parity

- 官方 `ASE` 官网里“白骑士拿剑盾的很多动作”，在本仓库中落为 motion-library parity，而不是更多 task family。
- 当前唯一真源：
  - `data/motions/reallusion/ase_reallusion_sword_shield_manifest.tsv`
  - `tools/ue_bridge/build_ase_reallusion_motion_render_root.py`
- 资产口径：
  - 总数 `87`
  - LLC train-enabled `82`
  - fall view-only `5`
- 渲染口径：
  - helper 生成 synthetic `output/train/<root>/best_by_case.tsv`
  - 再复用 `tools/ue_bridge/build_mimickit_render_sequences.py`
  - 输出目录固定为 `output/img/<root>/runs/view_motion_humanoid_sword_shield_args/<motion_id>/render`
- `2026-03-12` motion-library 验证结果：
  - 训练根目录：`output/train/case_ase_reallusion_motion_library_smoke_20260312_143511`
  - 图片根目录：`output/img/case_ase_reallusion_motion_library_smoke_20260312_143511`
  - 渲染索引：`infer_viz_index.tsv`
  - 结果：`87/87 ok`
