#!/usr/bin/env python3
import argparse
import json
import os
import re
import shlex
import signal
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TRAIN_ROOT = ROOT / "output" / "train"
RUN_PY = ROOT / "mimickit" / "run.py"

DEFAULT_PYTHON = os.environ.get("MIMICKIT_TRAIN_PY", "/root/miniconda3/envs/mimickit/bin/python")
OFFICIAL_LLC_TARGET_SAMPLES = 13_107_200_000
OFFICIAL_HLC_TARGET_SAMPLES = 1_310_720_000

NCCL_ENV = {
    "NCCL_P2P_DISABLE": "1",
    "NCCL_IB_DISABLE": "1",
    "NCCL_CUMEM_ENABLE": "0",
    "TORCH_NCCL_ASYNC_ERROR_HANDLING": "1",
    "TORCH_NCCL_BLOCKING_WAIT": "1",
}


@dataclass(frozen=True)
class CaseSpec:
    key: str
    arg_file: str
    out_name: str
    llc_dep: str = ""


CASE_SPECS = [
    CaseSpec("ase_humanoid", "args/ase_humanoid_args.txt", "ase_humanoid_l2"),
    CaseSpec("ase_humanoid_sword_shield", "args/ase_humanoid_sword_shield_args.txt", "ase_humanoid_sword_shield_l2"),
    CaseSpec("ase_getup_humanoid_sword_shield", "args/ase_getup_humanoid_sword_shield_args.txt", "ase_getup_humanoid_sword_shield_l2"),
    CaseSpec(
        "ase_heading_humanoid_sword_shield",
        "args/ase_heading_humanoid_sword_shield_args.txt",
        "ase_heading_humanoid_sword_shield_l2",
        llc_dep="ase_humanoid_sword_shield",
    ),
    CaseSpec(
        "ase_location_humanoid_sword_shield",
        "args/ase_location_humanoid_sword_shield_args.txt",
        "ase_location_humanoid_sword_shield_l2",
        llc_dep="ase_humanoid_sword_shield",
    ),
    CaseSpec(
        "ase_reach_humanoid_sword_shield",
        "args/ase_reach_humanoid_sword_shield_args.txt",
        "ase_reach_humanoid_sword_shield_l2",
        llc_dep="ase_humanoid_sword_shield",
    ),
    CaseSpec(
        "ase_strike_humanoid_sword_shield",
        "args/ase_strike_humanoid_sword_shield_args.txt",
        "ase_strike_humanoid_sword_shield_l2",
        llc_dep="ase_humanoid_sword_shield",
    ),
]


@dataclass(frozen=True)
class Strategy:
    name: str
    devices: str
    num_envs: int


def read_text(path: Path):
    try:
        return path.read_text(errors="ignore")
    except Exception:
        return ""


def split_columns(line: str):
    return re.split(r"\s{2,}", line.strip())


def to_number(text: str):
    try:
        if re.fullmatch(r"[+-]?\d+", text):
            return int(text)
        return float(text)
    except Exception:
        return text


def parse_training_rows(log_path: Path):
    raw = read_text(log_path)
    if not raw:
        return []

    lines = [x.strip() for x in raw.replace("\r", "\n").split("\n") if x.strip()]
    header = None
    rows = []
    for line in lines:
        if header is None and "Iteration" in line and "Samples" in line:
            header = split_columns(line)
            continue
        if header is None:
            continue
        parts = split_columns(line)
        if len(parts) != len(header):
            continue
        if not re.fullmatch(r"\d+", parts[0]):
            continue
        rows.append({k: to_number(v) for k, v in zip(header, parts)})

    dedup = {}
    for row in rows:
        dedup[int(row["Iteration"])] = row
    return [dedup[k] for k in sorted(dedup)]


def latest_training_row(log_path: Path):
    rows = parse_training_rows(log_path)
    return rows[-1] if rows else {}


def parse_csv_list(text: str):
    return [x.strip() for x in text.split(",") if x.strip()]


def classify_log_text(text: str):
    t = text.lower()
    if "processgroupnccl" in t or "distbackenderror" in t or "nccl" in t:
        return "nccl"
    if "out of memory" in t or "failed to allocate" in t or "cuda failure 2 'out of memory'" in t:
        return "oom"
    if "keyboardinterrupt" in t:
        return "interrupt"
    if "assertionerror" in t:
        return "assert"
    if "traceback" in t or "exception" in t or "error" in t:
        return "runtime"
    return ""


