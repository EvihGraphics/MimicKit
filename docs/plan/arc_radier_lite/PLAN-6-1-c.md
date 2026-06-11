# EvihAnimation 角色视觉一致性下一步测试目标

## Summary
下一步目标从“骨骼轨迹一致”升级为“带角色外观的视觉一致”。但当前 Walk/Stop 的 MimicKit baseline 实际是 XML geom 渲染，不是 USD/mesh 渲染；因此测试分两层推进：

1. 先做 **Evih character geom parity**：Evih 根据同一套 skeleton trajectory + MJCF XML 几何体渲染角色外形，对齐当前 MimicKit Walk/Stop baseline。
2. 再做 **true mesh parity**：先补出 MimicKit 成功的 USD/white-knight mesh reference，再让 Evih 加载/转换同一 mesh 并对齐视觉结果。

## Key Changes
- 在 Evih replay 中新增角色视觉通道：
  - 读取 `visual_alignment_contract` / `render_meta` 中的 `resolved_char_file`、`preferred_visual_asset`、`visual_kind`。
  - 当前 Walk/Stop 使用 `data/assets/sword_shield/humanoid_sword_shield.xml` 作为第一阶段真值。
  - 解析 MJCF body-local geoms：`sphere`、`capsule`、`box`、`cylinder`，包括 sword / shield。
  - 将 geoms 绑定到已验证一致的 body transforms 上渲染，而不是只画 stick skeleton。

- 每个 case 新增正式结果包：
  - `evih_character_geom_replay/frames/`
  - `evih_character_geom_replay/character_replay.mp4`
  - `evih_character_geom_replay/visual_asset_manifest.json`
  - `mimickit_geom_vs_evih_geom_sheet.png`
  - `visual_character_compare_report.json`

- 当前 `mimickit_skeleton_reference/` 和 `evih_skeleton_replay/` 保留，作为底层 correctness gate：
  - 只有 skeleton data compare pass 后，character visual replay 才算有效。
  - character visual 不重新定义姿态真值，只验证“同一姿态驱动同一角色外观”。

- True mesh 阶段新增前置检查：
  - 当前 Walk/Stop `render_meta.json` 是 `visual_kind=geom`、`mesh_detected=0`，不能作为 mesh reference。
  - 需要先生成 MimicKit mesh reference，目标是 `.usd` asset 渲染成功且 `image_count=60`、`status=ok`。
  - Evih 侧优先采用 USD -> GLB 转换后走现有 GLB / skinned mesh 管线；若后续确认 Evih 可直接稳定读 USD，再切为直接导入。

## Test Plan
- WalkBrain geom parity：
  - 输入现有 Walk `ue_export` sidecars。
  - 使用已通过的 skeleton trajectory。
  - 输出 60 PNG、MP4、character manifest、geom-vs-geom compare sheet。
  - 报告检查：frame ids `[0,5,...,295]`、geom count 非零、missing geom bodies 为空、root trajectory OK。

- StopBrain geom parity：
  - 输入现有 Stop `ue_export_probe_gate` sidecars。
  - 同样输出 60 PNG、MP4、manifest、compare sheet。
  - 验收同 Walk。

- Mesh parity smoke：
  - 先在 MimicKit 侧生成一个成功的 USD mesh reference。
  - 验收 `render_meta.visual_kind=mesh`、`mesh_detected=1`、`image_count=60`、`status=ok`。
  - Evih 再生成 `evih_mesh_replay/` 和 `mimickit_mesh_vs_evih_mesh_sheet.png`。
  - v1 mesh 验收先用 side-by-side sheet + MP4 人工检查，不做 pixel-diff pass gate。

## Assumptions
- “和 MimicKit 视觉一致”分为当前 baseline 的 geom 一致，以及后续真正 USD/mesh 一致。
- 当前 Walk/Stop 不能直接声称 mesh parity，因为 MimicKit reference 不是 mesh。
- 不修改原始 dirty checkout：`/mnt/d/AnimationTech-learning/EvihAnimation` 仍保持只读参考。
- 第一阶段不追求材质、光照、相机像素级一致，重点是角色 body、sword、shield 随 skeleton 正确运动。
