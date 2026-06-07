# AMP / ARC 当前状态 Checkpoint (2026-05-21)

## 最终目标

- 最终目标仍然是完成 `docs/skill/arc-raiders-industrial-locomotion-skill-v3/SKILL.md` 定义的 ARC-like 工业化链路：
  - MimicKit AMP 多脑训练
  - render-viz / demo 验证
  - ONNX 与 runtime 数据契约
  - AI4AnimationPy parity / trace 验证
  - UE5 Shadow Mode 与后续物理驱动运行时接入
- 本 checkpoint 接续 `docs/memory/20260430_amp_arc_status_checkpoint.md`，不覆盖旧记录。
- 当前阶段已经从 “WalkBrain probe running” 推进到：
  - `WalkBrain` 1B long train 完成
  - `TurnBrain` 1B long train 完成
  - 两个 root 都完成 post-train test / visualize / render
  - 初始 checkpoint pass 仅 `WalkBrain` 已观察到 `ue_export/` package；本文件后续记录了本轮补出的 `TurnBrain` export

## 当前状态总览

- snapshot_time: `2026-05-21`
- current_stage: `Stage A / MimicKit AMP 多脑训练后验收与 Stage B/C 准备`
- runtime_state: `completed/offline`
- dashboard_state: `not live`
- training_sessions: no observed `train_amp` / `monitor_amp` tmux sessions
- dashboard_api: `http://127.0.0.1:8789/api/status` did not return JSON during this checkpoint pass
- engine: `data/engines/newton_engine.yaml`
- python: `/root/miniconda3/envs/mimickit/bin/python`

## 已完成训练 root

| Brain | Root | Case | Status | Samples | Test Return | Render | UE export |
|---|---|---|---|---:|---:|---|---|
| `WalkBrain` | `amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637` | `amp_location_humanoid_sword_shield` | completed `2026-05-01` | `1000013824` | `428.6161` | ready, `mp4_count=1` | present |
| `TurnBrain` | `amp_TurnBrain_dual_newton_hiutil_e1024_20260506_153936` | `amp_steering_humanoid_sword_shield` | completed `2026-05-06` | `1000013824` | `247.1339` | ready, `mp4_count=1` | generated after initial checkpoint pass |

### WalkBrain evidence

- summary:
  - `output/train/amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637/post_train_summary.md`
- keepalive status:
  - `output/train/amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637/keepalive_status.json`
- model:
  - `output/train/amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637/long_train/model.pt`
- render:
  - `output/img/amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637/infer_viz_index.tsv`
  - `output/img/amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637/long_train/render/render.mp4`
  - `output/img/amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637/long_train/render/render_meta.json`
- UE export package:
  - `output/train/amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637/ue_export/policy_actor.onnx`
  - `output/train/amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637/ue_export/WalkBrain.onnx`
  - `output/train/amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637/ue_export/schema.json`
  - `output/train/amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637/ue_export/obs_fixture.jsonl`
  - `output/train/amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637/ue_export/ref_actions.jsonl`
  - `output/train/amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637/ue_export/normalization_stats.json`
  - `output/train/amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637/ue_export/obs_action_spec.yaml`
  - `output/train/amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637/ue_export/brain_manifest.json`
  - `output/train/amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637/ue_export/joint_order.json`
  - `output/train/amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637/ue_export/export_package_manifest.json`

### TurnBrain evidence

- summary:
  - `output/train/amp_TurnBrain_dual_newton_hiutil_e1024_20260506_153936/post_train_summary.md`
- keepalive status:
  - `output/train/amp_TurnBrain_dual_newton_hiutil_e1024_20260506_153936/keepalive_status.json`
- model:
  - `output/train/amp_TurnBrain_dual_newton_hiutil_e1024_20260506_153936/long_train/model.pt`
- render:
  - `output/img/amp_TurnBrain_dual_newton_hiutil_e1024_20260506_153936/infer_viz_index.tsv`
  - `output/img/amp_TurnBrain_dual_newton_hiutil_e1024_20260506_153936/long_train/render/render.mp4`
  - `output/img/amp_TurnBrain_dual_newton_hiutil_e1024_20260506_153936/long_train/render/render_meta.json`