def resolve_root(root_out: str):
    p = Path(root_out)
    if p.is_absolute():
        return p
    return TRAIN_ROOT / root_out


def signal_from_name(name: str):
    sig = getattr(signal, name, None)
    if sig is None:
        raise ValueError(f"Unsupported signal: {name}")
    return sig


def case_segments(root_out: Path, spec: CaseSpec):
    segs = []
    base = root_out / spec.out_name
    if base.exists() and base.is_dir():
        segs.append(base)

    pat = re.compile(rf"^{re.escape(spec.out_name)}_resume(\d+)$")
    resumes = []
    for p in root_out.glob(f"{spec.out_name}_resume*"):
        if not p.is_dir():
            continue
        m = pat.match(p.name)
        if not m:
            continue
        resumes.append((int(m.group(1)), p))
    resumes.sort(key=lambda x: x[0])
    segs.extend([p for _, p in resumes])
    return segs


def summarize_case(root_out: Path, spec: CaseSpec):
    segments = case_segments(root_out, spec)
    total_samples = 0
    total_wall_h = 0.0
    latest_model = ""
    latest_segment = ""
    latest_row = {}
    segment_rows = []

    for seg in segments:
        row = latest_training_row(seg / "log.txt")
        samples = int(row.get("Samples", 0) or 0)
        wall_h = float(row.get("Wall_Time", 0) or 0.0)
        total_samples += samples
        total_wall_h += wall_h
        model_file = seg / "model.pt"
        if model_file.exists():
            latest_model = str(model_file)
            latest_segment = seg.name
        if row:
            latest_row = row
        segment_rows.append(
            {
                "name": seg.name,
                "path": str(seg),
                "samples": samples,
                "wall_time_h": wall_h,
                "has_model": model_file.exists(),
            }
        )

    return {
        "segments": segment_rows,
        "segment_count": len(segment_rows),
        "total_samples": total_samples,
        "total_wall_time_h": total_wall_h,
        "latest_model": latest_model,
        "latest_segment": latest_segment,
        "latest_row": latest_row,
    }


def next_resume_dir(root_out: Path, spec: CaseSpec):
    segs = case_segments(root_out, spec)
    if not segs:
        return root_out / spec.out_name

    next_idx = 1
    pat = re.compile(rf"^{re.escape(spec.out_name)}_resume(\d+)$")
    for seg in segs[1:]:
        m = pat.match(seg.name)
        if not m:
            continue
        next_idx = max(next_idx, int(m.group(1)) + 1)
    return root_out / f"{spec.out_name}_resume{next_idx:02d}"


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def latest_case_error(session_log: Path):
    text = read_text(session_log)
    if not text:
        return ""
    return classify_log_text(text[-40000:])


def build_strategies(args):
    fallback_devices = args.devices_train if args.strict_dual_gpu else args.fallback_devices
    strategies = [Strategy(f"dual_{args.primary_num_envs}", args.devices_train, args.primary_num_envs)]
    seen = {(args.devices_train, args.primary_num_envs)}
    for idx, num_envs in enumerate(parse_csv_list(args.fallback_num_envs), start=1):
        try:
            n = int(num_envs)
        except Exception:
            continue
        if n <= 0:
            continue
        item = (fallback_devices, n)
        if item in seen:
            continue
        seen.add(item)
        strategies.append(Strategy(f"fallback_{idx}_{n}", fallback_devices, n))
    return strategies


def load_keepalive_state(path: Path):
    if not path.exists():
        return {"current_case": "", "cases": {}, "events": []}
    try:
        data = json.loads(path.read_text())
    except Exception:
        return {"current_case": "", "cases": {}, "events": []}
    if not isinstance(data, dict):
        return {"current_case": "", "cases": {}, "events": []}
    data.setdefault("current_case", "")
    data.setdefault("cases", {})
    data.setdefault("events", [])
    return data


def save_keepalive_state(path: Path, state):
    ensure_dir(path.parent)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n")


def append_event(state, message: str):
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    state.setdefault("events", []).append(f"{stamp} | {message}")
    state["events"] = state["events"][-200:]


