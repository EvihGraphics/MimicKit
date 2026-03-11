# BaselineConfig

This baseline locks the first deliverable for `UE5 x MimicKit` integration.

Current project-goal note:

- This file remains the historical baseline for the first `UE5 x MimicKit` deliverable.
- The current top-level training objective has moved to [`README_ASE_Dual4090_SOP.md`](README_ASE_Dual4090_SOP.md).
- Read that SOP first if your target is `ASE` large-scale training on dual `RTX 4090`; keep this file for UE bridge/output contract constraints.

## Locked Baseline

- Arg case: `args/deepmimic_humanoid_ppo_args.txt`
- Engine config: `data/engines/newton_engine.yaml`
- Environment config: `data/envs/deepmimic_humanoid_env.yaml`
- Agent config: `data/agents/deepmimic_humanoid_ppo_agent.yaml`
- Control mode: `pos`
- Control frequency: `30 Hz`
- Sim frequency: `240 Hz`

## Evidence

- `mimickit/run.py`
  - `load_args`, `build_env`, `build_agent`, `train`, `test`
- `mimickit/envs/char_env.py`
  - `compute_char_obs`, `_apply_action`
- `mimickit/engines/newton_engine.py`
  - `set_cmd`, `control_freq`, `sim_freq`
- `mimickit/learning/base_agent.py`
  - `train_model`, `test_model`, `save`, `load`

## Observation Contract (UE Side)

From `mimickit/envs/char_env.py::compute_char_obs`:

`[root_h?] + root_rot_obs + root_vel_obs + root_ang_vel_obs + joint_rot_obs + dof_vel + key_pos_flat?`

Required schema fields exported by `tools/ue_bridge/export_schema.py`:

- `obs_dim`
- `act_dim`
- `action_low` / `action_high`
- `global_obs`
- `root_height_obs`
- `enable_tar_obs`
- `tar_obs_steps`

## Output Layout

Per training run, bridge artifacts are stored under:

`output/train/<run_name>/ue_export/`

- `schema.json`
- `policy_actor.onnx`
- `onnx_export_meta.json`
- optional trace conversions

## Inference Render Sequence Baseline

Batch inference visualization is exported by:

`tools/ue_bridge/build_mimickit_render_sequences.py`

Locked defaults:

- `train_root=output/train`
- `img_root=output/img`
- `root_scope=all` (all timestamp roots)
- `frames=300`
- `frame_stride=5`
- `device=cuda:0`
- `num_envs=1`
- `resume=true`

Discovery rule:

- Only rows with `final_ok=1` in `output/train/*/best_by_case.tsv` are rendered.

Output contracts:

- `output/img/<root>/runs/<case>/<variant>/render/frames/frame_000000.png`
- `output/img/<root>/runs/<case>/<variant>/render/render_meta.json`
- `output/img/<root>/infer_viz_index.tsv`
- `output/img/render_all_roots.tsv`

Execution notes:

- The exporter forces headless viewer mode (`MIMICKIT_VIEWER_HEADLESS=1`) and applies a non-MSAA fallback for WSL/headless OpenGL stacks.
- If an Isaac engine config is resolved but `isaacgym` is unavailable, the exporter falls back to `data/engines/newton_engine.yaml` for render-only sequence generation.

## Explicit Gaps (Evidence-based)

- No built-in ONNX exporter in MimicKit core (`onnx`, `torch.onnx` search under `MimicKit/**`)
- No built-in online RPC service (`socket`, `grpc`, `server` search under `mimickit/**`)
- No direct UE LearningAgents trainer protocol support (`LearningAgents` search under `MimicKit/**`)

Bridge tooling under `tools/ue_bridge/` is required to close these gaps.
