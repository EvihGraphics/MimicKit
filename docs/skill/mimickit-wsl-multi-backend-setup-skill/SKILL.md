---
name: mimickit-wsl-multi-backend-setup
description: Configure MimicKit in WSL2 with three isolated backends (Newton, Isaac Lab, Isaac Gym), including conda env strategy, activation hooks, dependency install order, smoke tests, and tmux keep-alive workflow for long-running training.
---

# MimicKit WSL Multi-Backend Setup

## Goal

Build a reproducible WSL2 setup where `MimicKit` can run with:
- `newton` backend
- `isaac_lab` backend
- `isaac_gym` backend

Each backend uses its own conda environment to avoid version conflicts.

## Environment Management (Important)

Keep one backend per conda env:
- `mimickit` -> Newton
- `mimickit-isaaclab` -> Isaac Lab
- `mimickit-isaacgym` -> Isaac Gym

Daily management commands:

```bash
source /root/miniconda3/etc/profile.d/conda.sh
conda env list

conda activate mimickit
conda activate mimickit-isaaclab
conda activate mimickit-isaacgym
```

Freeze envs for reproducibility:

```bash
conda activate mimickit && conda env export --no-builds > /root/Project/MimicKit/docs/env-mimickit.yml
conda activate mimickit-isaaclab && conda env export --no-builds > /root/Project/MimicKit/docs/env-mimickit-isaaclab.yml
conda activate mimickit-isaacgym && conda env export --no-builds > /root/Project/MimicKit/docs/env-mimickit-isaacgym.yml
```

Never install mixed backend dependencies into one env. If a backend breaks, rebuild only that env.

## tmux Policy for Long Training

Use tmux by default for any `--mode train` run and whenever SSH/network reliability is uncertain.

Keep one training job per tmux session, and encode backend in the session name:
- Newton: `mk-newton-<exp>`
- Isaac Lab: `mk-ilab-<exp>`
- Isaac Gym: `mk-igym-<exp>`

Core tmux commands:

```bash
tmux new -s mk-newton-exp01
tmux ls
tmux attach -t mk-newton-exp01
tmux kill-session -t mk-newton-exp01
```

Detach safely:
- press `Ctrl+b`, release, then press `d`

Use pane split to monitor GPU:
- `Ctrl+b` then `%` or `"`
- run `watch -n 1 nvidia-smi` or `nvtop` in the monitor pane

## Environment Layout

Use fixed paths:

```bash
export MIMICKIT_DIR=/root/Project/MimicKit
export NEWTON_DIR=/root/Project/newton
export ISAACLAB_DIR=/root/Project/IsaacLab_full
export ISAACSIM_DIR=/root/Project/isaacsim
export ISAACGYM_DIR=/root/Project/isaacgym
export MINICONDA_DIR=/root/miniconda3
```

Recommended env names:
- `mimickit` (Newton)
- `mimickit-isaaclab`
- `mimickit-isaacgym`

Optional proxy:

```bash
export HTTP_PROXY=http://127.0.0.1:7897
export HTTPS_PROXY=http://127.0.0.1:7897
export http_proxy=$HTTP_PROXY
export https_proxy=$HTTPS_PROXY
```

## 1. Base Precheck

```bash
uname -a
nvidia-smi
git --version
```

If conda is missing:

```bash
wget -O /tmp/miniconda.sh https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash /tmp/miniconda.sh -b -p "$MINICONDA_DIR"
"$MINICONDA_DIR/bin/conda" init bash
source "$MINICONDA_DIR/etc/profile.d/conda.sh"
```

Accept conda ToS once:

```bash
"$MINICONDA_DIR/bin/conda" tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main
"$MINICONDA_DIR/bin/conda" tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r
```

## 2. Newton Backend (`mimickit`)

Create env and install:

```bash
"$MINICONDA_DIR/bin/conda" create -y -n mimickit python=3.10
source "$MINICONDA_DIR/etc/profile.d/conda.sh"
conda activate mimickit
python -m pip install -U pip setuptools wheel
python -m pip install -r "$MIMICKIT_DIR/requirements.txt"
python -m pip install torch
python -m pip install mujoco --pre -f https://py.mujoco.org/
python -m pip install warp-lang --pre -U -f https://pypi.nvidia.com/warp-lang/
python -m pip install git+https://github.com/google-deepmind/mujoco_warp.git@main
python -m pip install -e "$NEWTON_DIR"
python -m pip install pyglet
```

Persist Newton runtime paths (if script exists):

```bash
install -d "$MINICONDA_DIR/envs/mimickit/etc/conda/activate.d"
cat > "$MINICONDA_DIR/envs/mimickit/etc/conda/activate.d/newton_path.sh" <<'EOF'
#!/usr/bin/env bash
if [ -f /root/Project/newton/build/newton_hlc_path.sh ]; then
  . /root/Project/newton/build/newton_hlc_path.sh
fi
EOF
chmod +x "$MINICONDA_DIR/envs/mimickit/etc/conda/activate.d/newton_path.sh"
```

