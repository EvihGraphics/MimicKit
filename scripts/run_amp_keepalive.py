#!/usr/bin/env python3
import argparse
import json
import os
import re
import shlex
import signal
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TRAIN_ROOT = ROOT / "output" / "train"
EVIH_RESULTS_ROOT = Path(
    os.environ.get(
        "MIMICKIT_EVIH_RESULTS_ROOT",
        "/mnt/d/AnimationTech-learning/EvihAnimation-mimickit-bridge-v3/Demos/MimicKitReplay/results",
    )
)
RUN_PY = ROOT / "mimickit" / "run.py"
DEFAULT_PYTHON = os.environ.get("MIMICKIT_TRAIN_PY", "/root/miniconda3/envs/mimickit/bin/python")
DEFAULT_HEADLESS_ENV = {
    "MIMICKIT_VIEWER_HEADLESS": "1",
    "MESA_GL_VERSION_OVERRIDE": "3.3",
    "MESA_GLSL_VERSION_OVERRIDE": "330",
}
NCCL_ENV = {
    "NCCL_P2P_DISABLE": "1",
    "NCCL_IB_DISABLE": "1",
    "NCCL_CUMEM_ENABLE": "0",
    "TORCH_NCCL_ASYNC_ERROR_HANDLING": "1",
    "TORCH_NCCL_BLOCKING_WAIT": "1",
}
STAGE_ORDER = [
    "smoke_test",
    "smoke_visualize",
    "smoke_train",
    "probe_train",
    "long_train",
]
TRAIN_STAGE_NAMES = {"smoke_train", "probe_train", "long_train"}


@dataclass(frozen=True)
class BrainSpec:
    brain: str
    arg_file: str
    case_key: str
    short_name: str
    healthy_throughput: int
    smoke_model_candidates: tuple[str, ...]


BRAIN_SPECS = {
    "WalkBrain": BrainSpec(
        brain="WalkBrain",
        arg_file="args/amp_location_humanoid_sword_shield_args.txt",
        case_key="amp_location_humanoid_sword_shield",
        short_name="AMP Walk",
        healthy_throughput=4800,
        smoke_model_candidates=(
            "data/models/amp_location_humanoid_sword_shield_model.pt",
        ),
    ),
    "TurnBrain": BrainSpec(
        brain="TurnBrain",
        arg_file="args/amp_steering_humanoid_sword_shield_args.txt",
        case_key="amp_steering_humanoid_sword_shield",
        short_name="AMP Turn",
        healthy_throughput=4550,
        smoke_model_candidates=(
            "data/models/amp_steering_humanoid_sword_shield_model.pt",
            "data/models/amp_steering_humanoid_model.pt",
        ),
    ),
    "StopBrain": BrainSpec(
        brain="StopBrain",
        arg_file="args/amp_stop_humanoid_sword_shield_args.txt",
        case_key="amp_stop_humanoid_sword_shield",
        short_name="AMP Stop",
        healthy_throughput=4550,
        smoke_model_candidates=(
            "data/models/amp_steering_humanoid_sword_shield_model.pt",
            "data/models/amp_steering_humanoid_model.pt",
        ),
    ),
}


def now_str():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def resolve_root(root_out: str):
    raw = Path(root_out)
    if raw.is_absolute():
        return raw
    return TRAIN_ROOT / root_out


def read_text(path: Path):
    if not path or not path.exists():
        return ""
    try:
        return path.read_text(errors="ignore")
    except Exception:
        return ""


