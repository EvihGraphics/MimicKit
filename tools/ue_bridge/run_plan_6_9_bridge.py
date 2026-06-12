#!/usr/bin/env python3
"""Run PLAN-6-9 gates without allowing a previous-gate bypass."""

from __future__ import annotations

import argparse
import json
import shutil
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
DEFAULT_FRAMEWORK_PYTHON = Path("/root/miniconda3/envs/evihanimation-mimickit-bridge/bin/python")
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
GENERATION_GATES = ("white-knight-smoke", "white-knight", "walk-exact", "stop-exact")
REVIEW_PROMOTION_GATE = "promote-review"
FRAMEWORK_PREFLIGHT_GATE = "framework-preflight"
FRAMEWORK_RENDER_GATE = "framework-render"


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


def preflight_report(
    evih_worktree: Path,
    python: Path,
    framework_python: Path = DEFAULT_FRAMEWORK_PYTHON,
) -> dict[str, Any]:
    baseline = read_json(BASELINE_SNAPSHOT)
    required_paths = {
        "python": python,
        "powershell": Path(shutil.which("powershell.exe") or shutil.which("pwsh") or "/__missing__/powershell"),
        "ffmpeg": Path(shutil.which("ffmpeg") or "/__missing__/ffmpeg"),
        "ffprobe": Path(shutil.which("ffprobe") or "/__missing__/ffprobe"),
        "windows_native_workspace": Path("/mnt/d/MimicKitNative/workspace/MimicKit"),
        "white_knight_builder": ROOT / "tools" / "ue_bridge" / "build_mimickit_mesh_reference.py",
        "exact_builder": ROOT / "tools" / "ue_bridge" / "build_mimickit_exact_mesh_reference.py",
        "white_knight_native_script": ROOT / "tools" / "windows" / "build_white_knight_mesh_reference_native.ps1",
        "exact_native_script": ROOT / "tools" / "windows" / "build_exact_mesh_reference_native.ps1",
        "evih_builder": evih_worktree / "Demos" / "MimicKitReplay" / "build_visual_results.py",
        "evih_replay": evih_worktree / "ai4animation" / "Standalone" / "MimicKitSkeletonReplay.py",
        "framework_python": framework_python,
        "framework_capture": evih_worktree / "Demos" / "MimicKitReplay" / "framework_capture.py",
        "walk_model": TRAIN_ROOT / CASES["walk-exact"]["source_root"] / CASES["walk-exact"]["source_stage"] / "model.pt",
        "walk_agent": TRAIN_ROOT / CASES["walk-exact"]["source_root"] / CASES["walk-exact"]["source_stage"] / "agent_config.yaml",
        "walk_env": TRAIN_ROOT / CASES["walk-exact"]["source_root"] / CASES["walk-exact"]["source_stage"] / "env_config.yaml",
        "stop_model": TRAIN_ROOT / CASES["stop-exact"]["source_root"] / CASES["stop-exact"]["source_stage"] / "model.pt",
        "stop_agent": TRAIN_ROOT / CASES["stop-exact"]["source_root"] / CASES["stop-exact"]["source_stage"] / "agent_config.yaml",
        "stop_env": TRAIN_ROOT / CASES["stop-exact"]["source_root"] / CASES["stop-exact"]["source_stage"] / "env_config.yaml",
    }
    checks = {f"{name}_exists": path.exists() for name, path in required_paths.items()}
    branch_result = run_command(["git", "branch", "--show-current"], cwd=evih_worktree) if evih_worktree.is_dir() else {"ok": False, "stdout_tail": ""}
    branch = str(branch_result.get("stdout_tail", "")).strip()
    checks["evih_v3_branch"] = branch == "codex/mimickit-bridge-v3"
    checks["preserved_geom_baseline_pass"] = bool(baseline.get("baseline_protection_pass"))
    framework_environment = (
        run_command(
            [
                str(framework_python),
                str(required_paths["framework_capture"]),
                "--package-dir",
                str(ROOT),
                "--mesh-asset",
                str(ROOT),
                "--scene-contract",
                str(ROOT),
                "--out-dir",
                str(BRIDGE_ROOT / "_framework_preflight"),
                "--environment-only",
            ],
            cwd=evih_worktree,
        )
        if framework_python.is_file() and required_paths["framework_capture"].is_file()
        else {"ok": False, "stdout_tail": "", "stderr_tail": ""}
    )
    checks["framework_environment_available"] = bool(framework_environment.get("ok"))
    blockers = [f"preflight_failed:{name}" for name, passed in checks.items() if not passed]
    return {
        "schema_version": 1,
        "preflight_pass": not blockers,
        "checks": checks,
        "blockers": blockers,
        "evih_worktree": str(evih_worktree),
        "evih_branch": branch,
        "baseline_snapshot": str(BASELINE_SNAPSHOT),
        "required_paths": {name: str(path) for name, path in required_paths.items()},
        "framework_environment": framework_environment,
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


def next_gate_status(evih_worktree: Path) -> tuple[str, str]:
    for case_name in ("white-knight", "walk-exact", "stop-exact"):
        blocker = prerequisite_blocker(case_name, evih_worktree)
        if blocker:
            return case_name, blocker
        case_manifest = read_json(case_paths(case_name, evih_worktree)["case_manifest"])
        if not case_manifest.get("case_acceptance_pass"):
            return case_name, f"gate_not_accepted:{case_name}"
    return "aggregate", ""


def source_build_command(case_name: str, python: Path) -> list[str]:
    case = CASES[case_name]
    common = [
        str(python),
        str(ROOT / "tools" / "ue_bridge" / (
            "build_mimickit_mesh_reference.py"
            if case_name in {"white-knight-smoke", "white-knight"}
            else "build_mimickit_exact_mesh_reference.py"
        )),
    ]
    if case_name in {"white-knight-smoke", "white-knight"}:
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


def evih_build_command(
    case_name: str,
    evih_worktree: Path,
    python: Path,
    *,
    framework_api: bool = False,
    framework_python: Path = DEFAULT_FRAMEWORK_PYTHON,
) -> list[str]:
    case = CASES[case_name]
    paths = case_paths(case_name, evih_worktree)
    manifest = read_json(paths["mimic_manifest"])
    package = Path(str((manifest.get("package_export") or {}).get("package_dir", "")))
    asset = Path(str((manifest.get("asset_export") or {}).get("glb_file", "")))
    scene = Path(str((manifest.get("render_summary") or {}).get("scene_contract_v3_file", "")))
    result_root = paths["evih_manifest"].parent
    command = [
        str(python), str(evih_worktree / "Demos" / "MimicKitReplay" / "build_visual_results.py"),
        "--package-dir", str(package), "--out-dir", str(result_root), "--label", case["evih_result"],
        "--frames", "300", "--stride", "5", "--fps", "12", "--width", "960", "--height", "540",
        "--skip-skeleton", "--skip-character-geom", "--true-mesh",
        "--mesh-asset", str(asset), "--mesh-reference-manifest", str(paths["mimic_manifest"]),
        "--scene-contract", str(scene),
    ]
    if framework_api:
        command.extend(["--framework-api", "--framework-python", str(framework_python)])
    return command


def review_promotion_command(
    case_name: str,
    evih_worktree: Path,
    python: Path,
    framework_python: Path = DEFAULT_FRAMEWORK_PYTHON,
) -> list[str]:
    """Revalidate a signed review against existing evidence without regenerating it."""
    command = evih_build_command(
        case_name,
        evih_worktree,
        python,
        framework_api=True,
        framework_python=framework_python,
    )
    command.append("--review-only")
    return command


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
    parser.add_argument(
        "--gate",
        choices=("preflight", FRAMEWORK_PREFLIGHT_GATE, "status", *GENERATION_GATES, FRAMEWORK_RENDER_GATE, REVIEW_PROMOTION_GATE, "aggregate"),
        default="status",
    )
    parser.add_argument(
        "--case",
        choices=GENERATION_GATES,
        help="Existing case to revalidate when --gate promote-review is used.",
    )
    parser.add_argument("--evih-worktree", type=Path, default=DEFAULT_EVIH_WORKTREE)
    parser.add_argument("--python", type=Path, default=DEFAULT_PYTHON)
    parser.add_argument("--framework-python", type=Path, default=DEFAULT_FRAMEWORK_PYTHON)
    args = parser.parse_args()
    evih_worktree = args.evih_worktree.resolve()
    python = args.python.resolve()
    framework_python = args.framework_python.resolve()
    execution: dict[str, Any] = {"schema_version": 1, "requested_gate": args.gate, "commands": [], "blockers": []}
    execution["preflight"] = preflight_report(evih_worktree, python, framework_python)
    if args.gate in {"preflight", FRAMEWORK_PREFLIGHT_GATE}:
        execution["blockers"] = execution["preflight"]["blockers"]
        write_execution_manifest(execution)
        print(json.dumps(execution, indent=2, ensure_ascii=False))
        return 0 if execution["preflight"]["preflight_pass"] else 5
    if not execution["preflight"]["preflight_pass"]:
        execution["blockers"] = execution["preflight"]["blockers"]
        write_execution_manifest(execution)
        print(json.dumps(execution, indent=2, ensure_ascii=False))
        return 5

    smoke_report = refresh_case("white-knight-smoke", evih_worktree)
    execution["smoke_case"] = smoke_report
    if args.gate == REVIEW_PROMOTION_GATE:
        if not args.case:
            execution["blockers"] = ["promote_review_requires_case"]
            write_execution_manifest(execution)
            print(json.dumps(execution, indent=2, ensure_ascii=False))
            return 3
        blocker = prerequisite_blocker(args.case, evih_worktree)
        if blocker:
            execution["blockers"] = [blocker]
            write_execution_manifest(execution)
            print(json.dumps(execution, indent=2, ensure_ascii=False))
            return 3
        paths = case_paths(args.case, evih_worktree)
        if not paths["mimic_manifest"].is_file():
            execution["blockers"] = [f"review_promotion_source_missing:{args.case}"]
            write_execution_manifest(execution)
            print(json.dumps(execution, indent=2, ensure_ascii=False))
            return 3
        review_result = run_command(
            review_promotion_command(args.case, evih_worktree, python, framework_python),
            cwd=evih_worktree,
        )
        execution["commands"].append(review_result)
        report = refresh_case(args.case, evih_worktree)
        execution["case"] = report
        execution["blockers"] = report.get("blockers", [])
        execution["review_promotion_pass"] = bool(report.get("case_acceptance_pass"))
        execution["next_gate"], execution["next_gate_blocker"] = next_gate_status(evih_worktree)
        if execution["next_gate_blocker"]:
            execution["blockers"] = list(dict.fromkeys([*execution["blockers"], execution["next_gate_blocker"]]))
        write_execution_manifest(execution)
        print(json.dumps(execution, indent=2, ensure_ascii=False))
        return 0 if execution["review_promotion_pass"] else 2
    if args.gate == "status":
        execution["blockers"] = smoke_report.get("blockers", [])
        execution["next_gate"], execution["next_gate_blocker"] = next_gate_status(evih_worktree)
        if execution["next_gate_blocker"]:
            execution["blockers"] = list(dict.fromkeys([*execution["blockers"], execution["next_gate_blocker"]]))
        write_execution_manifest(execution)
        print(json.dumps(execution, indent=2, ensure_ascii=False))
        return 0 if smoke_report.get("case_acceptance_pass") else 2

    if args.gate == FRAMEWORK_RENDER_GATE:
        if not args.case or args.case == "white-knight-smoke":
            execution["blockers"] = ["framework_render_requires_final_case"]
            write_execution_manifest(execution)
            print(json.dumps(execution, indent=2, ensure_ascii=False))
            return 3
        blocker = prerequisite_blocker(args.case, evih_worktree)
        if blocker:
            execution["blockers"] = [blocker]
            write_execution_manifest(execution)
            print(json.dumps(execution, indent=2, ensure_ascii=False))
            return 3
        result = run_command(
            evih_build_command(
                args.case,
                evih_worktree,
                python,
                framework_api=True,
                framework_python=framework_python,
            ),
            cwd=evih_worktree,
        )
        execution["commands"].append(result)
        report = refresh_case(args.case, evih_worktree)
        execution["case"] = report
        execution["blockers"] = report.get("blockers", [])
        execution["framework_render_automatic_pass"] = bool(
            report.get("checks", {}).get("evih_framework_api_replay_pass")
            and report.get("checks", {}).get("framework_visual_metric_pass")
            and report.get("checks", {}).get("framework_media_ok")
        )
        write_execution_manifest(execution)
        print(json.dumps(execution, indent=2, ensure_ascii=False))
        return 0 if execution["framework_render_automatic_pass"] else 2

    if args.gate in GENERATION_GATES:
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
    execution["next_gate"], execution["next_gate_blocker"] = next_gate_status(evih_worktree)
    if execution["next_gate_blocker"]:
        execution["blockers"] = list(dict.fromkeys([*execution["blockers"], execution["next_gate_blocker"]]))
    write_execution_manifest(execution)
    print(json.dumps(execution, indent=2, ensure_ascii=False))
    return 0 if full_chain.get("full_chain_bridge_pass") else 2


if __name__ == "__main__":
    raise SystemExit(main())
