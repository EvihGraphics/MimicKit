# ARC / AMP Memory-First Continuation Plan (2026-05-21)

> Superseded by `docs/plan/ARC_RADIER/PLAN-521-b.md`.
> PLAN-521-a is retained as historical context. Current filesystem truth differs: UE Saved has Walk/Turn/Stop packages, StopBrain UE package parity passes, and local `output/train` currently only retains the WalkBrain source root.

## Summary

- Source of truth: `docs/memory/20260521_amp_arc_status_checkpoint.md`.
- Current state: `WalkBrain` and `TurnBrain` have both completed 1B Newton AMP long training and render-viz.
- Immediate continuation:
  - export `TurnBrain` into the same `ue_export/` package shape as `WalkBrain` (completed)
  - run AI4AnimationPy package probe and ONNX parity trace for exported brains (completed for Walk/Turn)
  - keep UE work in `GASPALSShadow` read-only Shadow Mode
  - prepare `StopBrain` as a zero-speed steering/settle MVP (smoke chain completed)

## Key Changes

- Preserve the historical `20260430` memory file and use the new `20260521` memory checkpoint for all next decisions.
- Treat `ue_export/` as the single downstream contract boundary:
  - `policy_actor.onnx`
  - `<Brain>.onnx`
  - `schema.json`
  - `obs_fixture.jsonl`
  - `ref_actions.jsonl`
  - `normalization_stats.json`
  - `obs_action_spec.yaml`
  - `brain_manifest.json`
  - `joint_order.json`
  - `export_package_manifest.json`
- Add `StopBrain` public AMP entrypoints:
  - `args/amp_stop_humanoid_sword_shield_args.txt`
  - `data/envs/amp_stop_humanoid_sword_shield_env.yaml`
  - `scripts/run_amp_keepalive.py --brain StopBrain`
  - dashboard / UE bridge brain-name inference support
- Keep StopBrain v1 deliberately narrow: use the existing steering task family with near-zero target speed and fixed heading as a settle proxy.

## Parallel Workstreams

- Main agent:
  - owns `docs/memory`, this plan, and cross-stream integration
  - verifies final changed files and test results
- Worker A:
  - owns MimicKit AMP StopBrain training prep and smoke/probe execution
  - does not run long training until smoke/probe/render are acceptable
- Worker B:
  - owns `TurnBrain` export package generation under `output/train/amp_TurnBrain_dual_newton_hiutil_e1024_20260506_153936/ue_export`
  - verifies package inventory and ONNX export metadata
- Worker C:
  - owns AI4AnimationPy package probe and `trace_harness.py` parity outputs
  - consumes exported packages, does not invent a separate schema
- Worker D:
  - owns UE `GASPALSShadow` read-only consumption planning
  - no runtime inference takeover and no locomotion output replacement yet

## Test Plan

- Memory and package sanity:
  - parse both completed roots' `keepalive_status.json`
  - confirm memory-referenced model/render/export files exist
- TurnBrain export:
  - run `tools/ue_bridge/run_mimic_visual_case.py --amp-root amp_TurnBrain_dual_newton_hiutil_e1024_20260506_153936 --device cpu --num-envs 1 --test-episodes 1`
  - confirm `policy_actor.onnx`, `TurnBrain.onnx`, `schema.json`, fixtures, normalization stats, joint order, and manifest files exist
- AI4AnimationPy:
  - run `Demos/Locomotion/MimicKitBridge/package_probe.py` for WalkBrain and TurnBrain roots
  - run `Demos/Locomotion/MimicKitBridge/trace_harness.py` for WalkBrain and TurnBrain roots
  - fail the handoff if ONNX parity exceeds the harness threshold
- StopBrain:
  - smoke test
  - smoke visualize
  - smoke train with `--stop-after-stage smoke_train`
  - only then run 50M probe, render-viz, and a 1B long train if probe and visual behavior are acceptable
- UE Shadow Mode:
  - consume package/trace artifacts read-only
  - validate `GASPALSShadow` session logging before any ONNX runtime integration

## Execution Notes

- `TurnBrain` export completed successfully and produced the expected `ue_export/` package files.
- AI4AnimationPy parity passed:
  - `WalkBrain`: `300` rows, `obs_dim=160`, `action_dim=31`, max abs diff about `4.768e-07`
  - `TurnBrain`: `300` rows, max abs diff about `6.0e-07`
- `StopBrain` smoke chain completed at `output/train/amp_StopBrain_dual_newton_hiutil_e1024_smoke_20260521_codex/`.
- UE `GASPALSShadow` remains read-only; next work is manifest/trace consumption planning, not runtime takeover.

## Assumptions

- Continue using Newton and `/root/miniconda3/envs/mimickit/bin/python`.
- Continue using humanoid sword/shield as the ARC proxy.
- Treat StopBrain v1 as a training-interface and behavior-validation milestone, not final production stopping behavior.
- Do not add a multi-brain queue before single-brain StopBrain smoke/probe is stable.