def read_json_file(path: Path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def write_json(path: Path, data):
    ensure_dir(path.parent)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


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


def parse_resume_context(path: Path):
    ctx_path = path / "resume_context.tsv"
    raw = read_text(ctx_path)
    if not raw:
        return {}
    rows = {}
    for line in raw.splitlines():
        if not line.strip() or "\t" not in line:
            continue
        key, value = line.split("\t", 1)
        if key == "key":
            continue
        rows[key.strip()] = value.strip()
    return rows


def stage_segments(root_out: Path, base_name: str):
    segs = []
    base = root_out / base_name
    if base.exists() and base.is_dir():
        segs.append(base)

    pat = re.compile(rf"^{re.escape(base_name)}_resume(\d+)$")
    resumes = []
    for path in root_out.glob(f"{base_name}_resume*"):
        if not path.is_dir():
            continue
        match = pat.match(path.name)
        if not match:
            continue
        resumes.append((int(match.group(1)), path))
    resumes.sort(key=lambda x: x[0])
    segs.extend([p for _, p in resumes])
    return segs


def build_stage_chain_rows(root_out: Path, base_name: str):
    rows = []
    segments = []
    for seg_root in stage_segments(root_out, base_name):
        resume_ctx = parse_resume_context(seg_root)
        base_samples = int(resume_ctx.get("source_last_samples", "0") or 0)
        seg_rows = parse_training_rows(seg_root / "log.txt")
        latest_seg = seg_rows[-1] if seg_rows else {}
        segment_samples = int(latest_seg.get("Samples", 0) or 0)
        wall_time_h = float(latest_seg.get("Wall_Time", 0) or 0.0) if latest_seg else 0.0
        model_file = seg_root / "model.pt"
        segments.append(
            {
                "name": seg_root.name,
                "path": str(seg_root),
                "base_samples": base_samples,
                "segment_samples": segment_samples,
                "total_samples": base_samples + segment_samples,
                "wall_time_h": wall_time_h,
                "has_model": model_file.exists(),
                "model_file": str(model_file) if model_file.exists() else "",
            }
        )
        for row in seg_rows:
            new_row = dict(row)
            new_row["Segment_Samples"] = int(row.get("Samples", 0) or 0)
            new_row["Samples"] = base_samples + int(row.get("Samples", 0) or 0)
            rows.append(new_row)

    rows = sorted(
        rows,
        key=lambda r: (
            float(r.get("Samples", 0) or 0),
            float(r.get("Wall_Time", 0) or 0),
            int(r.get("Iteration", 0) or 0),
        ),
    )
    return segments, rows


def summarize_stage(root_out: Path, base_name: str):
    segments, rows = build_stage_chain_rows(root_out, base_name)
    latest = rows[-1] if rows else {}
    latest_model = ""
    latest_path = ""
    has_events = False
    for seg in segments:
        if seg["model_file"]:
            latest_model = seg["model_file"]
            latest_path = seg["path"]
        seg_path = Path(seg["path"])
        if not has_events and list(seg_path.glob("events.out.tfevents.*")):
            has_events = True
    total_samples = int(latest.get("Samples", 0) or 0)
    total_wall_time_h = float(latest.get("Wall_Time", 0) or 0.0) if latest else 0.0
    return {
        "base_name": base_name,
        "segments": segments,
        "rows": rows,
        "segment_count": len(segments),
        "total_samples": total_samples,
        "total_wall_time_h": total_wall_time_h,
        "latest_row": latest,
        "latest_model": latest_model,
        "latest_path": latest_path,
        "has_events": has_events,
    }


def next_resume_dir(root_out: Path, base_name: str):
    segs = stage_segments(root_out, base_name)
    if not segs:
        return root_out / base_name

    next_idx = 1
    pat = re.compile(rf"^{re.escape(base_name)}_resume(\d+)$")
    for seg in segs[1:]:
        match = pat.match(seg.name)
        if not match:
            continue
        next_idx = max(next_idx, int(match.group(1)) + 1)
    return root_out / f"{base_name}_resume{next_idx:02d}"


def write_resume_context(out_dir: Path, previous_segment: str, previous_model: str, previous_samples: int):
    rows = [
        ("key", "value"),
        ("source_run", previous_segment),
        ("source_model_file", previous_model),
        ("source_last_samples", str(previous_samples)),
    ]
    ensure_dir(out_dir)
    with (out_dir / "resume_context.tsv").open("w") as handle:
        for key, value in rows:
            handle.write(f"{key}\t{value}\n")


def classify_log_text(text: str):
    t = text.lower()
    if "processgroupnccl" in t or "distbackenderror" in t or "nccl" in t:
        return "nccl"
    if "out of memory" in t or "failed to allocate" in t or "cuda failure 2 'out of memory'" in t:
        return "oom"
    if "keyboardinterrupt" in t:
        return "interrupt"
    if "traceback" in t or "exception" in t or "error" in t:
        return "runtime"
    return ""


def mean_tail(rows, key: str, fallback: str = "", count: int = 3):
    if not rows:
        return None
    vals = []
    for row in rows[-count:]:
        value = row.get(key)
        if value is None and fallback:
            value = row.get(fallback)
        try:
            val = float(value)
        except Exception:
            continue
        vals.append(val)
    if not vals:
        return None
    return sum(vals) / len(vals)


def infer_samples_per_sec(row: dict):
    try:
        direct = row.get("Samples_Per_Sec")
        if direct is not None:
            value = float(direct)
            if value > 0:
                return value
    except Exception:
        pass
    try:
        samples = float(row.get("Samples", 0) or 0)
        wall_h = float(row.get("Wall_Time", 0) or 0)
    except Exception:
        return 0.0
    if samples <= 0 or wall_h <= 0:
        return 0.0
    return samples / (wall_h * 3600.0)


def within_disc_band(latest: dict):
    try:
        agent = float(latest.get("Disc_Agent_Acc"))
        demo = float(latest.get("Disc_Demo_Acc"))
    except Exception:
        return False
    return 0.55 <= agent <= 0.95 and 0.55 <= demo <= 0.95


def compute_best_scalar(root_out: Path, spec: BrainSpec, args):
    probe = summarize_stage(root_out, "probe_train")
    long_stage = summarize_stage(root_out, "long_train")
    candidates = []

    def add_candidate(name: str, summary: dict, total_samples: int):
        rows = summary["rows"]
        latest = summary["latest_row"]
        if not rows or not latest or not summary["latest_model"]:
            return
        samples_per_sec = infer_samples_per_sec(latest)
        eligible = (
            total_samples >= args.best_min_samples
            and samples_per_sec >= spec.healthy_throughput
            and within_disc_band(latest)
        )
        candidates.append(
            {
                "stage": name,
                "eligible": eligible,
                "model_file": summary["latest_model"],
                "out_dir": summary["latest_path"],
                "samples": total_samples,
                "test_return_smooth": mean_tail(rows, "Test_Return", "Train_Return"),
                "train_return_smooth": mean_tail(rows, "Train_Return"),
                "disc_reward_smooth": mean_tail(rows, "Disc_Reward_Mean"),
                "latest_row": latest,
            }
        )

    add_candidate("probe_train", probe, probe["total_samples"])
    add_candidate("long_train", long_stage, probe["total_samples"] + long_stage["total_samples"])

    if not candidates:
        return {}

    def score(row):
        test_return = row.get("test_return_smooth")
        train_return = row.get("train_return_smooth")
        disc_reward = row.get("disc_reward_smooth")
        return (
            1 if row["eligible"] else 0,
            float(test_return if test_return is not None else -1e18),
            float(train_return if train_return is not None else -1e18),
            float(disc_reward if disc_reward is not None else -1e18),
            int(row["samples"]),
        )

    best = sorted(candidates, key=score, reverse=True)[0]
    best["status_label"] = (
        "best scalar checkpoint"
        if best.get("eligible")
        else "warming up"
    )
    return best


def render_summary(root_out: Path, render_root_arg: str):
    if render_root_arg:
        base = Path(render_root_arg)
        render_root = base if base.name == root_out.name else base / root_out.name
    else:
        render_root = ROOT / "output" / "img" / root_out.name

    infer_index = render_root / "infer_viz_index.tsv"
    global_index = render_root.parent / "render_all_roots.tsv"
    render_meta = sorted(render_root.glob("**/render_meta.json"))
    mp4s = sorted(render_root.glob("**/*.mp4"))
    mesh_manifests = sorted(render_root.glob("**/mesh_reference_manifest.json"))
    visual_result_manifests = sorted(render_root.glob("**/visual_result_manifest.json"))
    comparison_sheets = sorted(render_root.glob("**/*_vs_*_sheet.png")) + sorted(render_root.glob("**/*contact_sheet.png"))
    comparison_videos = sorted(render_root.glob("**/*_vs_*_dynamic.mp4"))
    comparison_markdown = sorted(render_root.glob("**/comparison_sheet.md"))
    metric_reports = (
        sorted(render_root.glob("**/visual_metric_report.json"))
        + sorted(render_root.glob("**/scene_contract_compare_report.json"))
        + sorted(render_root.glob("**/scene_visual_metric_report.json"))
        + sorted(render_root.glob("**/rgb_metric_report.json"))
    )
    visual_reviews = sorted(render_root.glob("**/visual_review.json"))
    bridge_case_manifests = sorted({*render_root.glob("**/bridge_case_manifest.json"), *root_out.glob("**/bridge_case_manifest.json")})
    full_chain_manifests = sorted(render_root.parent.glob("**/full_chain_bridge_manifest.json"))
    bridge_execution_manifests = sorted(render_root.parent.glob("**/plan_6_9_execution_manifest.json"))

    evih_result_files = []
    evih_visual_result_manifests = []
    evih_mp4s = []
    evih_comparison_sheets = []
    evih_comparison_videos = []
    evih_comparison_markdown = []
    evih_metric_reports = []
    evih_visual_reviews = []
    if EVIH_RESULTS_ROOT.exists():
        for manifest_path in sorted(EVIH_RESULTS_ROOT.glob("**/visual_result_manifest.json")):
            raw = read_text(manifest_path)
            if root_out.name in raw or render_root.name in raw:
                evih_result_files.append(str(manifest_path))
                evih_visual_result_manifests.append(manifest_path)
                result_dir = manifest_path.parent
                for child in sorted(result_dir.glob("**/*_vs_*_sheet.png")):
                    evih_result_files.append(str(child))
                    evih_comparison_sheets.append(child)
                for child in sorted(result_dir.glob("**/*_vs_*_dynamic.mp4")):
                    evih_result_files.append(str(child))
                    evih_comparison_videos.append(child)
                for child in sorted(result_dir.glob("**/*.mp4")):
                    evih_result_files.append(str(child))
                    evih_mp4s.append(child)
                for child in sorted(result_dir.glob("**/*_report.json")):
                    evih_result_files.append(str(child))
                    evih_metric_reports.append(child)
                for child in sorted(result_dir.glob("**/visual_review.json")):
                    evih_result_files.append(str(child))
                    evih_visual_reviews.append(child)
                for child in sorted(result_dir.glob("**/comparison_sheet.md")):
                    evih_result_files.append(str(child))
                    evih_comparison_markdown.append(child)
        # Current Walk/Stop result directories predate root-name linkage; expose them
        # when viewing their known AMP roots so the dashboard remains useful.
        known_pairs = {
            "amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637": "walkbrain_skeleton_replay",
            "amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01": "stopbrain_skeleton_replay",
        }
        known_result_name = known_pairs.get(root_out.name, "")
        known_dir = EVIH_RESULTS_ROOT / known_result_name if known_result_name else Path()
        if known_result_name and known_dir.exists():
            for child in [known_dir / "visual_result_manifest.json", *sorted(known_dir.glob("*_vs_*_sheet.png")), *sorted(known_dir.glob("**/*.mp4"))]:
                if child.exists():
                    evih_result_files.append(str(child))

    mp4s = sorted({*mp4s, *evih_mp4s})
    visual_result_manifests = sorted({*visual_result_manifests, *evih_visual_result_manifests})
    comparison_sheets = sorted({*comparison_sheets, *evih_comparison_sheets})
    comparison_videos = sorted({*comparison_videos, *evih_comparison_videos})
    comparison_markdown = sorted({*comparison_markdown, *evih_comparison_markdown})
    metric_reports = sorted({*metric_reports, *evih_metric_reports})
    visual_reviews = sorted({*visual_reviews, *evih_visual_reviews})
    files = []
    for path in [infer_index, global_index, *render_meta[:8], *mp4s[:8], *mesh_manifests[:8], *visual_result_manifests[:8], *comparison_sheets[:8], *comparison_videos[:8], *comparison_markdown[:8], *metric_reports[:8], *visual_reviews[:8], *full_chain_manifests[:4], *bridge_execution_manifests[:4]]:
        if path.exists():
            files.append(str(path))
    files.extend(evih_result_files[:24])

    parsed_mesh = [read_json_file(path) for path in mesh_manifests]
    parsed_visual = [read_json_file(path) for path in visual_result_manifests]
    parsed_render = [read_json_file(path) for path in render_meta]
    parsed_bridge = [read_json_file(path) for path in bridge_case_manifests]
    parsed_full = [read_json_file(path) for path in full_chain_manifests]
    parsed_execution = [read_json_file(path) for path in bridge_execution_manifests]

    case_acceptance_detected = any(item.get("case_acceptance_pass") for item in parsed_bridge)
    pass_detected = any(item.get("full_chain_bridge_pass") for item in parsed_full)
    software_geometry_pass_count = sum(bool(item.get("software_geometry_replay_pass")) for item in parsed_visual)
    framework_api_pass_count = sum(bool(item.get("evih_framework_api_replay_pass")) for item in parsed_visual)
    accepted_case_count = sum(bool(item.get("case_acceptance_pass")) for item in parsed_bridge)
    blockers = []
    for item in [*parsed_bridge, *parsed_full, *parsed_execution, *parsed_mesh, *parsed_visual, *parsed_render]:
        primary = str(item.get("blocker") or item.get("error") or "").strip()
        if primary:
            blockers.append(primary)
        blockers.extend(str(value).strip() for value in item.get("blockers", []) if str(value).strip())
        report = item.get("report", {}) if isinstance(item.get("report"), dict) else {}
        blockers.extend(str(value).strip() for value in report.get("blockers", []) if str(value).strip())
    blockers = list(dict.fromkeys(blockers))
    has_artifacts = bool(infer_index.exists() or render_meta or mp4s or mesh_manifests or visual_result_manifests or comparison_sheets or evih_result_files)
    status = "available" if pass_detected else ("failed" if blockers else ("pending" if not has_artifacts else "incomplete"))
    return {
        "root_path": str(render_root),
        "status": status,
        "case_acceptance_detected": case_acceptance_detected,
        "full_chain_bridge_pass": pass_detected,
        "software_geometry_pass_count": software_geometry_pass_count,
        "framework_api_pass_count": framework_api_pass_count,
        "accepted_case_count": accepted_case_count,
        "blocker": blockers[0] if blockers else "",
        "blockers": blockers,
        "infer_viz_index": str(infer_index) if infer_index.exists() else "",
        "render_all_roots": str(global_index) if global_index.exists() else "",
        "render_meta_files": [str(path) for path in render_meta[:12]],
        "mp4_files": [str(path) for path in mp4s[:12]],
        "mesh_manifest_files": [str(path) for path in mesh_manifests[:12]],
        "visual_result_manifest_files": [str(path) for path in visual_result_manifests[:12]],
        "comparison_sheet_files": [str(path) for path in comparison_sheets[:12]],
        "comparison_video_files": [str(path) for path in comparison_videos[:12]],
        "comparison_markdown_files": [str(path) for path in comparison_markdown[:12]],
        "metric_report_files": [str(path) for path in metric_reports[:12]],
        "visual_review_files": [str(path) for path in visual_reviews[:12]],
        "bridge_case_manifest_files": [str(path) for path in bridge_case_manifests[:12]],
        "full_chain_manifest_files": [str(path) for path in full_chain_manifests[:6]],
        "bridge_execution_manifest_files": [str(path) for path in bridge_execution_manifests[:6]],
        "evih_result_files": evih_result_files[:24],
        "evih_visual_result_manifest_files": [str(path) for path in evih_visual_result_manifests[:12]],
        "files": files,
    }


def read_gpu_snapshot():
    cmd = [
        "nvidia-smi",
        "--query-gpu=index,utilization.gpu,memory.used,memory.total,temperature.gpu",
        "--format=csv,noheader,nounits",
    ]
    try:
        out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL, timeout=5)
    except Exception:
        return []

    gpus = []
    for line in out.splitlines():
        parts = [x.strip() for x in line.split(",")]
        if len(parts) < 5:
            continue
        try:
            gpus.append(
                {
                    "index": int(parts[0]),
                    "util": int(float(parts[1])),
                    "mem_used": int(float(parts[2])),
                    "mem_total": int(float(parts[3])),
                    "temp_c": int(float(parts[4])),
                }
            )
        except Exception:
            continue
    return gpus


