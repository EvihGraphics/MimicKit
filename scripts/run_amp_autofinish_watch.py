#!/usr/bin/env python3
"""Watch an AMP keepalive root and auto-run post-train inference/render steps."""

from __future__ import annotations

import argparse
import csv
import json
import os
import shlex
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import urlopen

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from run_amp_keepalive import ROOT, TRAIN_ROOT, read_text  # noqa: E402


DEFAULT_ROOT_OUT = "amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637"
WATCH_STAGE_ORDER = [
    "watching",
    "triggered",
    "build_best_by_case",
    "post_train_test",
    "post_train_visualize",
    "post_train_render",
    "completed",
    "failed",
]
VIEWER_ERROR_HINTS = (
    "display is not set",
    "xvfb-run was not found",
    "shaderexception",
    "glsl",
    "viewer not available",
    "pyglet",
)
RENDER_OK_STATUSES = {"ok", "skipped_resume"}


def now_str() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def resolve_root(root_out: str) -> Path:
    raw = Path(root_out)
    if raw.is_absolute():
        return raw.resolve()
    return (TRAIN_ROOT / root_out).resolve()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_json(path: Path, data: dict[str, Any]):
    ensure_dir(path.parent)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def append_watch_log(path: Path, text: str):
    ensure_dir(path.parent)
    with path.open("ab") as handle:
        handle.write(f"[{now_str()}] {text}\n".encode("utf-8"))


def read_tsv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as fp:
        return list(csv.DictReader(fp, delimiter="\t"))


def shell_join(cmd: list[str]) -> str:
    return shlex.join(cmd)


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root-out", default=DEFAULT_ROOT_OUT, help="AMP keepalive root name under output/train or absolute path")
    ap.add_argument("--python-bin", default="/root/miniconda3/envs/mimickit/bin/python")
    ap.add_argument("--dashboard-api", default="http://127.0.0.1:8789/api/status")
    ap.add_argument("--dashboard-page", default="http://127.0.0.1:8789/")
    ap.add_argument("--poll-sec", type=int, default=30)
    ap.add_argument("--test-timeout-sec", type=int, default=900)
    ap.add_argument("--visualize-timeout-sec", type=int, default=900)
    ap.add_argument("--render-timeout-sec", type=int, default=3600)
    ap.add_argument("--test-episodes", type=int, default=10)
    ap.add_argument("--visualize-episodes", type=int, default=1)
    ap.add_argument("--render-frames", type=int, default=300)
    ap.add_argument("--render-frame-stride", type=int, default=5)
    ap.add_argument("--render-device", default="cuda:0")
    ap.add_argument("--render-num-envs", type=int, default=1)
    return ap.parse_args()


def default_stage_payload() -> dict[str, Any]:
    return {
        "status": "pending",
        "started_at": "",
        "completed_at": "",
        "command": "",
        "log_file": "",
        "rc": None,
        "notes": "",
        "attempt_count": 0,
    }


def init_state(root_path: Path, args) -> dict[str, Any]:
    stages = {name: default_stage_payload() for name in WATCH_STAGE_ORDER}
    return {
        "root_name": root_path.name,
        "root_path": str(root_path),
        "status": "watching",
        "current_stage": "watching",
        "started_at": now_str(),
        "updated_at": now_str(),
        "dashboard_api": args.dashboard_api,
        "dashboard_page": f"{args.dashboard_page.rstrip('/')}/?root={quote(root_path.name)}",
        "summary_file": str(root_path / "post_train_summary.md"),
        "stages": stages,
        "artifacts": {
            "best_by_case": str(root_path / "best_by_case.tsv"),
            "summary_md": str(root_path / "post_train_summary.md"),
            "render_root": str(ROOT / "output" / "img" / root_path.name),
            "render_index": str(ROOT / "output" / "img" / root_path.name / "infer_viz_index.tsv"),
        },
        "last_live": {},
        "warnings": [],
    }


def stage_meta(state: dict[str, Any], name: str) -> dict[str, Any]:
    stages = state.setdefault("stages", {})
    if name not in stages:
        stages[name] = default_stage_payload()
    return stages[name]


def mark_stage_running(state: dict[str, Any], name: str, command: str = "", log_file: str = "", notes: str = ""):
    meta = stage_meta(state, name)
    meta["status"] = "running"
    meta["started_at"] = meta.get("started_at") or now_str()
    meta["command"] = command
    meta["log_file"] = log_file
    meta["notes"] = notes
    meta["attempt_count"] = int(meta.get("attempt_count", 0)) + 1
    state["status"] = "running"
    state["current_stage"] = name
    state["updated_at"] = now_str()


