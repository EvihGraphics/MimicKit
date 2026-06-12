# MimicKit UE Bridge Tools

This folder contains the UE bridge tooling for the `MimicKit` -> `UE5` workflow:

- `run_mimic_visual_case.py`
- `export_schema.py`
- `export_actor_onnx.py`
- `export_obs_fixture.py`
- `serve_inference.py`
- `convert_ue_trace_to_mimickit.py`
- `build_mimickit_render_sequences.py`
- `finalize_ue_visual_capture.py`
- `build_ue_visual_contact_sheet.py`

## Evidence Anchors

- Train/test entry: `mimickit/run.py`
- Environment dispatch: `mimickit/envs/env_builder.py`
- Agent dispatch: `mimickit/learning/agent_builder.py`
- Training artifact save/load (`model.pt`): `mimickit/learning/base_agent.py`
- Action application: `mimickit/envs/char_env.py::_apply_action` -> `mimickit/engines/newton_engine.py::set_cmd`
- Observation contract: `mimickit/envs/char_env.py::compute_char_obs`

## Quick Start

Run from repository root:

```bash
cd /root/Project/MimicKit
```

### 1) Build the authoritative ARC export package

For ARC Stage B/C consumers, the supported entrypoint is the wrapper below. It runs MimicKit test inference, exports the policy package, writes parity fixtures, and emits the sidecar files consumed by AI4AnimationPy and UE Shadow work.

```bash
python tools/ue_bridge/run_mimic_visual_case.py \
  --amp-root amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637 \
  --device cpu \
  --num-envs 1 \
  --test-episodes 1
```

Output root:

- `output/train/<root>/ue_export/`

Required package artifacts:

- `schema.json`
- `policy_actor.onnx`
- `onnx_export_meta.json`
- `obs_fixture.jsonl`
- `ref_actions.jsonl`
- `fixture_meta.json`
- `joint_order.json`
- `normalization_stats.json`
- `obs_action_spec.yaml`
- `brain_manifest.json`
- `visual_alignment_contract.json`
- `export_package_manifest.json`

The wrapper also writes:

- `mimic_case_summary.json`
- `mimic_test.log`
- `mimic_export.log`
- `mimic_action_heatmap.ppm`

### 2) Export schema only

```bash
python tools/ue_bridge/export_schema.py \
  --arg-file args/deepmimic_humanoid_ppo_args.txt \
  --engine-config data/engines/newton_engine.yaml \
  --model-file output/train/<run_name>/model.pt
```

Output:

- `output/train/<run_name>/ue_export/schema.json`

### 3) Export ONNX only

```bash
python tools/ue_bridge/export_actor_onnx.py \
  --arg-file args/deepmimic_humanoid_ppo_args.txt \
  --engine-config data/engines/newton_engine.yaml \
  --model-file output/train/<run_name>/model.pt \
  --verify
```

Outputs:

- `output/train/<run_name>/ue_export/policy_actor.onnx`
- `output/train/<run_name>/ue_export/onnx_export_meta.json`

### 4) Export observation fixtures only

```bash
python tools/ue_bridge/export_obs_fixture.py \
  --arg-file args/deepmimic_humanoid_ppo_args.txt \
  --engine-config data/engines/newton_engine.yaml \
  --model-file output/train/<run_name>/model.pt
```

Outputs:

- `output/train/<run_name>/ue_export/obs_fixture.jsonl`
- `output/train/<run_name>/ue_export/ref_actions.jsonl`
- `output/train/<run_name>/ue_export/fixture_meta.json`

### 5) Run fallback socket inference service

```bash
python tools/ue_bridge/serve_inference.py \
  --arg-file args/deepmimic_humanoid_ppo_args.txt \
  --engine-config data/engines/newton_engine.yaml \
  --model-file output/train/<run_name>/model.pt \
  --host 127.0.0.1 --port 18080
```

Protocol (JSON-line):

- Request: `{"obs": [ ... ]}`
- Response: `{"ok": true, "action": [ ... ]}`

### 6) Convert UE trace to offline MimicKit dataset

```bash
python tools/ue_bridge/convert_ue_trace_to_mimickit.py \
  --input /path/to/ue_trace.jsonl \
  --output-dir output/train/<run_name>/ue_export \
  --output-name ue_trace_dataset
```

Outputs:

