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
unset VK_ICD_FILENAMES
EOF
chmod +x "$MINICONDA_DIR/envs/mimickit-isaaclab/etc/conda/activate.d/setenv.sh"
```

Important:
- Do not export `VK_ICD_FILENAMES=/usr/lib/wsl/drivers/.../nv-vk64.json` in Linux.
- That manifest points at Windows DLLs such as `voglv64.dll` and causes `ERROR_INCOMPATIBLE_DRIVER` when probed from `vulkaninfo` or Isaac Sim on WSL.
- Let the Linux Vulkan loader discover ICDs normally unless you are testing a specific Mesa ICD on purpose.

WSL runtime helpers:

```bash
sudo ln -sf /usr/lib/wsl/lib/nvidia-smi /usr/bin/nvidia-smi
sudo apt-get update
sudo apt-get install -y libglu1-mesa
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

White-knight sword/shield mesh validation should stay isolated in `mimickit-isaaclab`.

Minimal precheck:

```bash
source /root/miniconda3/etc/profile.d/conda.sh
conda activate mimickit-isaaclab
python - <<'PY'
import isaaclab, carb, omni, torch
print("python", __import__("sys").executable)
print("isaaclab", isaaclab.__file__)
print("torch", torch.__version__, torch.cuda.is_available())
PY
```

Build a one-clip synthetic render root:

```bash
ROOT_NAME=tmp_white_knight_render_$(date +%Y%m%d_%H%M%S)
python /root/Project/MimicKit/tools/ue_bridge/build_ase_reallusion_motion_render_root.py \
  --root-name "$ROOT_NAME" \
  --motion-ids RL_Avatar_Atk_2xCombo01_Motion \
  --base-env-config /root/Project/MimicKit/data/envs/view_motion_humanoid_sword_shield_mesh_env.yaml \
  --engine-config /root/Project/MimicKit/data/engines/isaac_lab_engine.yaml
```

Dry-run:

```bash
python /root/Project/MimicKit/tools/ue_bridge/build_mimickit_render_sequences.py \
  --roots "$ROOT_NAME" \
  --cases view_motion_humanoid_sword_shield_args \
  --dry-run --max-cases 1
```

Headless render attempt:

```bash
unset DISPLAY
export OMNI_KIT_ACCEPT_EULA=YES
export MIMICKIT_SKIP_XVFB=1
export MIMICKIT_VIEWER_HEADLESS=1
python /root/Project/MimicKit/tools/ue_bridge/build_mimickit_render_sequences.py \
  --roots "$ROOT_NAME" \
  --cases view_motion_humanoid_sword_shield_args \
  --frames 10 \
  --frame-stride 5 \
  --device cuda:0 \
  --num-envs 1 \
  --force
```

Acceptance:

- `infer_viz_index.tsv` should record `visual_kind=mesh`.
- The generated env should point `char_file` to `humanoid_sword_shield.usd`.
- If the host WSL Vulkan stack is healthy, the render should write PNGs under:
  - `output/img/<root>/runs/view_motion_humanoid_sword_shield_args/<motion_id>/render/frames`

Known WSL blocker observed on this machine:

- Isaac Sim can pass Python import and package discovery, but headless mesh render may still fail in GPU foundation startup.
- `MIMICKIT_VIEWER_HEADLESS=1` should use `isaaclab.python.headless.rendering.kit`; MimicKit's Isaac Lab engine now routes render-sequence export there.
- `IsaacLab_full/apps/isaacsim_4_5/isaaclab.python.headless.rendering.kit` was patched with `[settings.ngx] enabled = false` to get past the first NGX-dependent abort.
- Typical signatures:
  - `VkResult: ERROR_INCOMPATIBLE_DRIVER`
  - `vkCreateInstance failed`
  - `GPU Foundation is not initialized`
  - later `omni.physx.ui` / `omni.kit.viewport.window` startup errors or segfaults
- On the same Windows host, an isolated `Ubuntu 22.04` WSL distro still reports `virtio_icd.x86_64.json -> ERROR_INCOMPATIBLE_DRIVER`, while `lvp_icd.x86_64.json` falls back to `llvmpipe`.
- This is a WSL Vulkan/windowing problem, not a Newton/MimicKit dependency conflict.
- Keep Newton in `mimickit` and Isaac Lab in `mimickit-isaaclab`; do not merge dependencies while debugging this.

### 3.1.1 2026-03-12 White-Knight Host Findings

