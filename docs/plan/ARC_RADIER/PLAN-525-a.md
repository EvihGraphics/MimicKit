# MimicKit → UE 双闭环计划：同源角色 Full Visual Parity + Live Policy/Chaos Contact

## Summary
当前已经通过的是 `skeletal_visual_pass=true`，但它仍是 UE 端程序化骨架图像：没有加载真实 `USkeletalMesh`，没有驱动 MimicKit 同源角色资产，也没有 live UE policy control / Chaos contact 验收。

本轮目标拆成两个必须同时闭环的 gate：

1. **同源角色闭环**：从 MimicKit `humanoid_sword_shield.xml/.usd` 生成或导入 UE 可驱动的同源 `USkeletalMesh + USkeleton + PhysicsAsset`，用真实 UE SkeletalMesh replay `joint_order + dof_pos`，产出 PNG/MP4/report/ledger，并允许 `full_visual_parity=true`。
2. **Live runtime 闭环**：UE 无 Python 加载 ONNX policy，按 package contract 构造 observation，输出 action，映射到 Chaos/PhysicsControl/constraint motor，采集 foot contact/sliding/root stability，产出 runtime report/ledger，并允许 `live_policy_control=true`、`chaos_contact_validated=true`。

默认 canary 仍是 `StopBrain_long01_probe`。Walk/Turn/Stop 先继续做 package/trace/contract regression，等 canary 双闭环通过后再扩展。

## Key Changes
- 新增 MimicKit source rig asset spec：
  - 新工具：`tools/ue_bridge/build_mimickit_source_rig_asset_spec.py`
  - 输入：`humanoid_sword_shield.xml`、`humanoid_sword_shield.usd`、`joint_order.json`
  - 输出：`mimickit_source_rig_asset_spec.json`
  - 内容必须包含 source SHA、body hierarchy、local body transforms、geom primitives、joint axes/ranges、actuator gear/stiffness/damping、sword/shield attachments、contact bodies。
- 新增 UE Editor import/generation path：
  - 新 UE editor-only module：`GASPALSShadowEditor`
  - 新 automation/commandlet：`GASPALSShadow.MimicKitSourceRigAssetBuild`
  - 默认资产路径：`/Game/MimicKit/SwordShield/`
  - 默认生成资产：
    - `/Game/MimicKit/SwordShield/SK_MimicKit_SwordShield`
    - `/Game/MimicKit/SwordShield/Skeleton_MimicKit_SwordShield`
    - `/Game/MimicKit/SwordShield/PA_MimicKit_SwordShield`
  - 先尝试 USD import；若 USD 无 `UsdSkel/SkelRoot`，走 MJCF primitive → generated SkeletalMesh，不再使用 Manny fallback。
- 新增真实 SkeletalMesh replay capture：
  - 保留当前程序化 `MimicKitSkeletalVisualReplayCapture`，但它只能算 `skeletal_visual_pass`。
  - 新 test：`GASPALSShadow.MimicKitSourceCharacterReplayCapture`
  - 必须创建 `UPoseableMeshComponent` 或 ControlRig-backed `USkeletalMeshComponent`，加载 `/Game/MimicKit/SwordShield/SK_MimicKit_SwordShield`，逐帧应用 root + bone local transforms。
  - `capture_meta.json` 必须写：
    - `capture_mode=source_character_skeletalmesh_replay`
    - `target_mesh=/Game/MimicKit/SwordShield/SK_MimicKit_SwordShield`
    - `driver_component=UPoseableMeshComponent` 或 `ControlRig`
    - `fallback_renderer=""`
    - `mimickit_source_asset_imported_to_ue=true`
    - `full_character_parity=true`
- 新增 runtime control contract：
  - 新文件：`runtime_control_contract.json`
  - 包含 observation layout、normalization stats binding、action-to-joint mapping、policy/control/physics hz、coordinate basis、PD gains、action clamps、contact bodies、runtime thresholds。
  - `visual_alignment_contract.json` v3 追加 `runtime_scope`：
    - `offline_source_character_replay=true`
    - `live_policy_control=true`
    - `chaos_contact_validated=true`
    - `runtime_backend=NNERuntimeORT` for first closure, with backend abstraction kept swappable for native ONNX Runtime later。
- 新增 UE runtime closure automation：
  - 新 test：`GASPALSShadow.MimicKitLivePolicyChaosClosure`
  - UE 加载 package ONNX、normalization、runtime contract、source character physics asset。
  - 以固定 timestep 运行：policy 30 Hz，physics 240 Hz。
  - 每 policy tick 构造 observation，运行 ONNX，输出 action。
  - 每 physics substep 将 action 转成 joint PD/motor target。
  - 采集 root trajectory、joint target error、foot contact、foot sliding、fall/stability、NaN/action clamp、inference latency。
