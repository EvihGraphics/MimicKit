#!/usr/bin/env python3
"""Build a single-row AMP best_by_case.tsv from keepalive_status.json."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TRAIN_ROOT = ROOT / "output" / "train"

FIELDS = [
    "case",
    "method",
    "case_type",
    "variant",
    "agent_config",
    "num_envs",
    "final_ok",
    "note",
    "out_dir",
    "long_out_dir",
    "model_file",
    "env_config",
    "engine_config",
    "llc_model_file",
    "motion_id",
    "motion_file",
    "source_pack",
    "category",
    "train_enabled",
    "view_enabled",
]


def resolve_root(root_out: str) -> Path:
    raw = Path(root_out)
    if raw.is_absolute():
        return raw.resolve()
    return (TRAIN_ROOT / root_out).resolve()


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def safe_path(path: Path | str) -> str:
    curr = Path(path)
    return str(curr.resolve()) if curr.exists() else ""


def bool_to_flag(v: bool) -> str:
    return "1" if v else "0"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root-out", required=True, help="AMP keepalive root name under output/train or absolute path")
    ap.add_argument("--stage", default="long_train", help="Training stage to summarize, e.g. long_train or probe_train")
    ap.add_argument("--output", default="", help="Output TSV path, default: <root>/best_by_case.tsv")
    args = ap.parse_args()

    root_dir = resolve_root(args.root_out)
    status_path = root_dir / "keepalive_status.json"
    status = read_json(status_path)
    if not status:
        raise SystemExit(f"[ERROR] missing or invalid keepalive status: {status_path}")

    arg_file = str(status.get("arg_file", "")).strip()
    case_key = str(status.get("case_key", "")).strip()
    if not arg_file or not case_key:
        raise SystemExit(f"[ERROR] keepalive status missing arg_file/case_key: {status_path}")

    stage_name = str(args.stage).strip() or "long_train"
    stage_meta = ((status.get("stages") or {}).get(stage_name) or {})
    out_dir = Path(str(stage_meta.get("latest_path", "")).strip() or str(status.get("current_train_dir", "")).strip() or str(root_dir / stage_name))
    model_path = Path(str(stage_meta.get("latest_model", "")).strip() or str(out_dir / "model.pt"))

    if not model_path.exists():
        raise SystemExit(f"[ERROR] missing {stage_name} model file: {model_path}")

    env_cfg = Path(str(stage_meta.get("env_config", "")).strip() or str(status.get("current_env_config", "")).strip() or str(out_dir / "env_config.yaml"))
    agent_cfg = Path(str(stage_meta.get("agent_config", "")).strip() or str(status.get("current_agent_config", "")).strip() or str(out_dir / "agent_config.yaml"))
    engine_cfg = Path(str(stage_meta.get("engine_config", "")).strip() or str(status.get("current_engine_config", "")).strip() or str(out_dir / "engine_config.yaml"))

    stage_status = str(stage_meta.get("status", "")).strip().lower()
    current_stage = str(status.get("current_stage", "")).strip().lower()
    current_stage_status = str(status.get("current_stage_status", "")).strip().lower()
    if stage_name == "long_train":
        long_target = int(status.get("long_target_samples") or 0)
        long_progress = int(status.get("overall_long_samples") or 0)
        train_completed = (
            stage_status == "completed"
            or (current_stage == "complete" and long_progress >= long_target > 0)
            or (current_stage == "long_train" and current_stage_status == "completed")
        )
    else:
        train_completed = stage_status == "completed" or (current_stage == stage_name and current_stage_status == "completed")

    note = "auto_generated_from_amp_keepalive_status_completed" if train_completed else "auto_generated_from_amp_keepalive_status_incomplete"
    row = {
        "case": Path(arg_file).name,
        "method": "amp_keepalive_summary",
        "case_type": "trainable",
        "variant": out_dir.name,
        "agent_config": safe_path(agent_cfg),
        "num_envs": str(status.get("num_envs", "")),
        "final_ok": bool_to_flag(train_completed),
        "note": note,
        "out_dir": safe_path(out_dir),
        "long_out_dir": safe_path(out_dir),
        "model_file": safe_path(model_path),
        "env_config": safe_path(env_cfg),
        "engine_config": safe_path(engine_cfg),
        "llc_model_file": "",
        "motion_id": "",
        "motion_file": "",
        "source_pack": root_dir.name,
        "category": case_key,
        "train_enabled": "true",
        "view_enabled": "true",
    }

    output_path = Path(args.output).resolve() if args.output else (root_dir / "best_by_case.tsv")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=FIELDS, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        writer.writerow(row)

    print(f"[DONE] wrote {output_path} rows=1 final_ok={row['final_ok']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