This machine has already been pushed past the first WSL blocker. The remaining issue is no longer basic package import or missing USD support.

What was fixed:

- Windows host WSL package was upgraded from `2.3.26.0` to `2.6.3.0`.
- `WSLg` was upgraded from `1.0.65` to `1.0.71`.
- `mimickit-isaaclab` activation keeps Isaac Lab isolated from Newton and unsets the bad Linux-side `VK_ICD_FILENAMES`.
- `IsaacLab_full/apps/isaacsim_4_5/isaaclab.python.headless.rendering.kit` was patched with:
  - `[settings.ngx]`
  - `enabled = false`
- `Ubuntu-20.04` and isolated `Ubuntu2204-CJM` were both upgraded to `Mesa 25.0.7` from `ppa:kisak/turtle`.

What changed after the Mesa upgrade:

- `dzn_icd.x86_64.json` becomes available under `/usr/share/vulkan/icd.d`.
- Headless `vulkaninfo` is no longer limited to `llvmpipe`.
- The active distro can enumerate real WSL D3D12-backed GPUs:
  - `Microsoft Direct3D12 (NVIDIA GeForce RTX 4090)`

What still blocks final white-knight PNG output:

- Isaac Sim still rejects the WSL GPU state during long startup and never finishes GPU Foundation initialization.
- The dominant late-stage signatures are:
  - `Multiple Installable Client Drivers (ICDs) are found for the same GPU`
  - `Skipping NVIDIA GPU due CUDA being in bad state`
  - `Failed to create any GPU devices`
  - `GPU Foundation is not initialized`
- On this dual-4090 machine, Isaac Sim still sees two D3D12-backed `RTX 4090` devices and eventually rejects them as unstable, even though `vulkaninfo` itself succeeds.

Important interpretation:

- This is better than the earlier `ERROR_INCOMPATIBLE_DRIVER` / `llvmpipe-only` state.
- The remaining blocker is now host-level WSL multi-GPU Vulkan/CUDA interaction, not a MimicKit config bug.
- Do not clean docs, commit, or push until a render actually writes `frame_*.png`.

### 3.1.2 Before Restarting WSL

If you decide to restart WSL, the goal is to clear the bad CUDA state after the Mesa/WSL upgrade.

Recommended Windows-side restart:

```powershell
wsl --shutdown
```

After WSL comes back, verify Vulkan first:

```bash
source /root/miniconda3/etc/profile.d/conda.sh
conda activate mimickit-isaaclab

env -u DISPLAY -u WAYLAND_DISPLAY \
  MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA \
  MESA_VK_DEVICE_SELECT_FORCE_DEFAULT_DEVICE=1 \
  vulkaninfo 2>&1 | sed -n '1,160p'
```

Healthy signs:

- `Microsoft Direct3D12 (NVIDIA GeForce RTX 4090)` appears.
- It should not fall back to pure `llvmpipe`.

Then re-run the minimal white-knight render:

```bash
source /root/miniconda3/etc/profile.d/conda.sh
conda activate mimickit-isaaclab

unset DISPLAY
unset WAYLAND_DISPLAY
export LD_LIBRARY_PATH=/usr/lib/wsl/lib:${LD_LIBRARY_PATH:-}
export OMNI_KIT_ACCEPT_EULA=YES
export MIMICKIT_SKIP_XVFB=1
export MIMICKIT_VIEWER_HEADLESS=1
export VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/dzn_icd.x86_64.json
export MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA
export MESA_VK_DEVICE_SELECT_FORCE_DEFAULT_DEVICE=1

python /root/Project/MimicKit/tools/ue_bridge/build_mimickit_render_sequences.py \
  --train-root /root/Project/MimicKit/output/train \
  --img-root /root/Project/MimicKit/output/img \
  --roots tmp_white_knight_render_20260312_154854 \
  --cases view_motion_humanoid_sword_shield_args \
  --frames 10 \
  --frame-stride 5 \
  --device cuda:0 \
  --num-envs 1 \
  --force
```

Post-restart success condition:

- `output/img/tmp_white_knight_render_20260312_154854/runs/view_motion_humanoid_sword_shield_args/RL_Avatar_Atk_2xCombo01_Motion/render/frames/frame_000000.png`

If it still fails after restart:

- collect the newest `kit_*.log` under `/root/Project/isaacsim/kit/logs/Kit/Isaac-Sim/4.5`
- check whether the failure is still the same dual-GPU / bad CUDA state
- only then consider host-level single-GPU masking or a full Windows reboot