- UE export package:
  - `output/train/amp_TurnBrain_dual_newton_hiutil_e1024_20260506_153936/ue_export/policy_actor.onnx`
  - `output/train/amp_TurnBrain_dual_newton_hiutil_e1024_20260506_153936/ue_export/TurnBrain.onnx`
  - `output/train/amp_TurnBrain_dual_newton_hiutil_e1024_20260506_153936/ue_export/schema.json`
  - `output/train/amp_TurnBrain_dual_newton_hiutil_e1024_20260506_153936/ue_export/obs_fixture.jsonl`
  - `output/train/amp_TurnBrain_dual_newton_hiutil_e1024_20260506_153936/ue_export/ref_actions.jsonl`
  - `output/train/amp_TurnBrain_dual_newton_hiutil_e1024_20260506_153936/ue_export/normalization_stats.json`
  - `output/train/amp_TurnBrain_dual_newton_hiutil_e1024_20260506_153936/ue_export/obs_action_spec.yaml`
  - `output/train/amp_TurnBrain_dual_newton_hiutil_e1024_20260506_153936/ue_export/brain_manifest.json`
  - `output/train/amp_TurnBrain_dual_newton_hiutil_e1024_20260506_153936/ue_export/joint_order.json`
  - `output/train/amp_TurnBrain_dual_newton_hiutil_e1024_20260506_153936/ue_export/export_package_manifest.json`

## 重要警告

- `WalkBrain` 和 `TurnBrain` 的 post-train summary 都记录：
  - `discriminator: 判别器失衡`
  - `render: render ready`
- 这意味着 scalar 和 render 产物都已生成，但不能只凭 reward 宣布工业化可用。
- 后续推进到 AI4AnimationPy / UE5 前，必须进行人工 render 观感复核和 ONNX parity 验证。

## 当前差距

训练侧：

- `WalkBrain` 和 `TurnBrain` 已完成 1B。
- `StopBrain` 已完成最小 smoke chain，但还没有进入 50M probe 或 1B long train。
- `StompBrain`、`RecoverBrain` 尚未训练。
- `scripts/run_amp_keepalive.py` 已补 `WalkBrain` / `TurnBrain` / `StopBrain` 单脑入口。
- AMP v1 仍是 single-brain mode，没有正式 `run_amp_series_queue.py` 多脑串列控制器。

导出与契约侧：

- `WalkBrain` 已有 `ue_export/` package。
- `TurnBrain` 已补跑同一套 `tools/ue_bridge/run_mimic_visual_case.py` export package。
- 多脑统一 manifest 尚未锁定。
- `obs_action_spec.yaml`、`normalization_stats.json`、`brain_manifest.json` 仍需进入 Walk/Turn/Stop 三脑一致性检查。

Stage B / C：

- AI4AnimationPy 已有 `Demos/Locomotion/MimicKitBridge` 入口，并已基于 Walk/Turn package 跑过 probe 与 trace harness。
- UE 工程 `/mnt/d/UE/COLMM/GASPALS` 已有 `GASPALSShadow` read-only plugin。
- UE 侧下一步仍应保持 Shadow Mode，不接管正式 locomotion 输出链。

## 下一步命令入口

### 1. TurnBrain UE export package

```bash
cd /root/Project/MimicKit
/root/miniconda3/envs/mimickit/bin/python tools/ue_bridge/run_mimic_visual_case.py \
  --amp-root amp_TurnBrain_dual_newton_hiutil_e1024_20260506_153936 \
  --device cpu \
  --num-envs 1 \
  --test-episodes 1
```

This command was run successfully after the initial checkpoint pass.

### 2. AI4AnimationPy package probe / parity trace

```bash
cd /mnt/d/WorldModel/place_holder/ai4animationpy
python Demos/Locomotion/MimicKitBridge/package_probe.py \
  /root/Project/MimicKit/output/train/amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637
python Demos/Locomotion/MimicKitBridge/trace_harness.py \
  /root/Project/MimicKit/output/train/amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637
```

The same two commands were also run successfully for:

