# AMP / UE Visual Difference Log (2026-05-21)

## Purpose

This ledger is mandatory for MimicKit-to-UE visual bridge validation. `output/img` remains the MimicKit golden visual reference; UE captures/logs are compared against it and recorded here. A UE visual bridge milestone is not accepted unless the corresponding run has an entry in this file.

## Entry Template

```markdown
### YYYY-MM-DD HH:MM TZ - <BrainName> - <run label>

- brain/root/package source:
- MimicKit reference:
  - mp4:
  - frames:
  - render_meta:
- UE capture/log:
  - capture:
  - log:
- camera/map/replay mode:
- observed differences:
  - scale:
  - root trajectory:
  - facing:
  - pose:
  - contact/sliding:
  - timing:
  - jitter:
  - missing assets:
- verdict: pass | watch | block
- next action:
```

## Entries

### 2026-05-21 PLAN-521-b Initialization - Ledger Created

- brain/root/package source: not a visual validation run
- MimicKit reference:
  - mp4: not applicable
  - frames: not applicable
  - render_meta: not applicable
- UE capture/log:
  - capture: not applicable
  - log: not applicable
- camera/map/replay mode: ledger setup
- observed differences:
  - scale: not evaluated
  - root trajectory: not evaluated
  - facing: not evaluated
  - pose: not evaluated
  - contact/sliding: not evaluated
  - timing: not evaluated
  - jitter: not evaluated
  - missing assets: not evaluated
- verdict: watch
- next action: append one entry per future MimicKit-vs-UE visual comparison before accepting any UE visual bridge milestone

### 2026-05-21 23:43 Asia/Shanghai - Walk/Turn/Stop - NullRHI Sidecar Load Baseline

