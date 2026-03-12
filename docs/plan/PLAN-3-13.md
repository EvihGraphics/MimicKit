# ASE 白骑士 Native Windows 视觉闭环回灌

## Summary

- 目标：把隔离的 native Windows 工作集里已经跑通的白骑士 `mesh/usd`
  视觉闭环，最小回灌到 `main` 仓库。
- 约束：不动用户当前 feature worktree，只在
  `/root/Project/MimicKit-main` 和独立的 native Windows 工作集上操作。
- 结果：白骑士 `view_motion -> render sequence` 已在 native Windows 闭环，
  当前回灌内容包括运行时代码、Windows helper、外部 IsaacLab hotfix 脚本、
  以及 SOP/skill 文档。

## Repo Changes

- `mimickit/engines/isaac_lab_engine.py`
  - 先 bootstrap `isaacsim`，再 import `carb`
  - 增加 Isaac Lab viewport 抓帧 wrapper
  - 暴露 `_viewer` 给 render-sequence 工具使用
  - 支持 `MIMICKIT_VIEWER_HEADLESS`
  - 显式设置 `multi_gpu=False`
  - 禁用 `sim_cfg.use_fabric`
- `tools/ue_bridge/build_mimickit_render_sequences.py`
  - 仅在 `isaac_gym` 不可用时才 fallback 到 Newton
  - 支持 `MIMICKIT_SKIP_XVFB`
  - 渲染抓帧兼容 `warp` tensor 和 `numpy.ndarray`
  - 保留 `MIMICKIT_VIEWER_HEADLESS` 作为外部可覆写开关
- `tools/windows/*`
  - 新增 native Windows bootstrap、viewport 验证、render-sequence 验证脚本
  - 新增 `apply_native_isaaclab_hotfixes.py`
  - 新增 `flatdict` shim 与 native-Windows 额外依赖清单

## External IsaacLab Contract

白骑士 native Windows 闭环不只依赖 MimicKit repo 自身，还依赖外部
`IsaacLab_full` 的 3 处最小 hotfix：

- `articulation.py`
- `articulation_data.py`
- `hdf5_dataset_file_handler.py`

这些变更不属于 MimicKit 仓库本身，因此本轮把它们收敛到
`tools/windows/apply_native_isaaclab_hotfixes.py`，由 bootstrap 脚本统一施加。

## Validation

已验证的 native Windows 输出根目录：

- `D:\MimicKitNative\workspace\MimicKit\output\img\case_white_knight_mesh_native_20260312_224041`

关键验收记录：

- motion: `RL_Avatar_Atk_2xCombo01_Motion`
- index: `infer_viz_index.tsv`
- result: `status=ok`
- `visual_kind=mesh`
- `image_count=6`

对应帧目录：

- `output/img/case_white_knight_mesh_native_20260312_224041/runs/view_motion_humanoid_sword_shield_args/RL_Avatar_Atk_2xCombo01_Motion/render/frames`

## Notes

- 这轮成功走通的是 native Windows 的 GUI 渲染路径：
  - `MIMICKIT_SKIP_XVFB=1`
  - `MIMICKIT_VIEWER_HEADLESS=0`
- WSL 仍保留给 Newton train/test parity。
- 对这台双 `RTX 4090` 主机，最终白骑士 `usd` 视觉闭环的 validated path
  是 native Windows，而不是 WSL headless。
