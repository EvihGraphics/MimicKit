#!/usr/bin/env python3
"""Build an exact AMP-root USD mesh reference without modifying the source root."""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from visual_bridge_validation import validate_body_world_replay

from build_mimickit_mesh_reference import (
    body_order_from_mjcf,
    build_contact_sheet,
    expected_image_count,
    finalize_manifest_gate_fields,
    localize_native_manifest_paths,
    sha256_file,
)


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TRAIN_ROOT = ROOT / "output" / "train"
DEFAULT_IMG_ROOT = ROOT / "output" / "img"
DEFAULT_USD = ROOT / "data" / "assets" / "sword_shield" / "humanoid_sword_shield.usd"
DEFAULT_XML = ROOT / "data" / "assets" / "sword_shield" / "humanoid_sword_shield.xml"
DEFAULT_ENGINE = ROOT / "data" / "engines" / "isaac_lab_engine.yaml"
DEFAULT_WINDOWS_WORKSPACE_ROOT = "D:\\MimicKitNative"
DEFAULT_WINDOWS_WORKSPACE_WSL = Path("/mnt/d/MimicKitNative/workspace/MimicKit")
DEFAULT_WINDOWS_CONDA_ENV = "D:\\MimicKitNative\\conda\\mimickit-isaaclab-win"

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


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def write_tsv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=BEST_BY_CASE_FIELDS, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def run_command(cmd: list[str], env: dict[str, str] | None = None) -> dict[str, Any]:
    proc = subprocess.run(
        cmd,
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    return {
        "cmd": cmd,
        "returncode": int(proc.returncode),
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
        "ok": proc.returncode == 0,
    }


def copy_tree(src: Path, dst: Path) -> dict[str, Any]:
    if not src.exists():
        return {"ok": False, "src": str(src), "dst": str(dst), "error": "source missing"}
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    return {"ok": True, "src": str(src), "dst": str(dst)}


def sync_native_workspace_scripts(args: argparse.Namespace) -> dict[str, Any]:
    workspace = Path(args.windows_workspace_wsl).resolve()
    if not workspace.exists():
        return {"ok": False, "workspace": str(workspace), "error": "windows workspace missing"}
    rel_paths = [
        "tools/ue_bridge/build_mimickit_exact_mesh_reference.py",
        "tools/ue_bridge/build_mimickit_mesh_reference.py",
        "tools/ue_bridge/_bridge_common.py",
        "tools/ue_bridge/build_mimickit_render_sequences.py",
        "tools/ue_bridge/visual_bridge_validation.py",
        "tools/ue_bridge/run_mimic_visual_case.py",
        "tools/ue_bridge/build_mimickit_source_rig_asset_spec.py",
        "tools/ue_bridge/omni/metrics/assembler/core.py",
        "mimickit/engines/isaac_lab_engine.py",
        "mimickit/envs/char_env.py",
        "mimickit/engines/engine.py",
        "mimickit/engines/newton_engine.py",
        "tools/windows/export_usd_to_gltf_asset.py",
        "tools/windows/build_exact_mesh_reference_native.ps1",
    ]
    copied: list[dict[str, str]] = []
    missing: list[str] = []
    for rel in rel_paths:
        src = ROOT / rel
        dst = workspace / rel
        if not src.exists():
            missing.append(rel)
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied.append({"src": str(src), "dst": str(dst)})
    return {"ok": not missing, "workspace": str(workspace), "copied": copied, "missing": missing}


def run_windows_native_reference(args: argparse.Namespace, root_name: str, source_root_arg: str) -> dict[str, Any]:
    powershell = shutil.which("powershell.exe") or shutil.which("pwsh") or ""
    if not powershell:
        return {"ok": False, "error": "powershell.exe/pwsh not found"}
    script = ROOT / "tools" / "windows" / "build_exact_mesh_reference_native.ps1"
    cmd = [
        powershell,
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script),
        "-WorkspaceRoot",
        args.windows_workspace_root,
        "-CondaEnvName",
        args.windows_conda_env,
        "-SourceRoot",
        source_root_arg,
        "-Stage",
        args.stage,
        "-RootName",
        root_name,
        "-Frames",
        str(args.frames),
        "-FrameStride",
        str(args.frame_stride),
        "-Mp4Fps",
        str(args.mp4_fps),
        "-Device",
        args.device,
        "-NumEnvs",
        str(args.num_envs),
        "-Seed",
        str(args.seed),
    ]
    if args.case:
        cmd.extend(["-Case", args.case])
    if args.force_root:
        cmd.append("-ForceRoot")
    if args.skip_asset_export:
        cmd.append("-SkipAssetExport")
    return run_command(cmd)


