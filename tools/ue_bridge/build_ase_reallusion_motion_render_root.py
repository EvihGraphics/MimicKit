#!/usr/bin/env python3
"""Generate a synthetic MimicKit render root for ASE white-knight motion coverage."""

from __future__ import annotations

import argparse
import copy
import csv
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TRAIN_ROOT = ROOT / "output" / "train"
DEFAULT_MANIFEST = ROOT / "data" / "motions" / "reallusion" / "ase_reallusion_sword_shield_manifest.tsv"
DEFAULT_BASE_ENV = ROOT / "data" / "envs" / "view_motion_humanoid_sword_shield_env.yaml"
DEFAULT_ENGINE = ROOT / "data" / "engines" / "newton_engine.yaml"
DEFAULT_CASE = "view_motion_humanoid_sword_shield_args.txt"

BEST_BY_CASE_FIELDS = [
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


def resolve_path(path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path.resolve()
    return (ROOT / path).resolve()


def parse_csv_list(text: str) -> list[str]:
    out: list[str] = []
    for token in text.split(","):
        curr = token.strip()
        if curr:
            out.append(curr)
    return out


def read_manifest(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fp:
        rows = list(csv.DictReader(fp, delimiter="\t"))

    required = {"motion_id", "file", "source_pack", "category", "train_enabled", "view_enabled"}
    if not rows:
        raise RuntimeError(f"manifest is empty: {path}")
    missing = required.difference(rows[0].keys())
    if missing:
        raise RuntimeError(f"manifest missing columns {sorted(missing)}: {path}")
    return rows


def read_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError(f"expected mapping yaml: {path}")
    return data


def write_tsv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def parse_args() -> argparse.Namespace:
    default_root_name = "case_ase_reallusion_motion_library_" + datetime.now().strftime("%Y%m%d_%H%M%S")

    parser = argparse.ArgumentParser(description="Build a synthetic output/train root for ASE white-knight per-clip renders")
    parser.add_argument("--train-root", default=str(DEFAULT_TRAIN_ROOT))
    parser.add_argument("--root-name", default=default_root_name)
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--base-env-config", default=str(DEFAULT_BASE_ENV))
    parser.add_argument("--engine-config", default=str(DEFAULT_ENGINE))
    parser.add_argument("--case", default=DEFAULT_CASE)
    parser.add_argument("--motion-ids", default="")
    parser.add_argument("--include-non-view-enabled", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    return args


def main() -> int:
    args = parse_args()

    train_root = resolve_path(args.train_root)
    manifest_path = resolve_path(args.manifest)
    base_env_path = resolve_path(args.base_env_config)
    engine_path = resolve_path(args.engine_config)
    out_root = (train_root / args.root_name).resolve()

    if out_root.exists():
        if not args.force:
            raise RuntimeError(f"output root already exists: {out_root}")
        shutil.rmtree(out_root)

    rows = read_manifest(manifest_path)
    base_env = read_yaml(base_env_path)

    selected_ids = set(parse_csv_list(args.motion_ids))
    case_stem = args.case.replace(".txt", "")
    generated_env_dir = out_root / "generated_envs"
    generated_rows: list[dict[str, Any]] = []

    for row in rows:
        motion_id = str(row["motion_id"]).strip()
        motion_file = str(row["file"]).strip()
        source_pack = str(row["source_pack"]).strip()
        category = str(row["category"]).strip()
        train_enabled = str(row["train_enabled"]).strip().lower()
        view_enabled = str(row["view_enabled"]).strip().lower()

        if selected_ids and motion_id not in selected_ids:
            continue
        if view_enabled != "true" and not args.include_non_view_enabled:
            continue

        motion_path = resolve_path(motion_file)
        if not motion_path.exists():
            raise FileNotFoundError(f"motion file not found: {motion_path}")

        env_data = copy.deepcopy(base_env)
        env_data["motion_file"] = str(motion_path)
        env_path = generated_env_dir / f"{motion_id}.yaml"
        env_path.parent.mkdir(parents=True, exist_ok=True)
        env_path.write_text(yaml.safe_dump(env_data, sort_keys=False), encoding="utf-8")

        run_dir = (out_root / "runs" / case_stem / motion_id).resolve()
        generated_rows.append(
            {
                "case": args.case,
                "method": "ase_motion_library",
                "case_type": "nontrainable",
                "variant": motion_id,
                "agent_config": "",
                "num_envs": "1",
                "final_ok": "1",
                "note": "ase_reallusion_manifest_generated",
                "out_dir": str(run_dir),
                "long_out_dir": str(run_dir),
                "model_file": "",
                "env_config": str(env_path),
                "engine_config": str(engine_path),
                "llc_model_file": "",
                "motion_id": motion_id,
                "motion_file": motion_file,
                "source_pack": source_pack,
                "category": category,
                "train_enabled": train_enabled,
                "view_enabled": view_enabled,
            }
        )

    if not generated_rows:
        raise RuntimeError("no manifest rows selected")

    write_tsv(out_root / "best_by_case.tsv", generated_rows, BEST_BY_CASE_FIELDS)

    summary = {
        "root": out_root.name,
        "generated_count": len(generated_rows),
        "manifest": str(manifest_path),
        "base_env_config": str(base_env_path),
        "engine_config": str(engine_path),
        "case": args.case,
        "motion_ids_filter": sorted(selected_ids),
    }
    (out_root / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[OK] root={out_root}")
    print(f"[OK] generated_rows={len(generated_rows)}")
    print(f"[OK] best_by_case={out_root / 'best_by_case.tsv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