- brain/root/package source:
  - `D:\UE\COLMM\GASPALS\Saved\MimicKitPackages\WalkBrain\`
  - `D:\UE\COLMM\GASPALS\Saved\MimicKitPackages\TurnBrain\`
  - `D:\UE\COLMM\GASPALS\Saved\MimicKitPackages\StopBrain\`
- MimicKit reference:
  - mp4:
    - WalkBrain: `output/img/amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637/long_train/render/render.mp4`
    - TurnBrain: `output/img/amp_TurnBrain_dual_newton_hiutil_e1024_20260506_153936/long_train/render/render.mp4`
    - StopBrain: `output/img/amp_StopBrain_dual_newton_hiutil_e1024_20260521_probe01/probe_train/render/render.mp4`
  - frames:
    - WalkBrain: `output/img/amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637/long_train/render/frames/`
    - TurnBrain: `output/img/amp_TurnBrain_dual_newton_hiutil_e1024_20260506_153936/long_train/render/frames/`
    - StopBrain: `output/img/amp_StopBrain_dual_newton_hiutil_e1024_20260521_probe01/probe_train/render/frames/`
  - render_meta:
    - WalkBrain: `output/img/amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637/long_train/render/render_meta.json`
    - TurnBrain: `output/img/amp_TurnBrain_dual_newton_hiutil_e1024_20260506_153936/long_train/render/render_meta.json`
    - StopBrain: `output/img/amp_StopBrain_dual_newton_hiutil_e1024_20260521_probe01/probe_train/render/render_meta.json`
- UE capture/log:
  - capture: not produced; this run used `-NullRHI` package/replay validation only
  - log: `D:\UE\COLMM\GASPALS\Saved\Logs\GASPALSShadow_MimicKitTests_exec.log`
- camera/map/replay mode: UE 5.7 `UnrealEditor-Cmd.exe`, `-NullRHI`, `Automation RunTests GASPALSShadow;Quit`; read-only package, trace, and visual replay sidecar validation
- observed differences:
  - scale: not visually evaluated; sidecar only validated dimensions and finite values
  - root trajectory: not visually evaluated; `pose_dof_replay.jsonl` rows load and validate
  - facing: not visually evaluated
  - pose: not visually evaluated; `dof_pos` is present, but no UE skeletal pose application happened
  - contact/sliding: not visually evaluated
  - timing: sidecar row count and package frequencies validated; no rendered timing comparison
  - jitter: not visually evaluated
  - missing assets: no render/capture assets were generated in UE for this run
- verdict: block
- next action: run the first non-NullRHI UE debug-geometry visual capture against `output/img`, then append a visual diff entry before accepting any visual bridge milestone


### 2026-05-22 09:02 Asia/Shanghai - StopBrain - long01 fresh probe debug-geometry capture

- brain/root/package source:
  - root: `amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01`
  - package: `D:\UE\COLMM\GASPALS\Saved\MimicKitPackages\StopBrain_long01_probe`
- MimicKit reference:
  - mp4: `/root/Project/MimicKit/output/img/amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/probe_train/render/render.mp4`
  - frames: `/root/Project/MimicKit/output/img/amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/probe_train/render/frames`
  - render_meta: `/root/Project/MimicKit/output/img/amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/probe_train/render/render_meta.json`
- UE capture/log:
  - capture: `/mnt/d/UE/COLMM/GASPALS/Saved/MimicKitVisualCaptures/StopBrain_long01_probe`
  - log: `D:\UE\COLMM\GASPALS\Saved\Logs\GASPALSShadow_MimicKitVisualReplayCapture.log`
- camera/map/replay mode: non-NullRHI UE automation, transient debug replay, top-down root trajectory/facing capture, no skeletal pose application
- observed differences:
  - scale: watch: UE debug capture plots root_pos_m in training meters; no skeletal mesh scale validation yet.
  - root trajectory: watch: UE top-down root trajectory is visible; compare against MimicKit perspective render qualitatively.
  - facing: watch: UE facing axis is drawn from root_rot_xyzw; quaternion convention still pending full skeleton validation.
  - pose: block for full parity: debug capture does not apply dof_pos to a UE skeleton.
  - contact/sliding: block for full parity: no UE skeletal feet/contact surfaces are rendered.
  - timing: watch: capture stride matches MimicKit frame stride; no wall-clock playback validation.
  - jitter: watch: root trajectory can expose coarse jumps, but no per-joint jitter validation.
  - missing assets: watch: transient debug capture intentionally uses no content assets.
- debug artifact clarification:
  - `contact_sheet.png` is a keyframe side-by-side visual sheet for MimicKit render frames and UE debug capture frames; it is not a physical contact table.
  - UE `.ppm` frames are raster debug images drawn from `root_pos_m`, `root_rot_xyzw`, and frame index.
  - Visible UE `.ppm` signals are root marker, root trajectory, facing axis, grid/reference marks, and frame id.
  - UE `.ppm` frames do not encode `dof_pos` skeletal application, foot contact, contact force, sliding, Chaos state, or UE animation pose.
- verdict: watch
- next action: keep `long_train` gated; implement UE skeletal pose replay/joint mapping before any full visual parity pass


### 2026-05-24 22:28 Asia/Shanghai - StopBrain - long01 fresh probe debug-geometry capture

- brain/root/package source:
  - root: `amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01`
  - package: `/mnt/d/UE/COLMM/GASPALS/Saved/MimicKitPackages/StopBrain_long01_probe`
- MimicKit reference:
  - mp4: `/root/Project/MimicKit/output/img/amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/probe_train/render/render.mp4`
  - frames: `/root/Project/MimicKit/output/img/amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/probe_train/render/frames`
  - render_meta: `/root/Project/MimicKit/output/img/amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/probe_train/render/render_meta.json`
- UE capture/log:
  - capture: `/mnt/d/UE/COLMM/GASPALS/Saved/MimicKitVisualCaptures/StopBrain_long01_probe`
  - png frames: `/mnt/d/UE/COLMM/GASPALS/Saved/MimicKitVisualCaptures/StopBrain_long01_probe/png_frames`
  - mp4: `/mnt/d/UE/COLMM/GASPALS/Saved/MimicKitVisualCaptures/StopBrain_long01_probe/capture.mp4`
  - log: `D:\UE\COLMM\GASPALS\Saved\Logs\GASPALSShadow_MimicKitVisualReplayCapture.log`
- camera/map/replay mode: non-NullRHI UE automation, transient debug replay, top-down root trajectory/facing capture, no skeletal pose application
- observed differences:
  - scale: watch: UE debug capture plots root_pos_m in training meters; no skeletal mesh scale validation yet.
  - root trajectory: watch: UE top-down root trajectory is visible; compare against MimicKit perspective render qualitatively.
  - facing: watch: UE facing axis is drawn from root_rot_xyzw; quaternion convention still pending full skeleton validation.
  - pose: block for full parity: debug capture does not apply dof_pos to a UE skeleton.
  - contact/sliding: block for full parity: no UE skeletal feet/contact surfaces are rendered.
  - timing: watch: capture stride matches MimicKit frame stride; no wall-clock playback validation.
  - jitter: watch: root trajectory can expose coarse jumps, but no per-joint jitter validation.
  - missing assets: watch: transient debug capture intentionally uses no content assets.
- verdict: watch
- next action: keep `long_train` gated; implement UE skeletal pose replay/joint mapping before any full visual parity pass


### 2026-05-24 23:58 Asia/Shanghai - StopBrain - long01 fresh probe debug-geometry capture

- brain/root/package source:
  - root: `amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01`
  - package: `/mnt/d/UE/COLMM/GASPALS/Saved/MimicKitPackages/StopBrain_long01_probe`
- MimicKit reference:
  - mp4: `/root/Project/MimicKit/output/img/amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/probe_train/render/render.mp4`
  - frames: `/root/Project/MimicKit/output/img/amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/probe_train/render/frames`
  - render_meta: `/root/Project/MimicKit/output/img/amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/probe_train/render/render_meta.json`
- UE capture/log:
  - capture: `/mnt/d/UE/COLMM/GASPALS/Saved/MimicKitVisualCaptures/StopBrain_long01_probe_closure`
  - png frames: `/mnt/d/UE/COLMM/GASPALS/Saved/MimicKitVisualCaptures/StopBrain_long01_probe_closure/png_frames`
  - mp4: `/mnt/d/UE/COLMM/GASPALS/Saved/MimicKitVisualCaptures/StopBrain_long01_probe_closure/capture.mp4`
  - log: `D:\UE\COLMM\GASPALS\Saved\Logs\GASPALSShadow_MimicKitVisualReplayCapture_closure.log`
- camera/map/replay mode: non-NullRHI UE automation, transient debug replay, top-down root trajectory/facing capture, no skeletal pose application
- observed differences:
  - scale: watch: UE debug capture plots root_pos_m in training meters; no skeletal mesh scale validation yet.
  - root trajectory: watch: UE top-down root trajectory is visible; compare against MimicKit perspective render qualitatively.
  - facing: watch: UE facing axis is drawn from root_rot_xyzw; quaternion convention still pending full skeleton validation.
  - pose: block for full parity: debug capture does not apply dof_pos to a UE skeleton.
  - contact/sliding: block for full parity: no UE skeletal feet/contact surfaces are rendered.
  - timing: watch: capture stride matches MimicKit frame stride; no wall-clock playback validation.
  - jitter: watch: root trajectory can expose coarse jumps, but no per-joint jitter validation.
  - missing assets: watch: transient debug capture intentionally uses no content assets.
- verdict: watch
- next action: keep `long_train` gated; implement UE skeletal pose replay/joint mapping before any full visual parity pass


### 2026-05-25 00:25 Asia/Shanghai - StopBrain - skeletal replay visual closure

- brain/root/package source:
  - root: `amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01`
  - package: `/mnt/d/UE/COLMM/GASPALS/Saved/MimicKitPackages/StopBrain_long01_probe`
- MimicKit reference:
  - mp4: `/root/Project/MimicKit/output/img/amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/probe_train/render/render.mp4`
  - frames: `/root/Project/MimicKit/output/img/amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/probe_train/render/frames`
  - render_meta: `/root/Project/MimicKit/output/img/amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/probe_train/render/render_meta.json`
- UE capture/log:
  - capture: `/mnt/d/UE/COLMM/GASPALS/Saved/MimicKitVisualCaptures/StopBrain_long01_probe_skeletal_closure`
  - png frames: `/mnt/d/UE/COLMM/GASPALS/Saved/MimicKitVisualCaptures/StopBrain_long01_probe_skeletal_closure/png_frames`
  - mp4: `/mnt/d/UE/COLMM/GASPALS/Saved/MimicKitVisualCaptures/StopBrain_long01_probe_skeletal_closure/capture.mp4`
  - log: `D:\UE\COLMM\GASPALS\Saved\Logs\GASPALSShadow_MimicKitSkeletalVisualReplayCapture.log`
- camera/map/replay mode: non-NullRHI UE automation, offline skeletal replay capture, root_pos/root_rot/dof_pos applied to declared skeletal replay target
- capture mode: `skeletal_replay`
- UE target:
  - mesh: `/GASPALS/Characters/UE5_Mannequins/Meshes/SKM_Manny.SKM_Manny`
  - fallback renderer: `procedural_mimickit_skeletal_replay`
  - bone_map_hash: `1d7e3aaf1290193d26ec198ae9cd5c71f831f8dbb567d037dbcc2d75dc4f55c9`
  - basis_transform_hash: `a1063452ec5e1cece42f55ac93d6a7c264ef6cd31b9d626cb19e7a19622f64d7`
- observed differences:
  - scale: pass: offline basis transform is declared and capture writes meter-to-centimeter mapping metadata.
  - root trajectory: pass: UE skeletal capture is driven from visual_replay root_pos_m.
  - facing: pass: root_rot_xyzw is consumed for skeletal replay orientation/projection.
  - pose: pass: dof_pos is applied through the skeletal replay path for every captured frame.
  - contact/sliding: pass: foot bodies are present in the skeletal replay frames; contact physics remains outside this visual gate.
  - timing: pass: capture stride and frame IDs are preserved from MimicKit visual_replay.
  - jitter: watch: per-joint jitter is visually exposed in the contact sheet but not numerically scored.
  - missing assets: watch: skeletal replay uses the declared UE fallback/procedural target; do not claim full MimicKit character parity.
  - runtime physics/control: watch: this is offline skeletal replay, not live UE policy control or Chaos takeover.
- verdict: pass
- skeletal_visual_pass: true
- full_visual_parity: false
- next action: extend the skeletal gate to Walk/Turn/Stop and replace the fallback target with an imported MimicKit USD SkeletalMesh before claiming full visual parity


### 2026-05-25 09:10 Asia/Shanghai - StopBrain - source character full visual parity closure

- brain/root/package source:
  - root: `amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01`
  - package: `/mnt/d/UE/COLMM/GASPALS/Saved/MimicKitPackages/StopBrain_long01_probe`
- MimicKit reference:
  - mp4: `/root/Project/MimicKit/output/img/amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/probe_train/render/render.mp4`
  - frames: `/root/Project/MimicKit/output/img/amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/probe_train/render/frames`
  - render_meta: `/root/Project/MimicKit/output/img/amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/probe_train/render/render_meta.json`
- UE capture/log:
  - capture: `/mnt/d/UE/COLMM/GASPALS/Saved/MimicKitVisualCaptures/StopBrain_long01_probe_source_character_closure`
  - png frames: `/mnt/d/UE/COLMM/GASPALS/Saved/MimicKitVisualCaptures/StopBrain_long01_probe_source_character_closure/png_frames`
  - mp4: `/mnt/d/UE/COLMM/GASPALS/Saved/MimicKitVisualCaptures/StopBrain_long01_probe_source_character_closure/capture.mp4`
  - log: `D:\UE\COLMM\GASPALS\Saved\Logs\GASPALSShadow_MimicKitSourceCharacterReplayCapture.log`
- camera/map/replay mode: non-NullRHI UE automation, offline source-character SkeletalMesh replay, root_pos/root_rot/dof_pos applied to generated MimicKit source character
- capture mode: `source_character_skeletalmesh_replay`
- UE target:
  - mesh: `/Game/MimicKit/SwordShield/SK_MimicKit_SwordShield`
  - fallback renderer: ``
  - bone_map_hash: `1d7e3aaf1290193d26ec198ae9cd5c71f831f8dbb567d037dbcc2d75dc4f55c9`
  - basis_transform_hash: `a1063452ec5e1cece42f55ac93d6a7c264ef6cd31b9d626cb19e7a19622f64d7`
- observed differences:
  - scale: pass: source character capture uses the package basis transform and UE centimeter scene units.
  - root trajectory: pass: root_pos_m drives the source-character PoseableMeshComponent root transform.
  - facing: pass: root_rot_xyzw is applied to the source-character driver component.
  - pose: pass: dof_pos is applied through the source-character skeletal replay path.
  - contact/sliding: watch: source feet are visible and contact bodies are declared; Chaos contact is validated by the live runtime gate.
  - timing: pass: capture stride and frame IDs are preserved from MimicKit visual_replay.
  - jitter: watch: per-joint jitter is visually exposed in the contact sheet but not numerically scored.
  - missing assets: pass: UE target is the generated MimicKit source-character SkeletalMesh, not Manny/procedural fallback.
  - runtime physics/control: watch: this is offline source-character replay; live policy/Chaos closure is a separate gate.
- verdict: pass
- skeletal_visual_pass: false
- source_character_replay_pass: true
- full_visual_parity: true
- next action: run live policy/Chaos closure and keep this source-character capture as the visual parity gate


### 2026-05-25 19:43 Asia/Shanghai - StopBrain - source character full visual parity closure

- brain/root/package source:
  - root: `amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01`
  - package: `/mnt/d/UE/COLMM/GASPALS/Saved/MimicKitPackages/StopBrain_long01_probe`
- MimicKit reference:
  - mp4: `/root/Project/MimicKit/output/img/amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/probe_train/render/render.mp4`
  - frames: `/root/Project/MimicKit/output/img/amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/probe_train/render/frames`
  - render_meta: `/root/Project/MimicKit/output/img/amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/probe_train/render/render_meta.json`
- UE capture/log:
  - capture: `/mnt/d/UE/COLMM/GASPALS/Saved/MimicKitVisualCaptures/StopBrain_long01_probe_source_character_closure`
  - png frames: `/mnt/d/UE/COLMM/GASPALS/Saved/MimicKitVisualCaptures/StopBrain_long01_probe_source_character_closure/png_frames`
  - mp4: `/mnt/d/UE/COLMM/GASPALS/Saved/MimicKitVisualCaptures/StopBrain_long01_probe_source_character_closure/capture.mp4`
  - log: `D:\UE\COLMM\GASPALS\Saved\Logs\GASPALSShadow_MimicKitSourceCharacterReplayCapture.log`
- camera/map/replay mode: non-NullRHI UE automation, offline source-character SkeletalMesh replay, root_pos/root_rot/dof_pos applied to generated MimicKit source character
- capture mode: `source_character_skeletalmesh_replay`
- UE target:
  - mesh: `/Game/MimicKit/SwordShield/SK_MimicKit_SwordShield`
  - fallback renderer: ``
  - bone_map_hash: `1d7e3aaf1290193d26ec198ae9cd5c71f831f8dbb567d037dbcc2d75dc4f55c9`
  - basis_transform_hash: `a1063452ec5e1cece42f55ac93d6a7c264ef6cd31b9d626cb19e7a19622f64d7`
- observed differences:
  - scale: pass: source character capture uses the package basis transform and UE centimeter scene units.
  - root trajectory: pass: root_pos_m drives the source-character PoseableMeshComponent inside a UE SceneCapture world.
  - facing: pass: root_rot_xyzw is applied to the source-character driver component before render-target capture.
  - pose: pass: dof_pos is applied and captured through UE SceneCapture/RenderTarget, not procedural pixels.
  - contact/sliding: watch: source feet are visible and contact bodies are declared; Chaos contact is validated by the live runtime gate.
  - timing: pass: capture stride and frame IDs are preserved from MimicKit visual_replay.
  - jitter: watch: per-joint jitter is visually exposed in the contact sheet but not numerically scored.
  - missing assets: pass: UE target is the generated MimicKit source-character SkeletalMesh, not Manny/procedural fallback.
  - runtime physics/control: watch: this is offline source-character replay; live policy/Chaos closure is a separate gate.
- verdict: pass
- skeletal_visual_pass: false
- source_character_replay_pass: true
- full_visual_parity: true
- next action: run live policy/Chaos closure and keep this source-character capture as the visual parity gate


### 2026-05-26 01:15 Asia/Shanghai - StopBrain - long01 fresh probe debug-geometry capture

- brain/root/package source:
  - root: `amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01`
  - package: `/mnt/d/UE/COLMM/GASPALS/Saved/MimicKitPackages/StopBrain_long01_probe`
- MimicKit reference:
  - mp4: `/root/Project/MimicKit/output/img/amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/probe_train/render/render.mp4`
  - frames: `/root/Project/MimicKit/output/img/amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/probe_train/render/frames`
  - render_meta: `/root/Project/MimicKit/output/img/amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/probe_train/render/render_meta.json`
- UE capture/log:
  - capture: `/mnt/d/UE/COLMM/GASPALS/Saved/MimicKitVisualCaptures/StopBrain_long01_probe_source_character_closure`
  - png frames: `/mnt/d/UE/COLMM/GASPALS/Saved/MimicKitVisualCaptures/StopBrain_long01_probe_source_character_closure/png_frames`
  - mp4: `/mnt/d/UE/COLMM/GASPALS/Saved/MimicKitVisualCaptures/StopBrain_long01_probe_source_character_closure/capture.mp4`
  - log: ``
- camera/map/replay mode: non-NullRHI UE automation, transient debug replay, top-down root trajectory/facing capture, no skeletal pose application
- capture mode: `source_character_skeletalmesh_replay`
- UE target:
  - mesh: `/Game/MimicKit/SwordShield/SK_MimicKit_SwordShield`
  - fallback renderer: ``
  - bone_map_hash: `1d7e3aaf1290193d26ec198ae9cd5c71f831f8dbb567d037dbcc2d75dc4f55c9`
  - basis_transform_hash: `a1063452ec5e1cece42f55ac93d6a7c264ef6cd31b9d626cb19e7a19622f64d7`
- observed differences:
  - scale: pass: source character capture uses the package basis transform and UE centimeter scene units.
  - root trajectory: pass: root_pos_m drives the source-character PoseableMeshComponent inside a UE SceneCapture world.
  - facing: pass: root_rot_xyzw is applied to the source-character driver component before render-target capture.
  - pose: pass: dof_pos is applied and captured through UE SceneCapture/RenderTarget, not procedural pixels.
  - contact/sliding: watch: source feet are visible and contact bodies are declared; Chaos contact is validated by the live runtime gate.
  - timing: pass: capture stride and frame IDs are preserved from MimicKit visual_replay.
  - jitter: watch: per-joint jitter is visually exposed in the contact sheet but not numerically scored.
  - missing assets: pass: UE target is the generated MimicKit source-character SkeletalMesh, not Manny/procedural fallback.
  - runtime physics/control: watch: this is offline source-character replay; live policy/Chaos closure is a separate gate.
- verdict: block
- skeletal_visual_pass: false
- source_character_replay_pass: false
- full_visual_parity: false
- next action: keep `long_train` gated; implement UE skeletal pose replay/joint mapping before any full visual parity pass


### 2026-05-26 01:15 Asia/Shanghai - StopBrain - source character full visual parity closure

- brain/root/package source:
  - root: `amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01`
  - package: `/mnt/d/UE/COLMM/GASPALS/Saved/MimicKitPackages/StopBrain_long01_probe`
- MimicKit reference:
  - mp4: `/root/Project/MimicKit/output/img/amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/probe_train/render/render.mp4`
  - frames: `/root/Project/MimicKit/output/img/amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/probe_train/render/frames`
  - render_meta: `/root/Project/MimicKit/output/img/amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/probe_train/render/render_meta.json`
- UE capture/log:
  - capture: `/mnt/d/UE/COLMM/GASPALS/Saved/MimicKitVisualCaptures/StopBrain_long01_probe_source_character_closure`
  - png frames: `/mnt/d/UE/COLMM/GASPALS/Saved/MimicKitVisualCaptures/StopBrain_long01_probe_source_character_closure/png_frames`
  - mp4: `/mnt/d/UE/COLMM/GASPALS/Saved/MimicKitVisualCaptures/StopBrain_long01_probe_source_character_closure/capture.mp4`
  - log: ``
- camera/map/replay mode: non-NullRHI UE automation, offline source-character SkeletalMesh replay, root_pos/root_rot/dof_pos applied to generated MimicKit source character
- capture mode: `source_character_skeletalmesh_replay`
- UE target:
  - mesh: `/Game/MimicKit/SwordShield/SK_MimicKit_SwordShield`
  - fallback renderer: ``
  - bone_map_hash: `1d7e3aaf1290193d26ec198ae9cd5c71f831f8dbb567d037dbcc2d75dc4f55c9`
  - basis_transform_hash: `a1063452ec5e1cece42f55ac93d6a7c264ef6cd31b9d626cb19e7a19622f64d7`
- observed differences:
  - scale: pass: source character capture uses the package basis transform and UE centimeter scene units.
  - root trajectory: pass: root_pos_m drives the source-character PoseableMeshComponent inside a UE SceneCapture world.
  - facing: pass: root_rot_xyzw is applied to the source-character driver component before render-target capture.
  - pose: pass: dof_pos is applied and captured through UE SceneCapture/RenderTarget, not procedural pixels.
  - contact/sliding: watch: source feet are visible and contact bodies are declared; Chaos contact is validated by the live runtime gate.
  - timing: pass: capture stride and frame IDs are preserved from MimicKit visual_replay.
  - jitter: watch: per-joint jitter is visually exposed in the contact sheet but not numerically scored.
  - missing assets: pass: UE target is the generated MimicKit source-character SkeletalMesh, not Manny/procedural fallback.
  - runtime physics/control: watch: this is offline source-character replay; live policy/Chaos closure is a separate gate.
- verdict: pass
- skeletal_visual_pass: false
- source_character_replay_pass: true
- full_visual_parity: true
- next action: run live policy/Chaos closure and keep this source-character capture as the visual parity gate


### 2026-05-26 15:29 Asia/Shanghai - StopBrain - source character full visual parity closure

- brain/root/package source:
  - root: `amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01`
  - package: `/mnt/d/UE/COLMM/GASPALS/Saved/MimicKitPackages/StopBrain_long01_probe`
- MimicKit reference:
  - mp4: `/root/Project/MimicKit/output/img/amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/probe_train/render/render.mp4`
  - frames: `/root/Project/MimicKit/output/img/amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/probe_train/render/frames`
  - render_meta: `/root/Project/MimicKit/output/img/amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/probe_train/render/render_meta.json`
- UE capture/log:
  - capture: `/mnt/d/UE/COLMM/GASPALS/Saved/MimicKitVisualCaptures/StopBrain_long01_probe_source_character_closure`
  - png frames: `/mnt/d/UE/COLMM/GASPALS/Saved/MimicKitVisualCaptures/StopBrain_long01_probe_source_character_closure/png_frames`
  - mp4: `/mnt/d/UE/COLMM/GASPALS/Saved/MimicKitVisualCaptures/StopBrain_long01_probe_source_character_closure/capture.mp4`
  - log: ``
- camera/map/replay mode: non-NullRHI UE automation, offline source-character SkeletalMesh replay, root_pos/root_rot/dof_pos applied to generated MimicKit source character
- capture mode: `source_character_skeletalmesh_replay`
- UE target:
  - mesh: `/Game/MimicKit/SwordShield/SK_MimicKit_SwordShield`
  - fallback renderer: ``
  - bone_map_hash: `1d7e3aaf1290193d26ec198ae9cd5c71f831f8dbb567d037dbcc2d75dc4f55c9`
  - basis_transform_hash: `a1063452ec5e1cece42f55ac93d6a7c264ef6cd31b9d626cb19e7a19622f64d7`
- observed differences:
  - scale: pass: source character capture uses the package basis transform and UE centimeter scene units.
  - root trajectory: pass: root_pos_m drives the source-character PoseableMeshComponent inside a UE SceneCapture world.
  - facing: pass: root_rot_xyzw is applied to the source-character driver component before render-target capture.
  - pose: pass: dof_pos is applied and captured through UE SceneCapture/RenderTarget, not procedural pixels.
  - contact/sliding: watch: source feet are visible and contact bodies are declared; Chaos contact is validated by the live runtime gate.
  - timing: pass: capture stride and frame IDs are preserved from MimicKit visual_replay.
  - jitter: watch: per-joint jitter is visually exposed in the contact sheet but not numerically scored.
  - missing assets: pass: UE target is the generated MimicKit source-character SkeletalMesh, not Manny/procedural fallback.
  - runtime physics/control: watch: this is offline source-character replay; live policy/Chaos closure is a separate gate.
- verdict: pass
- skeletal_visual_pass: false
- source_character_replay_pass: true
- full_visual_parity: true
- next action: run live policy/Chaos closure and keep this source-character capture as the visual parity gate


### 2026-05-26 15:30 Asia/Shanghai - StopBrain - source character visual + live Chaos full closure

- brain/root/package source:
  - root: `amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01`
  - package: `/mnt/d/UE/COLMM/GASPALS/Saved/MimicKitPackages/StopBrain_long01_probe`
- MimicKit reference:
  - mp4: `/root/Project/MimicKit/output/img/amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/probe_train/render/render.mp4`
  - frames: `/root/Project/MimicKit/output/img/amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/probe_train/render/frames`
  - render_meta: `/root/Project/MimicKit/output/img/amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/probe_train/render/render_meta.json`
- UE capture/log:
  - capture: `/mnt/d/UE/COLMM/GASPALS/Saved/MimicKitVisualCaptures/StopBrain_long01_probe_source_character_closure`
  - png frames: `/mnt/d/UE/COLMM/GASPALS/Saved/MimicKitVisualCaptures/StopBrain_long01_probe_source_character_closure/png_frames`
  - mp4: `/mnt/d/UE/COLMM/GASPALS/Saved/MimicKitVisualCaptures/StopBrain_long01_probe_source_character_closure/capture.mp4`
  - visual report: `/mnt/d/UE/COLMM/GASPALS/Saved/MimicKitVisualCaptures/StopBrain_long01_probe_source_character_closure/visual_diff_report.json`
  - runtime report: `/mnt/d/UE/COLMM/GASPALS/Saved/MimicKitRuntimeClosures/StopBrain_long01_probe_live_chaos/runtime_closure_report.json`
  - combined report: `/mnt/d/UE/COLMM/GASPALS/Saved/MimicKitRuntimeClosures/StopBrain_long01_probe_live_chaos/mimickit_ue_full_closure_report.json`
  - log: `D:\UE\COLMM\GASPALS\Saved\Logs\GASPALSShadow_MimicKitLivePolicyChaosClosure.log`
- camera/map/replay mode: source-character SceneCapture visual parity plus `-NullRHI` live UE NNE policy / Chaos runtime closure
- observed differences:
  - scale: pass: source character capture uses the package basis transform and UE centimeter scene units.
  - root trajectory: pass: root_pos_m drives the generated MimicKit source character during visual replay.
  - facing: pass: root_rot_xyzw is applied before render-target capture.
  - pose: pass: dof_pos is applied through the source-character skeletal replay path.
  - contact/sliding: pass: live Chaos runtime recorded `right_foot_contact_frames=300`, `left_foot_contact_frames=300`, `contact_events=600`, and `max_foot_sliding_mps_raw=0`.
  - timing: pass: visual capture preserves 300 source rows at stride 5; runtime closure ran 300 policy frames at 30 Hz with 2400 physics substeps at 240 Hz.
  - jitter: watch: per-joint jitter remains visually inspectable but not separately scored.
  - missing assets: pass: UE target is `/Game/MimicKit/SwordShield/SK_MimicKit_SwordShield`.
- runtime closure:
  - policy backend: `NNERuntimeORTCpu`
  - observation/action: `163 / 31`
  - observation source: `ue_physics_actor_state`
  - contact source: `chaos_contact_query`
  - ground alignment: `visual_replay_frame0_foot_body_bounds_min_z`, `ground_top_z_m=-0.42814174374821745`
  - pre-policy settle substeps: `60`
  - trace fallback used: `false`
  - kinematic proxy combined pass: `false`
- verdict: pass
- source_character_replay_pass: true
- full_visual_parity: true
- live_policy_control_pass: true
- chaos_contact_validated: true
- combined_pass: true
- next action: full MimicKit-to-UE StopBrain canary bridge is closed for the probe; keep these reports as the regression gate before broadening to other brains or production asset import.