class MonitorThread(threading.Thread):
    def __init__(self, path: Path, interval_sec: int):
        super().__init__(daemon=True)
        self._path = path
        self._interval_sec = max(2, int(interval_sec))
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        ensure_dir(self._path.parent)
        while not self._stop_event.is_set():
            payload = {"time": now_str(), "gpus": read_gpu_snapshot()}
            try:
                with self._path.open("a") as handle:
                    handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
            except Exception:
                pass
            self._stop_event.wait(self._interval_sec)


def initial_state(spec: BrainSpec):
    stages = {}
    for stage in STAGE_ORDER:
        stages[stage] = {
            "status": "pending",
            "attempt_count": 0,
            "attempts": [],
            "started_at": "",
            "completed_at": "",
            "log_file": "",
            "out_dir": "",
            "notes": "",
        }
    return {
        "brain": spec.brain,
        "case_key": spec.case_key,
        "current_stage": "",
        "events": [],
        "stages": stages,
    }


def load_state(path: Path, spec: BrainSpec):
    if not path.exists():
        return initial_state(spec)
    try:
        data = json.loads(path.read_text())
    except Exception:
        return initial_state(spec)
    if not isinstance(data, dict):
        return initial_state(spec)
    base = initial_state(spec)
    base.update({k: v for k, v in data.items() if k in base})
    base["stages"].update(data.get("stages", {}))
    for stage in STAGE_ORDER:
        stage_meta = base["stages"].setdefault(stage, {})
        stage_meta.setdefault("status", "pending")
        stage_meta.setdefault("attempt_count", 0)
        stage_meta.setdefault("attempts", [])
        stage_meta.setdefault("started_at", "")
        stage_meta.setdefault("completed_at", "")
        stage_meta.setdefault("log_file", "")
        stage_meta.setdefault("out_dir", "")
        stage_meta.setdefault("notes", "")
    base["brain"] = spec.brain
    base["case_key"] = spec.case_key
    base.setdefault("events", [])
    base.setdefault("current_stage", "")
    return base