- `ue_trace_dataset.npz`
- `ue_trace_dataset.jsonl`
- `ue_trace_dataset_summary.json`

### 7) Build per-case inference render frame sequences

```bash
python tools/ue_bridge/build_mimickit_render_sequences.py \
  --train-root output/train \
  --img-root output/img \
  --root-scope all \
  --frames 300 \
  --frame-stride 5 \
  --device cuda:0 \
  --num-envs 1
```

Key behavior:

- Discover from `output/train/*/best_by_case.tsv` and keep only `final_ok=1`.
- Mirror run hierarchy from `output/train/<root>/...` into `output/img/<root>/...`.
- Export render frames at `frame_XXXXXX.png` every `frame_stride` steps.
- Write per-root and global indices:
  - `output/img/<root>/infer_viz_index.tsv`
  - `output/img/render_all_roots.tsv`

Useful flags:

- `--dry-run`: discovery/index planning only.
- `--resume` / `--force`: incremental rerun or full rebuild.
- `--roots` / `--cases`: whitelist execution scope.

Runtime notes:

- Inference renderer uses headless viewer mode by default (`MIMICKIT_VIEWER_HEADLESS=1`).
- If Isaac Gym engine config is resolved but `isaacgym` is unavailable, render export falls back to `data/engines/newton_engine.yaml`.
- When the resolved engine is `newton`, bridge tooling auto-promotes simulation/probing from a requested `cpu` device to `cuda:0` when CUDA is available. ONNX export/verification still runs on the configured export device.
- Render sequence capture uses the public engine `capture_frame()` interface.
  It writes RGB and silhouette PNG sequences plus `scene_contract_v2.json`.
  IsaacLab capture uses an offscreen render product and does not access the
  private viewer object.

### MimicKit -> EvihAnimation v2 mesh gate

Historical v2 diagnostics used a two-frame white-knight native smoke:

```bash
PYTHONPATH=tools/ue_bridge python tools/ue_bridge/build_mimickit_mesh_reference.py \
  --run-native-windows \
  --root-name tmp_white_knight_mesh_reference_20260607_bridge_smoke_v2 \
  --frames 10 --frame-stride 5 --width 960 --height 540 --mp4-fps 12 \
  --asset-export-format glb --force-root
```

That command is retained only as historical evidence. Current v3 code rejects
it because `scene_contract_v3.json` requires the 60-frame dynamic sequence.

The gate requires:

- decodable RGB and silhouette PNG sequences
- ffprobe-valid MP4 with matching frame count/fps
- `scene_contract_v2.json`
- complete replay/joint/source-rig/alignment package
- structurally valid GLB with renderable nodes, vertices, sword, and shield
- no body-order compatibility fallback

Use `snapshot_bridge_baselines.py` to protect existing Walk/Stop geom results,
and `build_full_chain_bridge_manifest.py` to aggregate the final MimicKit/Evih
manifests and human reviews.

For PLAN-6-9 v3, use the strict gate orchestrator:

```bash
PYTHONPATH=tools/ue_bridge python tools/ue_bridge/run_plan_6_9_bridge.py --gate preflight
PYTHONPATH=tools/ue_bridge python tools/ue_bridge/run_plan_6_9_bridge.py --gate framework-preflight
PYTHONPATH=tools/ue_bridge python tools/ue_bridge/run_plan_6_9_bridge.py --gate status
PYTHONPATH=tools/ue_bridge python tools/ue_bridge/run_plan_6_9_bridge.py --gate white-knight-smoke
PYTHONPATH=tools/ue_bridge python tools/ue_bridge/run_plan_6_9_bridge.py --gate white-knight
PYTHONPATH=tools/ue_bridge python tools/ue_bridge/run_plan_6_9_bridge.py --gate framework-render --case white-knight
PYTHONPATH=tools/ue_bridge python tools/ue_bridge/run_plan_6_9_bridge.py --gate walk-exact
PYTHONPATH=tools/ue_bridge python tools/ue_bridge/run_plan_6_9_bridge.py --gate stop-exact
PYTHONPATH=tools/ue_bridge python tools/ue_bridge/run_plan_6_9_bridge.py --gate aggregate
```