Newton smoke test:

```bash
conda activate mimickit
python "$MIMICKIT_DIR/mimickit/run.py" \
  --arg_file "$MIMICKIT_DIR/args/deepmimic_humanoid_ppo_args.txt" \
  --engine_config "$MIMICKIT_DIR/data/engines/newton_engine.yaml" \
  --num_envs 1 --visualize false --mode test --test_episodes 1 --devices cuda:0
```

## 3. Isaac Lab Backend (`mimickit-isaaclab`)

Prereq:
- Isaac Sim extracted under `$ISAACSIM_DIR`
- Isaac Lab checkout at tested commit `2ed331a`
- symlink: `$ISAACLAB_DIR/_isaac_sim -> $ISAACSIM_DIR`

Create env:

```bash
"$MINICONDA_DIR/bin/conda" create -y -n mimickit-isaaclab python=3.10
source "$MINICONDA_DIR/etc/profile.d/conda.sh"
conda activate mimickit-isaaclab
python -m pip install -U pip setuptools wheel
```

Install Isaac Lab (editable packages under `source/`) and MimicKit deps:

```bash
python -m pip install torch==2.7.0 torchvision --index-url https://download.pytorch.org/whl/cu128
for p in "$ISAACLAB_DIR"/source/*; do
  if [ -f "$p/setup.py" ] || [ -f "$p/pyproject.toml" ]; then
    python -m pip install -e "$p"
  fi
done
python -m pip install -r "$MIMICKIT_DIR/requirements.txt"
```

Add activate hook:

```bash
install -d "$MINICONDA_DIR/envs/mimickit-isaaclab/etc/conda/activate.d"
cat > "$MINICONDA_DIR/envs/mimickit-isaaclab/etc/conda/activate.d/setenv.sh" <<'EOF'
#!/usr/bin/env bash
export LD_LIBRARY_PATH="/root/Project/isaacsim/extscache/omni.usd.libs-1.0.1+d02c707b.lx64.r.cp310/bin:/usr/lib/wsl/lib:${LD_LIBRARY_PATH-}"
export PYTHONPATH="/root/Project/isaacsim/extscache/omni.usd.metrics.assembler-106.1.0+106.1.lx64.r.cp310:${PYTHONPATH-}"
EOF
chmod +x "$MINICONDA_DIR/envs/mimickit-isaaclab/etc/conda/activate.d/setenv.sh"
```

Isaac Lab smoke test:

```bash
conda activate mimickit-isaaclab
python "$MIMICKIT_DIR/mimickit/run.py" \
  --arg_file "$MIMICKIT_DIR/args/deepmimic_humanoid_ppo_args.txt" \
  --engine_config "$MIMICKIT_DIR/data/engines/isaac_lab_engine.yaml" \
  --num_envs 1 --visualize false --mode test --test_episodes 1 --devices cuda:0
```

## 3.1 White-Knight Mesh Validation

When WSL can still train/test but cannot finish the white-knight `usd` render path,
keep Newton in WSL and move only the mesh visualization/render step to native
Windows.

Repo-side helpers:

- `tools/windows/bootstrap_native_windows_workspace.ps1`
- `tools/windows/apply_native_isaaclab_hotfixes.py`
- `tools/windows/run_white_knight_mesh_viewmotion.ps1`
- `tools/windows/run_white_knight_mesh_render_sequence.ps1`

Recommended native Windows layout:

```text
D:\MimicKitNative\
  workspace\
    MimicKit\
    IsaacLab_full\
  conda\
    mimickit-isaaclab-win\
  logs\
```

Bootstrap the native workspace:

```powershell
powershell -ExecutionPolicy Bypass -File D:\MimicKitNative\workspace\MimicKit\tools\windows\bootstrap_native_windows_workspace.ps1 `
  -WorkspaceRoot D:\MimicKitNative `
  -CondaPrefix D:\MimicKitNative\conda\mimickit-isaaclab-win
```

What the bootstrap now does:

- creates or reuses the prefix env `D:\MimicKitNative\conda\mimickit-isaaclab-win`
- installs Isaac Sim `4.5.0` via pip by default
- installs Isaac Lab source packages from `IsaacLab_full`
- installs MimicKit requirements plus the missing native-Windows extras
- writes the `flatdict` compatibility shim into `site-packages`
- accepts the Omniverse EULA
- applies the minimal external IsaacLab hotfixes through `apply_native_isaaclab_hotfixes.py`

Interactive white-knight viewport validation:

```powershell
powershell -ExecutionPolicy Bypass -File D:\MimicKitNative\workspace\MimicKit\tools\windows\run_white_knight_mesh_viewmotion.ps1 `
  -WorkspaceRoot D:\MimicKitNative `
  -CondaPrefix D:\MimicKitNative\conda\mimickit-isaaclab-win `
  -Device cuda:0 `
  -MotionFile D:\MimicKitNative\workspace\MimicKit\data\motions\reallusion\RL_Avatar_Atk_2xCombo01_Motion.pkl
```

Render-sequence export on native Windows:

```powershell
powershell -ExecutionPolicy Bypass -File D:\MimicKitNative\workspace\MimicKit\tools\windows\run_white_knight_mesh_render_sequence.ps1 `
  -WorkspaceRoot D:\MimicKitNative `
  -CondaPrefix D:\MimicKitNative\conda\mimickit-isaaclab-win `
  -RootName case_white_knight_mesh_native_20260312_224041 `
  -Frames 60 `
  -FrameStride 10 `
  -Device cuda:0
```

Important native-Windows render settings:

- `MIMICKIT_SKIP_XVFB=1`
- `MIMICKIT_VIEWER_HEADLESS=0`

These keep the export on `isaaclab.python.rendering.kit`. The validated white-knight
closure on `2026-03-12` used the GUI render path instead of the headless
`physx.fabric` path.

Validated closure from the isolated native workspace:

- root: `case_white_knight_mesh_native_20260312_224041`
- motion: `RL_Avatar_Atk_2xCombo01_Motion`
- index: `output/img/case_white_knight_mesh_native_20260312_224041/infer_viz_index.tsv`
- result: `status=ok`, `visual_kind=mesh`, `image_count=6`
- frames:
  - `output/img/case_white_knight_mesh_native_20260312_224041/runs/view_motion_humanoid_sword_shield_args/RL_Avatar_Atk_2xCombo01_Motion/render/frames`

Interpretation:

- WSL remains the recommended home for Newton train/test parity.
- Native Windows is the validated escape hatch for final white-knight `usd`
  visualization and render-sequence export on this dual-4090 host.

## 4. Isaac Gym Backend (`mimickit-isaacgym`)

Prereq:
- Isaac Gym Preview4 extracted to `$ISAACGYM_DIR`

Create env and install compatible stack:

```bash
"$MINICONDA_DIR/bin/conda" create -y -n mimickit-isaacgym python=3.7
"$MINICONDA_DIR/bin/conda" install -y -q -n mimickit-isaacgym -c pytorch -c nvidia pytorch=1.13.1 torchvision=0.14.1 pytorch-cuda=11.7
source "$MINICONDA_DIR/etc/profile.d/conda.sh"
conda activate mimickit-isaacgym
python -m pip install -U pip setuptools wheel
python -m pip install -e "$ISAACGYM_DIR/python"
python -m pip install gymnasium==0.28.1 matplotlib==3.5.3 tensorboardX wandb==0.17.9
```

Add activate/deactivate hooks:

```bash
install -d "$MINICONDA_DIR/envs/mimickit-isaacgym/etc/conda/activate.d" "$MINICONDA_DIR/envs/mimickit-isaacgym/etc/conda/deactivate.d"
cat > "$MINICONDA_DIR/envs/mimickit-isaacgym/etc/conda/activate.d/setenv.sh" <<'EOF'
#!/usr/bin/env bash
export _MIMICKIT_ISAACGYM_OLD_PYTHONPATH="${PYTHONPATH-}"
export _MIMICKIT_ISAACGYM_OLD_LD_LIBRARY_PATH="${LD_LIBRARY_PATH-}"
ISAACGYM_PYTHON="/root/Project/isaacgym/python"
ISAACGYM_BINDINGS="/root/Project/isaacgym/python/isaacgym/_bindings/linux-x86_64"
WSL_CUDA_LIB="/usr/lib/wsl/lib"
CONDA_LIB="${CONDA_PREFIX}/lib"
export PYTHONPATH="${ISAACGYM_PYTHON}${PYTHONPATH:+:${PYTHONPATH}}"
export LD_LIBRARY_PATH="${ISAACGYM_BINDINGS}:${CONDA_LIB}:${WSL_CUDA_LIB}${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"
EOF
cat > "$MINICONDA_DIR/envs/mimickit-isaacgym/etc/conda/deactivate.d/unsetenv.sh" <<'EOF'
#!/usr/bin/env bash
if [ "${_MIMICKIT_ISAACGYM_OLD_PYTHONPATH+x}" = "x" ]; then export PYTHONPATH="${_MIMICKIT_ISAACGYM_OLD_PYTHONPATH}"; else unset PYTHONPATH; fi
if [ "${_MIMICKIT_ISAACGYM_OLD_LD_LIBRARY_PATH+x}" = "x" ]; then export LD_LIBRARY_PATH="${_MIMICKIT_ISAACGYM_OLD_LD_LIBRARY_PATH}"; else unset LD_LIBRARY_PATH; fi
unset _MIMICKIT_ISAACGYM_OLD_PYTHONPATH
unset _MIMICKIT_ISAACGYM_OLD_LD_LIBRARY_PATH
EOF
chmod +x "$MINICONDA_DIR/envs/mimickit-isaacgym/etc/conda/activate.d/setenv.sh" "$MINICONDA_DIR/envs/mimickit-isaacgym/etc/conda/deactivate.d/unsetenv.sh"
```