### 3.1.3 Post-Restart White-Knight Re-Run Findings

Observed on `2026-03-12` after `WSL 2.6.3.0 / WSLg 1.0.71` came back:

- `vulkaninfo` under `mimickit-isaaclab` was healthier than before:
  - `Microsoft Direct3D12 (NVIDIA GeForce RTX 4090)` was visible again
  - it no longer fell back to pure `llvmpipe`
- `virtio` was still unusable on this machine:
  - `VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/virtio_icd.x86_64.json vulkaninfo`
    failed with `ERROR_INITIALIZATION_FAILED`
- MimicKit-side mitigation that is worth keeping:
  - `mimickit/engines/isaac_lab_engine.py` now sets `multi_gpu=False` in the
    `AppLauncher` config
  - this removes `--/renderer/multiGpu/enabled=True` from the Isaac Sim
    command line, which is the correct behavior for our single-case render path

Additional host probes:

- `DRI_PRIME=1!` with `dzn` can force `vulkaninfo` into a single visible GPU:
  - `selectable devices:` still lists both `4090`
  - but the resulting `VK_LAYER_MESA_device_select` device view becomes `count = 1`
- This improvement did **not** carry through to Isaac Sim itself:
  - the white-knight render still showed two `Microsoft Direct3D12 (NVIDIA GeForce RTX 4090)` entries inside `gpu.foundation`
  - the run still failed before any PNG frame was written

Latest failing signatures after the restart and re-run:

- `Multiple Installable Client Drivers (ICDs) are found for the same GPU`
- `Failed to create any GPU devices`
- `CUDA libs are present, but no suitable CUDA GPU was found!`
- `It appears that the "nvidia" kernel module is not loaded.`
- `It appears that there are no "nvidia" device nodes.`

Interpretation:

- WSL-side Vulkan enumeration is now good enough for `vulkaninfo`, but Isaac
  Sim 4.5 on this WSL host still expects a Linux-style NVIDIA render/CUDA path
  that is not actually present.
- On this machine, `dzn` improves Vulkan visibility but does not make Isaac
  Sim's RTX / GPU Foundation stack usable.
- Therefore the remaining blocker is host-platform support, not the MimicKit
  white-knight configuration.

Fastest next decision points:

- If you need final white-knight PNG output, move the Isaac Lab / Isaac Sim
  render step to:
  - native Ubuntu with supported NVIDIA Linux driver, or
  - native Windows Isaac Sim/Isaac Lab
- Keep Newton in WSL for train/test parity and use the mesh/USD path only on a
  host that Isaac Sim officially supports.

### 3.1.4 Native Windows Escape Hatch

When WSL Vulkan looks healthy enough for `vulkaninfo` but Isaac Sim still fails
inside `gpu.foundation`, stop pushing the WSL path and move the white-knight
mesh workflow to native Windows.

Recommended D-drive layout:

```text
D:\MimicKitNative\
  workspace\
    MimicKit\
    IsaacLab_full\
  runtime\
    isaacsim-4.5.0\           # optional if using binary Isaac Sim
  bootstrap\
  logs\
```

Repo-side bootstrap helpers:

- `tools/windows/bootstrap_native_windows_workspace.ps1`
- `tools/windows/run_white_knight_mesh_viewmotion.ps1`

Minimal migration flow:

1. Sync `MimicKit` and `IsaacLab_full` into `D:\MimicKitNative\workspace`.
2. On Windows, open PowerShell and run:

```powershell
powershell -ExecutionPolicy Bypass -File D:\MimicKitNative\workspace\MimicKit\tools\windows\bootstrap_native_windows_workspace.ps1
```

What the bootstrap script does:

- reuses Windows Anaconda if present
- creates `mimickit-isaaclab-win`
- installs Isaac Sim `4.5.0` via pip by default
- installs Isaac Lab source packages from the synced `IsaacLab_full`
- installs MimicKit Python requirements

Then run the white-knight viewport validation:

```powershell
powershell -ExecutionPolicy Bypass -File D:\MimicKitNative\workspace\MimicKit\tools\windows\run_white_knight_mesh_viewmotion.ps1
```

Success condition on native Windows:

- the white-knight mesh appears in the Isaac Lab viewer
- `view_motion_humanoid_sword_shield_mesh_env.yaml` runs without the WSL-only
  `gpu.foundation` / `no nvidia device nodes` failure family

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
