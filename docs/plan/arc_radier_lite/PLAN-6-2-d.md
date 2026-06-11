# MimicKit -> EvihAnimation 全链路 Mesh 视觉桥接

## Summary
- 保留现有 WalkBrain/StopBrain 通过结果：skeleton parity、XML geom parity、60 PNG、MP4 继续有效，但保持 `mesh_scope=false`，不把当前 `visual_kind=geom` 升级成 true mesh。
- 当前硬阻塞是 MimicKit 侧还没有 `mesh_reference_pass=true`：WSL 缺 `mimickit-isaaclab`，Windows native smoke 则因内层 precheck 没透传 prefix Python，错误寻找 `mimickit-isaaclab`。
- 目标产物是 MimicKit USD mesh reference + GLB asset + replay sidecar，Evih 使用同一 sidecar、同一 scene contract、同一角色资产输出 PNG 序列、MP4、mesh 对比 sheet；PPM-only 一律不能通过。

## Key Changes
- 修 Windows native env handoff：更新 `tools/windows/build_white_knight_mesh_reference_native.ps1`，在 prefix env 存在时显式传入 `--render-python`、`--asset-export-python`、`--package-export-python` 指向 `D:\MimicKitNative\conda\mimickit-isaaclab-win\python.exe`，并在执行前 `Set-Location` 到 native MimicKit workspace。
- 保持 MimicKit mesh gate 使用现有 `tools/ue_bridge/build_mimickit_mesh_reference.py`：smoke root 固定 `tmp_white_knight_mesh_reference_20260602_bridge_smoke`，full root 固定 `tmp_white_knight_mesh_reference_20260602_bridge_full`。
- 为 Walk/Stop exact mesh root 增加 native Windows 执行/ingest 路径，复用 `tools/ue_bridge/build_mimickit_exact_mesh_reference.py`，不覆盖旧 geom roots。
- Evih 侧使用现有 `/mnt/d/AnimationTech-learning/EvihAnimation-skeleton-replay` true-mesh 路径：`--true-mesh --mesh-asset <glb> --mesh-reference-manifest <json>`，必要时补齐 `pygltflib==1.16.5` 到运行该 replay 的 Python 环境。
- Dashboard 保持现有扫描逻辑，确认链接 `mesh_reference_manifest.json`、mesh MP4、Evih `visual_result_manifest.json`、`mimickit_mesh_vs_evih_mesh_sheet.png`。

## Interfaces And Gates
- MimicKit mesh manifest 必须包含并通过：`mesh_reference_pass=true`、`render_summary.visual_kind=mesh`、`mesh_detected=true`、`png_count=60`、`frame_ids=[0,5,...,295]`、`mp4_ok=true`、`source_was_ppm_only=false`、`asset_export.ok=true`、`asset_export.format=glb`、`package_export.ok=true`。
- Mesh package 必须输出 `ue_export_mesh_reference/visual_replay/pose_dof_replay.jsonl`、`pose_dof_meta.json`、`joint_order.json`、`mimickit_source_rig_asset_spec.json`、`visual_alignment_contract.json`。
- Scene contract 固定为 `camera_mode=track`、flat ground、root-follow framing、`960x540`、stride `5`、mesh MP4 fps `12`。
- Evih mesh result 必须输出 `evih_mesh_replay/frames/`、`mesh_replay.mp4`、`mesh_replay_meta.json`、`visual_mesh_compare_report.json`、`mimickit_mesh_vs_evih_mesh_sheet.png`，并记录 `mesh_mode=skinned|rigid_node` 与 binding report。
- Negative gates：缺 GLB、asset export failed、PPM-only、MimicKit mesh reference failed、frame ids 不匹配、缺 required mesh joints、Evih PNG/MP4 缺失都必须 fail，不回退 XML geom。

## Test Plan
- 先回归现有 Walk/Stop result manifests：`skeleton_data_compare_pass=true`、`character_geom_compare_pass=true`、`evih_character_geom_png_count=60`、MP4 非零。
- 跑 white-knight smoke：`frames=10`、`frame_stride=5`，验收 2 PNG、mesh detected、nonzero MP4、GLB、sidecar package。
- 跑 white-knight full：`frames=300`、`frame_stride=5`，验收 60 PNG、`render.mp4`、contact sheet、`mesh_reference_manifest.json` pass。
- 跑 Evih white-knight true mesh replay，用 full manifest 的 `asset_export.glb_file`，验收 60 PNG、nonzero `mesh_replay.mp4`、binding pass、mesh side-by-side sheet。
- 分别生成 WalkBrain/StopBrain exact mesh roots，再重复 MimicKit mesh gate 和 Evih mesh replay gate；旧 geom packages 保持 green 且 `mesh_scope=false`。
- Dashboard smoke：打开 AMP dashboard，确认 mesh manifest、mesh MP4、Evih manifest、comparison sheet 都出现在 artifact links。

## Assumptions
- 默认解锁路径是 Windows native Isaac Lab：`D:\MimicKitNative\workspace\MimicKit` + `D:\MimicKitNative\conda\mimickit-isaaclab-win`。
- v1 视觉验收采用机械 gate + side-by-side 人工视觉检查，不做 pixel-diff pass gate。
- true mesh 资产固定为 `data/assets/sword_shield/humanoid_sword_shield.usd`，Evih v1 输入固定为 GLB。
