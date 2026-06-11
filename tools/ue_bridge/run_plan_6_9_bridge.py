#!/usr/bin/env python3
"""Run PLAN-6-9 gates without allowing a previous-gate bypass."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from build_full_chain_bridge_manifest import case_report, write_case_manifest
from build_mimickit_mesh_reference import finalize_manifest_gate_fields
from visual_bridge_validation import write_json


ROOT = Path(__file__).resolve().parents[2]
TRAIN_ROOT = ROOT / "output" / "train"
IMG_ROOT = ROOT / "output" / "img"
DEFAULT_EVIH_WORKTREE = Path("/mnt/d/AnimationTech-learning/EvihAnimation-mimickit-bridge-v3")
DEFAULT_PYTHON = Path("/root/miniconda3/envs/mimickit/bin/python")
BRIDGE_ROOT = IMG_ROOT / "mimickit_evih_bridge_v3"
BASELINE_SNAPSHOT = IMG_ROOT / "mimickit_evih_bridge_v2" / "baseline_snapshot.json"

CASES: dict[str, dict[str, str]] = {
    "white-knight-smoke": {
        "label": "white-knight-smoke",
        "mimic_root": "tmp_white_knight_mesh_reference_20260611_bridge_smoke_v3",
        "evih_result": "white_knight_mesh_replay_v3_smoke",
    },
    "white-knight": {
        "label": "white-knight",
        "mimic_root": "tmp_white_knight_mesh_reference_20260611_bridge_full_v3",
        "evih_result": "white_knight_mesh_replay_v3",
    },
    "walk-exact": {
        "label": "walk-exact",
        "mimic_root": "amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637_long_train_exact_mesh_v3",
        "evih_result": "walk_exact_mesh_replay_v3",
        "source_root": "amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637",
        "source_stage": "long_train",
    },
    "stop-exact": {
        "label": "stop-exact",
        "mimic_root": "amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01_probe_train_exact_mesh_v3",
        "evih_result": "stop_exact_mesh_replay_v3",
        "source_root": "amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01",
        "source_stage": "probe_train",
    },
}

PREREQUISITES = {
    "white-knight": "white-knight-smoke",
    "walk-exact": "white-knight",
    "stop-exact": "walk-exact",
}


def read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def run_command(command: list[str], *, cwd: Path) -> dict[str, Any]:
    process = subprocess.run(
        command,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return {
        "command": command,
        "cwd": str(cwd),
        "returncode": int(process.returncode),
        "stdout_tail": process.stdout[-4000:],
        "stderr_tail": process.stderr[-4000:],
        "ok": process.returncode == 0,
    }


def case_paths(case_name: str, evih_worktree: Path) -> dict[str, Path]:
    case = CASES[case_name]
    mimic_root = TRAIN_ROOT / case["mimic_root"]
    evih_root = evih_worktree / "Demos" / "MimicKitReplay" / "results" / case["evih_result"]
    return {
        "mimic_manifest": mimic_root / "mesh_reference_manifest.json",
        "case_manifest": mimic_root / "bridge_case_manifest.json",
        "evih_manifest": evih_root / "visual_result_manifest.json",
        "review": evih_root / "evih_mesh_replay" / "visual_review.json",
    }


def refresh_case(case_name: str, evih_worktree: Path) -> dict[str, Any]:
    paths = case_paths(case_name, evih_worktree)
    mimic = read_json(paths["mimic_manifest"])
    if mimic:
        finalize_manifest_gate_fields(mimic)
        write_json(paths["mimic_manifest"], mimic)
        image_manifest = IMG_ROOT / CASES[case_name]["mimic_root"] / "mesh_reference_manifest.json"
        if image_manifest.is_file():
            write_json(image_manifest, mimic)
    report = case_report(
        {
            "label": CASES[case_name]["label"],
            "mimic": paths["mimic_manifest"],
            "evih": paths["evih_manifest"],
            "review": paths["review"],
        }
    )
    write_case_manifest(report, paths["mimic_manifest"])
    return report


def prerequisite_blocker(case_name: str, evih_worktree: Path) -> str:
    predecessor = PREREQUISITES.get(case_name)
    if not predecessor:
        return ""
    predecessor_manifest = read_json(case_paths(predecessor, evih_worktree)["case_manifest"])
    if not predecessor_manifest.get("case_acceptance_pass"):
        return f"previous_gate_not_accepted:{predecessor}"
    return ""


def source_build_command(case_name: str, python: Path) -> list[str]:
    case = CASES[case_name]
    common = [
        str(python),
        str(ROOT / "tools" / "ue_bridge" / (
            "build_mimickit_mesh_reference.py" if case_name == "white-knight" else "build_mimickit_exact_mesh_reference.py"
        )),
    ]
    if case_name == "white-knight":
        return common + [
            "--run-native-windows", "--root-name", case["mimic_root"],
            "--frames", "300", "--frame-stride", "5", "--mp4-fps", "12",
            "--width", "960", "--height", "540", "--device", "cuda:0", "--num-envs", "1",
            "--seed", "7", "--force-root",
        ]
    return common + [
        "--run-native-windows", "--source-root", case["source_root"], "--stage", case["source_stage"],
        "--root-name", case["mimic_root"], "--frames", "300", "--frame-stride", "5", "--mp4-fps", "12",
        "--width", "960", "--height", "540", "--device", "cuda:0", "--num-envs", "1",
        "--seed", "7", "--force-root",
    ]


def evih_build_command(case_name: str, evih_worktree: Path, python: Path) -> list[str]:
    case = CASES[case_name]
    paths = case_paths(case_name, evih_worktree)
    manifest = read_json(paths["mimic_manifest"])
    package = Path(str((manifest.get("package_export") or {}).get("package_dir", "")))
    asset = Path(str((manifest.get("asset_export") or {}).get("glb_file", "")))
    scene = Path(str((manifest.get("render_summary") or {}).get("scene_contract_v3_file", "")))
    result_root = paths["evih_manifest"].parent
    return [
        str(python), str(evih_worktree / "Demos" / "MimicKitReplay" / "build_visual_results.py"),
        "--package-dir", str(package), "--out-dir", str(result_root), "--label", case["evih_result"],
        "--frames", "300", "--stride", "5", "--fps", "12", "--width", "960", "--height", "540",
        "--skip-skeleton", "--skip-character-geom", "--true-mesh",
        "--mesh-asset", str(asset), "--mesh-reference-manifest", str(paths["mimic_manifest"]),
        "--scene-contract", str(scene),
    ]


def aggregate_command(evih_worktree: Path, python: Path) -> list[str]:
    command = [
        str(python), str(ROOT / "tools" / "ue_bridge" / "build_full_chain_bridge_manifest.py"),
        "--baseline-snapshot", str(BASELINE_SNAPSHOT),
        "--out", str(BRIDGE_ROOT / "full_chain_bridge_manifest.json"),
    ]
    for case_name in ("white-knight", "walk-exact", "stop-exact"):
        paths = case_paths(case_name, evih_worktree)
        if paths["mimic_manifest"].is_file() or paths["evih_manifest"].is_file() or paths["review"].is_file():
            command.extend(
                [
                    "--case",
                    f"label={case_name},mimic={paths['mimic_manifest']},evih={paths['evih_manifest']},review={paths['review']}",
                ]
            )
    return command


def write_execution_manifest(data: dict[str, Any]) -> None:
    data["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
    write_json(BRIDGE_ROOT / "plan_6_9_execution_manifest.json", data)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gate", choices=("status", "white-knight", "walk-exact", "stop-exact", "aggregate"), default="status")
    parser.add_argument("--evih-worktree", type=Path, default=DEFAULT_EVIH_WORKTREE)
    parser.add_argument("--python", type=Path, default=DEFAULT_PYTHON)
    args = parser.parse_args()
    evih_worktree = args.evih_worktree.resolve()
    python = args.python.resolve()
    execution: dict[str, Any] = {"schema_version": 1, "requested_gate": args.gate, "commands": [], "blockers": []}

    smoke_report = refresh_case("white-knight-smoke", evih_worktree)
    execution["smoke_case"] = smoke_report
    if args.gate == "status":
        execution["blockers"] = smoke_report.get("blockers", [])
        write_execution_manifest(execution)
        print(json.dumps(execution, indent=2, ensure_ascii=False))
        return 0 if smoke_report.get("case_acceptance_pass") else 2

    if args.gate in PREREQUISITES:
        blocker = prerequisite_blocker(args.gate, evih_worktree)
        if blocker:
            execution["blockers"] = [blocker]
            write_execution_manifest(execution)
            print(json.dumps(execution, indent=2, ensure_ascii=False))
            return 3
        source_result = run_command(source_build_command(args.gate, python), cwd=ROOT)
        execution["commands"].append(source_result)
        if not source_result["ok"]:
            execution["blockers"] = ["mimickit_source_build_failed"]
            write_execution_manifest(execution)
            print(json.dumps(execution, indent=2, ensure_ascii=False))
            return 4
        evih_result = run_command(evih_build_command(args.gate, evih_worktree, python), cwd=evih_worktree)
        execution["commands"].append(evih_result)
        report = refresh_case(args.gate, evih_worktree)
        execution["case"] = report
        execution["blockers"] = report.get("blockers", [])

    aggregate_result = run_command(aggregate_command(evih_worktree, python), cwd=ROOT)
    execution["commands"].append(aggregate_result)
    full_chain = read_json(BRIDGE_ROOT / "full_chain_bridge_manifest.json")
    execution["full_chain"] = full_chain
    execution["blockers"] = list(dict.fromkeys([*execution["blockers"], *full_chain.get("blockers", [])]))
    write_execution_manifest(execution)
    print(json.dumps(execution, indent=2, ensure_ascii=False))
    return 0 if full_chain.get("full_chain_bridge_pass") else 2


if __name__ == "__main__":
    raise SystemExit(main())
