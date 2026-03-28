#!/usr/bin/env python3
import argparse
import json
import os
import shlex
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UPSTREAM_ROOT = ROOT / "third_party" / "ase_upstream"
UPSTREAM_ASE_ROOT = UPSTREAM_ROOT / "ase"
DEFAULT_PYTHON = "/root/miniconda3/envs/mimickit-isaacgym/bin/python"
DEFAULT_ENV_BIN = "/root/miniconda3/envs/mimickit-isaacgym/bin"
DEFAULT_ENV_LIB = "/root/miniconda3/envs/mimickit-isaacgym/lib"
DEFAULT_ISAACGYM_ROOT = "/root/Project/isaacgym/python"


@dataclass(frozen=True)
class RefCase:
    key: str
    task: str
    cfg_env: str
    cfg_train: str
    motion_file: str
    checkpoint: str
    llc_checkpoint: str = ""


CASES = [
    RefCase(
        key="getup",
        task="HumanoidAMPGetup",
        cfg_env="ase/data/cfg/humanoid_ase_sword_shield_getup.yaml",
        cfg_train="ase/data/cfg/train/rlg/ase_humanoid.yaml",
        motion_file="ase/data/motions/reallusion_sword_shield/dataset_reallusion_sword_shield.yaml",
        checkpoint="ase/data/models/ase_llc_reallusion_sword_shield.pth",
    ),
    RefCase(
        key="heading",
        task="HumanoidHeading",
        cfg_env="ase/data/cfg/humanoid_sword_shield_heading.yaml",
        cfg_train="ase/data/cfg/train/rlg/hrl_humanoid.yaml",
        motion_file="ase/data/motions/reallusion_sword_shield/RL_Avatar_Idle_Ready_Motion.npy",
        checkpoint="ase/data/models/ase_hlc_heading_reallusion_sword_shield.pth",
        llc_checkpoint="ase/data/models/ase_llc_reallusion_sword_shield.pth",
    ),
    RefCase(
        key="location",
        task="HumanoidLocation",
        cfg_env="ase/data/cfg/humanoid_sword_shield_location.yaml",
        cfg_train="ase/data/cfg/train/rlg/hrl_humanoid.yaml",
        motion_file="ase/data/motions/reallusion_sword_shield/RL_Avatar_Idle_Ready_Motion.npy",
        checkpoint="ase/data/models/ase_hlc_location_reallusion_sword_shield.pth",
        llc_checkpoint="ase/data/models/ase_llc_reallusion_sword_shield.pth",
    ),
    RefCase(
        key="reach",
        task="HumanoidReach",
        cfg_env="ase/data/cfg/humanoid_sword_shield_reach.yaml",
        cfg_train="ase/data/cfg/train/rlg/hrl_humanoid.yaml",
        motion_file="ase/data/motions/reallusion_sword_shield/RL_Avatar_Idle_Ready_Motion.npy",
        checkpoint="ase/data/models/ase_hlc_reach_reallusion_sword_shield.pth",
        llc_checkpoint="ase/data/models/ase_llc_reallusion_sword_shield.pth",
    ),
    RefCase(
        key="strike",
        task="HumanoidStrike",
        cfg_env="ase/data/cfg/humanoid_sword_shield_strike.yaml",
        cfg_train="ase/data/cfg/train/rlg/hrl_humanoid.yaml",
        motion_file="ase/data/motions/reallusion_sword_shield/RL_Avatar_Idle_Ready_Motion.npy",
        checkpoint="ase/data/models/ase_hlc_strike_reallusion_sword_shield.pth",
        llc_checkpoint="ase/data/models/ase_llc_reallusion_sword_shield.pth",
    ),
]


def parse_case_filter(text: str):
    if not text.strip():
        return [c.key for c in CASES]
    return [x.strip() for x in text.split(",") if x.strip()]


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def classify_log(text: str):
    fatal_tokens = [
        "traceback (most recent call last)",
        "runtimeerror:",
        "segmentation fault",
        "illegal memory access",
        "core dumped",
        "module not found",
        "assertionerror",
        "failed to create a physx cuda context manager",
        "must enable gpu pipeline",
        "invalid resource handle",
        "cuda error:",
    ]
    low = text.lower()
    for token in fatal_tokens:
        if token in low:
            return token
    return ""


def build_cmd(case: RefCase, args):
    cmd = [
        args.python_bin,
        "ase/run.py",
        "--test",
        "--headless",
        "--sim_device",
        args.sim_device,
        "--rl_device",
        args.rl_device,
        "--pipeline",
        "gpu",
        "--num_envs",
        str(args.num_envs),
        "--task",
        case.task,
        "--cfg_env",
        case.cfg_env,
        "--cfg_train",
        case.cfg_train,
        "--motion_file",
        case.motion_file,
        "--checkpoint",
        case.checkpoint,
    ]
    if case.llc_checkpoint:
        cmd.extend(["--llc_checkpoint", case.llc_checkpoint])
    return cmd


