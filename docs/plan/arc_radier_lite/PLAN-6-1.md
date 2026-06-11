# evihanimation EvihAnimation Skill + Skeleton Replay Baseline

## Summary

Replace the previous AnimationTech notebook-oriented plan with the corrected source:

- Correct source repo: `D:\AnimationTech-learning\EvihAnimation` (`/mnt/d/AnimationTech-learning/EvihAnimation`)
- Remote: `EvihGraphics/EvihAnimation`
- Current source worktree is dirty and contains useful local demo/render outputs, so treat it as **read-only reference**.
- Create a separate worktree for implementation, and add the new MimicKit skill at `docs/skill/evihanimation-animationtech-skill-v1/`.

First implementation target: reproduce MimicKit `output/` inference visualization functionally inside/alongside EvihAnimation, starting with **skeleton-only replay parity**. Character mesh parity is explicitly out of v1 scope.

## Key Changes

- New skill documents EvihAnimation as the target framework:
  - AI4AnimationPy-style ECS/update loop
  - `Motion`, BVH/FBX/GLB import, skeleton transforms
  - existing skeleton GIF paths in `Demos/MotionGraph/render_video.py` and `Demos/MotionMatching/render_video.py`
  - existing mesh renderer ideas from `OfflineMeshRenderer.py`, but mesh remains optional later work

- Use MimicKit existing baseline artifacts:
  - Walk: `output/train/amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637/ue_export`
  - Stop canary: `output/train/amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/ue_export_probe_gate`
  - Visual refs: corresponding `output/img/.../render/render_meta.json`, PNG frames, MP4s

- Add a standalone EvihAnimation replay entrypoint that consumes MimicKit export sidecars:
  - `visual_replay/pose_dof_replay.jsonl`
  - `pose_dof_meta.json`
  - `joint_order.json`
  - optional `mimickit_source_rig_asset_spec.json`
  - optional MJCF XML fallback

## Implementation Plan

- Worktree:
  - Create clean implementation worktree from `EvihGraphics/EvihAnimation`.
  - Keep `/mnt/d/AnimationTech-learning/EvihAnimation` untouched as reference, including untracked MP4/GIF/render scripts.

- Skeleton replay:
  - Load 300-frame `pose_dof_replay.jsonl`.
  - Validate finite root pose, `dof_pos_dim=31`, monotonic frames, `quat_xyzw`.
  - Use `joint_order.json` for body/joint order and dof slices.
  - Prefer source rig spec joint axes; fallback to MJCF parsing.
  - Convert root + dof into per-body global positions via deterministic FK.
  - Render stick skeleton frames using Matplotlib/PyVista-independent fallback first.

- Output contract:
  - `frames/frame_000000.png ...`
  - `skeleton_replay.mp4`
  - `skeleton_replay_meta.json`
  - `visual_compare_report.json`
  - report fields include `skeleton_replay_pass`, `mesh_scope=false`, `root_trajectory_ok`, `dof_dim_ok`, `png_count`, `mp4_ok`.

## Acceptance

- WalkBrain package produces 60 PNGs and MP4 from 300 replay frames at stride 5.
- StopBrain canary package produces the same.
- Skeleton root trajectory follows `root_pos_m`.
- All non-fixed `joint_order` dof slices are consumed exactly once.
- Missing mesh or GLB does not fail replay.
- Output visually shows moving skeleton, not static or jitter-only frames.
- Existing dirty EvihAnimation worktree and MimicKit `output/` baselines remain read-only.

## Assumptions

- Keep the skill directory name `evihanimation-animationtech-skill-v1` unless renamed later.
- “Functional一致” means matching replay timing, root path, skeleton articulation, and media outputs, not matching MimicKit code structure.
- Mesh rendering can be added after skeleton parity is stable.
