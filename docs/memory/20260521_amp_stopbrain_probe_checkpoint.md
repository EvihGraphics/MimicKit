# AMP StopBrain Probe + UE Shadow Replay Checkpoint (2026-05-21)

## 最终目标
- ARC/AMP 当前阶段目标：在 WalkBrain + TurnBrain 已完成 1B 与 UE package/AI4 trace 的基础上，补齐 StopBrain 的低速 steering/settle MVP 证据，并让 UE `GASPALSShadow` 只读消费 MimicKit package/trace。
- 本 checkpoint 的边界：StopBrain 只推进到 `50M probe + render-viz + memory`，不进入 1B long train；UE 只做 package ingest、trace replay、日志与自动化测试，不接管 AnimBP、Pose Search、Traversal、Overlay 或 locomotion 输出。
- 上游状态来源：`docs/memory/20260521_amp_arc_status_checkpoint.md` 与 `docs/plan/ARC_RADIER/PLAN-521-a.md`。

## 目前状态
- snapshot_time: `2026-05-21 10:24 Asia/Shanghai`
- runtime: `tmux ls` 无 tmux server；`ps` 未发现 `run_amp_keepalive` / `mimickit/run.py --arg_file args/amp_stop...` 残留进程。
- StopBrain root: `output/train/amp_StopBrain_dual_newton_hiutil_e1024_20260521_probe01`
- command:
  ```bash
  /root/miniconda3/envs/mimickit/bin/python scripts/run_amp_keepalive.py \
    --brain StopBrain \
    --root-out amp_StopBrain_dual_newton_hiutil_e1024_20260521_probe01 \
    --engine-config data/engines/newton_engine.yaml \
    --devices cuda:0 cuda:1 \
    --num-envs 1024 \
    --master-port 40590 \
    --smoke-train-samples 16384 \
    --probe-target-samples 50000000 \
    --long-target-samples 1000000000 \
    --stop-after-stage probe_train
  ```
- keepalive stages:
  - `smoke_test`: completed, `2026-05-21 09:52:26` -> `09:53:41`
  - `smoke_visualize`: completed, `2026-05-21 09:53:41` -> `09:54:06`
  - `smoke_train`: completed, `Samples=65536`
  - `probe_train`: completed, `2026-05-21 09:54:51` -> `10:18:23`
  - `long_train`: pending; intentionally not started.
- StopBrain probe final row:
  - `Samples=50003968`
  - `Iteration=762`
  - `Wall_Time=0.3860083461801211 h`
  - `Test_Return=246.8626480102539`
  - `Train_Return=214.54656982421875`
  - `Test_Episode_Length=292.37440490722656`
  - `Disc_Reward_Mean=0.3658236265182495`
  - `Disc_Agent_Acc=0.9933166801929474`
  - `Disc_Demo_Acc=1.0`
- StopBrain artifacts:
  - `output/train/amp_StopBrain_dual_newton_hiutil_e1024_20260521_probe01/keepalive_status.json`
  - `output/train/amp_StopBrain_dual_newton_hiutil_e1024_20260521_probe01/best_by_case.tsv`
  - `output/train/amp_StopBrain_dual_newton_hiutil_e1024_20260521_probe01/probe_train/model.pt`
  - `output/train/amp_StopBrain_dual_newton_hiutil_e1024_20260521_probe01/probe_train/log.txt`
  - `output/train/amp_StopBrain_dual_newton_hiutil_e1024_20260521_probe01/probe_train/events.out.tfevents.1779328506.HIVE-4090x2`
- StopBrain render-viz:
  - command:
    ```bash
    /root/miniconda3/envs/mimickit/bin/python tools/ue_bridge/build_mimickit_render_sequences.py \
      --roots amp_StopBrain_dual_newton_hiutil_e1024_20260521_probe01 \
      --cases amp_stop_humanoid_sword_shield_args \
      --frames 300 \
      --frame-stride 5 \
      --device cuda:0 \
      --num-envs 1 \
      --force
    ```
  - status: `ok`, `visual_kind=geom`, `image_count=60`, `frames=300`, `frame_stride=5`
  - artifacts:
    - `output/img/amp_StopBrain_dual_newton_hiutil_e1024_20260521_probe01/infer_viz_index.tsv`
    - `output/img/amp_StopBrain_dual_newton_hiutil_e1024_20260521_probe01/probe_train/render/render_meta.json`
    - `output/img/amp_StopBrain_dual_newton_hiutil_e1024_20260521_probe01/probe_train/render/render.mp4`
    - `output/img/amp_StopBrain_dual_newton_hiutil_e1024_20260521_probe01/probe_train/render/frames/`
  - visual spot check: `frame_000000.png` is blank, likely first-frame viewer warmup; `frame_000005.png`, `frame_000150.png`, and `frame_000295.png` show visible humanoids on the ground plane with no obvious fly-away. Full human video pass is still required before accepting 1B promotion.