def append_event(state, message: str):
    state.setdefault("events", []).append(f"{now_str()} | {message}")
    state["events"] = state["events"][-200:]


def save_state(path: Path, state):
    write_json(path, state)


def runner_logger(root_out: Path):
    runner_log = root_out / "runner.log"

    def _log(message: str):
        ensure_dir(runner_log.parent)
        line = f"[{now_str()}] {message}"
        print(line, flush=True)
        with runner_log.open("a") as handle:
            handle.write(line + "\n")

    return _log


def phase_target(stage: str, args):
    if stage == "smoke_train":
        return int(args.smoke_train_samples)
    if stage == "probe_train":
        return int(args.probe_target_samples)
    if stage == "long_train":
        return int(args.long_target_samples)
    return 0


def current_progress_target(stage: str, args):
    if stage == "smoke_train":
        return int(args.smoke_train_samples), "smoke_train"
    if stage == "probe_train":
        return int(args.probe_target_samples), "probe_train"
    return int(args.long_target_samples), "long_train"


def pick_smoke_model(spec: BrainSpec):
    for rel in spec.smoke_model_candidates:
        path = ROOT / rel
        if path.exists():
            return path
    return None


def current_train_stage(state, root_out: Path):
    stage = state.get("current_stage", "")
    if stage in TRAIN_STAGE_NAMES:
        return stage
    for name in ("long_train", "probe_train", "smoke_train"):
        if summarize_stage(root_out, name)["segment_count"] > 0:
            return name
    return ""