def case_meta(state, spec: CaseSpec):
    cases = state.setdefault("cases", {})
    meta = cases.setdefault(spec.key, {"attempts": [], "status": "pending", "next_strategy_index": 0})
    meta.setdefault("attempts", [])
    meta.setdefault("status", "pending")
    meta.setdefault("next_strategy_index", 0)
    return meta


def infer_initial_strategy(meta: dict, session_log: Path):
    try:
        stored_idx = int(meta.get("next_strategy_index", 0))
    except Exception:
        stored_idx = 0

    # Respect the persisted fallback choice when a case was already in-flight
    # and the supervisor was interrupted before it could append a completed
    # attempt row.
    if meta.get("status") in {"running", "resuming"}:
        return stored_idx

    if meta.get("attempts"):
        return stored_idx

    err = latest_case_error(session_log)
    if err == "nccl":
        return 1
    return 0


def write_resume_context(out_dir: Path, previous_segment: str, previous_model: str, previous_samples: int, previous_wall_h: float, strategy: Strategy):
    rows = [
        ("key", "value"),
        ("source_run", previous_segment),
        ("source_model_file", previous_model),
        ("source_last_samples", str(previous_samples)),
        ("source_last_wall_time_h", f"{previous_wall_h:.6f}"),
        ("resume_strategy", strategy.name),
        ("resume_devices", strategy.devices),
        ("resume_num_envs", str(strategy.num_envs)),
    ]
    ensure_dir(out_dir)
    with (out_dir / "resume_context.tsv").open("w") as f:
        for key, value in rows:
            f.write(f"{key}\t{value}\n")


def run_attempt(cmd, attempt_log: Path, session_log: Path, timeout_sec: int, stop_sig, grace_sec: int, env: dict):
    ensure_dir(attempt_log.parent)
    ensure_dir(session_log.parent)

    pipeline = (
        "set -o pipefail; "
        + shlex.join(cmd)
        + " 2>&1"
        + f" | tee {shlex.quote(str(attempt_log))}"
        + f" | tee -a {shlex.quote(str(session_log))}"
    )

    proc = subprocess.Popen(
        ["bash", "-lc", pipeline],
        cwd=str(ROOT),
        env=env,
        preexec_fn=os.setsid,
    )

    timed_out = False
    stop_reason = "exit"
    try:
        if timeout_sec > 0:
            proc.wait(timeout=timeout_sec)
        else:
            proc.wait()
    except subprocess.TimeoutExpired:
        timed_out = True
        stop_reason = f"budget_reached_{signal.Signals(stop_sig).name}"
        try:
            os.killpg(os.getpgid(proc.pid), stop_sig)
        except Exception:
            stop_reason = f"budget_signal_failed_{signal.Signals(stop_sig).name}"
        try:
            proc.wait(timeout=max(1, int(grace_sec)))
        except subprocess.TimeoutExpired:
            stop_reason = "budget_grace_term"
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except Exception:
                pass
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                stop_reason = "budget_force_kill"
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except Exception:
                    pass
                try:
                    proc.wait(timeout=5)
                except Exception:
                    pass

    rc = proc.returncode if proc.returncode is not None else 124
    if timed_out and rc == 0:
        rc = 124
    return rc, timed_out, stop_reason


def write_status_summary(root_out: Path, state, specs, args):
    rows = {
        "current_case": state.get("current_case", ""),
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "root_out": str(root_out),
        "target_samples": args.target_samples,
        "llc_target_samples": effective_llc_target_samples(args),
        "hlc_target_samples": effective_hlc_target_samples(args),
        "case_budget_hours": args.case_budget_hours,
        "cases": {},
    }
    for spec in specs:
        summary = summarize_case(root_out, spec)
        meta = case_meta(state, spec)
        rows["cases"][spec.key] = {
            "status": meta.get("status", "pending"),
            "next_strategy_index": meta.get("next_strategy_index", 0),
            "target_samples": target_samples_for_spec(spec, args),
            "latest_model": summary["latest_model"],
            "total_samples": summary["total_samples"],
            "total_wall_time_h": summary["total_wall_time_h"],
            "segments": summary["segments"],
            "attempt_count": len(meta.get("attempts", [])),
        }
    (root_out / "keepalive_status.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n")