## UE Shadow 只读消费状态
- Mirrored packages:
  - `D:\UE\COLMM\GASPALS\Saved\MimicKitPackages\WalkBrain\`
  - `D:\UE\COLMM\GASPALS\Saved\MimicKitPackages\TurnBrain\`
- Added sidecar-only C++ support under `Plugins/GASPALSShadow`:
  - `GASPALSMimicKitPackageLoader.h/.cpp`
  - `GASPALSMimicKitTraceReplay.h/.cpp`
  - `GASPALSMimicKitAutomationTests.cpp`
  - `UGASPALSShadowWorldSubsystem::AppendMimicKitShadowEvent(...)`
  - `FGASPALSShadowSessionManifest::MimicKitShadowFile = "mimickit_shadow.jsonl"`
- Loader contract:
  - Parses JSON: `brain_manifest.json`, `export_package_manifest.json`, `schema.json`, `joint_order.json`, `normalization_stats.json`, `ai4animation_trace/trace_meta.json`
  - Requires `obs_action_spec.yaml` as opaque file evidence; no YAML dependency added.
  - Sanitizes nonstandard `Infinity`, `-Infinity`, `NaN` in JSON before parsing; this is needed for `normalization_stats.json` `action.clip`.
- Trace replay contract:
  - Reads `ai4animation_trace/onnx_trace.jsonl`.
  - Validates finite rows, dims, `row_count=300`, and parity threshold.
  - Expected contracts:
    - WalkBrain: `obs_dim=160`, `action_dim=31`, `policy_hz=30`, `physics_hz=240`, `rows=300`, `parity_max_abs=4.768e-07`
    - TurnBrain: `obs_dim=163`, `action_dim=31`, `policy_hz=30`, `physics_hz=240`, `rows=300`, `parity_max_abs=5.960e-07`
- UE build:
  ```powershell
  & 'D:\Program Files\Epic Games\UE_5.7\Engine\Build\BatchFiles\Build.bat' `
    GASPALSEditor Win64 Development `
    -Project='D:\UE\COLMM\GASPALS\GASPALS.uproject' -WaitMutex -NoHotReload
  ```
  - result: succeeded.
- UE automation:
  - `-run=Automation` failed because UE 5.7 did not expose `AutomationCommandlet` in this install.
  - Working command:
    ```powershell
    & 'D:\Program Files\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor-Cmd.exe' `
      'D:\UE\COLMM\GASPALS\GASPALS.uproject' `
      -unattended -nop4 -nosplash -NullRHI `
      -ExecCmds='Automation RunTests GASPALSShadow;Quit' `
      -TestExit='Automation Test Queue Empty' `
      -abslog='D:\UE\COLMM\GASPALS\Saved\Logs\GASPALSShadow_MimicKitTests_exec.log'
    ```
  - tests found: `2`
  - passed:
    - `GASPALSShadow.AI4AnimationTraceReplay`
    - `GASPALSShadow.MimicKitPackageLoad`
  - log evidence: `D:\UE\COLMM\GASPALS\Saved\Logs\GASPALSShadow_MimicKitTests_exec.log`, line contains `**** TEST COMPLETE. EXIT CODE: 0 ****`

## 和最终目标还差多少
- StopBrain:
  - Full human video pass is still pending; scalar probe alone is not promotion evidence.
  - First render frame is blank; likely viewer warmup, but note it before judging the mp4.
  - StopBrain has no `ue_export/` package yet. Generate package only if visual pass is acceptable.
  - Do not start 1B long_train until the probe video is accepted and StopBrain contract is reviewed.
- UE Shadow:
  - Shadow package ingest + trace replay pass, but live UE observation building remains blocked.
  - `brain_manifest.coordinate_basis` is still `training_basis_pending_explicit_contract`; live observation parity must stay blocked until coordinate basis is explicit.
  - Reconcile docs that mention `gaspals_shadow/v1` with code that emits `gaspals_shadow/v2` before locking downstream consumers.
  - No AnimBP/Pose Search/Traversal/Overlay/content asset mutation was required for this phase; keep it that way until a separate takeover plan exists.
- Multi-brain ARC scope:
  - WalkBrain and TurnBrain are package-ready and trace-tested.
  - StopBrain is probe/render-ready but not exported.
  - StompBrain and RecoverBrain remain untrained.

## 新会话快速了解与复现入口
- 文档入口:
  - `docs/memory/20260521_amp_arc_status_checkpoint.md`
  - `docs/memory/20260521_amp_stopbrain_probe_checkpoint.md`
  - `docs/plan/ARC_RADIER/PLAN-521-a.md`
  - `docs/skill/arc-raiders-industrial-locomotion-skill-v3/SKILL.md`
