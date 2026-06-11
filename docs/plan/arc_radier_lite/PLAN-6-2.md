# EvihAnimation 视觉复现当前状态与下一步计划

## Summary
当前已经完成 **skeleton parity** 和 **XML character geom parity**；Walk/Stop 两个 case 都能证明 Evih 使用同一套 sidecar skeleton trajectory 正确复现骨骼和角色几何体。距离最终 “携带 true mesh 并与 MimicKit 视觉一致” 的主要缺口，是还没有成功的 MimicKit `humanoid_sword_shield.usd` mesh reference。

## Current Status
- Evih 正式视觉目录：
  - `/mnt/d/AnimationTech-learning/EvihAnimation-skeleton-replay/Demos/MimicKitReplay/results/walkbrain_skeleton_replay/`
  - `/mnt/d/AnimationTech-learning/EvihAnimation-skeleton-replay/Demos/MimicKitReplay/results/stopbrain_skeleton_replay/`
- WalkBrain：
  - `skeleton_data_compare_pass=true`
  - `max_body_pos_error_m=0.0`
  - `character_geom_compare_pass=true`
  - `evih_character_geom_png_count=60`
  - `evih_character_geom_count=21`
- StopBrain：
  - `skeleton_data_compare_pass=true`
  - `max_body_pos_error_m=0.0`
  - `character_geom_compare_pass=true`
  - `evih_character_geom_png_count=60`
  - `evih_character_geom_count=21`
- MimicKit mesh smoke：
  - root: `tmp_white_knight_mesh_reference_20260601_smoke_codex`
  - synthetic root build: pass
  - dry-run mesh job: pass
  - WSL precheck: fail
  - blocker: `isaaclab_precheck_failed`
  - reason: WSL 当前没有 `/root/miniconda3/envs/mimickit-isaaclab`
- Windows fallback：
  - helper exists: `D:\MimicKitNative\workspace\MimicKit\tools\windows\run_white_knight_mesh_viewmotion.ps1`
  - 默认下一步走 Windows native Isaac Lab，而不是继续卡 WSL。

## Next Plan
- 先解锁 MimicKit mesh reference：
  - 使用 Windows native workspace `D:\MimicKitNative\workspace\MimicKit`
  - 使用 env path `D:\MimicKitNative\conda\mimickit-isaaclab-win`
  - 预检必须通过：`isaaclab`、`carb`、`omni`、`omni.kit.usd`、`torch.cuda.is_available()`
  - 若 `carb` / `omni` 缺失，修 Windows Isaac Sim / Isaac Lab Python path，不切回 Newton。

- 生成 white-knight mesh smoke：
  - 运行 `view_motion_humanoid_sword_shield_mesh_env.yaml`
  - engine 固定为 `isaac_lab_engine.yaml`
  - motion 固定为 `RL_Avatar_Atk_2xCombo01_Motion`
  - smoke 参数：`frames=10`, `frame_stride=5`
  - 验收：`visual_kind=mesh`, `mesh_detected=1`, `status=ok`, `image_count=2`

- 生成 full mesh reference：
  - 参数：`frames=300`, `frame_stride=5`
  - 输出 60 PNG、`render.mp4`、`render_meta.json`、contact sheet、`mesh_reference_manifest.json`
  - 验收：`mesh_reference_pass=true`

- 回接 Evih true mesh parity：
  - 将成功的 MimicKit mesh reference 写入 Evih results manifest。
  - 新增 `mimickit_mesh_vs_evih_mesh_sheet.png`。
  - Evih 侧优先走 USD -> GLB，再接现有 GLB/skinned mesh 管线。
  - 初版只做人工视觉验收，不做 pixel-diff pass gate。

## Assumptions
- 当前 XML geom 结果继续保留为通过状态，不覆盖。
- true mesh 目标资产固定为 `data/assets/sword_shield/humanoid_sword_shield.usd`。
- 只有 MimicKit mesh reference 成功后，Evih results 才能把 `true_mesh_reference_available` 改成 `true`。
