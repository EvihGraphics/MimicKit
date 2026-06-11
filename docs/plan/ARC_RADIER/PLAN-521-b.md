# PLAN-521-b: UE Visual Bridge, Diff Logging, And StopBrain Long-Train Lane

## Summary

- Update current memory with the 2026-05-21 filesystem truth: UE Saved has Walk/Turn/Stop MimicKit packages and trace tests cover all three, while local MimicKit `output/train` currently only retains the WalkBrain source root.
- Make MimicKit-vs-UE visual difference logging mandatory for every bridge validation run.
- Add a read-only visual replay sidecar to MimicKit packages before any UE pose application, live observation building, or Chaos takeover.
- Run StopBrain as the parallel long-training target, but gate true `long_train` behind a fresh probe/render visual check because the old StopBrain probe root is absent locally.

## Memory And Package Truth

- `docs/memory/20260521_amp_stopbrain_probe_checkpoint.md` and `docs/memory/20260521_amp_arc_status_checkpoint.md` now carry PLAN-521-b follow-up sections.
- Current local source-root caveat:
  - `output/train/amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637/` exists locally.
  - `output/train/amp_TurnBrain_dual_newton_hiutil_e1024_20260506_153936/` is absent locally.
  - `output/train/amp_StopBrain_dual_newton_hiutil_e1024_20260521_probe01/` is absent locally.
- Current UE Saved packages:
  - `D:\UE\COLMM\GASPALS\Saved\MimicKitPackages\WalkBrain\`
  - `D:\UE\COLMM\GASPALS\Saved\MimicKitPackages\TurnBrain\`
  - `D:\UE\COLMM\GASPALS\Saved\MimicKitPackages\StopBrain\`
- `output/img` is the golden visual reference for manual and later automated comparison; it is not runtime input.

## Visual Difference Logging

- Required ledger: `docs/memory/20260521_amp_ue_visual_diff_log.md`.
- Every MimicKit-vs-UE validation appends one entry with:
  - brain/root/package source
  - MimicKit reference mp4/frame/render metadata
  - UE capture/log path
  - camera/map/replay mode
  - observed differences for scale, root trajectory, facing, pose, contact/sliding, timing, jitter, and missing assets
  - verdict: `pass`, `watch`, or `block`
  - next action
- No UE visual bridge milestone is accepted without a ledger entry.

## UE Visual Bridge Sidecar

- MimicKit package sidecar:
  - `visual_replay/pose_dof_replay.jsonl`
  - `visual_replay/pose_dof_meta.json`
- Per-row fields:
  - `frame`, `episode`, `time_seconds`
  - `root_pos_m`, `root_rot_xyzw`
  - `dof_pos`, `policy_action`
  - optional `root_vel_mps`, `root_ang_vel_radps`, `dof_vel`
- Contract rules:
  - `ref_action` remains a legacy alias only; stable meaning is `dof_pos`.
  - `brain_manifest.json`, `export_package_manifest.json`, and `obs_action_spec.yaml` register visual replay paths for new exports.
  - `tools/ue_bridge/backfill_visual_replay_from_fixture.py` can derive the sidecar from existing package fixtures when source roots are unavailable.
- UE `GASPALSShadow` remains read-only:
  - `GASPALSMimicKitVisualReplay` validates the sidecar.
  - `GASPALSShadow.MimicKitVisualReplayLoad` checks finite rows, dimensions, frame monotonicity, and manifest frequency consistency.

## Parallel StopBrain Training Lane

- Worker T owns only:
  - `output/train/amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/`
- Because the old StopBrain probe root is absent locally, start a new root through the existing StopBrain keepalive flow.
- Probe-gate command:

```bash
/root/miniconda3/envs/mimickit/bin/python scripts/run_amp_keepalive.py \
  --brain StopBrain \
  --root-out amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01 \
  --engine-config data/engines/newton_engine.yaml \
  --devices cuda:0 cuda:1 \
  --num-envs 1024 \
  --master-port 40690 \
  --smoke-train-samples 16384 \
  --probe-target-samples 50000000 \
  --long-target-samples 1000000000 \
  --stop-after-stage probe_train
```

- After probe scalar checks, render-viz, and a visual diff log entry pass, resume the same root with `--stop-after-stage complete` to enter `long_train`.
- Worker T must not write `ue_export/` for this root while training is active.

## Test Plan

- Python bridge syntax:
  - `python -m py_compile tools/ue_bridge/export_obs_fixture.py tools/ue_bridge/run_mimic_visual_case.py tools/ue_bridge/backfill_visual_replay_from_fixture.py`
- Package sidecar:
  - Generate or backfill visual replay for Walk first.
  - Backfill UE Saved Walk/Turn/Stop packages while local Turn/Stop source roots are absent.
- UE:
  - Build `GASPALSEditor Win64 Development`.
  - Run `Automation RunTests GASPALSShadow;Quit`.
  - Require package load, AI4 trace replay, and visual replay load to pass for Walk/Turn/Stop.
- StopBrain training:
  - Start only the fresh probe-gated root first.
  - Accept true long training only after render-viz and visual diff ledger acceptance.

## Execution Status (2026-05-21 23:56 Asia/Shanghai)

- Memory and visual-diff ledger updates are in place.
- `PLAN-521-a.md` is marked superseded by this file.
- MimicKit visual replay sidecar generation/backfill is implemented and existing Walk/Turn/Stop UE Saved packages were backfilled.
- UE `GASPALSShadow` read-only package, trace, and visual replay tests pass for Walk/Turn/Stop.
- StopBrain Worker T is running the new gated root in tmux session `train_amp_stop_long`.
- `long_train` remains intentionally pending until the fresh probe render and MimicKit-vs-UE visual diff ledger verdict pass.

## Blockers For Later Runtime Control

- `coordinate_basis=training_basis_pending_explicit_contract`.
- UE `compute_char_obs` parity is not implemented.
- Quaternion convention, handedness, root frame, and meters-to-centimeters mapping are not locked.
- `dof_pos` to UE skeleton/control/physics joint mapping is not validated.
- No Chaos/Physical Animation takeover until visual replay and pose application have measurable agreement with MimicKit output.