def mark_stage_completed(state: dict[str, Any], name: str, notes: str = "", rc: int | None = 0):
    meta = stage_meta(state, name)
    meta["status"] = "completed"
    meta["completed_at"] = now_str()
    meta["rc"] = rc
    if notes:
        meta["notes"] = notes
    state["updated_at"] = now_str()


def mark_stage_failed(state: dict[str, Any], name: str, notes: str = "", rc: int | None = 1):
    meta = stage_meta(state, name)
    meta["status"] = "failed"
    meta["completed_at"] = now_str()
    meta["rc"] = rc
    if notes:
        meta["notes"] = notes
    stage_meta(state, "failed")["status"] = "completed"
    stage_meta(state, "failed")["started_at"] = stage_meta(state, "failed").get("started_at") or now_str()
    stage_meta(state, "failed")["completed_at"] = now_str()
    stage_meta(state, "failed")["notes"] = f"{name}: {notes}".strip()
    state["status"] = "failed"
    state["current_stage"] = "failed"
    state["updated_at"] = now_str()


def finalize_completed(state: dict[str, Any]):
    stage_meta(state, "completed")["status"] = "completed"
    stage_meta(state, "completed")["started_at"] = stage_meta(state, "completed").get("started_at") or now_str()
    stage_meta(state, "completed")["completed_at"] = now_str()
    stage_meta(state, "completed")["notes"] = "all auto-finish stages completed"
    state["status"] = "completed"
    state["current_stage"] = "completed"
    state["updated_at"] = now_str()


def acquire_lock(lock_path: Path) -> dict[str, Any]:
    payload = {"pid": os.getpid(), "host": socket.gethostname(), "started_at": now_str()}
    if lock_path.exists():
        old = read_json(lock_path)
        old_pid = int(old.get("pid") or 0)
        if old_pid > 0:
            try:
                os.kill(old_pid, 0)
            except OSError:
                pass
            else:
                raise SystemExit(f"[ERROR] watcher already running pid={old_pid} lock={lock_path}")
    write_json(lock_path, payload)
    return payload


def release_lock(lock_path: Path):
    try:
        if lock_path.exists():
            lock_path.unlink()
    except Exception:
        pass


def fetch_dashboard_status(api_url: str, root_name: str) -> dict[str, Any]:
    sep = "&" if "?" in api_url else "?"
    url = f"{api_url}{sep}root={quote(root_name)}"
    try:
        with urlopen(url, timeout=5) as resp:
            if int(resp.status) != 200:
                return {}
            return json.loads(resp.read().decode("utf-8"))
    except (URLError, TimeoutError, json.JSONDecodeError, OSError, ValueError):
        return {}


def runner_log_status(root_path: Path) -> dict[str, Any]:
    text = read_text(root_path / "runner.log")
    done = "all AMP single-brain stages completed" in text or "supervisor_complete" in text
    return {
        "source": "runner_log",
        "complete": done,
        "notes": "runner log fallback",
    }


def collect_live_status(root_path: Path, args) -> dict[str, Any]:
    keepalive = read_json(root_path / "keepalive_status.json")
    if keepalive:
        keepalive["source"] = "keepalive_status"
        return keepalive
    dashboard = fetch_dashboard_status(args.dashboard_api, root_path.name)
    if dashboard:
        dashboard["source"] = "dashboard_api"
        return dashboard
    return runner_log_status(root_path)


def live_long_completed(live: dict[str, Any]) -> bool:
    if not live:
        return False
    if live.get("source") == "runner_log":
        return bool(live.get("complete"))
    stages = live.get("stages") or {}
    long_meta = stages.get("long_train") or {}
    long_status = str(long_meta.get("status", "")).strip().lower()
    if long_status == "completed":
        return True
    current_stage = str(live.get("current_stage", "")).strip().lower()
    current_stage_status = str(live.get("current_stage_status", "")).strip().lower()
    overall_long = int(live.get("overall_long_samples") or 0)
    long_target = int(live.get("long_target_samples") or 0)
    if current_stage == "complete" and long_target > 0 and overall_long >= long_target:
        return True
    if current_stage == "long_train" and current_stage_status == "completed":
        return True
    return False