The runner refuses each generation gate until its predecessor has
`case_acceptance_pass=true`. It has no unreviewed-gate bypass and records the
next allowed gate in `output/img/mimickit_evih_bridge_v3/plan_6_9_execution_manifest.json`.
Every v3 generation gate uses 300 source frames sampled at stride 5 and must
emit 60 changing RGB/silhouette/ground-mask PNG frames plus a 60-frame MP4.
Evih must additionally emit the 60-frame side-by-side
`mimickit_vs_evih_dynamic.mp4`; manual review evidence is bound to that video.
For final true-mesh cases, the stdlib rasterizer is only the software geometry
baseline. Acceptance also requires EvihAnimation Framework API capture through
`AI4Animation.Mode.CAPTURE`, `Actor`, rigid-node mesh registration, and
`RenderPipeline`, with Framework provenance and scene application reports.
After each final case reaches automatic-gate completion, stop for human review;
`promote-review` validates the existing signed evidence without rerendering it.

The v3 Isaac capture records a settled renderer contract. Each capture waits
for the configured RTX settle updates, and the source contract records the
actual `0.5m` grid spacing. Manual review templates are bound to current
artifact hashes; regeneration invalidates an older signed review.

### 8) Finalize a UE visual replay capture into PNG + MP4

UE `GASPALSShadow.MimicKitVisualReplayCapture` writes debug root/facing frames.
UE `GASPALSShadow.MimicKitSkeletalVisualReplayCapture` writes the skeletal replay
canary: it consumes `joint_order.json + visual_replay/pose_dof_replay.jsonl`,
sets `capture_mode=skeletal_replay`, and requires `dof_pos_applied=true` in
`capture_meta.json`. Both paths write PNG directly and may also leave legacy PPM
files for compatibility. To build the required MP4, run:

```bash
python tools/ue_bridge/finalize_ue_visual_capture.py \
  --ue-capture-dir /mnt/d/UE/COLMM/GASPALS/Saved/MimicKitVisualCaptures/<label> \
  --fps 12 \
  --force
```

Outputs:

- `png_frames/frame_XXXXXX.png`
- `capture.mp4`
- `capture_media_manifest.json`

Then build the MimicKit-vs-UE visual sheet and ledger entry:

```bash
python tools/ue_bridge/build_ue_visual_contact_sheet.py \
  --brain StopBrain \
  --root amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01 \
  --package-dir /mnt/d/UE/COLMM/GASPALS/Saved/MimicKitPackages/StopBrain_long01_probe \
  --mimic-render-dir output/img/amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01/probe_train/render \
  --ue-capture-dir /mnt/d/UE/COLMM/GASPALS/Saved/MimicKitVisualCaptures/StopBrain_long01_probe \
  --out-report /mnt/d/UE/COLMM/GASPALS/Saved/MimicKitVisualCaptures/StopBrain_long01_probe/visual_diff_report.json \
  --contact-sheet /mnt/d/UE/COLMM/GASPALS/Saved/MimicKitVisualCaptures/StopBrain_long01_probe/contact_sheet.png \
  --ledger docs/memory/20260521_amp_ue_visual_diff_log.md
```

The report gate returns `verdict=pass` only for skeletal captures with PNG/MP4
media, `dof_pos_applied=true`, non-empty bone/basis hashes, and no pose/contact
blockers. Debug-geometry captures remain `watch` and cannot claim full visual
parity.

## Consumer Boundary

Downstream tools should treat `ue_export/` as the single package boundary:

- `brain_manifest.json` declares brain identity, frequencies, and package file mapping.
- `obs_action_spec.yaml` declares the runtime observation/action contract.
- `normalization_stats.json` and `joint_order.json` are static sidecars for parity and runtime integration.
- `visual_alignment_contract.json` declares the character asset, preferred visual asset, scene/camera assumptions, unit/rotation conventions, and required UE visual capture outputs.
- `skeletal_mapping_contract.json` declares the UE visual target, MimicKit body-to-bone map, offline basis transform, joint axis order, sword/shield attachment fallback, and skeletal visual acceptance gates.
- `export_package_manifest.json` is the package-level inventory and status summary.

## Explicit Gaps

Repository evidence still shows no built-in:

- ONNX export pipeline in core MimicKit
- Online inference RPC service in core MimicKit
- Direct compatibility with UE LearningAgents trainer protocol

These tools provide the missing bridge layer without changing MimicKit core training code.
