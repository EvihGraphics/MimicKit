# ASE Prework Snapshot Then Fullchain Worktree

## Summary
先不把当前脏工作树直接推到 `origin/main`。本轮先把“当前分支里的 ASE 相关预备改动”整理到远端特性分支 `feat/ase-prework`，推送成功后记录该提交 SHA，再从这个已推送的确定提交创建新 worktree `feat/ase-fullchain-agent`。新 worktree 的第一优先级仍然是训练闭环：`LLC -> HLC -> test -> 基础 visualize`；白骑士观感复刻继续放到第二阶段。

## Key Changes
- 当前工作树先从 `main` 切到新分支 `feat/ase-prework` 再提交，避免本地提交落在 `main` 并误推 `origin/main`。
- 本次 `feat/ase-prework` 提交只收 ASE 相关改动，明确包含：
  - `.gitignore` 中对 `data/envs/*mesh_env.yaml` 的放行
  - ASE 文档更新：`README_ASE_FullChain_TrainInferVisual_SOP`、`README_ASE`
  - 运行时支持：`mimickit/engines/isaac_lab_engine.py`、`mimickit/engines/newton_engine.py`、`mimickit/envs/char_env.py`
  - 渲染 helper：`tools/ue_bridge/build_mimickit_render_sequences.py`
  - 新增的 `data/envs/*mesh_env.yaml`
- 本次提交明确排除：
  - 本地临时文件：`agent_config.yaml`、`env_config.yaml`、`engine_config.yaml`
  - `Zone.Identifier`
  - `docs/plan/*` 计划稿
  - `docs/skill/*` 的工作流说明改动
  - 仅权限位变化的脚本
  - 无关脚本与 Windows helper
  - `export_obs_fixture.py` 这种无实质行为变化的噪音改动
- 提交信息固定为一条清晰快照，例如：`ASE prework: add mesh envs and render/runtime support`
- 推送目标固定为 `origin/feat/ase-prework`，推送后记录实际 SHA。
- 新 worktree 从“已推送 SHA”创建，而不是从浮动分支名或当前脏树创建：
  - 分支：`feat/ase-fullchain-agent`
  - 路径：`/root/Project/MimicKit-ase-fullchain`

## Public Interfaces
- 这次快照会引入的对外配置能力只有两类：
  - `data/envs/*mesh_env.yaml`
  - `env_config` 中的 `kin_char_file` 支持
- 现有 `args/*.txt`、`--llc_model_file`、`--mode train|test`、ASE case 名称不变。
- 新 worktree 第一阶段不扩展新的训练 CLI，只基于现有 ASE 入口完成训练闭环。

## Test Plan
- 提交前检查：
  - staged diff 只包含上面列出的 ASE 相关文件
  - 没有临时 YAML、`Zone.Identifier`、chmod-only 文件进入提交
- 推送后检查：
  - `origin/feat/ase-prework` 存在
  - 本地 `HEAD` 与远端分支指向同一 SHA
- worktree 创建后检查：
  - `/root/Project/MimicKit-ase-fullchain` 指向 `feat/ase-fullchain-agent`
  - worktree 基线就是刚推送的 SHA
  - `git status` 干净
- 新 worktree 第一阶段验收：
  - `ase_humanoid`、`ase_humanoid_sword_shield`、`ase_getup` 的 LLC 可训练并产出 `model.pt`
  - `ase_heading/location/reach/strike` 的 HLC 在提供 `--llc_model_file` 时可训练并产出 `model.pt`
  - LLC/HLC 均可完成 `test`
  - 至少一条 LLC 主链和抽样 HLC case 可完成基础 `visualize=true`

## Assumptions
- 为了安全推送，本地当前工作树会先离开 `main`，改挂到 `feat/ase-prework` 后再提交。
- 不会直接向 `origin/main` 推送当前未整理改动。
- `feat/ase-prework` 是“当前 ASE 相关预备工作快照”，不是最终 fullchain 实现分支。
- 即使快照里已带有 `mesh` 相关能力，新 worktree 第一阶段仍以训练闭环为最高优先级，不把白骑士观感复刻作为阻塞项。
