---
name: mimickit-render-viz-sequence-skill
description: Build MimicKit inference visualization frame sequences from output/train best_by_case.tsv final_ok=1 cases, mirror output/train hierarchy into output/img, export per-step render PNGs with stride sampling, and produce root/global TSV indices. Use when running dry-run discovery, per-root/per-case rendering, resume/force control, or troubleshooting MimicKit render-path failures across Newton, Isaac Gym, and Isaac Lab.
---

# MimicKit Render Viz Sequence

## Use Commands

- Dry-run discovery (no rendering):
```bash
/root/miniconda3/envs/mimickit/bin/python tools/ue_bridge/build_mimickit_render_sequences.py \
  --dry-run --max-cases 5
```

- Single root + single case render:
```bash
/root/miniconda3/envs/mimickit/bin/python tools/ue_bridge/build_mimickit_render_sequences.py \
  --roots <root_name> --cases <case_name_without_txt> \
  --frames 300 --frame-stride 5 --device cuda:0 --num-envs 1
```

- Full pass (only roots whose rows are all final_ok=1):
```bash
/root/miniconda3/envs/mimickit/bin/python tools/ue_bridge/build_mimickit_render_sequences.py \
  --root-scope full_pass
```

- Force rebuild (ignore resume):
```bash
/root/miniconda3/envs/mimickit/bin/python tools/ue_bridge/build_mimickit_render_sequences.py \
  --roots <root_name> --cases <case_name_without_txt> --force
```

- Native Windows white-knight mesh render:
```powershell
powershell -ExecutionPolicy Bypass -File D:\MimicKitNative\workspace\MimicKit\tools\windows\run_white_knight_mesh_render_sequence.ps1 `
  -WorkspaceRoot D:\MimicKitNative `
  -CondaPrefix D:\MimicKitNative\conda\mimickit-isaaclab-win `
  -RootName case_white_knight_mesh_native_20260312_224041 `
  -Frames 60 `
  -FrameStride 10 `
  -Device cuda:0
```

## Workflow

1. Discover `output/train/*/best_by_case.tsv`.
2. Keep only rows with `final_ok=1`.
3. Map each case `out_dir` (relative to root) into `output/img/<root>/.../render`.
4. Resolve model/configs with fallback chain:
   - model: `long_out_dir/model.pt -> train_out_dir/model.pt -> probe_out_dir/model.pt -> out_dir/{long_train,train,probe_train}/model.pt`
   - configs: model-dir yaml -> TSV fields -> `args/<case>.txt`
5. Build runtime with `build_runtime_context(..., visualize=True)`.
6. Force offscreen viewer path by default (`MIMICKIT_VIEWER_HEADLESS=1`) to avoid interactive event-loop blocking in headless/WSL sessions.
7. If resolved engine config points to `isaac_gym` but `isaacgym` is unavailable, fallback to `data/engines/newton_engine.yaml`.
8. Generate actions:
   - policy case: prefer the agent test loop (`set_mode(TEST) -> _reset_envs -> _decide_action -> _step_env -> _reset_done_envs`)
   - fallback only when the agent loop is unavailable: deterministic actor (`eval_actor + norm`)
   - dummy case: zero action clipped to action space
9. Capture frame every `frame_stride` from the engine viewer and save `frame_XXXXXX.png`.
   - Newton / Isaac Gym can still return the old warp-backed viewer tensor.
   - Isaac Lab can now return a `numpy.ndarray` via the viewport wrapper in `isaac_lab_engine.py`.
10. Write case meta (`render_meta.json`) and indices:
   - `output/img/<root>/infer_viz_index.tsv`
   - `output/img/render_all_roots.tsv`

ASE-specific note:

- Do not judge ASE quality from renders that bypass the agent test loop.
- A static actor wrapper can skip latent reset/update behavior and produce false negatives such as “blue agent jitters in place”.
- If an ASE render looks like idle wobble or near-frozen poses, rerender with the agent test loop before concluding the checkpoint collapsed.

## Acceptance

- Path contract:
  - `output/img/<root>/runs/<case>/<variant>/render/frames/frame_000000.png`
  - `output/img/<root>/runs/<case>/<variant>/render/render_meta.json`
  - `output/img/<root>/infer_viz_index.tsv`
  - `output/img/render_all_roots.tsv`
- Selection contract: all indexed rows come from `final_ok=1`.
- Visual contract: `visual_kind` is recorded as `mesh|geom|unknown` and `mesh_detected` is present.
- ASE visual contract: for ASE policy cases, sampled frames should show pose progression across the sequence; near-identical frames are a render-path warning first, not immediate proof of bad training.
- Resume contract: second run with same params returns `status=skipped_resume` only when prior `status=ok` and frame count reaches expected count.
- Force contract: `--force` bypasses resume and rebuilds.

## Troubleshooting

- `ShaderException` / GLSL version too low:
  - Symptom: `GLSL 1.50 is not supported` in `render_error.log`.
  - Action: run under a valid OpenGL-capable desktop/X server; ensure driver and context satisfy viewer shader requirements.
- Frequent `Warp CUDA error 304` while rendering:
  - Symptom: repeated CUDA/GL interop warnings.
  - Action: expected on WSL/non-interop stacks; rendering continues through copy fallback.
- `DISPLAY is not set and xvfb-run was not found`:
  - Install `xvfb-run` (package `xvfb`) or provide a desktop session with valid `DISPLAY`.
- Native Windows render should not use `xvfb-run`:
  - Set `MIMICKIT_SKIP_XVFB=1` and `MIMICKIT_VIEWER_HEADLESS=0`.
  - The validated white-knight mesh closure on `2026-03-12` used the GUI `isaaclab.python.rendering.kit` path.
- `ModuleNotFoundError: isaacgym`:
  - Action: use Newton engine fallback (`data/engines/newton_engine.yaml`) only for Isaac Gym render-only export.
- `missing model file for policy case`:
  - Check fallback candidates in TSV (`long_out_dir`, `train_out_dir`, `probe_out_dir`, `out_dir`).
- `env_config not found` / `engine_config not found`:
  - Ensure config YAMLs exist in model dir or are resolvable from TSV/arg file.
- Unexpected skips:
  - Use `--force` to rebuild and reset the render directory.
- ASE agent only jitters or stands nearly still:
  - Symptom: blue agent pose barely changes while the green/demo reference moves.
  - Action: verify the render is using the agent test loop rather than a static policy wrapper; rerender with `--force` after updating `tools/ue_bridge/build_mimickit_render_sequences.py`.
- `viewer not available (render path requires visualize=True)` with Isaac Lab mesh:
  - Action: update `mimickit/engines/isaac_lab_engine.py` to expose a viewport-backed `_viewer`.
  - Current `main` already includes the wrapper used by the validated native Windows white-knight export.