def extract_paths(root_path: Path, live: dict[str, Any]) -> dict[str, str]:
    stages = live.get("stages") or {}
    long_meta = stages.get("long_train") or {}
    arg_file = str(live.get("arg_file", "")).strip()
    engine_cfg = str(live.get("engine_config", "")).strip()
    model_file = str(long_meta.get("latest_model", "")).strip()
    if not model_file:
        model_file = str(root_path / "long_train" / "model.pt")
    current_env = str(live.get("current_env_config", "")).strip() or str(root_path / "long_train" / "env_config.yaml")
    current_agent = str(live.get("current_agent_config", "")).strip() or str(root_path / "long_train" / "agent_config.yaml")
    current_engine = str(live.get("current_engine_config", "")).strip() or str(root_path / "long_train" / "engine_config.yaml")
    return {
        "arg_file": arg_file,
        "engine_config": engine_cfg,
        "model_file": model_file,
        "env_config": current_env,
        "agent_config": current_agent,
        "engine_config_snapshot": current_engine,
    }


def case_name_from_arg(arg_file: str) -> str:
    name = Path(arg_file).name
    return name[:-4] if name.endswith(".txt") else name


def stage_log_path(root_path: Path, stage_name: str, attempt: int) -> Path:
    return root_path / "session_logs" / f"autofinish_{stage_name}.attempt{attempt:02d}.log"


def run_process(cmd: list[str], cwd: Path, env: dict[str, str], log_path: Path, timeout_sec: int) -> tuple[int, bool]:
    ensure_dir(log_path.parent)
    with log_path.open("ab") as handle:
        proc = subprocess.Popen(
            cmd,
            cwd=str(cwd),
            env=env,
            stdout=handle,
            stderr=subprocess.STDOUT,
            preexec_fn=os.setsid,
        )
        start = time.time()
        timed_out = False
        while True:
            rc = proc.poll()
            if rc is not None:
                return int(rc), timed_out
            if timeout_sec > 0 and (time.time() - start) >= timeout_sec:
                timed_out = True
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                except Exception:
                    pass
                try:
                    proc.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                    except Exception:
                        pass
                    proc.wait(timeout=5)
                return int(proc.returncode if proc.returncode is not None else 124), timed_out
            time.sleep(1)


def classify_viewer_failure(text: str) -> bool:
    low = text.lower()
    return any(token in low for token in VIEWER_ERROR_HINTS)


def existing_render_ok(root_path: Path) -> bool:
    infer_index = ROOT / "output" / "img" / root_path.name / "infer_viz_index.tsv"
    rows = read_tsv_rows(infer_index)
    return any(str(row.get("status", "")).strip() in RENDER_OK_STATUSES for row in rows)


def existing_best_by_case_ok(root_path: Path) -> bool:
    best_tsv = root_path / "best_by_case.tsv"
    rows = read_tsv_rows(best_tsv)
    return any(str(row.get("final_ok", "")).strip() == "1" for row in rows)


def build_mp4s_for_root(root_path: Path, log_path: Path) -> list[str]:
    ffmpeg = shutil_which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found in PATH")

    render_root = ROOT / "output" / "img" / root_path.name
    mp4s: list[str] = []
    frame_dirs = sorted(render_root.glob("**/render/frames"))
    with log_path.open("ab") as handle:
        for frames_dir in frame_dirs:
            output_mp4 = frames_dir.parent / "render.mp4"
            cmd = [
                ffmpeg,
                "-framerate",
                "30",
                "-pattern_type",
                "glob",
                "-i",
                str(frames_dir / "frame_*.png"),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-y",
                str(output_mp4),
            ]
            handle.write((f"[mp4] {shell_join(cmd)}\n").encode("utf-8"))
            rc = subprocess.call(cmd, stdout=handle, stderr=subprocess.STDOUT, cwd=str(ROOT))
            if rc != 0:
                raise RuntimeError(f"ffmpeg failed rc={rc} for {frames_dir}")
            if output_mp4.exists():
                mp4s.append(str(output_mp4))
    return mp4s


def shutil_which(cmd: str) -> str:
    return subprocess.check_output(["bash", "-lc", f"command -v {shlex.quote(cmd)} || true"], text=True).strip()