- 运行态事实入口:
  - `output/train/amp_StopBrain_dual_newton_hiutil_e1024_20260521_probe01/keepalive_status.json`
  - `output/train/amp_StopBrain_dual_newton_hiutil_e1024_20260521_probe01/probe_train/log.txt`
  - `output/img/amp_StopBrain_dual_newton_hiutil_e1024_20260521_probe01/infer_viz_index.tsv`
  - `output/img/amp_StopBrain_dual_newton_hiutil_e1024_20260521_probe01/probe_train/render/render.mp4`
  - `D:\UE\COLMM\GASPALS\Saved\Logs\GASPALSShadow_MimicKitTests_exec.log`
- Minimum validation commands:
  ```bash
  /root/miniconda3/envs/mimickit/bin/python - <<'PY'
  import json
  from pathlib import Path
  for p in [
      Path('output/train/amp_StopBrain_dual_newton_hiutil_e1024_20260521_probe01/keepalive_status.json'),
      Path('output/img/amp_StopBrain_dual_newton_hiutil_e1024_20260521_probe01/probe_train/render/render_meta.json'),
  ]:
      json.loads(p.read_text())
      print('json_ok', p)
  PY
  ```
  ```powershell
  & 'D:\Program Files\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor-Cmd.exe' `
    'D:\UE\COLMM\GASPALS\GASPALS.uproject' `
    -unattended -nop4 -nosplash -NullRHI `
    -ExecCmds='Automation RunTests GASPALSShadow;Quit' `
    -TestExit='Automation Test Queue Empty' `
    -abslog='D:\UE\COLMM\GASPALS\Saved\Logs\GASPALSShadow_MimicKitTests_exec.log'
  ```
- Next recommended move:
  1. Human-watch StopBrain `render.mp4`.
  2. If acceptable, run StopBrain UE export/package + AI4 trace parity.
  3. Mirror `Saved/MimicKitPackages/StopBrain/`.
  4. Extend UE package tests to include StopBrain.
  5. Only then decide on StopBrain 1B long train.

## Follow-up Delta: PLAN-521-b Implementation Facts (2026-05-21)

This section supersedes the older "StopBrain not exported / not mirrored / tests need StopBrain" statements above.

- Current local MimicKit `output/train` truth:
  - `output/train/amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637/` exists and includes `ue_export/`.
  - `output/train/amp_TurnBrain_dual_newton_hiutil_e1024_20260506_153936/` is not present in the current local workspace.
  - `output/train/amp_StopBrain_dual_newton_hiutil_e1024_20260521_probe01/` is not present in the current local workspace.
  - StopBrain visual evidence still exists under `output/img/amp_StopBrain_dual_newton_hiutil_e1024_20260521_probe01/probe_train/render/`.
- Current UE package truth:
  - `D:\UE\COLMM\GASPALS\Saved\MimicKitPackages\WalkBrain\`
  - `D:\UE\COLMM\GASPALS\Saved\MimicKitPackages\TurnBrain\`
  - `D:\UE\COLMM\GASPALS\Saved\MimicKitPackages\StopBrain\`
- StopBrain UE package / AI4 trace evidence:
  - `obs_dim=163`
  - `action_dim=31`
  - `policy_hz=30`
  - `physics_hz=240`
  - `rows=300`
  - `parity_max_abs=5.960464477539062e-07`
  - `threshold_passed=true`
- UE automation note:
  - The UE log still reports 2 test names, but `GASPALSShadow.MimicKitPackageLoad` and `GASPALSShadow.AI4AnimationTraceReplay` each loop over `WalkBrain`, `TurnBrain`, and `StopBrain`.
  - Latest known log evidence: `D:\UE\COLMM\GASPALS\Saved\Logs\GASPALSShadow_MimicKitTests_exec.log` ended with `**** TEST COMPLETE. EXIT CODE: 0 ****`.
- Visual bridge rule added by PLAN-521-b:
  - `output/img` is the golden visual reference and is not runtime input.
  - Every UE visual bridge validation must append a MimicKit-vs-UE visual difference entry to `docs/memory/20260521_amp_ue_visual_diff_log.md`.
  - No UE visual bridge milestone is accepted without that diff entry.
- StopBrain long-train rule:
  - Because the old StopBrain probe source root is absent locally, do not claim same-root continuation from `probe_train/model.pt`.
  - A parallel StopBrain worker must use a new root, defaulting to `output/train/amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/`, and must stop at a fresh `probe_train` gate before entering true `long_train`.

## Follow-up Delta: PLAN-521-b Execution Verification (2026-05-21 23:56 Asia/Shanghai)

This section supersedes the "UE log still reports 2 test names" note above for runs after the visual replay sidecar landed.

- MimicKit package sidecar added:
  - `visual_replay/pose_dof_replay.jsonl`
  - `visual_replay/pose_dof_meta.json`
  - Stable replay meaning is `dof_pos`; `ref_action` remains only a legacy alias.
- UE `GASPALSShadow` now has 3 read-only automation test names:
  - `GASPALSShadow.AI4AnimationTraceReplay`
  - `GASPALSShadow.MimicKitPackageLoad`
  - `GASPALSShadow.MimicKitVisualReplayLoad`
  - Each test loops over `WalkBrain`, `TurnBrain`, and `StopBrain`.
- Latest UE automation command completed successfully:
  - log: `D:\UE\COLMM\GASPALS\Saved\Logs\GASPALSShadow_MimicKitTests_exec.log`
  - result line: `**** TEST COMPLETE. EXIT CODE: 0 ****`
- Visual acceptance remains blocked:
  - The latest UE run used `-NullRHI`; it validated package and sidecar data but produced no UE visual capture.
  - A blocking ledger entry was added to `docs/memory/20260521_amp_ue_visual_diff_log.md` so this run cannot be mistaken for visual parity.
- Parallel StopBrain training lane is active:
  - tmux session: `train_amp_stop_long`
  - root: `output/train/amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/`
  - current stage at this checkpoint: `probe_train`
  - current progress at this checkpoint: `6619136 / 50000000` samples
  - `long_train` status: `pending`
  - UE package export for this new root remains blocked while training is active.

## Follow-up Delta: StopBrain Long01 UE Debug Visual Comparison (2026-05-22 09:03 Asia/Shanghai)

- Fresh StopBrain probe root:
  - root: `output/train/amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/`
  - stage: `probe_train`
  - samples: `50003968 / 50000000`
  - `long_train`: still `pending`
- Fresh MimicKit visual golden reference:
  - mp4: `output/img/amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/probe_train/render/render.mp4`
  - frames: `output/img/amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/probe_train/render/frames/`
  - frame count: `60`
  - render meta: `output/img/amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/probe_train/render/render_meta.json`
- Fresh UE package mirror:
  - MimicKit source package: `output/train/amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/ue_export_probe_gate/`
  - UE mirror: `D:\UE\COLMM\GASPALS\Saved\MimicKitPackages\StopBrain_long01_probe\`
  - This did not overwrite the older `D:\UE\COLMM\GASPALS\Saved\MimicKitPackages\StopBrain\` package.
- UE debug capture:
  - capture: `D:\UE\COLMM\GASPALS\Saved\MimicKitVisualCaptures\StopBrain_long01_probe\`
  - frame count: `60`
  - capture meta: `D:\UE\COLMM\GASPALS\Saved\MimicKitVisualCaptures\StopBrain_long01_probe\capture_meta.json`
  - log: `D:\UE\COLMM\GASPALS\Saved\Logs\GASPALSShadow_MimicKitVisualReplayCapture.log`
  - mode: non-NullRHI transient debug geometry, top-down root trajectory and facing axis; no skeletal pose application.
- Comparison artifact:
  - contact sheet: `output/img/amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/probe_train/ue_debug_compare/contact_sheet.png`
  - diff report: `output/img/amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/probe_train/ue_debug_compare/diff_report.json`
  - ledger entry: `docs/memory/20260521_amp_ue_visual_diff_log.md`
  - verdict: `watch`
- PPM / contact sheet interpretation:
  - MimicKit review entry: `output/img/amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/probe_train/render/`
  - UE capture review entry: `/mnt/d/UE/COLMM/GASPALS/Saved/MimicKitVisualCaptures/StopBrain_long01_probe/`
  - comparison review entry: `output/img/amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/probe_train/ue_debug_compare/`
  - `contact_sheet.png` is a keyframe visual comparison sheet; "contact" here does not mean foot/ground contact physics.
  - UE `.ppm` files are pixel frames from the transient debug world, drawn from `root_pos_m`, `root_rot_xyzw`, and frame index.
  - The `.ppm` frames can help review root scale, root trajectory, facing axis, coarse timing, and obvious root jitter.
  - The `.ppm` frames cannot validate `dof_pos` to UE skeleton mapping, pose quality, foot contact, contact force, sliding, Chaos takeover, or final animation pose.
- Gate note:
  - This is the first real non-NullRHI UE visual comparison entry, but it is debug geometry only.
  - It validates UE can read and visualize root trajectory/facing from the fresh package.
  - It does not validate `dof_pos` to skeleton mapping, pose, foot contact, sliding, or Chaos takeover.
  - Keep `long_train` gated until skeletal pose replay/joint mapping has an accepted visual verdict.