def should_mark_complete(summary, spec: CaseSpec, args):
    if summary["total_samples"] >= target_samples_for_spec(spec, args):
        return "completed_target"
    budget_hours = case_budget_hours_for_spec(spec, args)
    if budget_hours is not None and summary["total_wall_time_h"] >= budget_hours and summary["latest_model"]:
        return "completed_budget"
    return ""


def latest_model_for_case(root_out: Path, spec: CaseSpec):
    return summarize_case(root_out, spec)["latest_model"]


def spec_by_key(key: str):
    for spec in CASE_SPECS:
        if spec.key == key:
            return spec
    raise KeyError(key)


def effective_llc_target_samples(args):
    return int(args.llc_target_samples if args.llc_target_samples > 0 else args.target_samples)


def effective_hlc_target_samples(args):
    return int(args.hlc_target_samples if args.hlc_target_samples > 0 else args.target_samples)


def target_samples_for_spec(spec: CaseSpec, args):
    return effective_hlc_target_samples(args) if spec.llc_dep else effective_llc_target_samples(args)


def case_budget_hours_for_spec(spec: CaseSpec, args):
    if args.case_budget_hours <= 0:
        return None
    return float(args.case_budget_hours)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root-out", required=True, help="Relative name under output/train or absolute path.")
    ap.add_argument("--engine-config", default="data/engines/newton_engine.yaml")
    ap.add_argument("--python-bin", default=DEFAULT_PYTHON)
    ap.add_argument("--devices-train", default="cuda:0,cuda:1")
    ap.add_argument("--fallback-devices", default="cuda:0")
    ap.add_argument("--strict-dual-gpu", action="store_true")
    ap.add_argument("--primary-num-envs", type=int, default=4096)
    ap.add_argument("--fallback-num-envs", default="2048,1024,512")
    ap.add_argument("--mode", default="train")
    ap.add_argument("--target-samples", type=int, default=1_000_000_000)
    ap.add_argument(
        "--llc-target-samples",
        type=int,
        default=0,
        help=f"If >0, overrides --target-samples for LLC cases. Upstream ASE scale is {OFFICIAL_LLC_TARGET_SAMPLES}.",
    )
    ap.add_argument(
        "--hlc-target-samples",
        type=int,
        default=0,
        help=f"If >0, overrides --target-samples for HLC cases. Upstream ASE scale is {OFFICIAL_HLC_TARGET_SAMPLES}.",
    )
    ap.add_argument("--case-budget-hours", type=float, default=8.0)
    ap.add_argument("--budget-signal", choices=["SIGINT", "SIGTERM"], default="SIGINT")
    ap.add_argument("--budget-grace-sec", type=int, default=300)
    ap.add_argument("--retry-sleep-sec", type=int, default=30)
    ap.add_argument("--max-attempts-per-case", type=int, default=12)
    ap.add_argument("--session-log-dir", default="session_logs")
    args = ap.parse_args()

    if args.mode != "train":
        print("[ERROR] keepalive supervisor only supports train mode")
        return 2
    if args.strict_dual_gpu and len(parse_csv_list(args.devices_train)) < 2:
        print("[ERROR] --strict-dual-gpu requires at least 2 devices in --devices-train")
        return 2

    if not RUN_PY.exists():
        print(f"[ERROR] run.py not found: {RUN_PY}")
        return 2

    root_out = resolve_root(args.root_out)
    ensure_dir(root_out)
    ensure_dir(root_out / args.session_log_dir)

    state_file = root_out / "keepalive_state.json"
    state = load_keepalive_state(state_file)
    strategies = build_strategies(args)
    stop_sig = signal_from_name(args.budget_signal)

    append_event(state, f"supervisor_start root={root_out}")
    save_keepalive_state(state_file, state)

    for spec in CASE_SPECS:
        meta = case_meta(state, spec)
        session_log = root_out / args.session_log_dir / f"{spec.key}.log"
        state["current_case"] = spec.key
        (root_out / "current_case.txt").write_text(spec.key + "\n")

        summary = summarize_case(root_out, spec)
        complete_status = should_mark_complete(summary, spec, args)
        if complete_status:
            meta["status"] = complete_status
            append_event(state, f"{spec.key}: skip existing {complete_status} samples={summary['total_samples']} wall_h={summary['total_wall_time_h']:.2f}")
            save_keepalive_state(state_file, state)
            write_status_summary(root_out, state, CASE_SPECS, args)
            continue

        strategy_idx = infer_initial_strategy(meta, session_log)
        if strategy_idx >= len(strategies):
            strategy_idx = len(strategies) - 1

        attempts_used = 0
        while True:
            summary = summarize_case(root_out, spec)
            target_samples = target_samples_for_spec(spec, args)
            budget_hours = case_budget_hours_for_spec(spec, args)
            complete_status = should_mark_complete(summary, spec, args)
            if complete_status:
                meta["status"] = complete_status
                meta["next_strategy_index"] = strategy_idx
                append_event(
                    state,
                    f"{spec.key}: {complete_status} samples={summary['total_samples']} wall_h={summary['total_wall_time_h']:.2f}",
                )
                save_keepalive_state(state_file, state)
                write_status_summary(root_out, state, CASE_SPECS, args)
                break

            if attempts_used >= args.max_attempts_per_case:
                meta["status"] = "failed_max_attempts"
                append_event(state, f"{spec.key}: failed_max_attempts after {attempts_used} retries")
                save_keepalive_state(state_file, state)
                write_status_summary(root_out, state, CASE_SPECS, args)
                print(f"[ERROR] {spec.key} exceeded max attempts", flush=True)
                return 1

            strategy = strategies[strategy_idx]
            remaining_samples = max(1, target_samples - summary["total_samples"])
            if budget_hours is None:
                remaining_budget_h = None
                timeout_sec = 0
            else:
                remaining_budget_h = max(0.0, budget_hours - summary["total_wall_time_h"])
                timeout_sec = int(round(remaining_budget_h * 3600.0))
                if timeout_sec <= 0 and summary["latest_model"]:
                    meta["status"] = "completed_budget"
                    append_event(state, f"{spec.key}: budget exhausted, keeping latest model")
                    save_keepalive_state(state_file, state)
                    write_status_summary(root_out, state, CASE_SPECS, args)
                    break
                if timeout_sec <= 0:
                    timeout_sec = 300
            budget_text = "disabled" if remaining_budget_h is None else f"{remaining_budget_h:.2f}"

            out_dir = next_resume_dir(root_out, spec)
            source_model = summary["latest_model"]
            previous_segment = summary["latest_segment"]

            llc_model = ""
            if spec.llc_dep:
                dep_spec = spec_by_key(spec.llc_dep)
                llc_model = latest_model_for_case(root_out, dep_spec)
                if not llc_model:
                    meta["status"] = "blocked_missing_llc"
                    append_event(state, f"{spec.key}: blocked missing llc for {spec.llc_dep}")
                    save_keepalive_state(state_file, state)
                    write_status_summary(root_out, state, CASE_SPECS, args)
                    print(f"[ERROR] missing llc checkpoint for {spec.key}: {spec.llc_dep}", flush=True)
                    return 1

            cmd = [
                args.python_bin,
                str(RUN_PY),
                "--arg_file",
                spec.arg_file,
                "--engine_config",
                args.engine_config,
                "--mode",
                "train",
                "--visualize",
                "false",
                "--devices",
                *parse_csv_list(strategy.devices),
                "--num_envs",
                str(strategy.num_envs),
                "--max_samples",
                str(remaining_samples),
                "--out_dir",
                str(out_dir),
            ]
            if source_model:
                cmd.extend(["--model_file", source_model])
            if llc_model:
                cmd.extend(["--llc_model_file", llc_model])

            attempt_idx = len(meta.get("attempts", [])) + 1
            attempt_log = root_out / args.session_log_dir / f"{spec.key}.attempt{attempt_idx:02d}.log"
            write_resume_context(
                out_dir=out_dir,
                previous_segment=previous_segment,
                previous_model=source_model,
                previous_samples=summary["total_samples"],
                previous_wall_h=summary["total_wall_time_h"],
                strategy=strategy,
            )

            ensure_dir(session_log.parent)
            with session_log.open("a") as f:
                f.write(
                    f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] KEEPALIVE START "
                    f"case={spec.key} attempt={attempt_idx} strategy={strategy.name} "
                    f"devices={strategy.devices} num_envs={strategy.num_envs} "
                    f"target_samples={target_samples} remaining_samples={remaining_samples} remaining_budget_h={budget_text} "
                    f"out_dir={out_dir.name}\n"
                )

            env = os.environ.copy()
            env.update(NCCL_ENV)

            append_event(
                state,
                f"{spec.key}: attempt={attempt_idx} strategy={strategy.name} out={out_dir.name} target_samples={target_samples} remain_samples={remaining_samples} remain_budget_h={budget_text}",
            )
            meta["status"] = "running"
            meta["next_strategy_index"] = strategy_idx
            save_keepalive_state(state_file, state)
            write_status_summary(root_out, state, CASE_SPECS, args)

            print(
                f"[KEEPALIVE] case={spec.key} attempt={attempt_idx} strategy={strategy.name} "
                f"devices={strategy.devices} num_envs={strategy.num_envs} "
                f"target_samples={target_samples} remaining_samples={remaining_samples} remaining_budget_h={budget_text} "
                f"out_dir={out_dir.name}",
                flush=True,
            )

            start_ts = time.time()
            rc, timed_out, stop_reason = run_attempt(
                cmd=cmd,
                attempt_log=attempt_log,
                session_log=session_log,
                timeout_sec=timeout_sec,
                stop_sig=stop_sig,
                grace_sec=args.budget_grace_sec,
                env=env,
            )
            elapsed_sec = time.time() - start_ts
            attempts_used += 1

            new_summary = summarize_case(root_out, spec)
            log_text = read_text(attempt_log)
            error_kind = classify_log_text(log_text)
            complete_status = should_mark_complete(new_summary, spec, args)

            attempt_row = {
                "attempt": attempt_idx,
                "strategy": asdict(strategy),
                "out_dir": out_dir.name,
                "source_model": source_model,
                "llc_model_file": llc_model,
                "target_samples": target_samples,
                "remaining_samples": remaining_samples,
                "remaining_budget_h": remaining_budget_h,
                "rc": rc,
                "timed_out": timed_out,
                "stop_reason": stop_reason,
                "error_kind": error_kind,
                "elapsed_sec": elapsed_sec,
                "samples_before": summary["total_samples"],
                "samples_after": new_summary["total_samples"],
                "wall_h_before": summary["total_wall_time_h"],
                "wall_h_after": new_summary["total_wall_time_h"],
                "latest_model": new_summary["latest_model"],
            }
            meta.setdefault("attempts", []).append(attempt_row)

            with session_log.open("a") as f:
                f.write(
                    f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] KEEPALIVE END "
                    f"case={spec.key} attempt={attempt_idx} rc={rc} timed_out={int(timed_out)} "
                    f"stop_reason={stop_reason} error={error_kind or '-'} "
                    f"samples_after={new_summary['total_samples']} wall_h_after={new_summary['total_wall_time_h']:.3f}\n"
                )

            if complete_status:
                meta["status"] = complete_status
                meta["next_strategy_index"] = strategy_idx
                append_event(state, f"{spec.key}: {complete_status} after attempt={attempt_idx}")
                save_keepalive_state(state_file, state)
                write_status_summary(root_out, state, CASE_SPECS, args)
                break

            if error_kind in {"nccl", "oom"} and strategy_idx < (len(strategies) - 1):
                strategy_idx += 1
            meta["next_strategy_index"] = strategy_idx
            meta["status"] = "resuming"

            append_event(
                state,
                f"{spec.key}: resume attempt={attempt_idx} rc={rc} error={error_kind or '-'} total_samples={new_summary['total_samples']}",
            )
            save_keepalive_state(state_file, state)
            write_status_summary(root_out, state, CASE_SPECS, args)

            print(
                f"[KEEPALIVE] resume pending case={spec.key} rc={rc} error={error_kind or '-'} "
                f"next_strategy={strategies[strategy_idx].name} sleep={args.retry_sleep_sec}s",
                flush=True,
            )
            time.sleep(max(0, args.retry_sleep_sec))

    state["current_case"] = "COMPLETE"
    (root_out / "current_case.txt").write_text("COMPLETE\n")
    append_event(state, "supervisor_complete")
    save_keepalive_state(state_file, state)
    write_status_summary(root_out, state, CASE_SPECS, args)
    print("[KEEPALIVE] all ASE 7 cases completed or budget-closed", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