def update_summary(root_path: Path, args, state: dict[str, Any], live: dict[str, Any]):
    paths = extract_paths(root_path, live) if live else {}
    stages = live.get("stages") or {}
    long_meta = stages.get("long_train") or {}
    latest = long_meta.get("latest_row") or {}
    render_root = ROOT / "output" / "img" / root_path.name
    render_meta = sorted(render_root.glob("**/render_meta.json"))
    mp4s = sorted(render_root.glob("**/*.mp4"))
    infer_index = render_root / "infer_viz_index.tsv"
    summary_path = root_path / "post_train_summary.md"

    warnings: list[str] = []
    try:
        agent_acc = float(latest.get("Disc_Agent_Acc"))
        demo_acc = float(latest.get("Disc_Demo_Acc"))
    except Exception:
        agent_acc = -1.0
        demo_acc = -1.0
    if agent_acc < 0 or demo_acc < 0:
        warnings.append("discriminator: warming up")
    elif agent_acc > 0.95 and demo_acc > 0.95:
        warnings.append("discriminator: 判别器失衡")
    elif agent_acc < 0.55 and demo_acc < 0.55:
        warnings.append("discriminator: 判别器塌陷")
    else:
        warnings.append("discriminator: 判别器可用")

    infer_index_ok = any(str(row.get("status", "")).strip() in RENDER_OK_STATUSES for row in read_tsv_rows(infer_index))
    render_ready = infer_index_ok or bool(render_meta) or bool(mp4s)
    warnings.append(f"render: {'render ready' if render_ready else 'render pending'}")

    lines = [
        f"# AMP Auto Finish Summary ({now_str()})",
        "",
        "## Root",
        f"- root: `{root_path.name}`",
        f"- dashboard: `{state.get('dashboard_page', '')}`",
        f"- status: `{state.get('status', '-')}`",
        f"- current_stage: `{state.get('current_stage', '-')}`",
        "",
        "## Final Metrics",
        f"- overall_long_samples: `{live.get('overall_long_samples', 0)}`",
        f"- long_target_samples: `{live.get('long_target_samples', 0)}`",
        f"- Test_Return: `{latest.get('Test_Return', '-')}`",
        f"- Train_Return: `{latest.get('Train_Return', '-')}`",
        f"- Disc_Reward_Mean: `{latest.get('Disc_Reward_Mean', '-')}`",
        f"- Disc_Agent_Acc / Disc_Demo_Acc: `{latest.get('Disc_Agent_Acc', '-')}` / `{latest.get('Disc_Demo_Acc', '-')}`",
        "",
        "## Artifacts",
        f"- model_file: `{paths.get('model_file', '')}`",
        f"- arg_file: `{paths.get('arg_file', '')}`",
        f"- best_by_case: `{root_path / 'best_by_case.tsv'}`",
        f"- infer_viz_index: `{infer_index if infer_index.exists() else ''}`",
        f"- render_meta_count: `{len(render_meta)}`",
        f"- mp4_count: `{len(mp4s)}`",
        "",
        "## Auto Finish Stages",
    ]
    for stage_name in WATCH_STAGE_ORDER:
        meta = stage_meta(state, stage_name)
        if meta.get("status") == "pending":
            continue
        lines.append(
            f"- {stage_name}: `{meta.get('status', '-')}` rc=`{meta.get('rc', '-')}` log=`{meta.get('log_file', '')}` notes=`{meta.get('notes', '')}`"
        )
    warning_lines = [f"- {item}" for item in warnings] if warnings else ["- none"]
    lines.extend(
        [
            "",
            "## Warnings",
            *warning_lines,
            "",
        ]
    )
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_stage_command(
    state_path: Path,
    root_path_obj: Path,
    watch_log: Path,
    state: dict[str, Any],
    stage_name: str,
    cmd: list[str],
    timeout_sec: int,
    env_extra: dict[str, str] | None = None,
    retry_if=None,
    mutate_cmd_for_retry=None,
) -> bool:
    meta = stage_meta(state, stage_name)
    if meta.get("status") == "completed":
        return True

    attempt = 0
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)

    while True:
        attempt += 1
        attempt_cmd = list(cmd)
        if attempt > 1 and mutate_cmd_for_retry:
            attempt_cmd = mutate_cmd_for_retry(attempt_cmd, attempt)
        log_path = stage_log_path(root_path_obj, stage_name, attempt)
        mark_stage_running(state, stage_name, command=shell_join(attempt_cmd), log_file=str(log_path), notes=f"attempt={attempt}")
        write_json(state_path, state)
        append_watch_log(watch_log, f"{stage_name}: start attempt={attempt} cmd={shell_join(attempt_cmd)}")

        rc, timed_out = run_process(attempt_cmd, ROOT, env, log_path, timeout_sec=timeout_sec)
        log_text = read_text(log_path)
        notes = "timeout" if timed_out else ""
        if rc == 0:
            mark_stage_completed(state, stage_name, notes=notes or f"attempt={attempt}", rc=rc)
            write_json(state_path, state)
            append_watch_log(watch_log, f"{stage_name}: completed attempt={attempt} rc={rc}")
            return True

        if retry_if is not None and retry_if(log_text, attempt):
            meta["notes"] = f"retry scheduled after attempt={attempt}"
            meta["rc"] = rc
            state["updated_at"] = now_str()
            write_json(state_path, state)
            append_watch_log(watch_log, f"{stage_name}: retry scheduled attempt={attempt} rc={rc}")
            continue

        mark_stage_failed(state, stage_name, notes=f"rc={rc} {notes}".strip(), rc=rc)
        write_json(state_path, state)
        append_watch_log(watch_log, f"{stage_name}: failed attempt={attempt} rc={rc} notes={notes or '-'}")
        return False