- 更新 report/ledger gates：
  - `build_ue_visual_contact_sheet.py` 必须区分：
    - debug geometry: `watch`
    - procedural skeletal replay: `skeletal_visual_pass=true`, `full_visual_parity=false`
    - source character SkeletalMesh replay: `full_visual_parity=true`
    - live policy/Chaos: `live_policy_control=true`, `chaos_contact_validated=true`
  - 若 target mesh 仍是 Manny 或 `fallback_renderer=procedural_mimickit_skeletal_replay`，full parity 必须失败。

## Execution Flow
1. **Freeze current baseline**
   - 保留 `StopBrain_long01_probe_skeletal_closure` 作为已通过的 procedural skeletal baseline。
   - 不改写旧 ledger，只追加新条目。
2. **Build source rig spec**
   - 解析 MJCF body/joint/geom/actuator。
   - 对照 `joint_order.json` 验证 17 bodies、31 DOF、sword/shield fixed attachment、right/left foot contact bodies。
   - 写 `mimickit_source_rig_asset_spec.json` 到 package。
3. **Generate UE source character assets**
   - 启用 editor-only import/generation path。
   - 若 USD import 不能产生 SkeletalMesh，则使用 asset spec 生成 primitive-skinned SkeletalMesh。
   - 生成并保存 import report：source SHA、asset paths、bone count、geom count、physics asset bodies/constraints、warnings。
4. **Source character visual replay**
   - 用 `/Game/MimicKit/SwordShield/SK_MimicKit_SwordShield` 做 replay capture。
   - 输出到：
     `/mnt/d/UE/COLMM/GASPALS/Saved/MimicKitVisualCaptures/StopBrain_long01_probe_source_character_closure`
   - 后处理生成 PNG sequence、MP4、contact sheet、visual diff report。
   - Ledger 必须写 `full_visual_parity=true`，同时注明这是 offline source-character SkeletalMesh replay，不是 live policy。
5. **Live policy/Chaos closure**
   - 生成或加载 physics-controlled source character test actor。
   - 固定 flat ground、fixed command target、deterministic seed。
   - UE runtime 加载 StopBrain ONNX，构造 observation，运行 policy，映射 action 到 joint motor。
   - 运行 10 秒或 300 policy frames，输出 runtime trace、contact report、debug capture。
6. **Final combined gate**
   - 生成：
     `/mnt/d/UE/COLMM/GASPALS/Saved/MimicKitVisualCaptures/StopBrain_long01_probe_full_runtime_closure/mimickit_ue_full_closure_report.json`
   - 只有以下全部为 true 才算双闭环完成：
     - `source_character_replay_pass=true`
     - `full_visual_parity=true`
     - `live_policy_control_pass=true`
     - `chaos_contact_validated=true`
     - `png_ok=true`
     - `mp4_ok=true`
     - UE automation log `EXIT CODE: 0`

## Commands And Gates
- Source rig spec：
```bash
python tools/ue_bridge/build_mimickit_source_rig_asset_spec.py \
  --package-dir /mnt/d/UE/COLMM/GASPALS/Saved/MimicKitPackages/StopBrain_long01_probe \
  --char-xml data/assets/sword_shield/humanoid_sword_shield.xml \
  --char-usd data/assets/sword_shield/humanoid_sword_shield.usd \
  --out /mnt/d/UE/COLMM/GASPALS/Saved/MimicKitPackages/StopBrain_long01_probe/mimickit_source_rig_asset_spec.json
```

- UE source asset build：
```powershell
& 'D:\Program Files\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor-Cmd.exe' `
  'D:\UE\COLMM\GASPALS\GASPALS.uproject' `
  -unattended -nop4 -nosplash `
  -ExecCmds='Automation RunTests GASPALSShadow.MimicKitSourceRigAssetBuild;Quit' `
  -TestExit='Automation Test Queue Empty' `
  -MimicKitPackageDir='D:\UE\COLMM\GASPALS\Saved\MimicKitPackages\StopBrain_long01_probe' `
  -MimicKitAssetOut='/Game/MimicKit/SwordShield' `
  -abslog='D:\UE\COLMM\GASPALS\Saved\Logs\GASPALSShadow_MimicKitSourceRigAssetBuild.log'
```

- Source character replay capture：
```powershell
& 'D:\Program Files\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor-Cmd.exe' `
  'D:\UE\COLMM\GASPALS\GASPALS.uproject' `
  -unattended -nop4 -nosplash `
  -ExecCmds='Automation RunTests GASPALSShadow.MimicKitSourceCharacterReplayCapture;Quit' `
  -TestExit='Automation Test Queue Empty' `
  -MimicKitPackageDir='D:\UE\COLMM\GASPALS\Saved\MimicKitPackages\StopBrain_long01_probe' `
  -MimicKitCaptureOut='D:\UE\COLMM\GASPALS\Saved\MimicKitVisualCaptures\StopBrain_long01_probe_source_character_closure' `
  -MimicKitCaptureStride=5 `
  -MimicKitCaptureWidth=960 `
  -MimicKitCaptureHeight=540 `
  -abslog='D:\UE\COLMM\GASPALS\Saved\Logs\GASPALSShadow_MimicKitSourceCharacterReplayCapture.log'