def stage_completion_status(stage: str, root_out: Path, args):
    smoke = summarize_stage(root_out, "smoke_train")
    probe = summarize_stage(root_out, "probe_train")
    long_stage = summarize_stage(root_out, "long_train")
    if stage == "smoke_train":
        return bool(smoke["latest_model"]) and smoke["total_samples"] >= args.smoke_train_samples
    if stage == "probe_train":
        return bool(probe["latest_model"]) and probe["total_samples"] >= args.probe_target_samples
    if stage == "long_train":
        return bool(long_stage["latest_model"]) and (probe["total_samples"] + long_stage["total_samples"]) >= args.long_target_samples
    return False


def build_status(root_out: Path, state, spec: BrainSpec, args, monitor_log: Path, queue_log: str):
    smoke = summarize_stage(root_out, "smoke_train")
    probe = summarize_stage(root_out, "probe_train")
    long_stage = summarize_stage(root_out, "long_train")
    render = render_summary(root_out, args.render_root)
    best_scalar = compute_best_scalar(root_out, spec, args)
    active_train_stage = current_train_stage(state, root_out)

    current_target, current_target_label = current_progress_target(state.get("current_stage", ""), args)
    if state.get("current_stage") == "smoke_train":
        current_samples = smoke["total_samples"]
    elif state.get("current_stage") == "probe_train":
        current_samples = probe["total_samples"]
    else:
        current_samples = probe["total_samples"] + long_stage["total_samples"]

    stages = {}
    for stage in STAGE_ORDER:
        meta = state["stages"].get(stage, {})
        row = {}
        summary = {}
        if stage in TRAIN_STAGE_NAMES:
            summary = {"smoke_train": smoke, "probe_train": probe, "long_train": long_stage}[stage]
            row = summary["latest_row"] or {}
        stages[stage] = {
            "status": meta.get("status", "pending"),
            "attempt_count": meta.get("attempt_count", 0),
            "started_at": meta.get("started_at", ""),
            "completed_at": meta.get("completed_at", ""),
            "log_file": meta.get("log_file", ""),
            "out_dir": meta.get("out_dir", ""),
            "notes": meta.get("notes", ""),
            "latest_row": row,
            "total_samples": summary.get("total_samples", 0),
            "total_wall_time_h": summary.get("total_wall_time_h", 0.0),
            "latest_model": summary.get("latest_model", ""),
            "latest_path": summary.get("latest_path", ""),
            "segments": summary.get("segments", []),
            "has_events": summary.get("has_events", False),
        }

    active_path = ""
    if active_train_stage:
        active_path = stages[active_train_stage].get("latest_path", "")
    current_dir = Path(active_path) if active_path else None

    payload = {
        "generated_at": now_str(),
        "root_name": root_out.name,
        "root_path": str(root_out),
        "brain": spec.brain,
        "case_key": spec.case_key,
        "case_short": spec.short_name,
        "arg_file": spec.arg_file,
        "current_stage": state.get("current_stage", ""),
        "current_stage_status": state["stages"].get(state.get("current_stage", ""), {}).get("status", ""),
        "current_target_label": current_target_label,
        "current_target_samples": current_target,
        "current_progress_samples": current_samples,
        "probe_target_samples": int(args.probe_target_samples),
        "long_target_samples": int(args.long_target_samples),
        "overall_long_samples": probe["total_samples"] + long_stage["total_samples"],
        "devices": args.devices,
        "num_envs": int(args.num_envs),
        "engine_config": args.engine_config,
        "master_port": int(args.master_port),
        "monitor_log": str(monitor_log),
        "queue_log": queue_log,
        "queue_mode": "single-brain mode",
        "throughput_healthy_floor": spec.healthy_throughput,
        "current_train_stage": active_train_stage,
        "current_train_dir": active_path,
        "current_log": str((current_dir / "log.txt").resolve()) if current_dir else "",
        "current_env_config": str((current_dir / "env_config.yaml").resolve()) if current_dir else "",
        "current_agent_config": str((current_dir / "agent_config.yaml").resolve()) if current_dir else "",
        "current_engine_config": str((current_dir / "engine_config.yaml").resolve()) if current_dir else "",
        "smoke_model_file": str(pick_smoke_model(spec) or ""),
        "stages": stages,
        "best_scalar_checkpoint": best_scalar,
        "render": render,
        "events": state.get("events", [])[-120:],
        "runner_log": str(root_out / "runner.log"),
    }
    return payload


