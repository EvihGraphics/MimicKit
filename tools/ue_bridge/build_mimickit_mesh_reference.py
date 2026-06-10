#!/usr/bin/env python3
"""Build a MimicKit sword/shield USD mesh reference render root.

The script intentionally keeps mesh-reference outputs isolated from existing
Walk/Stop geom baselines. It can also stop after environment precheck/dry-run
and still writes a manifest that records the current blocker.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TRAIN_ROOT = ROOT / "output" / "train"
DEFAULT_IMG_ROOT = ROOT / "output" / "img"
DEFAULT_MOTION_ID = "RL_Avatar_Atk_2xCombo01_Motion"
DEFAULT_CASE = "view_motion_humanoid_sword_shield_args"
DEFAULT_BASE_ENV = ROOT / "data" / "envs" / "view_motion_humanoid_sword_shield_mesh_env.yaml"
DEFAULT_ENGINE = ROOT / "data" / "engines" / "isaac_lab_engine.yaml"
DEFAULT_USD = ROOT / "data" / "assets" / "sword_shield" / "humanoid_sword_shield.usd"
DEFAULT_XML = ROOT / "data" / "assets" / "sword_shield" / "humanoid_sword_shield.xml"
DEFAULT_WINDOWS_WORKSPACE_ROOT = "D:\\MimicKitNative"
DEFAULT_WINDOWS_WORKSPACE_WSL = Path("/mnt/d/MimicKitNative/workspace/MimicKit")
DEFAULT_WINDOWS_CONDA_ENV = "D:\\MimicKitNative\\conda\\mimickit-isaaclab-win"


def utc_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def default_root_name() -> str:
    return "tmp_white_knight_mesh_reference_" + datetime.now().strftime("%Y%m%d_%H%M%S")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as fp:
        for chunk in iter(lambda: fp.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def body_order_from_mjcf(path: Path = DEFAULT_XML) -> list[str]:
    world_body = ET.parse(path).getroot().find("worldbody")
    root_body = world_body.find("body") if world_body is not None else None
    if root_body is None:
        raise RuntimeError(f"MJCF root body missing: {path}")
    names: list[str] = []

    def visit(body: ET.Element) -> None:
        name = str(body.attrib.get("name", "")).strip()
        if not name:
            raise RuntimeError(f"unnamed MJCF body in {path}")
        names.append(name)
        for child in body.findall("body"):
            visit(child)

    visit(root_body)
    return names


def find_conda() -> str:
    candidates = [
        os.environ.get("CONDA_EXE", ""),
        "/root/miniconda3/bin/conda",
        shutil.which("conda") or "",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return "conda"


def tail(text: str, limit: int = 4000) -> str:
    if len(text) <= limit:
        return text
    return text[-limit:]


def run_command(cmd: list[str], env: dict[str, str] | None = None) -> dict[str, Any]:
    proc = subprocess.run(
        cmd,
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
        "stdout_tail": tail(proc.stdout),
        "stderr_tail": tail(proc.stderr),
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
        "tools/ue_bridge/build_mimickit_mesh_reference.py",
        "tools/ue_bridge/build_mimickit_exact_mesh_reference.py",
        "tools/ue_bridge/_bridge_common.py",
        "tools/ue_bridge/export_dummy_fixture.py",
        "tools/ue_bridge/run_mimic_visual_case.py",
        "tools/ue_bridge/build_mimickit_render_sequences.py",
        "tools/ue_bridge/visual_bridge_validation.py",
        "tools/ue_bridge/build_mimickit_source_rig_asset_spec.py",
        "tools/ue_bridge/build_ase_reallusion_motion_render_root.py",
        "mimickit/engines/engine.py",
        "mimickit/engines/newton_engine.py",
        "tools/ue_bridge/omni/metrics/assembler/core.py",
        "mimickit/engines/isaac_lab_engine.py",
        "mimickit/envs/char_env.py",
        "tools/windows/export_usd_to_gltf_asset.py",
        "tools/windows/build_white_knight_mesh_reference_native.ps1",
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


def run_windows_native_reference(args: argparse.Namespace, root_name: str) -> dict[str, Any]:
    powershell = shutil.which("powershell.exe") or shutil.which("pwsh") or ""
    if not powershell:
        return {"ok": False, "error": "powershell.exe/pwsh not found"}
    script = ROOT / "tools" / "windows" / "build_white_knight_mesh_reference_native.ps1"
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
        "-AssetExportFormat",
        args.asset_export_format,
    ]
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


def localize_native_manifest_paths(data: Any, train_root: Path, img_root: Path, root_name: str) -> Any:
    """Rewrite copied native-output paths so WSL/Evih consumers can open them."""
    train_marker = f"output/train/{root_name}"
    img_marker = f"output/img/{root_name}"

    def convert(value: str) -> str:
        normalized = value.replace("\\", "/")
        for marker, local_root in ((train_marker, train_root), (img_marker, img_root)):
            index = normalized.lower().find(marker.lower())
            if index >= 0:
                suffix = normalized[index + len(marker) :].lstrip("/")
                return str(local_root / root_name / suffix) if suffix else str(local_root / root_name)
        for marker in ("D:/MimicKitNative/workspace/MimicKit", "/mnt/d/MimicKitNative/workspace/MimicKit"):
            index = normalized.lower().find(marker.lower())
            if index >= 0:
                suffix = normalized[index + len(marker) :].lstrip("/")
                return str(ROOT / suffix) if suffix else str(ROOT)
        return value

    if isinstance(data, dict):
        preserved = {"cmd", "stdout_tail", "stderr_tail"}
        return {
            key: value if key in preserved else localize_native_manifest_paths(value, train_root, img_root, root_name)
            for key, value in data.items()
        }
    if isinstance(data, list):
        return [localize_native_manifest_paths(value, train_root, img_root, root_name) for value in data]
    if isinstance(data, str):
        return convert(data)
    return data


def python_command(args: argparse.Namespace, code: str) -> list[str]:
    if args.render_python:
        return [args.render_python, "-c", code]
    return [find_conda(), "run", "-n", args.conda_env, "python", "-c", code]


def run_precheck(args: argparse.Namespace) -> dict[str, Any]:
    code = r'''
import importlib
import json
import os
import sys

modules = ["isaaclab", "isaaclab.app", "carb", "omni", "omni.kit.app", "torch"]
result = {
    "python": sys.executable,
    "imports": {},
    "torch_cuda_available": False,
    "kit_bootstrap": {"ok": False, "method": "from isaaclab.app import AppLauncher"},
    "usd_context_probe": {"ok": False, "import_name": "omni.usd"},
}
ok = True
os.environ.setdefault("OMNI_KIT_ACCEPT_EULA", "YES")
try:
    from isaaclab.app import AppLauncher
    result["kit_bootstrap"]["ok"] = True
    result["kit_bootstrap"]["AppLauncher"] = repr(AppLauncher)
except Exception as exc:
    ok = False
    result["kit_bootstrap"]["error"] = f"{type(exc).__name__}: {exc}"
for name in modules:
    try:
        mod = importlib.import_module(name)
        result["imports"][name] = {"ok": True, "file": getattr(mod, "__file__", "")}
    except Exception as exc:
        ok = False
        result["imports"][name] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
try:
    import torch
    result["torch_version"] = torch.__version__
    result["torch_cuda_available"] = bool(torch.cuda.is_available())
    if not result["torch_cuda_available"]:
        ok = False
except Exception as exc:
    ok = False
    result["torch_error"] = f"{type(exc).__name__}: {exc}"
try:
    mod = importlib.import_module("omni.usd")
    result["usd_context_probe"] = {"ok": True, "import_name": "omni.usd", "file": getattr(mod, "__file__", "")}
except Exception as exc:
    result["usd_context_probe"] = {
        "ok": False,
        "import_name": "omni.usd",
        "error": f"{type(exc).__name__}: {exc}",
        "note": "omni.usd may require a launched Kit app; render stage is the authoritative gate.",
    }
print("MIMICKIT_ISAACLAB_PRECHECK_JSON_BEGIN")
print(json.dumps(result, indent=2))
print("MIMICKIT_ISAACLAB_PRECHECK_JSON_END")
raise SystemExit(0 if ok else 3)
'''
    command_result = run_command(python_command(args, code), env=render_env(args))
    parsed: dict[str, Any] = {}
    stdout = command_result.get("stdout_tail", "")
    try:
        begin = stdout.rindex("MIMICKIT_ISAACLAB_PRECHECK_JSON_BEGIN")
        end = stdout.rindex("MIMICKIT_ISAACLAB_PRECHECK_JSON_END")
        payload = stdout[begin + len("MIMICKIT_ISAACLAB_PRECHECK_JSON_BEGIN"):end].strip()
        parsed = json.loads(payload)
    except Exception:
        try:
            parsed = json.loads(stdout)
        except Exception:
            parsed = {}
    return {
        "ok": bool(command_result["ok"]),
        "conda_env": args.conda_env if not args.render_python else "",
        "render_python": args.render_python,
        "command": command_result,
        "details": parsed,
    }


def build_synthetic_root(args: argparse.Namespace, root_name: str) -> dict[str, Any]:
    cmd = [
        sys.executable,
        str(ROOT / "tools" / "ue_bridge" / "build_ase_reallusion_motion_render_root.py"),
        "--train-root",
        str(args.train_root),
        "--root-name",
        root_name,
        "--motion-ids",
        args.motion_id,
        "--base-env-config",
        str(args.base_env_config),
        "--engine-config",
        str(args.engine_config),
    ]
    if args.force_root:
        cmd.append("--force")
    return run_command(cmd)


def scene_contract(args: argparse.Namespace, root_name: str) -> dict[str, Any]:
    return {
        "schema_version": 3,
        "root_name": root_name,
        "camera_mode": "track",
        "ground": "mimickit_engine_default_flat_ground",
        "width": int(args.width),
        "height": int(args.height),
        "frames": int(args.frames),
        "frame_stride": int(args.frame_stride),
        "mp4_fps": int(args.mp4_fps),
        "expected_frame_ids": list(range(0, int(args.frames), max(1, int(args.frame_stride)))),
        "motion_id": args.motion_id,
        "case": args.case,
        "base_env_config": str(args.base_env_config),
        "engine_config": str(args.engine_config),
        "debug_overlays": False,
        "fov_degrees": 45.0,
        "seed": int(args.seed),
    }


def render_env(args: argparse.Namespace) -> dict[str, str]:
    env = os.environ.copy()
    env["OMNI_KIT_ACCEPT_EULA"] = "YES"
    env["MIMICKIT_SKIP_XVFB"] = "1"
    env["MIMICKIT_VIEWER_HEADLESS"] = "1"
    env["MIMICKIT_STRICT_BODY_ORDER"] = "1"
    env["MIMICKIT_REQUIRED_BODY_ORDER_JSON"] = json.dumps(body_order_from_mjcf(), separators=(",", ":"))
    if args.unset_display:
        env.pop("DISPLAY", None)
    if args.vk_icd_filenames:
        env["VK_ICD_FILENAMES"] = args.vk_icd_filenames
    return env


def render_command(args: argparse.Namespace, root_name: str, dry_run: bool) -> list[str]:
    if dry_run and not args.render_python:
        prefix = [sys.executable]
    else:
        prefix = [args.render_python] if args.render_python else [find_conda(), "run", "-n", args.conda_env, "python"]
    cmd = prefix + [
        str(ROOT / "tools" / "ue_bridge" / "build_mimickit_render_sequences.py"),
        "--train-root",
        str(args.train_root),
        "--img-root",
        str(args.img_root),
        "--roots",
        root_name,
        "--cases",
        args.case,
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
    if dry_run:
        cmd.append("--dry-run")
        cmd.extend(["--max-cases", "1"])
    return cmd


def expected_image_count(frames: int, stride: int) -> int:
    return int(math.ceil(float(frames) / float(max(1, stride))))


def render_dir_for(args: argparse.Namespace, root_name: str) -> Path:
    return Path(args.img_root) / root_name / "runs" / args.case / args.motion_id / "render"


def collect_frame_ids(frames_dir: Path) -> list[int]:
    ids: list[int] = []
    for path in sorted(frames_dir.glob("frame_*.png")):
        try:
            ids.append(int(path.stem.split("_")[-1]))
        except ValueError:
            pass
    return ids


def build_contact_sheet(render_dir: Path, out_file: Path, sample_count: int = 12) -> dict[str, Any]:
    frames = sorted((render_dir / "frames").glob("frame_*.png"))
    if not frames:
        return {"ok": False, "error": "no frames found"}
    try:
        from PIL import Image, ImageDraw
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    if len(frames) <= sample_count:
        selected = frames
    else:
        selected = [frames[round(i * (len(frames) - 1) / (sample_count - 1))] for i in range(sample_count)]

    thumb = (320, 180)
    cols = 4
    rows = math.ceil(len(selected) / cols)
    gutter = 16
    header = 52
    label = 22
    width = cols * thumb[0] + (cols + 1) * gutter
    height = header + rows * (thumb[1] + label + gutter) + gutter
    sheet = Image.new("RGB", (width, height), (246, 246, 244))
    draw = ImageDraw.Draw(sheet)
    draw.text((gutter, 18), "MimicKit white-knight mesh reference", fill=(20, 20, 20))

    for index, path in enumerate(selected):
        row = index // cols
        col = index % cols
        x = gutter + col * (thumb[0] + gutter)
        y = header + row * (thumb[1] + label + gutter)
        with Image.open(path) as image:
            sheet.paste(image.convert("RGB").resize(thumb, Image.Resampling.LANCZOS), (x, y))
        draw.rectangle([x, y, x + thumb[0], y + thumb[1]], outline=(210, 210, 210), width=1)
        draw.text((x, y + thumb[1] + 5), path.name, fill=(38, 38, 38))

    out_file.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_file)
    return {"ok": True, "file": str(out_file), "sampled_count": len(selected)}


def summarize_render(args: argparse.Namespace, root_name: str) -> dict[str, Any]:
    render_dir = render_dir_for(args, root_name)
    render_meta_path = render_dir / "render_meta.json"
    render_meta = read_json(render_meta_path)
    frames_dir = render_dir / "frames"
    frame_ids = collect_frame_ids(frames_dir)
    mp4_file = render_dir / "render.mp4"
    scene_contract_path = render_dir / "scene_contract_v3.json"
    scene_contract_v3 = read_json(scene_contract_path)
    legacy_ppm_count = len(list(frames_dir.glob("frame_*.ppm")))
    expected = expected_image_count(args.frames, args.frame_stride)
    status = str(render_meta.get("status", ""))
    visual_kind = str(render_meta.get("visual_kind", ""))
    mesh_detected = bool(int(render_meta.get("mesh_detected", 0) or 0))
    image_count = int(render_meta.get("image_count", 0) or 0)
    mp4_ok = bool(int(render_meta.get("mp4_ok", 0) or 0)) if "mp4_ok" in render_meta else mp4_file.exists()
    expected_frame_ids = list(range(0, int(args.frames), max(1, int(args.frame_stride))))
    pass_ok = (
        status in {"ok", "skipped_resume"}
        and visual_kind == "mesh"
        and mesh_detected
        and image_count >= expected
        and len(frame_ids) >= expected
        and frame_ids == expected_frame_ids
        and mp4_file.exists()
        and mp4_file.stat().st_size > 0
        and mp4_ok
        and bool(render_meta.get("motion_visible"))
        and bool(scene_contract_v3.get("scene_contract_sha256"))
    )
    return {
        "render_dir": str(render_dir),
        "render_meta": str(render_meta_path),
        "render_meta_exists": render_meta_path.exists(),
        "status": status,
        "error": str(render_meta.get("error", "")),
        "visual_kind": visual_kind,
        "mesh_detected": mesh_detected,
        "frames": int(args.frames),
        "frame_stride": int(args.frame_stride),
        "expected_image_count": expected,
        "image_count": image_count,
        "frame_count_on_disk": len(frame_ids),
        "frame_ids": frame_ids,
        "expected_frame_ids": expected_frame_ids,
        "legacy_ppm_count": legacy_ppm_count,
        "source_was_ppm_only": bool(legacy_ppm_count > 0 and len(frame_ids) == 0),
        "mp4_file": str(mp4_file),
        "mp4_exists": mp4_file.exists(),
        "mp4_size_bytes": mp4_file.stat().st_size if mp4_file.exists() else 0,
        "mp4_ok": mp4_ok,
        "motion_visible": bool(render_meta.get("motion_visible")),
        "scene_contract_v3_file": str(scene_contract_path),
        "scene_contract_v3": scene_contract_v3,
        "scene_contract_sha256": str(scene_contract_v3.get("scene_contract_sha256", "")),
        "mesh_reference_pass": pass_ok,
        "raw_render_meta": render_meta,
    }


def run_asset_export(args: argparse.Namespace, root_name: str) -> dict[str, Any]:
    output_dir = Path(args.img_root) / root_name / "assets"
    output_path = output_dir / f"humanoid_sword_shield.{args.asset_export_format}"
    result: dict[str, Any] = {
        "ok": False,
        "skipped": bool(args.skip_asset_export),
        "source_usd_file": str(DEFAULT_USD),
        "source_usd_sha256": sha256_file(DEFAULT_USD),
        "format": args.asset_export_format,
        "glb_file": str(output_path) if args.asset_export_format == "glb" else "",
        "gltf_file": str(output_path) if args.asset_export_format == "gltf" else "",
        "output_file": str(output_path),
        "output_sha256": "",
        "command": {},
    }
    if args.skip_asset_export:
        result["error"] = "asset export skipped by request"
        return result

    output_dir.mkdir(parents=True, exist_ok=True)
    helper = ROOT / "tools" / "windows" / "export_usd_to_gltf_asset.py"
    python_exe = args.asset_export_python or args.render_python or sys.executable
    cmd = [
        python_exe,
        str(helper),
        "--input-usd",
        str(DEFAULT_USD),
        "--output-asset",
        str(output_path),
        "--manifest",
        str(output_dir / "asset_export_manifest.json"),
        "--headless",
    ]
    command_result = run_command(cmd, env=render_env(args))
    result["command"] = command_result
    helper_manifest = read_json(output_dir / "asset_export_manifest.json")
    if helper_manifest:
        result.update(helper_manifest)
        result.setdefault("command", command_result)

    result["ok"] = bool(command_result.get("ok")) and output_path.exists() and output_path.stat().st_size > 0
    result["output_file"] = str(output_path)
    if args.asset_export_format == "glb":
        result["glb_file"] = str(output_path)
    else:
        result["gltf_file"] = str(output_path)
    result["output_sha256"] = sha256_file(output_path)
    if not result["ok"] and not result.get("error"):
        result["error"] = "asset converter did not create a non-empty output asset"
    return result


def run_package_export(args: argparse.Namespace, root_name: str) -> dict[str, Any]:
    package_dir = Path(args.train_root) / root_name / "ue_export_mesh_reference"
    generated_env = Path(args.train_root) / root_name / "generated_envs" / f"{args.motion_id}.yaml"
    arg_file = ROOT / "args" / (args.case if str(args.case).endswith(".txt") else f"{args.case}.txt")
    python_exe = args.package_export_python or args.render_python or sys.executable
    cmd = [
        python_exe,
        str(ROOT / "tools" / "ue_bridge" / "run_mimic_visual_case.py"),
        "--case-id",
        args.case,
        "--brain-name",
        "WhiteKnightMeshReference",
        "--case-kind",
        "dummy",
        "--arg-file",
        str(arg_file),
        "--env-config",
        str(generated_env),
        "--engine-config",
        str(args.engine_config),
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
    result = {
        "ok": False,
        "package_dir": str(package_dir),
        "arg_file": str(arg_file),
        "env_config": str(generated_env),
        "engine_config": str(args.engine_config),
        "command": {},
        "files": {},
        "error": "",
    }
    if not arg_file.exists():
        result["error"] = f"arg file not found: {arg_file}"
        return result
    if not generated_env.exists():
        result["error"] = f"generated env config not found: {generated_env}"
        return result

    command_result = run_command(cmd)
    result["command"] = command_result
    source_rig_cmd = [
        python_exe,
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
    result["source_rig"] = run_command(source_rig_cmd)
    scene_contract = render_dir_for(args, root_name) / "scene_contract_v3.json"
    if scene_contract.exists():
        shutil.copy2(scene_contract, package_dir / "scene_contract_v3.json")
    required = {
        "pose_dof_replay": package_dir / "visual_replay" / "pose_dof_replay.jsonl",
        "pose_dof_meta": package_dir / "visual_replay" / "pose_dof_meta.json",
        "joint_order": package_dir / "joint_order.json",
        "source_rig_asset_spec": package_dir / "mimickit_source_rig_asset_spec.json",
        "visual_alignment_contract": package_dir / "visual_alignment_contract.json",
        "scene_contract_v3": package_dir / "scene_contract_v3.json",
        "mesh_binding_contract": package_dir / "mesh_binding_contract.json",
    }
    result["files"] = {key: str(path) for key, path in required.items()}
    missing = [key for key, path in required.items() if not path.exists() or path.stat().st_size <= 0]
    result["missing"] = missing
    result["ok"] = bool(command_result.get("ok")) and not missing
    if not result["ok"] and not result.get("error"):
        result["error"] = "package export failed or required sidecars are missing"
    return result


def write_manifest(args: argparse.Namespace, root_name: str, manifest: dict[str, Any]) -> None:
    train_manifest = Path(args.train_root) / root_name / "mesh_reference_manifest.json"
    img_manifest = Path(args.img_root) / root_name / "mesh_reference_manifest.json"
    write_json(train_manifest, manifest)
    write_json(img_manifest, manifest)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a MimicKit white-knight sword/shield mesh reference.")
    parser.add_argument("--root-name", default=default_root_name())
    parser.add_argument("--train-root", default=str(DEFAULT_TRAIN_ROOT))
    parser.add_argument("--img-root", default=str(DEFAULT_IMG_ROOT))
    parser.add_argument("--motion-id", default=DEFAULT_MOTION_ID)
    parser.add_argument("--case", default=DEFAULT_CASE)
    parser.add_argument("--base-env-config", default=str(DEFAULT_BASE_ENV))
    parser.add_argument("--engine-config", default=str(DEFAULT_ENGINE))
    parser.add_argument("--conda-env", default="mimickit-isaaclab")
    parser.add_argument("--render-python", default="", help="Explicit Python executable; bypasses conda run.")
    parser.add_argument("--frames", type=int, default=10)
    parser.add_argument("--frame-stride", type=int, default=5)
    parser.add_argument("--mp4-fps", type=int, default=12)
    parser.add_argument("--width", type=int, default=960)
    parser.add_argument("--height", type=int, default=540)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--num-envs", type=int, default=1)
    parser.add_argument("--force-root", action="store_true")
    parser.add_argument("--skip-precheck", action="store_true")
    parser.add_argument("--dry-run-only", action="store_true")
    parser.add_argument("--no-render", action="store_true")
    parser.add_argument("--run-native-windows", action="store_true", help="Run the mesh reference builder in the Windows native workspace, then ingest outputs back into this workspace.")
    parser.add_argument("--ingest-native-windows", action="store_true", help="Copy an already-built Windows native mesh reference root back into this workspace.")
    parser.add_argument("--windows-workspace-root", default=DEFAULT_WINDOWS_WORKSPACE_ROOT)
    parser.add_argument("--windows-workspace-wsl", default=str(DEFAULT_WINDOWS_WORKSPACE_WSL))
    parser.add_argument("--windows-conda-env", default=DEFAULT_WINDOWS_CONDA_ENV)
    parser.add_argument("--no-sync-native-workspace-scripts", dest="sync_native_workspace_scripts", action="store_false", default=True)
    parser.add_argument("--asset-export-format", choices=("glb", "gltf"), default="glb")
    parser.add_argument("--asset-export-python", default="", help="Python executable for the Omniverse asset export helper; defaults to --render-python or the current interpreter.")
    parser.add_argument("--skip-asset-export", action="store_true", help="Skip USD->GLTF/GLB export. This prevents mesh_reference_pass from becoming true.")
    parser.add_argument("--package-export-python", default="", help="Python executable for ue_export_mesh_reference; defaults to --render-python or the current interpreter.")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--unset-display", action="store_true", default=True)
    parser.add_argument("--vk-icd-filenames", default="")
    args = parser.parse_args()
    args.train_root = Path(args.train_root).resolve()
    args.img_root = Path(args.img_root).resolve()
    args.base_env_config = Path(args.base_env_config).resolve()
    args.engine_config = Path(args.engine_config).resolve()
    return args


def main() -> int:
    args = parse_args()
    root_name = str(args.root_name).strip() or default_root_name()
    train_root_dir = Path(args.train_root) / root_name
    img_root_dir = Path(args.img_root) / root_name
    train_root_dir.mkdir(parents=True, exist_ok=True)
    img_root_dir.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, Any] = {
        "schema_version": 1,
        "created_at_utc": utc_now(),
        "root_name": root_name,
        "train_root_dir": str(train_root_dir),
        "img_root_dir": str(img_root_dir),
        "motion_id": args.motion_id,
        "case": args.case,
        "base_env_config": str(args.base_env_config),
        "engine_config": str(args.engine_config),
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
        "scene_contract": scene_contract(args, root_name),
        "conda_env": args.conda_env,
        "render_python": args.render_python,
        "asset_export": {
            "ok": False,
            "skipped": bool(args.skip_asset_export),
            "source_usd_file": str(DEFAULT_USD),
            "source_usd_sha256": sha256_file(DEFAULT_USD),
            "format": args.asset_export_format,
            "glb_file": "",
            "gltf_file": "",
            "output_file": "",
            "output_sha256": "",
        },
        "package_export": {
            "ok": False,
            "package_dir": str(train_root_dir / "ue_export_mesh_reference"),
            "files": {},
            "missing": [],
        },
        "native_windows": {
            "requested_run": bool(args.run_native_windows),
            "requested_ingest": bool(args.ingest_native_windows),
            "workspace_root": args.windows_workspace_root,
            "workspace_wsl": args.windows_workspace_wsl,
            "conda_env": args.windows_conda_env,
            "script_sync": {"ok": False, "skipped": not bool(args.sync_native_workspace_scripts)},
            "run": {"ok": False, "skipped": not bool(args.run_native_windows)},
            "ingest": {"ok": False, "skipped": not bool(args.ingest_native_windows or args.run_native_windows)},
        },
        "precheck": {"ok": False, "skipped": bool(args.skip_precheck)},
        "build_synthetic_root": {"ok": False},
        "dry_run": {"ok": False},
        "render": {"ok": False, "skipped": bool(args.no_render or args.dry_run_only)},
        "contact_sheet": {"ok": False},
        "mesh_reference_pass": False,
        "blocker": "",
        "native_windows_fallback": {
            "script": str(ROOT / "tools" / "windows" / "run_white_knight_mesh_viewmotion.ps1"),
            "recommended_when": "WSL Isaac Lab precheck/render fails due missing omni.kit.usd, gpu.foundation, Vulkan, or headless renderer startup",
        },
    }

    try:
        if args.run_native_windows:
            if args.sync_native_workspace_scripts:
                script_sync = sync_native_workspace_scripts(args)
                manifest["native_windows"]["script_sync"] = script_sync
                if not script_sync.get("ok"):
                    manifest["blocker"] = "native_windows_script_sync_failed"
                    write_manifest(args, root_name, manifest)
                    print(json.dumps(manifest, indent=2, ensure_ascii=False))
                    return 6
            native_run = run_windows_native_reference(args, root_name)
            manifest["native_windows"]["run"] = native_run
            if not native_run.get("ok"):
                manifest["blocker"] = "native_windows_mesh_reference_failed"
                diagnostic_ingest = ingest_windows_outputs(args, root_name)
                manifest["native_windows"]["ingest"] = diagnostic_ingest
                native_manifest = read_json(Path(args.train_root) / root_name / "mesh_reference_manifest.json")
                if native_manifest:
                    native_manifest = localize_native_manifest_paths(native_manifest, Path(args.train_root), Path(args.img_root), root_name)
                    native_manifest["native_windows"] = manifest["native_windows"]
                    native_manifest.setdefault("outer_blocker", manifest["blocker"])
                    write_manifest(args, root_name, native_manifest)
                    print(json.dumps(native_manifest, indent=2, ensure_ascii=False))
                    return 6
                write_manifest(args, root_name, manifest)
                print(json.dumps(manifest, indent=2, ensure_ascii=False))
                return 6
            args.ingest_native_windows = True

        if args.ingest_native_windows:
            ingest = ingest_windows_outputs(args, root_name)
            manifest["native_windows"]["ingest"] = ingest
            if not ingest.get("ok"):
                manifest["blocker"] = "native_windows_ingest_failed"
                write_manifest(args, root_name, manifest)
                print(json.dumps(manifest, indent=2, ensure_ascii=False))
                return 6
            native_manifest = read_json(Path(args.train_root) / root_name / "mesh_reference_manifest.json")
            if native_manifest:
                native_manifest = localize_native_manifest_paths(native_manifest, Path(args.train_root), Path(args.img_root), root_name)
                native_manifest["native_windows"] = manifest["native_windows"]
                write_manifest(args, root_name, native_manifest)
                print(json.dumps(native_manifest, indent=2, ensure_ascii=False))
                return 0 if native_manifest.get("mesh_reference_pass") else 4

        build_result = build_synthetic_root(args, root_name)
        manifest["build_synthetic_root"] = build_result
        if not build_result["ok"]:
            manifest["blocker"] = "synthetic_root_build_failed"
            write_manifest(args, root_name, manifest)
            print(json.dumps(manifest, indent=2, ensure_ascii=False))
            return 2

        dry_run_result = run_command(render_command(args, root_name, dry_run=True), env=render_env(args))
        manifest["dry_run"] = dry_run_result
        if not dry_run_result["ok"]:
            manifest["blocker"] = "dry_run_failed"
            write_manifest(args, root_name, manifest)
            print(json.dumps(manifest, indent=2, ensure_ascii=False))
            return 2

        precheck = {"ok": True, "skipped": True} if args.skip_precheck else run_precheck(args)
        manifest["precheck"] = precheck
        if not precheck["ok"] and not args.skip_precheck:
            manifest["blocker"] = "isaaclab_precheck_failed"
            write_manifest(args, root_name, manifest)
            print(json.dumps(manifest, indent=2, ensure_ascii=False))
            return 3

        if args.dry_run_only or args.no_render:
            manifest["blocker"] = "render_skipped_by_request"
            write_manifest(args, root_name, manifest)
            print(json.dumps(manifest, indent=2, ensure_ascii=False))
            return 0 if args.dry_run_only else 3

        render_result = run_command(render_command(args, root_name, dry_run=False), env=render_env(args))
        manifest["render"] = render_result
        summary = summarize_render(args, root_name)
        manifest["render_summary"] = summary
        manifest["frame_ids"] = summary.get("frame_ids", [])
        manifest["png_count"] = int(summary.get("image_count", 0) or summary.get("frame_count_on_disk", 0) or 0)
        manifest["mp4_ok"] = bool(summary.get("mp4_ok"))
        manifest["source_was_ppm_only"] = bool(summary.get("source_was_ppm_only"))
        manifest["scene_contract_v3"] = summary.get("scene_contract_v3", {})
        manifest["scene_contract_sha256"] = summary.get("scene_contract_sha256", "")
        contact = build_contact_sheet(Path(summary["render_dir"]), Path(summary["render_dir"]) / "mesh_reference_contact_sheet.png")
        manifest["contact_sheet"] = contact
        asset_export = run_asset_export(args, root_name)
        manifest["asset_export"] = asset_export
        package_export = run_package_export(args, root_name)
        manifest["package_export"] = package_export
        glb_export_ok = (
            str(asset_export.get("format", "")) == "glb"
            and bool(asset_export.get("ok"))
            and bool((asset_export.get("asset_structure") or {}).get("ok"))
            and bool(str(asset_export.get("glb_file", "")).strip())
            and Path(str(asset_export.get("glb_file", ""))).exists()
        )
        manifest["mesh_reference_pass"] = (
            bool(summary.get("mesh_reference_pass"))
            and bool(contact.get("ok"))
            and glb_export_ok
            and bool(package_export.get("ok"))
            and not bool(summary.get("source_was_ppm_only"))
        )
        if not manifest["mesh_reference_pass"]:
            if bool(summary.get("source_was_ppm_only")):
                manifest["blocker"] = "ppm_only_output_rejected"
            elif not bool(summary.get("mesh_reference_pass")):
                manifest["blocker"] = "mesh_render_failed_or_incomplete"
            elif not bool(contact.get("ok")):
                manifest["blocker"] = "contact_sheet_failed"
            elif not glb_export_ok:
                manifest["blocker"] = "mesh_asset_export_failed"
            elif not bool(package_export.get("ok")):
                manifest["blocker"] = "mesh_package_export_failed"
            else:
                manifest["blocker"] = "mesh_reference_gate_failed"
        write_manifest(args, root_name, manifest)
        print(json.dumps(manifest, indent=2, ensure_ascii=False))
        return 0 if manifest["mesh_reference_pass"] else 4
    except BaseException as exc:
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        manifest["blocker"] = "script_exception"
        manifest["exception"] = f"{type(exc).__name__}: {exc}"
        write_manifest(args, root_name, manifest)
        print(json.dumps(manifest, indent=2, ensure_ascii=False))
        return 5


if __name__ == "__main__":
    raise SystemExit(main())
