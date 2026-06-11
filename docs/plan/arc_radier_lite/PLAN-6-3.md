# PLAN-6-3 v2: MimicKit -> EvihAnimation Full-Chain Visual Bridge

## Scope

- Close the visual bridge for white-knight, WalkBrain long, and StopBrain probe.
- Preserve the existing Walk/Stop geom baselines and keep them marked
  `mesh_scope=false`.
- Use the same exported GLB, replay sidecars, and scene contract on both sides.
- Require decodable PNG sequences and MP4 media. PPM-only output is a failure.

## Current Truth

- The current native blocker is no longer `carb` or `omni.kit.usd` import.
- The old IsaacLab render path failed on the private `_viewer.get_frame()` API.
- The old 380-byte white-knight GLB is structurally empty and must not pass.
- The old dummy package omitted joint order, source rig spec, and alignment
  contracts.
- The old Evih source checkout and `EvihAnimation-skeleton-replay` worktree are
  read-only references. New implementation work uses:

```text
/mnt/d/AnimationTech-learning/EvihAnimation-mimickit-bridge
```

## Implemented Interfaces

- `Engine.capture_frame(width, height, include_silhouette=True) -> CaptureFrame`
  is the public capture boundary. IsaacLab uses an offscreen render product;
  render sequence code does not access `_viewer`.
- Every render writes RGB PNG, silhouette PNG, a validated MP4, and
  `scene_contract_v2.json`.
- The v2 scene contract fixes `960x540`, stride 5, 12 fps, seed 7, camera
  samples, coordinate system, ground, lighting, color space, and renderer
  identity.
- Dummy and policy exports share the visual package builder and must emit replay,
  joint order, skeletal mapping, visual alignment, and source rig sidecars.
- GLB acceptance is based on `asset_structure_manifest.json`, not file existence.
- Strict native mesh runs reject body-order compatibility fallback.
- Dashboard readiness is manifest-driven. Failed or incomplete manifests show
  blockers instead of `render ready`.

## Delivery Gates

### G0 Baseline Protection

- Snapshot existing Walk long and Stop probe geom artifacts.
- Require 60 decodable PNGs, valid MP4, and `mesh_scope=false`.
- Keep skeleton parity at `max_body_pos_error_m <= 1e-6`.

### G1 White-Knight Smoke

```text
tmp_white_knight_mesh_reference_20260607_bridge_smoke_v2
frames=[0,5]
```

Require RGB/silhouette PNGs, validated MP4, complete package, valid GLB, and
scene contract. Empty GLB, private viewer capture, missing sidecars, and
compatibility fallback are hard failures.

### G2 White-Knight Full

```text
tmp_white_knight_mesh_reference_20260607_bridge_full_v2
frames=[0,5,...,295]
```

Require 60 exact PNGs, MP4, contact sheet, complete asset/package, and
`mesh_reference_pass=true`.

### G3 Evih White-Knight

```text
/mnt/d/AnimationTech-learning/EvihAnimation-mimickit-bridge/Demos/MimicKitReplay/results/white_knight_mesh_replay_v2
```

Require matching GLB, replay sidecar, and scene hashes plus binding, scene,
trajectory, media, and visual metric passes.

### G4 Exact Training Roots

- Walk source: `amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637/long_train`
- Stop source: `amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/probe_train`
- Build independent exact-mesh roots. Never overwrite old geom roots.

### G5 Full-Chain Closure

`full_chain_bridge_manifest.json` passes only when white-knight, Walk long, and
Stop probe all pass with no blocker and required human reviews pass.

## Visual Acceptance

- Corresponding frame IDs must match.
- Mean silhouette IoU `>= 0.90`; p10 IoU `>= 0.80`.
- Mean centroid error `<= 2%` image diagonal; p95 `<= 4%`.
- Bbox area-ratio p10/p90 must stay within `[0.85, 1.15]`.
- `motion_visible=true`; black frames, duplicate static sequences, and PPM-only
  output fail.
- RGB perceptual differences are reported but are not a strict pixel-equality
  gate.
- `visual_review.json` must confirm character, sword/shield, pose, camera,
  ground, lighting, frame pairing, and no obvious drift or penetration.

## Commands

```bash
PYTHONPATH=tools/ue_bridge /root/miniconda3/envs/mimickit/bin/python \
  tools/ue_bridge/snapshot_bridge_baselines.py

PYTHONPATH=tools/ue_bridge /root/miniconda3/envs/mimickit/bin/python \
  tools/ue_bridge/build_mimickit_mesh_reference.py \
  --run-native-windows \
  --root-name tmp_white_knight_mesh_reference_20260607_bridge_smoke_v2 \
  --frames 10 --frame-stride 5 --width 960 --height 540 --mp4-fps 12 \
  --asset-export-format glb --force-root
```

Progression is smoke -> full -> Evih white-knight -> exact roots -> full-chain.
Do not advance a stage while the preceding manifest is failed.

## Assumptions

- Stop has a `probe_train` source, not a `long_train` source.
- Dirty/broken Evih checkouts remain unmodified.
- Evih must load the exact MimicKit-exported GLB; XML geom fallback cannot pass
  true-mesh gates.