```

- Live policy/Chaos closure：
```powershell
& 'D:\Program Files\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor-Cmd.exe' `
  'D:\UE\COLMM\GASPALS\GASPALS.uproject' `
  -unattended -nop4 -nosplash -NullRHI `
  -ExecCmds='Automation RunTests GASPALSShadow.MimicKitLivePolicyChaosClosure;Quit' `
  -TestExit='Automation Test Queue Empty' `
  -MimicKitPackageDir='D:\UE\COLMM\GASPALS\Saved\MimicKitPackages\StopBrain_long01_probe' `
  -MimicKitRuntimeOut='D:\UE\COLMM\GASPALS\Saved\MimicKitRuntimeClosures\StopBrain_long01_probe_live_chaos' `
  -MimicKitRuntimeSeconds=10 `
  -abslog='D:\UE\COLMM\GASPALS\Saved\Logs\GASPALSShadow_MimicKitLivePolicyChaosClosure.log'
```

- Media/report/ledger：
```bash
python tools/ue_bridge/finalize_ue_visual_capture.py \
  --ue-capture-dir /mnt/d/UE/COLMM/GASPALS/Saved/MimicKitVisualCaptures/StopBrain_long01_probe_source_character_closure \
  --fps 12 --force

python tools/ue_bridge/build_ue_visual_contact_sheet.py \
  --brain StopBrain \
  --root amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01 \
  --package-dir /mnt/d/UE/COLMM/GASPALS/Saved/MimicKitPackages/StopBrain_long01_probe \
  --mimic-render-dir output/img/amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/probe_train/render \
  --ue-capture-dir /mnt/d/UE/COLMM/GASPALS/Saved/MimicKitVisualCaptures/StopBrain_long01_probe_source_character_closure \
  --out-report /mnt/d/UE/COLMM/GASPALS/Saved/MimicKitVisualCaptures/StopBrain_long01_probe_source_character_closure/visual_diff_report.json \
  --contact-sheet /mnt/d/UE/COLMM/GASPALS/Saved/MimicKitVisualCaptures/StopBrain_long01_probe_source_character_closure/contact_sheet.png \
  --ledger docs/memory/20260521_amp_ue_visual_diff_log.md
```

## Test Plan
- Package/contract tests:
  - `visual_alignment_contract.json` schema v3 loads.
  - `mimickit_source_rig_asset_spec.json` exists and has source SHA for XML/USD.
  - `runtime_control_contract.json` exists and locks obs/action dims, joint order, normalization, PD gains, coordinate basis.
- Source asset tests:
  - UE loads `/Game/MimicKit/SwordShield/SK_MimicKit_SwordShield`.
  - Skeleton has required bodies/bones for pelvis, torso, head, arms, legs, sword, shield.
  - Physics asset has foot collision bodies and constraints for controllable joints.
  - Import report says no Manny fallback.
- Source character visual tests:
  - `capture_meta.json`: `capture_mode=source_character_skeletalmesh_replay`
  - `target_mesh` starts with `/Game/MimicKit/SwordShield/`
  - `fallback_renderer=""`
  - `dof_pos_applied=true`
  - `full_character_parity=true`
  - `capture_media_manifest.json`: `png_ok=true`, `mp4_ok=true`, `png_count=60`
  - `visual_diff_report.json`: `verdict=pass`, `full_visual_parity=true`
- Live policy/Chaos tests:
  - UE loads ONNX without Python.
  - Observation dim equals package schema.
  - Action dim equals 31 and all actions finite.
  - Runtime runs at 30 Hz policy / 240 Hz physics for 10 seconds.
  - Root remains finite and non-fallen.
  - Both foot contact bodies produce contact events.
  - Contact sliding stays under declared threshold.
  - `runtime_closure_report.json`: `live_policy_control_pass=true`, `chaos_contact_validated=true`
- Final ledger:
  - One entry for source character full visual parity.
  - One entry for live policy/Chaos closure.
  - Combined report states both gates passed and keeps remaining caveats limited to production hardening, not closure blockers.

## Assumptions
- Because the current USD appears to be primitive physics USD rather than UsdSkel/skinned mesh, the default route is **source-equivalent UE SkeletalMesh generation from MimicKit MJCF/USD source**, not blind raw USD import.
- Generated UE asset under `/Game/MimicKit/SwordShield/` is acceptable as the same-character closure if it is deterministic from source XML/USD and records source hashes.
- First live runtime closure may use UE `NNERuntimeORT` as the ONNX backend because it is present in UE 5.7; the runner interface must record backend and remain swappable for native ONNX Runtime C++.
- `full_visual_parity=true` and `chaos_contact_validated=true` are separate gates; neither can imply the other.
- Walk/Turn/Stop expansion happens only after `StopBrain_long01_probe` passes both closures.