```text
/root/Project/MimicKit/output/train/amp_TurnBrain_dual_newton_hiutil_e1024_20260506_153936
```

### 3. StopBrain MVP prep

Treat StopBrain v1 as a zero-speed steering/settle MVP:

- add `args/amp_stop_humanoid_sword_shield_args.txt`
- add matching env config based on `amp_steering_humanoid_sword_shield_env.yaml`
- extend `scripts/run_amp_keepalive.py` to accept `--brain StopBrain`
- extend dashboard/export brain inference so StopBrain does not get mislabeled
- validate in this order:
  1. smoke test
  2. smoke visualize
  3. smoke train
  4. 50M probe
  5. render-viz
  6. 1B long train only if probe is acceptable

Smoke test, smoke visualize, and smoke train were run successfully with:

```text
output/train/amp_StopBrain_dual_newton_hiutil_e1024_smoke_20260521_codex/
```

Latest smoke metrics:

- `Samples=65536`
- `Test_Return=11.5445`
- `Train_Return=5.6863`
- `Disc_Reward_Mean=0.8123`
- `Disc_Agent_Acc / Disc_Demo_Acc=0.8779 / 1.0`

## Handoff notes

- Use this file as the new source of truth before planning further Stage A/B/C work.
- Keep `docs/memory/20260430_amp_arc_status_checkpoint.md` unchanged as the older running-state checkpoint.
- Next execution plan should live under `docs/plan/ARC_RADIER/` and reference this memory file explicitly.
- Subagent work should be split after this memory checkpoint:
  - main agent: `docs/memory` and cross-stream coordination
  - Worker A: MimicKit AMP training/export prep, including StopBrain
  - Worker B: `tools/ue_bridge` package checks and TurnBrain export
  - Worker C: AI4AnimationPy package probe and ONNX parity trace
  - Worker D: UE `GASPALSShadow` read-only consumption planning

## Follow-up Delta: PLAN-521-b Current Truth (2026-05-21)

This follow-up supersedes the older StopBrain "smoke only / no 50M probe" status in this file.

- StopBrain has completed a documented 50M probe and render-viz pass:
  - render reference: `output/img/amp_StopBrain_dual_newton_hiutil_e1024_20260521_probe01/probe_train/render/render.mp4`
  - render metadata: `output/img/amp_StopBrain_dual_newton_hiutil_e1024_20260521_probe01/probe_train/render/render_meta.json`