Isaac Gym smoke test:

```bash
conda activate mimickit-isaacgym
TORCH_EXTENSIONS_DIR=/tmp/torch_extensions_isaacgym \
python "$MIMICKIT_DIR/mimickit/run.py" \
  --arg_file "$MIMICKIT_DIR/args/deepmimic_humanoid_ppo_args.txt" \
  --engine_config "$MIMICKIT_DIR/data/engines/isaac_gym_engine.yaml" \
  --num_envs 1 --visualize false --mode test --test_episodes 1 --devices cuda:0
```

## 5. Long-Run Training Sessions

Use backend-specific env + engine config inside the matching tmux session.

Newton example:
```bash
tmux new -s mk-newton-train01
conda activate mimickit
python "$MIMICKIT_DIR/mimickit/run.py" \
  --arg_file "$MIMICKIT_DIR/args/deepmimic_humanoid_ppo_args.txt" \
  --engine_config "$MIMICKIT_DIR/data/engines/newton_engine.yaml" \
  --mode train --num_envs 1024 --visualize false --devices cuda:0
```

Isaac Lab example:
```bash
tmux new -s mk-ilab-train01
conda activate mimickit-isaaclab
python "$MIMICKIT_DIR/mimickit/run.py" \
  --arg_file "$MIMICKIT_DIR/args/deepmimic_humanoid_ppo_args.txt" \
  --engine_config "$MIMICKIT_DIR/data/engines/isaac_lab_engine.yaml" \
  --mode train --num_envs 1024 --visualize false --devices cuda:0
```

Isaac Gym example:
```bash
tmux new -s mk-igym-train01
conda activate mimickit-isaacgym
TORCH_EXTENSIONS_DIR=/tmp/torch_extensions_isaacgym \
python "$MIMICKIT_DIR/mimickit/run.py" \
  --arg_file "$MIMICKIT_DIR/args/deepmimic_humanoid_ppo_args.txt" \
  --engine_config "$MIMICKIT_DIR/data/engines/isaac_gym_engine.yaml" \
  --mode train --num_envs 1024 --visualize false --devices cuda:0
```

## 6. Required Compatibility Patch

For old/new torch compatibility in Isaac Gym env, keep this change in `mimickit/envs/deepmimic_env.py`:
- replace `torch.linalg.vector_norm(..., dim=-1)` with `torch.norm(..., p=2, dim=-1)` in `compute_tracking_error`.

This avoids runtime failures when `torch.linalg.vector_norm` is unavailable.

## 7. Validation Checklist

Run:

```bash
source "$MINICONDA_DIR/etc/profile.d/conda.sh"
conda activate mimickit && python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
conda activate mimickit-isaaclab && python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
conda activate mimickit-isaacgym && python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

Expected:
- all envs import torch successfully
- `torch.cuda.is_available()` is `True`
- each backend smoke test reaches `Mean Return` output without crash

## 8. Project Initial Test Ladder

Run these checks in order after a fresh setup:

1) Python + CUDA import:

```bash
conda activate mimickit
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

2) Backend module import:

```bash
conda activate mimickit
python -c "import newton, mimickit; print('newton ok')"
conda activate mimickit-isaaclab
python -c "import torch; print('isaaclab env ok')"
conda activate mimickit-isaacgym
python -c "import isaacgym.gymapi as gymapi; print('isaacgym ok')"
```

3) MimicKit backend smoke tests:
- Newton: run command from section 2
- Isaac Lab: run command from section 3
- Isaac Gym: run command from section 4

4) Pass condition:
- each run prints `Building PPO agent`
- each run ends with `Mean Return` and `Episodes: 1`

## Known Issues

1. Long downloads stall:
- keep proxy configured
- re-run same conda command (resume from cache)

2. Isaac Lab warnings under WSL:
- GPU foundation/OmniHub warnings are common in headless WSL; run can still complete

3. Isaac Gym with outdated torch:
- `nvrtc invalid value for --gpu-architecture` means torch/cuda stack is too old for current GPU
- use `torch 1.13.1 + pytorch-cuda 11.7`

4. Motion data missing:
- extract MimicKit data pack into `data/` before smoke tests

5. SSH disconnect during training:
- this does not stop jobs running in tmux sessions
- reconnect and resume with `tmux attach -t <session>`