def ingest_windows_outputs(args: argparse.Namespace, root_name: str) -> dict[str, Any]:
    workspace = Path(args.windows_workspace_wsl).resolve()
    native_train = workspace / "output" / "train" / root_name
    native_img = workspace / "output" / "img" / root_name
    train_result = copy_tree(native_train, Path(args.train_root) / root_name)
    img_result = copy_tree(native_img, Path(args.img_root) / root_name)
    ok = bool(train_result.get("ok")) and bool(img_result.get("ok"))
    return {
        "ok": ok,
        "windows_workspace_wsl": str(workspace),
        "train": train_result,
        "img": img_result,
    }


def write_manifest(args: argparse.Namespace, root_name: str, manifest: dict[str, Any]) -> None:
    finalize_manifest_gate_fields(manifest)
    write_json(Path(args.train_root) / root_name / "mesh_reference_manifest.json", manifest)
    write_json(Path(args.img_root) / root_name / "mesh_reference_manifest.json", manifest)


def native_source_root_arg(source_root: Path, train_root: Path) -> str:
    try:
        source_root.relative_to(train_root)
        return source_root.name
    except ValueError:
        return str(source_root)


def infer_case(source_root: Path, source_stage: Path, explicit_case: str) -> str:
    if explicit_case:
        return explicit_case if explicit_case.endswith(".txt") else f"{explicit_case}.txt"
    render_meta = ROOT / "output" / "img" / source_root.name / source_stage.name / "render" / "render_meta.json"
    meta = read_json(render_meta)
    if meta.get("case"):
        return str(meta["case"])
    env = read_yaml(source_stage / "env_config.yaml")
    probe = f"{source_root.name} {env.get('env_name', '')}".lower()
    if "stop" in probe:
        return "amp_stop_humanoid_sword_shield_args.txt"
    return "amp_location_humanoid_sword_shield_args.txt"


def collect_frame_ids(frames_dir: Path) -> list[int]:
    out: list[int] = []
    for path in sorted(frames_dir.glob("frame_*.png")):
        try:
            out.append(int(path.stem.split("_")[-1]))
        except ValueError:
            pass
    return out


def summarize_render(args: argparse.Namespace, root_name: str) -> dict[str, Any]:
    render_dir = Path(args.img_root) / root_name / args.stage / "render"
    render_meta = read_json(render_dir / "render_meta.json")
    frames_dir = render_dir / "frames"
    silhouettes_dir = render_dir / "silhouettes"
    ground_masks_dir = render_dir / "ground_masks"
    frame_ids = collect_frame_ids(frames_dir)
    silhouette_ids = collect_frame_ids(silhouettes_dir)
    ground_mask_ids = collect_frame_ids(ground_masks_dir)
    mp4_file = render_dir / "render.mp4"
    scene_contract_path = render_dir / "scene_contract_v3.json"
    scene_contract_v3 = read_json(scene_contract_path)
    expected = expected_image_count(args.frames, args.frame_stride)
    expected_frame_ids = list(range(0, int(args.frames), max(1, int(args.frame_stride))))
    status = str(render_meta.get("status", ""))
    visual_kind = str(render_meta.get("visual_kind", ""))
    mesh_detected = bool(int(render_meta.get("mesh_detected", 0) or 0))
    image_count = int(render_meta.get("image_count", 0) or 0)
    mp4_ok = bool(int(render_meta.get("mp4_ok", 0) or 0)) if "mp4_ok" in render_meta else mp4_file.exists()
    legacy_ppm_count = len(list(frames_dir.glob("frame_*.ppm")))
    pass_ok = bool(
        status in {"ok", "skipped_resume"}
        and visual_kind == "mesh"
        and mesh_detected
        and image_count >= expected
        and frame_ids == expected_frame_ids
        and silhouette_ids == expected_frame_ids
        and ground_mask_ids == expected_frame_ids
        and mp4_ok
        and bool(render_meta.get("motion_visible"))
        and bool(scene_contract_v3.get("scene_contract_sha256"))
        and mp4_file.exists()
        and mp4_file.stat().st_size > 0
    )
    return {
        "render_dir": str(render_dir),
        "render_meta": str(render_dir / "render_meta.json"),
        "status": status,
        "visual_kind": visual_kind,
        "mesh_detected": mesh_detected,
        "expected_image_count": expected,
        "image_count": image_count,
        "frame_ids": frame_ids,
        "silhouette_frame_ids": silhouette_ids,
        "ground_mask_frame_ids": ground_mask_ids,
        "silhouette_image_count": len(silhouette_ids),
        "ground_mask_image_count": len(ground_mask_ids),
        "expected_frame_ids": expected_frame_ids,
        "legacy_ppm_count": legacy_ppm_count,
        "source_was_ppm_only": bool(legacy_ppm_count > 0 and not frame_ids),
        "mp4_file": str(mp4_file),
        "mp4_ok": mp4_ok,
        "mp4_size_bytes": mp4_file.stat().st_size if mp4_file.exists() else 0,
        "motion_visible": bool(render_meta.get("motion_visible")),
        "scene_contract_v3_file": str(scene_contract_path),
        "scene_contract_v3": scene_contract_v3,
        "scene_contract_sha256": str(scene_contract_v3.get("scene_contract_sha256", "")),
        "mesh_reference_pass": pass_ok,
        "raw_render_meta": render_meta,
    }