- UE Saved currently has three mirrored MimicKit packages:
  - `D:\UE\COLMM\GASPALS\Saved\MimicKitPackages\WalkBrain\`
  - `D:\UE\COLMM\GASPALS\Saved\MimicKitPackages\TurnBrain\`
  - `D:\UE\COLMM\GASPALS\Saved\MimicKitPackages\StopBrain\`
- StopBrain UE Saved package parity evidence:
  - `obs_dim=163`
  - `action_dim=31`
  - `policy_hz=30`
  - `physics_hz=240`
  - `row_count=300`
  - `parity_max_abs=5.960464477539062e-07`
  - `threshold_passed=true`
- Current local disk caveat:
  - `output/train/amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637/` exists locally.
  - `output/train/amp_TurnBrain_dual_newton_hiutil_e1024_20260506_153936/` is absent locally.
  - `output/train/amp_StopBrain_dual_newton_hiutil_e1024_20260521_probe01/` is absent locally.
  - Therefore UE Saved packages and `output/img` renders are current evidence for Turn/Stop, while local `output/train` is not complete evidence for those roots.
- UE `GASPALSShadow` status:
  - Package load and AI4 trace replay tests cover Walk/Turn/Stop.
  - New PLAN-521-b work adds a read-only `visual_replay/pose_dof_*` package sidecar and a dedicated visual replay automation test.
- Visual acceptance rule:
  - MimicKit-vs-UE visual differences must be recorded in `docs/memory/20260521_amp_ue_visual_diff_log.md` for every bridge validation run.
  - `output/img` remains the golden visual reference; UE does not consume it directly.
- StopBrain training lane:
  - StopBrain remains the next long-training target.
  - Because the old probe root is missing locally, start a new gated root at `output/train/amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/`.
  - Stop at `probe_train` first; only enter `long_train` after probe render-viz and visual diff log acceptance.

## Follow-up Delta: PLAN-521-b Execution Verification (2026-05-21 23:56 Asia/Shanghai)

- MimicKit package sidecar implementation:
  - New exports include `visual_replay/pose_dof_replay.jsonl` and `visual_replay/pose_dof_meta.json`.
  - Existing Walk/Turn/Stop UE Saved packages were backfilled from package fixtures.
- UE `GASPALSShadow` status after implementation:
  - Build target `GASPALSEditor Win64 Development` succeeded.
  - Automation now has 3 test names: package load, AI4 trace replay, and visual replay load.
  - All three test names cover `WalkBrain`, `TurnBrain`, and `StopBrain`.
  - Latest automation log: `D:\UE\COLMM\GASPALS\Saved\Logs\GASPALSShadow_MimicKitTests_exec.log`.
  - Latest result: `**** TEST COMPLETE. EXIT CODE: 0 ****`.
- Visual bridge status:
  - The latest UE validation was `-NullRHI` data loading only, not rendered visual parity.
  - A blocking entry was added to `docs/memory/20260521_amp_ue_visual_diff_log.md`.
  - First accepted UE visual milestone still requires a real UE capture compared against `output/img`.
- StopBrain Worker T:
  - tmux session: `train_amp_stop_long`.
  - root: `output/train/amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/`.
  - current stage at this checkpoint: `probe_train`, `6619136 / 50000000` samples.
  - `long_train` remains pending until the new probe render and visual diff verdict pass.

## Follow-up Delta: First Non-NullRHI UE Visual Debug Comparison (2026-05-22 09:03 Asia/Shanghai)

- StopBrain `long01` probe completed at `50003968` samples; `long_train` remains pending.
- Fresh MimicKit reference was generated at:
  - `output/img/amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/probe_train/render/render.mp4`
  - `output/img/amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/probe_train/render/frames/`
- Fresh visual package was exported and mirrored without touching the older StopBrain package:
  - source: `output/train/amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/ue_export_probe_gate/`
  - UE mirror: `D:\UE\COLMM\GASPALS\Saved\MimicKitPackages\StopBrain_long01_probe\`
- UE non-NullRHI debug capture passed:
  - test: `GASPALSShadow.MimicKitVisualReplayCapture`
  - capture: `D:\UE\COLMM\GASPALS\Saved\MimicKitVisualCaptures\StopBrain_long01_probe\`
  - frame count: `60`
  - mode: transient debug geometry, top-down root trajectory and facing axis
- Comparison artifact:
  - `output/img/amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/probe_train/ue_debug_compare/contact_sheet.png`
  - `output/img/amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/probe_train/ue_debug_compare/diff_report.json`
- Visual ledger verdict:
  - file: `docs/memory/20260521_amp_ue_visual_diff_log.md`
  - verdict: `watch`
- PPM/contact sheet note:
  - `contact_sheet.png` is a keyframe MimicKit-vs-UE debug visual sheet, not a physical contact report.
  - UE `.ppm` frames are raster captures of root/facing debug geometry from `root_pos_m` and `root_rot_xyzw`; they do not validate `dof_pos` skeletal replay, foot contact/sliding, or Chaos takeover.
- Acceptance caveat:
  - This is a real UE visual comparison entry, but it is not full visual parity.
  - `dof_pos` to UE skeleton mapping, foot contact/sliding, joint jitter, and Chaos takeover remain blocked.

## Follow-up Delta: PLAN-526-a Full MimicKit-to-UE Bridge Closure (2026-05-26 15:30 Asia/Shanghai)

- Scope:
  - canary root: `amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01`
  - package: `D:\UE\COLMM\GASPALS\Saved\MimicKitPackages\StopBrain_long01_probe\`
  - MimicKit golden reference: `output/img/amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/probe_train/render/`
  - UE source character: `/Game/MimicKit/SwordShield/SK_MimicKit_SwordShield`
- Build:
  - `GASPALSEditor Win64 Development` succeeded; UBT reported target up to date.
  - `GASPALSShadow` links `NNE`, `PhysicsCore`, `RenderCore`, `RHI`, and `ImageWrapper`.
- Source-character visual gate:
  - test: `GASPALSShadow.MimicKitSourceCharacterReplayCapture`
  - log: `D:\UE\COLMM\GASPALS\Saved\Logs\GASPALSShadow_MimicKitSourceCharacterReplayCapture.log`
  - result: `**** TEST COMPLETE. EXIT CODE: 0 ****`
  - capture: `D:\UE\COLMM\GASPALS\Saved\MimicKitVisualCaptures\StopBrain_long01_probe_source_character_closure\`
  - render source: `ue_scene_capture_render_target`
  - frame format: direct PNG, `legacy_ppm_written=false`
  - PNG/MP4: `png_ok=true`, `png_count=60`, `mp4_ok=true`
  - visual report: `visual_diff_report.json`
  - verdict: `pass`
  - `source_character_replay_pass=true`
  - `full_visual_parity=true`
- Live UE NNE + Chaos closure:
  - test: `GASPALSShadow.MimicKitLivePolicyChaosClosure`
  - log: `D:\UE\COLMM\GASPALS\Saved\Logs\GASPALSShadow_MimicKitLivePolicyChaosClosure.log`
  - result: `**** TEST COMPLETE. EXIT CODE: 0 ****`
  - runtime report: `D:\UE\COLMM\GASPALS\Saved\MimicKitRuntimeClosures\StopBrain_long01_probe_live_chaos\runtime_closure_report.json`
  - combined report: `D:\UE\COLMM\GASPALS\Saved\MimicKitRuntimeClosures\StopBrain_long01_probe_live_chaos\mimickit_ue_full_closure_report.json`
  - runtime backend: `NNERuntimeORTCpu`
  - observation/action dims: `163 / 31`
  - observation source: `ue_physics_actor_state`
  - policy/control: `policy_frames=300`, `policy_hz=30`, `physics_hz=240`, `physics_substeps=2400`
  - pre-policy settle: `pre_policy_settle_substeps=60`
  - contact source: `chaos_contact_query`
  - ground alignment: `visual_replay_frame0_foot_body_bounds_min_z`, `ground_top_z_m=-0.42814174374821745`
  - foot contact: `right_foot_contact_frames=300`, `left_foot_contact_frames=300`, `contact_events=600`
  - body validation: `right_foot_body_validated=true`, `left_foot_body_validated=true`
  - sliding: `max_foot_sliding_mps_raw=0`, `sliding_under_threshold=true`
  - `policy_inference_ran=true`
  - `trace_fallback_used=false`
  - `physics_simulated=true`
  - `joint_drive_applied=true`
  - `live_policy_control_pass=true`
  - `chaos_contact_validated=true`
  - `combined_pass=true`
- Negative gates:
  - `kinematic_proxy_report.json` remains diagnostic-only with `combined_pass=false`.
  - Debug/procedural visual reports remain non-full-parity: debug captures are `watch`, skeletal fallback has `full_visual_parity=false`, only source-character capture has `full_visual_parity=true`.
- Local sync:
  - Latest UE package contracts and build report were copied back into `output/train/amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/ue_export_probe_gate/`.
  - Latest `runtime_closure_report.json`, `mimickit_ue_full_closure_report.json`, `kinematic_proxy_report.json`, `runtime_trace.jsonl`, `visual_diff_report.json`, and `capture_media_manifest.json` were copied into the same local export gate.
- Implementation note:
  - No additional source patch was required in this pass. Rebuilding/rerunning picked up the newer PLAN-526-a runtime code already present in `GASPALSMimicKitVisualReplayCapture.cpp`, including source-rig joint data, deterministic frame0 ground alignment, per-foot body/shape evidence, and pre-policy settle.
- Status:
  - StopBrain probe canary now has a closed MimicKit-to-UE bridge: source-character visual parity, PNG sequence, MP4, live UE NNE policy inference, UE physics observation, joint drive, real two-foot Chaos contact, and strict negative gates all pass.