def render_retry_cmd(cmd: list[str], _attempt: int) -> list[str]:
    if "--force" in cmd:
        return cmd
    return [*cmd, "--force"]


def viewer_retry_predicate(log_text: str, attempt: int) -> bool:
    return attempt < 2 and classify_viewer_failure(log_text)


def render_retry_predicate(_log_text: str, attempt: int) -> bool:
    return attempt < 2


def build_commands(root_path: Path, live: dict[str, Any], args) -> dict[str, list[str]]:
    paths = extract_paths(root_path, live)
    arg_file = paths["arg_file"]
    engine_cfg = str(live.get("engine_config", "") or "data/engines/newton_engine.yaml")
    model_file = paths["model_file"]
    case_name = case_name_from_arg(arg_file)
    return {
        "build_best_by_case": [
            args.python_bin,
            str(ROOT / "scripts" / "build_amp_best_by_case_from_keepalive.py"),
            "--root-out",
            root_path.name,
        ],
        "post_train_test": [
            args.python_bin,
            str(ROOT / "mimickit" / "run.py"),
            "--arg_file",
            arg_file,
            "--engine_config",
            engine_cfg,
            "--mode",
            "test",
            "--visualize",
            "false",
            "--devices",
            args.render_device,
            "--num_envs",
            "1",
            "--test_episodes",
            str(args.test_episodes),
            "--model_file",
            model_file,
        ],
        "post_train_visualize": [
            args.python_bin,
            str(ROOT / "mimickit" / "run.py"),
            "--arg_file",
            arg_file,
            "--engine_config",
            engine_cfg,
            "--mode",
            "test",
            "--visualize",
            "true",
            "--devices",
            args.render_device,
            "--num_envs",
            "1",
            "--test_episodes",
            str(args.visualize_episodes),
            "--model_file",
            model_file,
        ],
        "post_train_render": [
            args.python_bin,
            str(ROOT / "tools" / "ue_bridge" / "build_mimickit_render_sequences.py"),
            "--roots",
            root_path.name,
            "--cases",
            case_name,
            "--frames",
            str(args.render_frames),
            "--frame-stride",
            str(args.render_frame_stride),
            "--device",
            args.render_device,
            "--num-envs",
            str(args.render_num_envs),
        ],
    }