def write_status(root_out: Path, state, spec: BrainSpec, args, monitor_log: Path, queue_log: str):
    payload = build_status(root_out, state, spec, args, monitor_log, queue_log)
    write_json(root_out / "keepalive_status.json", payload)


def run_process(
    cmd,
    cwd: Path,
    env: dict,
    stdout_log: Path,
    state_writer,
    poll_sec: int,
    timeout_sec: int = 0,
):
    ensure_dir(stdout_log.parent)
    with stdout_log.open("ab") as handle:
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
            state_writer()
            if rc is not None:
                return rc, timed_out
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
                state_writer()
                return proc.returncode if proc.returncode is not None else 124, timed_out
            time.sleep(max(1, int(poll_sec)))


def stop_after_reached(stage: str, args):
    return args.stop_after_stage == stage


def build_eval_cmd(spec: BrainSpec, args, visualize: bool, model_file: Path | None):
    cmd = [
        args.python_bin,
        str(RUN_PY),
        "--arg_file",
        spec.arg_file,
        "--engine_config",
        args.engine_config,
        "--mode",
        "test",
        "--visualize",
        "true" if visualize else "false",
        "--devices",
        args.eval_device,
        "--num_envs",
        "1",
        "--test_episodes",
        str(args.test_episodes),
    ]
    if model_file:
        cmd.extend(["--model_file", str(model_file)])
    return cmd


def build_train_cmd(spec: BrainSpec, args, source_model: str, out_dir: Path, remaining_samples: int):
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
        *args.devices,
        "--num_envs",
        str(args.num_envs),
        "--master_port",
        str(args.master_port),
        "--max_samples",
        str(max(1, int(remaining_samples))),
        "--out_dir",
        str(out_dir),
    ]
    if source_model:
        cmd.extend(["--model_file", source_model])
    return cmd


def determine_source_model(root_out: Path, stage: str, spec: BrainSpec):
    smoke = summarize_stage(root_out, "smoke_train")
    probe = summarize_stage(root_out, "probe_train")
    long_stage = summarize_stage(root_out, "long_train")

    if stage == "probe_train":
        if probe["latest_model"]:
            return probe["latest_model"], Path(probe["latest_path"]).name
        if smoke["latest_model"]:
            return smoke["latest_model"], Path(smoke["latest_path"]).name
    if stage == "long_train":
        if long_stage["latest_model"]:
            return long_stage["latest_model"], Path(long_stage["latest_path"]).name
        if probe["latest_model"]:
            return probe["latest_model"], Path(probe["latest_path"]).name
        if smoke["latest_model"]:
            return smoke["latest_model"], Path(smoke["latest_path"]).name

    smoke_model = pick_smoke_model(spec)
    if smoke_model:
        return str(smoke_model), smoke_model.name
    return "", ""


def remaining_stage_samples(root_out: Path, stage: str, args):
    smoke = summarize_stage(root_out, "smoke_train")
    probe = summarize_stage(root_out, "probe_train")
    long_stage = summarize_stage(root_out, "long_train")
    if stage == "smoke_train":
        return max(1, args.smoke_train_samples - smoke["total_samples"])
    if stage == "probe_train":
        return max(1, args.probe_target_samples - probe["total_samples"])
    overall = probe["total_samples"] + long_stage["total_samples"]
    return max(1, args.long_target_samples - overall)


