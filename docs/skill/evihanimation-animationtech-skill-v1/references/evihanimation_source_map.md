# EvihAnimation Source Map

## Correct Source

```text
/mnt/d/AnimationTech-learning/EvihAnimation
git@github.com:EvihGraphics/EvihAnimation.git
```

This checkout is dirty and should be treated as read-only reference. It contains useful local outputs and scripts that may not be committed upstream.

Implementation worktree:

```text
/mnt/d/AnimationTech-learning/EvihAnimation-mimickit-bridge
branch: codex/mimickit-bridge
```

## Relevant EvihAnimation Concepts

- `ai4animation/Animation/Motion.py`
  - Internal motion format: per-frame, per-joint 4x4 transforms.
  - BVH/FBX/GLB imports end up as skeleton transforms usable for visualization.

- `ai4animation/Components/Actor.py`
  - Game-engine-like actor component with `SetTransforms`, `GetBoneNames`, and scene sync.

- `Demos/MotionGraph/render_video.py`
  - Existing skeleton GIF style: Matplotlib stick skeleton from generated poses.

- `Demos/MotionMatching/render_video.py`
  - Existing skeleton GIF style for motion matching playback.

- Dirty-reference local files:
  - `Demos/MotionGraph/render_mesh_video.py`
  - `Demos/MotionMatching/render_mesh_video.py`
  - `ai4animation/Standalone/OfflineMeshRenderer.py`

Those mesh renderer files are useful design references for the future true mesh phase. Current character visual validation uses MJCF/source-spec primitives, not GLB, PyVista, or skinned mesh rendering.

## Implementation Surface

The implemented replay path lives in the clean worktree:

```text
ai4animation/Standalone/MimicKitSkeletonReplay.py
Demos/MimicKitReplay/replay_skeleton.py
Demos/MimicKitReplay/build_visual_results.py
```

The direct demo wrapper loads the replay module by file path so it can run without importing the full AI/network stack.

Current modes:

```text
--skeleton-only    sidecar-derived stick skeleton replay
--character-geom   body-attached MJCF/source-spec sphere/capsule/box/cylinder replay
--true-mesh        shared MimicKit GLB replay with scene/asset hash validation
```

The old `EvihAnimation-skeleton-replay` worktree is retained read-only because
its source/results are incomplete. New bridge results belong under the clean
`EvihAnimation-mimickit-bridge` worktree.
