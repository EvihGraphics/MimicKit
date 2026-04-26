#!/usr/bin/env python3
"""Build best_by_case.tsv from keepalive_status.json for ASE 7-case roots."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TRAIN_ROOT = ROOT / "output" / "train"


CASE_TO_ARG = {
    "ase_humanoid": "ase_humanoid_args.txt",
    "ase_humanoid_sword_shield": "ase_humanoid_sword_shield_args.txt",
    "ase_getup_humanoid_sword_shield": "ase_getup_humanoid_sword_shield_args.txt",
    "ase_heading_humanoid_sword_shield": "ase_heading_humanoid_sword_shield_args.txt",
    "ase_location_humanoid_sword_shield": "ase_location_humanoid_sword_shield_args.txt",
    "ase_reach_humanoid_sword_shield": "ase_reach_humanoid_sword_shield_args.txt",
    "ase_strike_humanoid_sword_shield": "ase_strike_humanoid_sword_shield_args.txt",
}

HLC_CASES = {
    "ase_heading_humanoid_sword_shield",
    "ase_location_humanoid_sword_shield",
    "ase_reach_humanoid_sword_shield",
    "ase_strike_humanoid_sword_shield",
}

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
    root = Path(root_out)
    if root.is_absolute():
        return root.resolve()
    return (TRAIN_ROOT / root_out).resolve()


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def safe_path(path: Path) -> str:
    return str(path.resolve()) if path.exists() else ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root-out", required=True, help="ASE root name under output/train or absolute path")
    ap.add_argument("--output", default="", help="Output TSV path, default: <root>/best_by_case.tsv")
    args = ap.parse_args()

    root_dir = resolve_root(args.root_out)
    status_path = root_dir / "keepalive_status.json"
    status = read_json(status_path)
    if not status:
        raise SystemExit(f"[ERROR] missing or invalid keepalive status: {status_path}")

    case_rows = status.get("cases", {})
    if not isinstance(case_rows, dict) or not case_rows:
        raise SystemExit(f"[ERROR] no cases in keepalive status: {status_path}")

    llc_model_file = str((case_rows.get("ase_humanoid_sword_shield", {}) or {}).get("latest_model", "")).strip()

    rows: list[dict[str, str]] = []
    for case_key, arg_file in CASE_TO_ARG.items():
        row = case_rows.get(case_key, {})
        if not isinstance(row, dict):
            continue

        latest_model = str(row.get("latest_model", "")).strip()
        if not latest_model:
            continue

        model_path = Path(latest_model)
        out_dir = model_path.parent

        env_cfg = out_dir / "env_config.yaml"
        engine_cfg = out_dir / "engine_config.yaml"
        agent_cfg = out_dir / "agent_config.yaml"
        variant = out_dir.name
        status_text = str(row.get("status", "")).strip().lower()
        final_ok = "1" if status_text.startswith("completed") else "0"

        rows.append(
            {
                "case": arg_file,
                "method": "ase_keepalive_summary",
                "case_type": "trainable",
                "variant": variant,
                "agent_config": safe_path(agent_cfg),
                "num_envs": "",
                "final_ok": final_ok,
                "note": "auto_generated_from_keepalive_status",
                "out_dir": safe_path(out_dir),
                "long_out_dir": safe_path(out_dir),
                "model_file": safe_path(model_path),
                "env_config": safe_path(env_cfg),
                "engine_config": safe_path(engine_cfg),
                "llc_model_file": llc_model_file if case_key in HLC_CASES else "",
                "motion_id": "",
                "motion_file": "",
                "source_pack": root_dir.name,
                "category": case_key,
                "train_enabled": "true",
                "view_enabled": "true",
            }
        )

    if not rows:
        raise SystemExit("[ERROR] no rows generated from keepalive_status.json")

    output_path = Path(args.output).resolve() if args.output else (root_dir / "best_by_case.tsv")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=FIELDS, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    print(f"[DONE] wrote {output_path} rows={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