def kill_proc_group(proc: subprocess.Popen, sig):
    try:
        os.killpg(os.getpgid(proc.pid), sig)
    except Exception:
        pass


def run_case(case: RefCase, args, root_out: Path):
    log_path = root_out / f"{case.key}.log"
    cmd = build_cmd(case, args)
    env = os.environ.copy()
    env["PATH"] = f"{args.env_bin}:{env.get('PATH', '')}"
    env["LD_LIBRARY_PATH"] = f"/usr/lib/wsl/lib:{args.env_lib}:{env.get('LD_LIBRARY_PATH', '')}"
    env["PYTHONPATH"] = f"{args.isaacgym_python}:{env.get('PYTHONPATH', '')}"
    env["PYTHONUNBUFFERED"] = "1"
    env["MESA_GL_VERSION_OVERRIDE"] = "3.3"
    env["MESA_GLSL_VERSION_OVERRIDE"] = "330"

    ensure_dir(log_path.parent)
    with log_path.open("w") as f:
        f.write("[CMD] " + shlex.join(cmd) + "\n")

    with log_path.open("a") as f:
        proc = subprocess.Popen(
            cmd,
            cwd=str(UPSTREAM_ROOT),
            env=env,
            stdout=f,
            stderr=subprocess.STDOUT,
            preexec_fn=os.setsid,
        )

    start = time.time()
    timed_out = False
    try:
        proc.wait(timeout=args.timeout_sec)
    except subprocess.TimeoutExpired:
        timed_out = True
        kill_proc_group(proc, signal.SIGTERM)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            kill_proc_group(proc, signal.SIGKILL)
            try:
                proc.wait(timeout=5)
            except Exception:
                pass

    elapsed = time.time() - start
    text = log_path.read_text(errors="ignore")
    fatal = classify_log(text)
    rc = proc.returncode if proc.returncode is not None else 124

    if timed_out and not fatal:
        status = "smoke_ok_timeout"
    elif rc == 0 and not fatal:
        status = "smoke_ok_exit0"
    else:
        status = "failed"

    result = {
        "case": case.key,
        "task": case.task,
        "status": status,
        "rc": rc,
        "timed_out": timed_out,
        "elapsed_sec": elapsed,
        "fatal_token": fatal,
        "log_file": str(log_path),
        "cmd": cmd,
    }
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default="getup,heading,location,reach,strike")
    ap.add_argument("--timeout-sec", type=int, default=90)
    ap.add_argument("--num-envs", type=int, default=1)
    ap.add_argument("--sim-device", default="cuda:0")
    ap.add_argument("--rl-device", default="cuda:0")
    ap.add_argument("--python-bin", default=DEFAULT_PYTHON)
    ap.add_argument("--env-bin", default=DEFAULT_ENV_BIN)
    ap.add_argument("--env-lib", default=DEFAULT_ENV_LIB)
    ap.add_argument("--isaacgym-python", default=DEFAULT_ISAACGYM_ROOT)
    ap.add_argument("--root-out", default="")
    args = ap.parse_args()

    selected = parse_case_filter(args.cases)
    case_map = {c.key: c for c in CASES}
    cases = []
    for key in selected:
        if key not in case_map:
            raise SystemExit(f"Unknown case: {key}")
        cases.append(case_map[key])

    ts = time.strftime("%Y%m%d_%H%M%S")
    root_name = args.root_out or f"ase_upstream_reference_smoke_{ts}"
    root_out = ROOT / "output" / "train" / root_name
    ensure_dir(root_out)

    results = []
    for case in cases:
        print(f"[REF] start case={case.key}", flush=True)
        result = run_case(case, args, root_out)
        print(f"[REF] end case={case.key} status={result['status']} rc={result['rc']} timed_out={int(result['timed_out'])}", flush=True)
        results.append(result)
        (root_out / "results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")

    ok = all(r["status"].startswith("smoke_ok") for r in results)
    summary_path = root_out / "results.tsv"
    with summary_path.open("w") as f:
        f.write("case\ttask\tstatus\trc\ttimed_out\telapsed_sec\tfatal_token\tlog_file\n")
        for r in results:
            f.write(
                f"{r['case']}\t{r['task']}\t{r['status']}\t{r['rc']}\t{int(r['timed_out'])}\t"
                f"{r['elapsed_sec']:.2f}\t{r['fatal_token']}\t{r['log_file']}\n"
            )

    print(f"[REF] root_out={root_out}", flush=True)
    print(f"[REF] summary={summary_path}", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