def default_root_name(source_root: Path, stage: str) -> str:
    return f"{source_root.name}_{stage}_mesh_reference_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def scene_contract(args: argparse.Namespace, root_name: str, source_root: Path, case: str) -> dict[str, Any]:
    return {
        "schema_version": 3,
        "root_name": root_name,
        "source_root": str(source_root),
        "source_stage": args.stage,
        "case": case,
        "camera_mode": "track",
        "ground": "mimickit_engine_default_flat_ground",
        "width": int(args.width),
        "height": int(args.height),
        "frames": int(args.frames),
        "frame_stride": int(args.frame_stride),
        "mp4_fps": int(args.mp4_fps),
        "expected_frame_ids": list(range(0, int(args.frames), max(1, int(args.frame_stride)))),
        "engine_config": str(DEFAULT_ENGINE),
        "debug_overlays": False,
        "fov_degrees": 45.0,
        "seed": int(args.seed),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an exact USD mesh reference root for an existing AMP training root.")
    parser.add_argument("--source-root", required=True, help="Existing AMP root name or absolute output/train path.")
    parser.add_argument("--stage", default="long_train")
    parser.add_argument("--root-name", default="")
    parser.add_argument("--case", default="")
    parser.add_argument("--train-root", default=str(DEFAULT_TRAIN_ROOT))
    parser.add_argument("--img-root", default=str(DEFAULT_IMG_ROOT))
    parser.add_argument("--frames", type=int, default=300)
    parser.add_argument("--frame-stride", type=int, default=5)
    parser.add_argument("--mp4-fps", type=int, default=12)
    parser.add_argument("--width", type=int, default=960)
    parser.add_argument("--height", type=int, default=540)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--num-envs", type=int, default=1)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--force-root", action="store_true")
    parser.add_argument("--no-render", action="store_true")
    parser.add_argument("--run-native-windows", action="store_true", help="Run the exact mesh reference builder in the Windows native workspace, then ingest outputs back into this workspace.")
    parser.add_argument("--ingest-native-windows", action="store_true", help="Copy an already-built Windows native exact mesh reference root back into this workspace.")
    parser.add_argument("--windows-workspace-root", default=DEFAULT_WINDOWS_WORKSPACE_ROOT)
    parser.add_argument("--windows-workspace-wsl", default=str(DEFAULT_WINDOWS_WORKSPACE_WSL))
    parser.add_argument("--windows-conda-env", default=DEFAULT_WINDOWS_CONDA_ENV)
    parser.add_argument("--no-sync-native-workspace-scripts", dest="sync_native_workspace_scripts", action="store_false", default=True)
    parser.add_argument("--skip-asset-export", action="store_true")
    parser.add_argument("--asset-export-python", default="")
    parser.add_argument("--package-export-python", default="")
    args = parser.parse_args()
    args.train_root = Path(args.train_root).resolve()
    args.img_root = Path(args.img_root).resolve()
    return args


