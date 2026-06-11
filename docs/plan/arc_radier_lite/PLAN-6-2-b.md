# MimicKit -> EvihAnimation Visual Bridge Plan

## Summary
- Preserve the current verified baseline: WalkBrain and StopBrain already pass sidecar data replay, skeleton parity, XML/source geom parity, 60 PNG frames, and MP4 output.
- Unblock true mesh parity by producing a real MimicKit USD mesh reference first. WSL is blocked by missing `/root/miniconda3/envs/mimickit-isaaclab`, so the default path is Windows native Isaac Lab at `D:\MimicKitNative`.
- Build Evih mesh replay only after MimicKit has `visual_kind=mesh`, `mesh_detected=1`, PNG sequence, MP4, and a passing `mesh_reference_manifest.json`.
- Do not claim true mesh parity for current Walk/Stop geom baselines. They remain `mesh_scope=false` until an exact mesh render reference exists.

## Interfaces And Artifacts
- Keep the stable data bridge unchanged: `visual_replay/pose_dof_replay.jsonl`, `pose_dof_meta.json`, `joint_order.json`, optional `mimickit_source_rig_asset_spec.json`, and `visual_alignment_contract.json`.
- Extend mesh manifests with: `mesh_reference_pass`, `asset_export.ok`, `asset_export.glb_file`, `scene_contract`, `frame_ids`, `png_count`, `mp4_ok`, `source_was_ppm_only=false`, and explicit `blocker` values.
- Add Evih CLI mode to `Demos/MimicKitReplay/replay_skeleton.py`: `--true-mesh --mesh-asset <glb> --mesh-reference-manifest <json>`.
- Add Evih result outputs: `evih_mesh_replay/frames/`, `evih_mesh_replay/mesh_replay.mp4`, `evih_mesh_replay/mesh_replay_meta.json`, `mimickit_mesh_vs_evih_mesh_sheet.png`, and manifest fields `mesh_scope=true`, `evih_mesh_replay_pass`, `true_mesh_reference_available`.
- Update the AMP dashboard to link mesh manifests, mesh MP4s, Evih visual manifests, and comparison sheets when present.

## Implementation Changes
- MimicKit mesh reference:
  - Add a Windows-native build/ingest path around `tools/ue_bridge/build_mimickit_mesh_reference.py`.
  - Use root names `tmp_white_knight_mesh_reference_20260602_bridge_smoke` and `tmp_white_knight_mesh_reference_20260602_bridge_full`.
  - Run smoke first with `frames=10`, `frame_stride=5`; run full with `frames=300`, `frame_stride=5`.
  - Canonicalize final artifacts back into `/root/Project/MimicKit/output/train/<root>/` and `/root/Project/MimicKit/output/img/<root>/`.

- USD to Evih asset:
  - Use Windows Isaac Sim `omni.kit.asset_converter` to export `humanoid_sword_shield.usd` to GLTF/GLB under the mesh reference root.
  - Record converter success, output hash, and source USD hash in the manifest.
  - If conversion fails, stop with `blocker=mesh_asset_export_failed`; do not fall back to XML geom.

- Evih mesh replay:
  - Port/adapt the dirty-source `OfflineMeshRenderer` path into the implementation worktree.
  - Add optional mesh dependency checks for `pygltflib` and `pyvista`; skeleton and geom modes must still run without them.
  - Drive mesh pose from the same solved FK used by skeleton/geom replay, using exact body/joint name matching from `joint_order.json` and source rig spec. Missing required mesh joints fails the mesh gate.
  - Use the existing `visual_alignment_contract.scene` as scene truth: `camera_mode=track`, default flat ground, root-follow framing, width `960`, height `540`, stride `5`, and mesh MP4 fps `12`.

- Result builder:
  - Extend `build_visual_results.py` to build mesh packages only when `mesh_reference_pass=true`.
  - Keep Walk/Stop skeleton and geom result packages green and unchanged.
  - Add mesh comparison sheets against MimicKit mesh frames; v1 gate is media/asset/trajectory consistency plus manual visual sheet review, not pixel-diff.

## Test Plan
- Verify existing WalkBrain and StopBrain result manifests still pass skeleton and character geom gates.
- Run MimicKit white-knight smoke: require `visual_kind=mesh`, `mesh_detected=true`, `image_count=2`, `mp4_ok=true`.
- Run MimicKit white-knight full: require 60 PNG frames, `frame_ids=[0,5,...,295]`, nonzero `render.mp4`, contact sheet, and `mesh_reference_pass=true`.
- Run Evih mesh replay from the full mesh reference: require 60 PNG frames, nonzero `mesh_replay.mp4`, `evih_mesh_replay_pass=true`, and `mimickit_mesh_vs_evih_mesh_sheet.png`.
- Verify no full-parity result passes if `source_was_ppm_only=true`, missing GLB, failed converter, missing required mesh joints, or failed MimicKit mesh reference.

## Assumptions
- Windows native Isaac Lab is the default unblock path because `/mnt/d/MimicKitNative/workspace/MimicKit` and `D:\MimicKitNative\conda\mimickit-isaaclab-win` exist.
- Current Walk/Stop `output/img` baselines are geom renders and remain valid training-result visual baselines.
- True mesh v1 starts with the isolated white-knight sword/shield reference, then the same bridge can be reused for Walk/Stop once MimicKit produces exact mesh references for those roots.
