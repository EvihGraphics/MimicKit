# ASE 白骑士动作全覆盖计划

## Summary
- 官方 `ASE` 的“任务 case”本来就不多，主口径仍是 `Getup / Perturb / ViewMotion / Heading / Location / Reach / Strike`；官网看起来“案例很多”，主要是因为白色剑盾骑士背后有一整套动作素材库，而不是额外几十个任务类型。官方来源以 [ASE project page](https://xbpeng.github.io/projects/ASE/index.html)、[upstream README](https://github.com/logic-three-body/ASE) 和 Reallusion 的 [Sword & Shield Stunts](https://www.reallusion.com/ContentStore/iClone/pack/Motion-Sword-Shield-Stunts/default.html?addfrom=14.00012) / [Sword & Shield Moves](https://www.reallusion.com/ContentStore/iClone/pack/Motion-Sword-Shield-moves/default.html) 为准。
- `MimicKit` 现在已经完成了官方任务级 parity；真正欠缺的是“动作素材级 parity”的显式化。当前本地白骑士剑盾库是 `82` 个启用动作，加上 `5` 个被注释的 fall 动作，共 `87` 个。
- 本轮不再新增更多自定义 ASE task，而是把这 `87` 个白骑士动作按 `MimicKit` 规范做成“可枚举、可索引、可逐条 view/render 验收”的一级资产覆盖。
- 采用你确认的默认口径：`82` 个现有训练动作继续作为 LLC 主训练集；`5` 个 fall 动作仅纳入 `view / render / index`，不重新并入 LLC 主训练集。

## Implementation Changes
- 新增一个白骑士动作权威清单，放在 `data/motions/reallusion/` 下，作为唯一 source of truth。
  - 每条记录至少包含：`motion_id`、`file`、`source_pack`、`category`、`train_enabled`、`view_enabled`。
  - `82` 个现有训练动作标记为 `train_enabled=true, view_enabled=true`。
  - `5` 个 fall 动作标记为 `train_enabled=false, view_enabled=true`，并显式分类为 `fall`。
- 保持 `data/datasets/dataset_humanoid_sword_shield.yaml` 的 LLC 训练口径不变。
  - 训练主线继续吃当前 `82` 动作的数据集。
  - 不把 fall 动作重新塞回 LLC 训练集，避免改动已验证过的 ASE 训练分布。
- 为白骑士动作库新增“自动枚举”能力，而不是生成 `87` 份独立 `args/env` 文件。
  - 新增一个 helper，读取动作 manifest，基于 `view_motion_humanoid_sword_shield` 生成一份 synthetic render root，再复用现有 `render-viz-sequence` 导出链路。
  - 每个动作导出成一个独立 variant，输出目录固定为：
    - `output/img/<root>/runs/view_motion_humanoid_sword_shield_args/<motion_id>/render/...`
  - 保留现有 `single_clip` 和 `dataset_yaml` 两个入口，不替换，只是在其上增加 `per-clip` 全覆盖模式。
- 扩展渲染索引字段，让 per-clip 动作导出可追溯。
  - 至少补充：`motion_id`、`motion_file`、`source_pack`、`category`、`train_enabled`。
  - 现有 policy-case 渲染行为不改，只是让 motion-library 模式也能被统一索引。
- 更新 ASE 文档口径，明确区分“任务案例”与“动作素材”。
  - `ASE SOP` 中新增“白骑士动作库全覆盖”章节。
  - case catalog / paper config catalog 中新增一张动作覆盖表，说明当前是 `7` 个官方任务 case + `87` 个白骑士动作条目。
  - 文档里明确写清：官方官网里看到的白骑士大量展示，映射到 `MimicKit` 时应归类为 motion-library parity，不应误写成几十个 ASE task。

## Public Interfaces
- 新增一个白骑士动作 manifest 文件，作为后续文档、渲染、索引、验收的统一输入。
- 新增一个 manifest-driven 的动作枚举 helper，用于为 `view_motion_humanoid_sword_shield` 生成 per-clip 渲染根。
- 现有 `ASE` task args、env 名、agent 接口保持不变；不新增 `87` 个 repo-tracked case 文件。

## Test Plan
- 动作清单完整性：
  - manifest 总数必须是 `87`。
  - `train_enabled=true` 必须是 `82`。
  - `train_enabled=false && view_enabled=true` 的 fall 动作必须是 `5`。
  - 每个 `motion_file` 都必须存在于本地。
- 训练口径回归：
  - `data/datasets/dataset_humanoid_sword_shield.yaml` 仍保持当前 `82` 个 LLC 训练动作，不被 fall 动作污染。
  - 现有 `ase_humanoid_sword_shield` / `ase_getup` / `ASEHRL` task 命令与验证口径不变。
- 枚举与渲染：
  - manifest-driven dry-run 必须发现 `87` 个 per-clip job。
  - full render 必须在统一根目录下产出 `87` 条 `ok` 索引记录。
  - 每条记录都要有独立 `render_meta.json` 和 `frames/`。
- 视图覆盖：
  - 至少抽样覆盖 `combo / slash / stab / locomotion / idle / taunt / block / parry / fall` 等主要类别。
  - `5` 个 fall 动作必须能单独 view/render，但不得被误标为 LLC 训练输入。

## Assumptions
- 官方 `ASE` 任务范围仍按 upstream 保持，不把官网视频里看起来“很多”的动作演示误扩成额外任务类型。
- “白色骑士拿剑盾的很多动作”对应的是 Reallusion 剑盾动作素材库，而不是新的 ASE task family。
- 本轮默认采用“统一 manifest + 自动枚举”的落地方式，不采用 `87` 个静态 args/env 文件。
- `5` 个 fall 动作默认只进 `view/render/index`，不进 LLC 训练主数据集。