def main() -> int:
    args = parse_args()
    root_path = resolve_root(args.root_out)
    ensure_dir(root_path)
    ensure_dir(root_path / "session_logs")

    state_path = root_path / "completion_watch.json"
    watch_log = root_path / "completion_watch.log"
    lock_path = root_path / "completion_watch.lock"

    existing = read_json(state_path)
    if existing.get("status") == "completed":
        print(f"[INFO] auto-finish already completed: {state_path}")
        return 0

    acquire_lock(lock_path)
    state = existing or init_state(root_path, args)
    write_json(state_path, state)

    append_watch_log(watch_log, f"watcher_start root={root_path}")

    try:
            while True:
                live = collect_live_status(root_path, args)
                state["last_live"] = live
                watch_meta = stage_meta(state, "watching")
                watch_meta["status"] = "running"
                watch_meta["started_at"] = watch_meta.get("started_at") or state.get("started_at", now_str())
                watch_meta["notes"] = (
                    f"source={live.get('source', '-')}"
                    f" current_stage={live.get('current_stage', live.get('run', {}).get('stage', '-'))}"
                    f" overall_long_samples={live.get('overall_long_samples', live.get('run', {}).get('overall_long_samples', 0))}"
                )
                state["status"] = "watching"
                state["current_stage"] = "watching"
                state["updated_at"] = now_str()
                write_json(state_path, state)
                update_summary(root_path, args, state, live)

                if live_long_completed(live):
                    break

                time.sleep(max(5, int(args.poll_sec)))

            mark_stage_completed(state, "watching", notes="detected long_train completion", rc=0)
            mark_stage_running(state, "triggered", notes="long_train completion detected")
            mark_stage_completed(state, "triggered", notes="auto-finish pipeline starting", rc=0)
            write_json(state_path, state)
            append_watch_log(watch_log, "long_train completion detected; auto-finish pipeline starting")

            commands = build_commands(root_path, state["last_live"], args)

            if existing_best_by_case_ok(root_path):
                mark_stage_completed(state, "build_best_by_case", notes="existing best_by_case.tsv final_ok=1", rc=0)
                write_json(state_path, state)
                append_watch_log(watch_log, "build_best_by_case: skipped existing final_ok=1")
            else:
                ok = run_stage_command(
                    state_path,
                    root_path,
                    watch_log,
                    state,
                    "build_best_by_case",
                    commands["build_best_by_case"],
                    timeout_sec=max(args.test_timeout_sec, 60),
                )
                if not ok:
                    update_summary(root_path, args, state, state["last_live"])
                    return 1

            if stage_meta(state, "post_train_test").get("status") != "completed":
                ok = run_stage_command(
                    state_path,
                    root_path,
                    watch_log,
                    state,
                    "post_train_test",
                    commands["post_train_test"],
                    timeout_sec=args.test_timeout_sec,
                )
                if not ok:
                    update_summary(root_path, args, state, state["last_live"])
                    return 1

            if stage_meta(state, "post_train_visualize").get("status") != "completed":
                ok = run_stage_command(
                    state_path,
                    root_path,
                    watch_log,
                    state,
                    "post_train_visualize",
                    commands["post_train_visualize"],
                    timeout_sec=args.visualize_timeout_sec,
                    env_extra={
                        "MIMICKIT_VIEWER_HEADLESS": "1",
                        "MESA_GL_VERSION_OVERRIDE": "3.3",
                        "MESA_GLSL_VERSION_OVERRIDE": "330",
                    },
                    retry_if=viewer_retry_predicate,
                )
                if not ok:
                    update_summary(root_path, args, state, state["last_live"])
                    return 1

            if existing_render_ok(root_path):
                mark_stage_completed(state, "post_train_render", notes="existing render output is reusable", rc=0)
                write_json(state_path, state)
                append_watch_log(watch_log, "post_train_render: skipped existing render output")
            else:
                render_ok = run_stage_command(
                    state_path,
                    root_path,
                    watch_log,
                    state,
                    "post_train_render",
                    commands["post_train_render"],
                    timeout_sec=args.render_timeout_sec,
                    retry_if=render_retry_predicate,
                    mutate_cmd_for_retry=render_retry_cmd,
                )
                if not render_ok:
                    update_summary(root_path, args, state, state["last_live"])
                    return 1

                render_log = Path(stage_meta(state, "post_train_render").get("log_file", ""))
                try:
                    mp4s = build_mp4s_for_root(root_path, render_log)
                    stage_meta(state, "post_train_render")["notes"] = (
                        f"{stage_meta(state, 'post_train_render').get('notes', '')} mp4_count={len(mp4s)}"
                    ).strip()
                    write_json(state_path, state)
                    append_watch_log(watch_log, f"post_train_render: mp4_count={len(mp4s)}")
                except Exception as err:
                    mark_stage_failed(state, "post_train_render", notes=str(err), rc=1)
                    write_json(state_path, state)
                    append_watch_log(watch_log, f"post_train_render: mp4 build failed err={err}")
                    update_summary(root_path, args, state, state["last_live"])
                    return 1

            state["last_live"] = collect_live_status(root_path, args)
            finalize_completed(state)
            write_json(state_path, state)
            update_summary(root_path, args, state, state["last_live"])
            append_watch_log(watch_log, "auto-finish completed")
            return 0
    finally:
        release_lock(lock_path)


if __name__ == "__main__":
    raise SystemExit(main())
