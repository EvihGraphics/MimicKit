# Mimickit Env Breakage Forensics

Timestamp: `2026-03-29 00:32:00 CST`
Env: `/root/miniconda3/envs/mimickit`
Workspace: `/root/Project/MimicKit`

## Scope

Investigate why the local `mimickit` conda env is currently broken:

- `import torch` segfaults
- `torch` currently reports as `2.10.0`
- known-good docs mention a different baseline, especially `torch==2.7.0 + cu128` for the tested Isaac Lab stack

This note is based only on local evidence.

## Direct Findings

### 1. The env is currently broken below the ASE layer

Current behavior:

- `/root/miniconda3/envs/mimickit/bin/python -c "import torch"` segfaults
- `strace` shows the crash occurs immediately after loading WSL's CUDA bridge library:
  - `/usr/lib/wsl/lib/libcuda.so.1`

Evidence:

- local trace file: `/tmp/mimickit_torch_import.strace`
- last lines include:
  - open `/usr/lib/wsl/lib/libcuda.so.1`
  - immediate `SIGSEGV`

This means the current failure is not primarily an `ASE` config bug. It is a runtime failure in the `PyTorch + CUDA/WSL` layer.

### 2. `torch 2.10.0` and the current `nvidia-cu12` stack were installed on 2026-02-06

File timestamps under the env show the current package set was written in one cluster on `2026-02-06 21:08-21:10 CST`.

Evidence:

- `stat` on current install:
  - `/root/miniconda3/envs/mimickit/lib/python3.10/site-packages/torch-2.10.0.dist-info`
  - `/root/miniconda3/envs/mimickit/lib/python3.10/site-packages/nvidia_*`

Examples:

- `2026-02-06 21:09:58` `torch-2.10.0.dist-info`
- `2026-02-06 21:09:37` `nvidia_cudnn_cu12-9.10.2.21.dist-info`
- `2026-02-06 21:08:53` `nvidia_nccl_cu12-2.27.5.dist-info`

This strongly suggests the env drift happened on `2026-02-06`, not during the current `2026-03-29` session.

### 3. There is no local evidence of a recent explicit user command changing the env today

What is present:

- `conda-meta/history` records only env creation:
  - `/root/miniconda3/envs/mimickit/conda-meta/history`
  - `2026-02-06 19:18:31`
  - `conda create -n mimickit python=3.10 -y`

What is absent:

- `~/.bash_history` does not currently contain a matching `pip install torch...` or `conda install torch...` command for the drift event
- no recent shell-history evidence points to a local operator changing `torch` today

Interpretation:

- there is no direct evidence that another user recently changed the env
- there is also no direct shell-history proof of the exact `2026-02-06` install command
- the most likely explanation is that the install happened in a non-persistent shell/tmux/scripted command path or the relevant history was never flushed

### 4. The env with `torch 2.10.0` was not immediately dead; it still trained successfully later

The last reliable getup training segment succeeded much later, on `2026-03-28`.

Evidence:

- `/root/Project/MimicKit/output/train/ase_7case_tmux_20260312_235006/ase_getup_humanoid_sword_shield_l2_resume11/log.txt`
- `/root/Project/MimicKit/output/train/ase_7case_tmux_20260312_235006/ase_getup_humanoid_sword_shield_l2_resume11/model.pt`
- file timestamps:
  - `2026-03-28 22:13:46`

That segment reached:

- `Iteration 2200`
- `Samples 36061184`

So:

- `torch 2.10.0` alone did not instantly make the env unusable
- the current segfault is more consistent with a later host/runtime interaction change than with a single bad install event alone

### 5. Host/runtime drift is a plausible co-factor and is documented locally

Repo docs record significant WSL graphics/runtime churn in March.

Evidence:

- `/root/Project/MimicKit/docs/skill/mimickit-wsl-multi-backend-setup-skill/SKILL.md`
- relevant entries include:
  - `WSLg was upgraded from 1.0.65 to 1.0.71`
  - WSL/graphics stack issues around `ERROR_INCOMPATIBLE_DRIVER`
  - repeated GPU Foundation / runtime instability notes

This does not prove that WSL updates alone broke `torch`, but it does support the hypothesis that the host-side GPU runtime changed after the original `torch 2.10.0` install.

## Likely Root Cause

### Primary conclusion

The current breakage is most likely the result of **two stacked problems**:

1. **Env drift on 2026-02-06**
   - the `mimickit` env ended up on an unpinned `torch 2.10.0 + nvidia-cu12` stack
   - this diverges from the more controlled baseline documented elsewhere

2. **Later host/runtime drift**
   - current `strace` shows the actual crash happens when `torch` hits WSL's `libcuda.so.1`
   - that points to a `PyTorch/CUDA/WSL` runtime incompatibility or corruption, not just a bad ASE checkpoint

### What is less likely

- "Another user changed the env very recently"
  - confidence: low
  - reason: no local history or recent package timestamps support a fresh env mutation today

- "ASE training code itself broke the env"
  - confidence: low
  - reason: `import torch` already segfaults before ASE code matters

## Confidence

- `torch import is broken at CUDA/WSL runtime layer`: **high**
- current `torch 2.10.0` stack was installed on `2026-02-06`: **high**
- no evidence of a recent local manual env mutation today: **medium**
- host/runtime drift is part of the current failure, not just package drift: **medium-high**

## Most Actionable Next Step

Repair the env as a runtime stack, not as an ASE config issue:

1. replace the current `torch 2.10.0 + cu12` stack with a known-good pinned stack
2. validate `import torch` before touching training again
3. only after that, resume dual-GPU `ase_getup`

## Key References

- `/root/miniconda3/envs/mimickit/conda-meta/history`
- `/root/miniconda3/envs/mimickit/lib/python3.10/site-packages/torch-2.10.0.dist-info`
- `/tmp/mimickit_torch_import.strace`
- `/root/Project/MimicKit/output/train/ase_7case_tmux_20260312_235006/ase_getup_humanoid_sword_shield_l2_resume11/log.txt`
- `/root/Project/MimicKit/docs/skill/mimickit-wsl-multi-backend-setup-skill/SKILL.md`
- `/root/Project/MimicKit/docs/skill/mimickit-wsl-newton-setup-skill/SKILL.md`