def run_smoke_stage(stage: str, spec: BrainSpec, root_out: Path, state, args, log, state_file: Path, monitor_log: Path):
    meta = state["stages"][stage]
    if meta.get("status") == "completed":
        return True

    model_file = pick_smoke_model(spec)
    meta["status"] = "running"
    meta["started_at"] = meta.get("started_at") or now_str()
    meta["attempt_count"] = int(meta.get("attempt_count", 0)) + 1
    attempt_idx = meta["attempt_count"]
    stdout_log = root_out / "session_logs" / f"{stage}.attempt{attempt_idx:02d}.log"
    meta["log_file"] = str(stdout_log)
    note = "using pretrained model" if model_file else "no pretrained model found; running smoke without --model_file"
    meta["notes"] = note
    state["current_stage"] = stage
    append_event(state, f"{stage}: start | {note}")
    save_state(state_file, state)
    write_status(root_out, state, spec, args, monitor_log, args.queue_log)
    log(f"{stage}: start | {note}")

    env = os.environ.copy()
    env.update(DEFAULT_HEADLESS_ENV if stage == "smoke_visualize" else {})
    cmd = build_eval_cmd(spec, args, visualize=(stage == "smoke_visualize"), model_file=model_file)
    log(f"{stage}: cmd={shlex.join(cmd)}")
    rc, timed_out = run_process(
        cmd=cmd,
        cwd=ROOT,
        env=env,
        stdout_log=stdout_log,
        state_writer=lambda: write_status(root_out, state, spec, args, monitor_log, args.queue_log),
        poll_sec=args.status_poll_sec,
        timeout_sec=args.eval_timeout_sec,
    )
    meta.setdefault("attempts", []).append({"attempt": attempt_idx, "rc": rc, "timed_out": timed_out, "log_file": str(stdout_log)})
    if rc != 0:
        meta["status"] = "failed"
        meta["notes"] = f"exit rc={rc}"
        append_event(state, f"{stage}: failed rc={rc}")
        save_state(state_file, state)
        write_status(root_out, state, spec, args, monitor_log, args.queue_log)
        return False

    meta["status"] = "completed"
    meta["completed_at"] = now_str()
    append_event(state, f"{stage}: completed")
    save_state(state_file, state)
    write_status(root_out, state, spec, args, monitor_log, args.queue_log)
    log(f"{stage}: completed")
    return True