def main() -> int:
    args = parse_args()
    root_name_explicit = bool(str(args.root_name).strip())
    if args.ingest_native_windows and not args.run_native_windows and not root_name_explicit:
        raise SystemExit("[ERROR] --ingest-native-windows requires --root-name unless paired with --run-native-windows")

    source_root = Path(args.source_root)
    if not source_root.is_absolute():
        source_root = args.train_root / source_root
    source_root = source_root.resolve()
    source_stage = source_root / args.stage
    if not source_stage.exists():
        raise SystemExit(f"[ERROR] source stage not found: {source_stage}")
    root_name = args.root_name.strip() or default_root_name(source_root, args.stage)
    out_root = args.train_root / root_name
    img_root = args.img_root / root_name

    case = infer_case(source_root, source_stage, args.case)
    native_windows: dict[str, Any] = {
        "requested_run": bool(args.run_native_windows),
        "requested_ingest": bool(args.ingest_native_windows),
        "workspace_root": args.windows_workspace_root,
        "workspace_wsl": args.windows_workspace_wsl,
        "conda_env": args.windows_conda_env,
        "script_sync": {"ok": False, "skipped": not bool(args.sync_native_workspace_scripts)},
        "run": {"ok": False, "skipped": not bool(args.run_native_windows)},
        "ingest": {"ok": False, "skipped": not bool(args.ingest_native_windows or args.run_native_windows)},
    }
    if args.run_native_windows or args.ingest_native_windows:
        out_root.mkdir(parents=True, exist_ok=True)
        img_root.mkdir(parents=True, exist_ok=True)
        manifest: dict[str, Any] = {
            "schema_version": 1,
            "root_name": root_name,
            "source_root": str(source_root),
            "source_stage": str(source_stage),
            "train_root_dir": str(out_root),
            "img_root_dir": str(img_root),
            "usd_asset": str(DEFAULT_USD),
            "xml_kinematic_asset": str(DEFAULT_XML),
            "frames": int(args.frames),
            "frame_stride": int(args.frame_stride),
            "expected_image_count": expected_image_count(args.frames, args.frame_stride),
            "expected_frame_ids": list(range(0, int(args.frames), max(1, int(args.frame_stride)))),
            "frame_ids": [],
            "png_count": 0,
            "mp4_ok": False,
            "source_was_ppm_only": False,
            "scene_contract": scene_contract(args, root_name, source_root, case),
            "native_windows": native_windows,
            "mesh_reference_pass": False,
            "blocker": "",
        }
        if args.run_native_windows:
            if args.sync_native_workspace_scripts:
                script_sync = sync_native_workspace_scripts(args)
                native_windows["script_sync"] = script_sync
                if not script_sync.get("ok"):
                    manifest["blocker"] = "native_windows_script_sync_failed"
                    write_manifest(args, root_name, manifest)
                    print(json.dumps(manifest, indent=2, ensure_ascii=False))
                    return 6
            native_run = run_windows_native_reference(args, root_name, native_source_root_arg(source_root, Path(args.train_root)))
            native_windows["run"] = native_run
            if not native_run.get("ok"):
                manifest["blocker"] = "native_windows_exact_mesh_reference_failed"
                diagnostic_ingest = ingest_windows_outputs(args, root_name)
                native_windows["ingest"] = diagnostic_ingest
                native_manifest = read_json(Path(args.train_root) / root_name / "mesh_reference_manifest.json")
                if native_manifest:
                    native_manifest = localize_native_manifest_paths(native_manifest, Path(args.train_root), Path(args.img_root), root_name)
                    native_manifest["native_windows"] = native_windows
                    native_manifest.setdefault("outer_blocker", manifest["blocker"])
                    write_manifest(args, root_name, native_manifest)
                    print(json.dumps(native_manifest, indent=2, ensure_ascii=False))
                    return 6
                write_manifest(args, root_name, manifest)
                print(json.dumps(manifest, indent=2, ensure_ascii=False))
                return 6
            args.ingest_native_windows = True
            native_windows["requested_ingest"] = True
            native_windows["ingest"]["skipped"] = False

        if args.ingest_native_windows:
            ingest = ingest_windows_outputs(args, root_name)
            native_windows["ingest"] = ingest
            if not ingest.get("ok"):
                manifest["blocker"] = "native_windows_ingest_failed"
                write_manifest(args, root_name, manifest)
                print(json.dumps(manifest, indent=2, ensure_ascii=False))
                return 6
            native_manifest = read_json(Path(args.train_root) / root_name / "mesh_reference_manifest.json")
            if native_manifest:
                native_manifest = localize_native_manifest_paths(native_manifest, Path(args.train_root), Path(args.img_root), root_name)
                native_manifest["native_windows"] = native_windows
                native_manifest.setdefault("scene_contract", scene_contract(args, root_name, source_root, case))
                write_manifest(args, root_name, native_manifest)
                print(json.dumps(native_manifest, indent=2, ensure_ascii=False))
                return 0 if native_manifest.get("mesh_reference_pass") else 4
            manifest["blocker"] = "native_windows_manifest_missing_after_ingest"
            write_manifest(args, root_name, manifest)
            print(json.dumps(manifest, indent=2, ensure_ascii=False))
            return 6

    if out_root.exists() and args.force_root:
        shutil.rmtree(out_root)
    if img_root.exists() and args.force_root:
        shutil.rmtree(img_root)
    out_root.mkdir(parents=True, exist_ok=True)
    img_root.mkdir(parents=True, exist_ok=True)

    stage_dir = out_root / args.stage
    stage_dir.mkdir(parents=True, exist_ok=True)
    model_file = source_stage / "model.pt"
    agent_config = source_stage / "agent_config.yaml"
    source_env = source_stage / "env_config.yaml"
    if not model_file.exists() or not agent_config.exists() or not source_env.exists():
        raise SystemExit("[ERROR] source stage must contain model.pt, agent_config.yaml, and env_config.yaml")
    copied_model = stage_dir / "model.pt"
    copied_agent = stage_dir / "agent_config.yaml"
    copied_env = stage_dir / "env_config.yaml"
    copied_engine = stage_dir / "engine_config.yaml"
    shutil.copy2(model_file, copied_model)
    shutil.copy2(agent_config, copied_agent)
    env_data = read_yaml(source_env)
    env_data["char_file"] = str(DEFAULT_USD.relative_to(ROOT))
    env_data["kin_char_file"] = str(DEFAULT_XML.relative_to(ROOT))
    env_data["camera_mode"] = "track"
    write_yaml(copied_env, env_data)
    shutil.copy2(DEFAULT_ENGINE, copied_engine)

    row = {
        "case": case,
        "method": "amp_exact_mesh_reference",
        "case_type": "trainable",
        "variant": args.stage,
        "agent_config": str(copied_agent),
        "num_envs": str(int(args.num_envs)),
        "final_ok": "1",
        "note": "exact_amp_policy_usd_mesh_reference",
        "out_dir": str(stage_dir),
        "long_out_dir": str(stage_dir),
        "model_file": str(copied_model),
        "env_config": str(copied_env),
        "engine_config": str(copied_engine),
        "llc_model_file": "",
        "motion_id": "",
        "motion_file": str(env_data.get("motion_file", "")),
        "source_pack": source_root.name,
        "category": case.replace("_args.txt", ""),
        "train_enabled": "true",
        "view_enabled": "true",
    }
    write_tsv(out_root / "best_by_case.tsv", [row])

    manifest: dict[str, Any] = {
        "schema_version": 1,
        "root_name": root_name,
        "source_root": str(source_root),
        "source_stage": str(source_stage),
        "train_root_dir": str(out_root),
        "img_root_dir": str(img_root),
        "usd_asset": str(DEFAULT_USD),
        "xml_kinematic_asset": str(DEFAULT_XML),
        "frames": int(args.frames),
        "frame_stride": int(args.frame_stride),
        "expected_image_count": expected_image_count(args.frames, args.frame_stride),
        "expected_frame_ids": list(range(0, int(args.frames), max(1, int(args.frame_stride)))),
        "frame_ids": [],
        "png_count": 0,
        "mp4_ok": False,
        "source_was_ppm_only": False,
        "scene_contract": scene_contract(args, root_name, source_root, case),
        "native_windows": native_windows,
        "render": {"ok": False, "skipped": bool(args.no_render)},
        "render_summary": {},
        "contact_sheet": {"ok": False},
        "asset_export": {
            "ok": False,
            "skipped": bool(args.skip_asset_export),
            "format": "glb",
            "source_usd_file": str(DEFAULT_USD),
            "source_usd_sha256": sha256_file(DEFAULT_USD),
            "glb_file": str(img_root / "assets" / "humanoid_sword_shield.glb"),
        },
        "package_export": {"ok": False, "package_dir": str(out_root / "ue_export_mesh_reference")},
        "mesh_reference_pass": False,
        "blocker": "",
    }

    if not args.no_render:
        render_cmd = [
            sys.executable,
            str(ROOT / "tools" / "ue_bridge" / "build_mimickit_render_sequences.py"),
            "--train-root",
            str(args.train_root),
            "--img-root",
            str(args.img_root),
            "--roots",
            root_name,
            "--cases",
            case,
            "--frames",
            str(args.frames),
            "--frame-stride",
            str(args.frame_stride),
            "--mp4-fps",
            str(args.mp4_fps),
            "--width",
            str(args.width),
            "--height",
            str(args.height),
            "--device",
            args.device,
            "--num-envs",
            str(args.num_envs),
            "--seed",
            str(args.seed),
            "--force",
        ]
        render_env = os.environ.copy()
        render_env["MIMICKIT_VIEWER_HEADLESS"] = "1"
        render_env["MIMICKIT_STRICT_BODY_ORDER"] = "1"
        render_env["MIMICKIT_REQUIRED_BODY_ORDER_JSON"] = json.dumps(body_order_from_mjcf(), separators=(",", ":"))
        manifest["render"] = run_command(render_cmd, env=render_env)
        summary = summarize_render(args, root_name)
        manifest["render_summary"] = summary
        manifest["frame_ids"] = summary.get("frame_ids", [])
        manifest["png_count"] = int(summary.get("image_count", 0) or len(summary.get("frame_ids", [])) or 0)
        manifest["mp4_ok"] = bool(summary.get("mp4_ok"))
        manifest["source_was_ppm_only"] = bool(summary.get("source_was_ppm_only"))
        manifest["scene_contract_v3"] = summary.get("scene_contract_v3", {})
        manifest["scene_contract_sha256"] = summary.get("scene_contract_sha256", "")
        contact = build_contact_sheet(Path(summary["render_dir"]), Path(summary["render_dir"]) / "mesh_reference_contact_sheet.png")
        manifest["contact_sheet"] = contact

    if not args.skip_asset_export:
        asset_dir = img_root / "assets"
        asset_dir.mkdir(parents=True, exist_ok=True)
        glb_file = asset_dir / "humanoid_sword_shield.glb"
        asset_cmd = [
            args.asset_export_python or sys.executable,
            str(ROOT / "tools" / "windows" / "export_usd_to_gltf_asset.py"),
            "--input-usd",
            str(DEFAULT_USD),
            "--output-asset",
            str(glb_file),
            "--manifest",
            str(asset_dir / "asset_export_manifest.json"),
            "--headless",
        ]
        asset_result = run_command(asset_cmd)
        asset_manifest = read_json(asset_dir / "asset_export_manifest.json")
        manifest["asset_export"].update(asset_manifest)
        manifest["asset_export"]["command"] = asset_result
        manifest["asset_export"]["ok"] = bool(asset_result.get("ok")) and glb_file.exists() and glb_file.stat().st_size > 0
        manifest["asset_export"]["glb_file"] = str(glb_file)
        manifest["asset_export"]["output_sha256"] = sha256_file(glb_file)

    package_dir = out_root / "ue_export_mesh_reference"
    package_cmd = [
        args.package_export_python or sys.executable,
        str(ROOT / "tools" / "ue_bridge" / "run_mimic_visual_case.py"),
        "--case-id",
        case,
        "--brain-name",
        "ExactMeshReference",
        "--case-kind",
        "policy",
        "--arg-file",
        str(ROOT / "args" / case),
        "--model-file",
        str(copied_model),
        "--env-config",
        str(copied_env),
        "--engine-config",
        str(copied_engine),
        "--agent-config",
        str(copied_agent),
        "--out-dir",
        str(package_dir),
        "--device",
        args.device,
        "--num-envs",
        str(args.num_envs),
        "--frames",
        str(args.frames),
        "--seed",
        str(args.seed),
        "--skip-test",
    ]
    package_env = os.environ.copy()
    package_env["MIMICKIT_VIEWER_HEADLESS"] = "1"
    package_env["MIMICKIT_STRICT_BODY_ORDER"] = "1"
    package_env["MIMICKIT_REQUIRED_BODY_ORDER_JSON"] = json.dumps(body_order_from_mjcf(), separators=(",", ":"))
    package_result = run_command(package_cmd, env=package_env)
    source_rig_result = run_command(
        [
            args.package_export_python or sys.executable,
            str(ROOT / "tools" / "ue_bridge" / "build_mimickit_source_rig_asset_spec.py"),
            "--package-dir",
            str(package_dir),
            "--char-xml",
            str(DEFAULT_XML),
            "--char-usd",
            str(DEFAULT_USD),
            "--out",
            str(package_dir / "mimickit_source_rig_asset_spec.json"),
        ]
    )
    render_summary_for_package = manifest.get("render_summary") if isinstance(manifest.get("render_summary"), dict) else {}
    scene_contract = (
        Path(str(render_summary_for_package.get("render_dir"))) / "scene_contract_v3.json"
        if render_summary_for_package.get("render_dir")
        else None
    )
    if scene_contract is not None and scene_contract.exists():
        shutil.copy2(scene_contract, package_dir / "scene_contract_v3.json")
    required_package = [
        package_dir / "visual_replay" / "pose_dof_replay.jsonl",
        package_dir / "visual_replay" / "body_world_replay.jsonl",
        package_dir / "visual_replay" / "body_world_contract.json",
        package_dir / "visual_replay" / "pose_dof_meta.json",
        package_dir / "joint_order.json",
        package_dir / "mimickit_source_rig_asset_spec.json",
        package_dir / "visual_alignment_contract.json",
        package_dir / "scene_contract_v3.json",
        package_dir / "mesh_binding_contract.json",
    ]
    data_binding = validate_body_world_replay(package_dir)
    manifest["data_binding"] = data_binding
    manifest["data_binding_ok"] = bool(data_binding.get("data_binding_ok"))
    manifest["package_export"] = {
        "ok": bool(package_result.get("ok")) and all(path.exists() and path.stat().st_size > 0 for path in required_package) and manifest["data_binding_ok"],
        "package_dir": str(package_dir),
        "command": package_result,
        "source_rig": source_rig_result,
        "missing": [str(path) for path in required_package if not path.exists() or path.stat().st_size <= 0],
    }

    summary = manifest.get("render_summary") if isinstance(manifest.get("render_summary"), dict) else {}
    glb_ok = (
        bool(manifest["asset_export"].get("ok"))
        and bool((manifest["asset_export"].get("asset_structure") or {}).get("ok"))
        and bool(str(manifest["asset_export"].get("glb_file", "")).strip())
    )
    manifest["mesh_reference_pass"] = bool(
        summary.get("mesh_reference_pass")
        and manifest["contact_sheet"].get("ok")
        and glb_ok
        and manifest["package_export"].get("ok")
        and manifest.get("data_binding_ok")
        and not manifest.get("source_was_ppm_only")
    )
    if not manifest["mesh_reference_pass"]:
        if manifest.get("source_was_ppm_only"):
            manifest["blocker"] = "ppm_only_output_rejected"
        elif not summary.get("mesh_reference_pass"):
            manifest["blocker"] = "mesh_render_failed_or_incomplete"
        elif not manifest["contact_sheet"].get("ok"):
            manifest["blocker"] = "contact_sheet_failed"
        elif not glb_ok:
            manifest["blocker"] = "mesh_asset_export_failed"
        elif not manifest["package_export"].get("ok"):
            manifest["blocker"] = "mesh_package_export_failed"
        elif not manifest.get("data_binding_ok"):
            manifest["blocker"] = "body_world_replay_invalid"
        else:
            manifest["blocker"] = "mesh_reference_gate_failed"

    finalize_manifest_gate_fields(manifest)
    write_json(out_root / "mesh_reference_manifest.json", manifest)
    write_json(img_root / "mesh_reference_manifest.json", manifest)
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0 if manifest["mesh_reference_pass"] else 4


if __name__ == "__main__":
    raise SystemExit(main())