def run_train_stage(stage: str, spec: BrainSpec, root_out: Path, state, args, log, state_file: Path, monitor_log: Path):
    meta = state["stages"][stage]
    if stage_completion_status(stage, root_out, args):
        meta["status"] = "completed"
        meta["completed_at"] = meta.get("completed_at") or now_str()
        save_state(state_file, state)
        write_status(root_out, state, spec, args, monitor_log, args.queue_log)
        return True

    attempts = int(meta.get("attempt_count", 0))
    while attempts < args.max_attempts_per_stage:
        attempts += 1
        meta["attempt_count"] = attempts
        meta["status"] = "running"
        meta["started_at"] = meta.get("started_at") or now_str()
        state["current_stage"] = stage

        out_dir = next_resume_dir(root_out, stage)
        remaining = remaining_stage_samples(root_out, stage, args)
        source_model, source_run = determine_source_model(root_out, stage, spec)
        summary_before = summarize_stage(root_out, stage)
        previous_samples = summary_before["total_samples"]
        meta["out_dir"] = str(out_dir)
        stdout_log = root_out / "session_logs" / f"{stage}.attempt{attempts:02d}.log"
        meta["log_file"] = str(stdout_log)
        meta["notes"] = f"remaining_samples={remaining}"
        write_resume_context(out_dir, source_run, source_model, previous_samples)
        append_event(state, f"{stage}: attempt={attempts} out={out_dir.name} remain={remaining}")
        save_state(state_file, state)
        write_status(root_out, state, spec, args, monitor_log, args.queue_log)

        if stage != "smoke_train" and not source_model:
            meta["status"] = "failed"
            meta["notes"] = "missing source model"
            append_event(state, f"{stage}: missing source model")
            save_state(state_file, state)
            write_status(root_out, state, spec, args, monitor_log, args.queue_log)
            return False

        env = os.environ.copy()
        env.update(NCCL_ENV)
        cmd = build_train_cmd(spec, args, source_model, out_dir, remaining)
        log(f"{stage}: attempt={attempts} cmd={shlex.join(cmd)}")
        rc, _ = run_process(
            cmd=cmd,
            cwd=ROOT,
            env=env,
            stdout_log=stdout_log,
            state_writer=lambda: write_status(root_out, state, spec, args, monitor_log, args.queue_log),
            poll_sec=args.status_poll_sec,
            timeout_sec=0,
        )

        summary_after = summarize_stage(root_out, stage)
        log_text = read_text(stdout_log)
        error_kind = classify_log_text(log_text[-40000:])
        meta.setdefault("attempts", []).append(
            {
                "attempt": attempts,
                "rc": rc,
                "error_kind": error_kind,
                "out_dir": str(out_dir),
                "remaining_samples": remaining,
                "source_model": source_model,
                "samples_after": summary_after["total_samples"],
                "latest_model": summary_after["latest_model"],
                "log_file": str(stdout_log),
            }
        )

        if stage_completion_status(stage, root_out, args):
            meta["status"] = "completed"
            meta["completed_at"] = now_str()
            append_event(state, f"{stage}: completed after attempt={attempts}")
            save_state(state_file, state)
            write_status(root_out, state, spec, args, monitor_log, args.queue_log)
            log(f"{stage}: completed after attempt={attempts}")
            return True

        if rc == 0 and summary_after["latest_model"]:
            meta["status"] = "resuming"
            meta["notes"] = "target not reached yet; scheduling resume"
            append_event(state, f"{stage}: partial progress, resume scheduled")
        else:
            meta["status"] = "resuming"
            meta["notes"] = f"rc={rc} error={error_kind or '-'}"
            append_event(state, f"{stage}: rc={rc} error={error_kind or '-'}; resume scheduled")

        save_state(state_file, state)
        write_status(root_out, state, spec, args, monitor_log, args.queue_log)
        if args.retry_sleep_sec > 0:
            time.sleep(args.retry_sleep_sec)

    meta["status"] = "failed"
    meta["notes"] = "max attempts reached"
    append_event(state, f"{stage}: failed_max_attempts")
    save_state(state_file, state)
    write_status(root_out, state, spec, args, monitor_log, args.queue_log)
    return False


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--brain", required=True, choices=sorted(BRAIN_SPECS.keys()))
    ap.add_argument("--root-out", required=True, help="Relative root under output/train or absolute path.")
    ap.add_argument("--engine-config", default="data/engines/newton_engine.yaml")
    ap.add_argument("--python-bin", default=DEFAULT_PYTHON)
    ap.add_argument("--devices", nargs="+", default=["cuda:0", "cuda:1"])
    ap.add_argument("--num-envs", type=int, default=1024)
    ap.add_argument("--master-port", type=int, default=40489)
    ap.add_argument("--eval-device", default="cuda:0")
    ap.add_argument("--test-episodes", type=int, default=1)
    ap.add_argument("--smoke-train-samples", type=int, default=16_384)
    ap.add_argument("--probe-target-samples", type=int, default=50_000_000)
    ap.add_argument("--long-target-samples", type=int, default=1_000_000_000)
    ap.add_argument("--best-min-samples", type=int, default=100_000_000)
    ap.add_argument("--eval-timeout-sec", type=int, default=900)
    ap.add_argument("--retry-sleep-sec", type=int, default=15)
    ap.add_argument("--status-poll-sec", type=int, default=5)
    ap.add_argument("--max-attempts-per-stage", type=int, default=8)
    ap.add_argument("--monitor-log", default="", help="Optional GPU monitor log path. Defaults to <root>/monitor.log.")
    ap.add_argument("--queue-log", default="", help="Forward-compat only; single-brain mode ignores queue state.")
    ap.add_argument("--render-root", default="", help="Optional output/img root or exact render root.")
    ap.add_argument("--series-cases", default="", help="Forward-compat only; dashboard shows single-brain mode.")
    ap.add_argument("--resume", action="store_true", help="Compatibility flag; same-root resume is automatic.")
    ap.add_argument("--stop-after-stage", default="complete", choices=[*STAGE_ORDER, "complete"])
    return ap.parse_args()


def main():
    args = parse_args()
    spec = BRAIN_SPECS[args.brain]
    root_out = resolve_root(args.root_out)
    ensure_dir(root_out)
    ensure_dir(root_out / "session_logs")

    if not RUN_PY.exists():
        print(f"[ERROR] run.py not found: {RUN_PY}")
        return 2

    state_file = root_out / "keepalive_state.json"
    state = load_state(state_file, spec)
    log = runner_logger(root_out)
    monitor_log = Path(args.monitor_log) if args.monitor_log else root_out / "monitor.log"
    monitor_thread = MonitorThread(monitor_log, interval_sec=args.status_poll_sec)
    monitor_thread.start()

    append_event(state, f"supervisor_start brain={spec.brain} root={root_out}")
    save_state(state_file, state)
    write_status(root_out, state, spec, args, monitor_log, args.queue_log)

    try:
        for stage in STAGE_ORDER:
            state["current_stage"] = stage
            save_state(state_file, state)
            write_status(root_out, state, spec, args, monitor_log, args.queue_log)

            if stage in {"smoke_test", "smoke_visualize"}:
                ok = run_smoke_stage(stage, spec, root_out, state, args, log, state_file, monitor_log)
            else:
                ok = run_train_stage(stage, spec, root_out, state, args, log, state_file, monitor_log)

            if not ok:
                log(f"{stage}: failed; stopping keepalive")
                return 1

            if stop_after_reached(stage, args):
                append_event(state, f"stop_after_stage={stage}")
                save_state(state_file, state)
                write_status(root_out, state, spec, args, monitor_log, args.queue_log)
                log(f"stop_after_stage reached: {stage}")
                return 0

        state["current_stage"] = "complete"
        append_event(state, "supervisor_complete")
        save_state(state_file, state)
        write_status(root_out, state, spec, args, monitor_log, args.queue_log)
        log("all AMP single-brain stages completed")
        return 0
    finally:
        monitor_thread.stop()
        monitor_thread.join(timeout=2)


if __name__ == "__main__":
    raise SystemExit(main())
