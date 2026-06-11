#!/usr/bin/env python3
"""Validation helpers shared by MimicKit visual bridge tooling."""

from __future__ import annotations

import hashlib
import json
import math
import shutil
import struct
import subprocess
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as fp:
        for chunk in iter(lambda: fp.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_json_sha256(data: dict[str, Any]) -> str:
    payload = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _read_glb_json(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    if len(raw) < 20:
        raise ValueError("GLB is too small")
    magic, version, total_length = struct.unpack_from("<4sII", raw, 0)
    if magic != b"glTF" or version != 2 or total_length != len(raw):
        raise ValueError("invalid GLB header")
    offset = 12
    while offset + 8 <= len(raw):
        chunk_length, chunk_type = struct.unpack_from("<II", raw, offset)
        offset += 8
        chunk = raw[offset : offset + chunk_length]
        offset += chunk_length
        if chunk_type == 0x4E4F534A:
            data = json.loads(chunk.rstrip(b" \t\r\n\0").decode("utf-8"))
            return data if isinstance(data, dict) else {}
    raise ValueError("GLB JSON chunk is missing")


def inspect_glb(path: Path) -> dict[str, Any]:
    report: dict[str, Any] = {
        "schema_version": 1,
        "asset_file": str(path),
        "asset_sha256": sha256_file(path),
        "asset_size_bytes": path.stat().st_size if path.exists() else 0,
        "ok": False,
        "blocker": "",
    }
    if not path.exists() or not path.is_file():
        report["blocker"] = "mesh_asset_missing"
        return report
    try:
        data = _read_glb_json(path) if path.suffix.lower() == ".glb" else json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        report["blocker"] = "mesh_asset_parse_failed"
        report["error"] = f"{type(exc).__name__}: {exc}"
        return report

    nodes = data.get("nodes") if isinstance(data.get("nodes"), list) else []
    meshes = data.get("meshes") if isinstance(data.get("meshes"), list) else []
    accessors = data.get("accessors") if isinstance(data.get("accessors"), list) else []
    buffers = data.get("buffers") if isinstance(data.get("buffers"), list) else []
    skins = data.get("skins") if isinstance(data.get("skins"), list) else []
    materials = data.get("materials") if isinstance(data.get("materials"), list) else []
    node_names = [str(node.get("name", "")) for node in nodes if isinstance(node, dict)]
    primitive_count = 0
    vertex_count = 0
    for mesh in meshes:
        primitives = mesh.get("primitives") if isinstance(mesh, dict) and isinstance(mesh.get("primitives"), list) else []
        primitive_count += len(primitives)
        for primitive in primitives:
            attrs = primitive.get("attributes") if isinstance(primitive, dict) and isinstance(primitive.get("attributes"), dict) else {}
            position_accessor = attrs.get("POSITION")
            if isinstance(position_accessor, int) and 0 <= position_accessor < len(accessors):
                accessor = accessors[position_accessor]
                if isinstance(accessor, dict):
                    vertex_count += int(accessor.get("count", 0) or 0)

    lowered_names = [name.lower() for name in node_names]
    required_named_nodes = {
        "sword": any("sword" in name for name in lowered_names),
        "shield": any("shield" in name for name in lowered_names),
    }
    renderable_node_count = sum(
        1 for node in nodes if isinstance(node, dict) and isinstance(node.get("mesh"), int)
    )
    mesh_mode = "skinned" if skins else ("rigid_node" if renderable_node_count else "")
    report.update(
        {
            "node_count": len(nodes),
            "mesh_count": len(meshes),
            "primitive_count": primitive_count,
            "vertex_count": vertex_count,
            "buffer_count": len(buffers),
            "skin_count": len(skins),
            "material_count": len(materials),
            "renderable_node_count": renderable_node_count,
            "node_names": node_names,
            "required_named_nodes": required_named_nodes,
            "mesh_mode": mesh_mode,
        }
    )
    report["ok"] = bool(
        buffers
        and nodes
        and meshes
        and primitive_count > 0
        and vertex_count > 0
        and renderable_node_count > 0
        and all(required_named_nodes.values())
    )
    if not report["ok"]:
        report["blocker"] = "mesh_asset_structure_invalid"
    return report


def inspect_png(path: Path, expected_width: int = 0, expected_height: int = 0) -> dict[str, Any]:
    report: dict[str, Any] = {"file": str(path), "ok": False}
    try:
        from PIL import Image, ImageStat

        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            rgb = image.convert("RGB")
            stat = ImageStat.Stat(rgb)
            extrema = rgb.getextrema()
            width, height = rgb.size
        dynamic = any(high > low for low, high in extrema)
        report.update(
            {
                "width": width,
                "height": height,
                "mean_rgb": [float(value) for value in stat.mean],
                "dynamic": dynamic,
                "ok": bool(
                    path.stat().st_size > 0
                    and dynamic
                    and (expected_width <= 0 or width == expected_width)
                    and (expected_height <= 0 or height == expected_height)
                ),
            }
        )
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
    return report


def inspect_mp4(path: Path, expected_fps: int = 0, expected_frames: int = 0) -> dict[str, Any]:
    report: dict[str, Any] = {"file": str(path), "ok": False, "size_bytes": path.stat().st_size if path.exists() else 0}
    ffprobe = shutil.which("ffprobe")
    if not path.exists() or path.stat().st_size <= 0:
        report["blocker"] = "mp4_missing_or_empty"
        return report
    if not ffprobe:
        try:
            import cv2

            capture = cv2.VideoCapture(str(path))
            fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
            frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
            height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
            opened = bool(capture.isOpened())
            capture.release()
            report.update(
                {
                    "probe_method": "opencv_fallback_pending_final_ffprobe",
                    "fps": fps,
                    "frame_count": frames,
                    "probe": {"width": width, "height": height},
                }
            )
            report["ok"] = bool(
                opened
                and width > 0
                and height > 0
                and (expected_fps <= 0 or math.isclose(fps, float(expected_fps), rel_tol=0.02, abs_tol=0.02))
                and (expected_frames <= 0 or frames == expected_frames)
            )
            if not report["ok"]:
                report["blocker"] = "mp4_probe_failed"
            return report
        except Exception as exc:
            report["blocker"] = "ffprobe_not_found"
            report["error"] = f"{type(exc).__name__}: {exc}"
            return report
    proc = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-count_frames",
            "-show_entries",
            "stream=codec_name,width,height,avg_frame_rate,nb_read_frames,duration",
            "-of",
            "json",
            str(path),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        payload = json.loads(proc.stdout)
        stream = payload.get("streams", [{}])[0]
    except Exception:
        stream = {}
    rate = str(stream.get("avg_frame_rate", "0/1"))
    numerator, denominator = (rate.split("/", 1) + ["1"])[:2]
    fps = float(numerator) / max(float(denominator), 1.0)
    frames = int(stream.get("nb_read_frames", 0) or 0)
    report.update({"probe": stream, "fps": fps, "frame_count": frames})
    report["ok"] = bool(
        proc.returncode == 0
        and stream.get("codec_name")
        and (expected_fps <= 0 or math.isclose(fps, float(expected_fps), rel_tol=0.02, abs_tol=0.02))
        and (expected_frames <= 0 or frames == expected_frames)
    )
    if not report["ok"]:
        report["blocker"] = "mp4_probe_failed"
        report["stderr_tail"] = proc.stderr[-1000:]
    return report


def build_scene_contract_v2(
    *,
    root_name: str,
    case: str,
    motion_id: str,
    width: int,
    height: int,
    frames: int,
    frame_stride: int,
    fps: int,
    seed: int,
    renderer: str,
    camera_samples: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    contract: dict[str, Any] = {
        "schema_version": 2,
        "root_name": root_name,
        "case": case,
        "motion_id": motion_id,
        "resolution": {"width": int(width), "height": int(height)},
        "timing": {
            "frames": int(frames),
            "frame_stride": int(frame_stride),
            "fps": int(fps),
            "expected_frame_ids": list(range(0, int(frames), max(1, int(frame_stride)))),
        },
        "seed": int(seed),
        "coordinate_system": {"basis": "mimickit_training_xyz", "root_pos_units": "meters", "rotation": "quat_xyzw"},
        "camera": {"mode": "track", "initial_eye_offset_m": [0.0, -5.0, 3.0], "initial_target_offset_m": [0.0, 0.0, 1.0]},
        "ground": {"kind": "flat_plane", "color_rgb": [0.017, 0.0153, 0.01275]},
        "lights": {
            "distant": {"intensity": 2000.0, "color_rgb": [0.8, 0.8, 0.8]},
            "dome": {"intensity": 800.0, "color_rgb": [0.7, 0.7, 0.7]},
        },
        "renderer": renderer,
        "color_space": "srgb",
        "camera_samples": camera_samples or [],
    }
    contract["scene_contract_sha256"] = stable_json_sha256(contract)
    return contract


def build_scene_contract_v3(
    *,
    root_name: str,
    case: str,
    motion_id: str,
    width: int = 960,
    height: int = 540,
    frames: int = 300,
    frame_stride: int = 5,
    fps: int = 12,
    seed: int = 7,
    base_env_config: str = "",
    engine_config: str = "",
    renderer: str = "",
    source_capture_index_sha256: str = "",
    camera_samples: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    expected_frame_ids = list(range(0, int(frames), max(1, int(frame_stride))))
    samples = camera_samples or []
    samples_by_frame = {
        int(sample.get("frame", -1)): sample
        for sample in samples
        if isinstance(sample, dict)
    }
    for frame_id in expected_frame_ids:
        sample = samples_by_frame.get(frame_id)
        if sample is None:
            raise ValueError(f"scene contract camera sample missing for frame {frame_id}")
        for field in ("eye", "target"):
            values = sample.get(field)
            if not isinstance(values, list) or len(values) != 3 or not all(math.isfinite(float(value)) for value in values):
                raise ValueError(f"scene contract camera sample has invalid {field} for frame {frame_id}")
        fov = sample.get("fov_degrees")
        if fov is None or not math.isfinite(float(fov)) or not 0.0 < float(fov) < 180.0:
            raise ValueError(f"scene contract camera sample has invalid fov_degrees for frame {frame_id}")
        if sample.get("fov_axis") not in {"horizontal", "vertical"}:
            raise ValueError(f"scene contract camera sample has invalid fov_axis for frame {frame_id}")
        if sample.get("projection") != "perspective":
            raise ValueError(f"scene contract camera sample has unsupported projection for frame {frame_id}")
        near = float(sample.get("near", 0.0))
        far = float(sample.get("far", 0.0))
        if not math.isfinite(near) or not math.isfinite(far) or near <= 0.0 or far <= near:
            raise ValueError(f"scene contract camera sample has invalid clipping range for frame {frame_id}")

    contract: dict[str, Any] = {
        "schema_version": 3,
        "root_name": root_name,
        "resolution": {"width": int(width), "height": int(height)},
        "timing": {
            "frames": int(frames),
            "frame_stride": int(frame_stride),
            "fps": int(fps),
            "expected_frame_ids": expected_frame_ids,
        },
        "motion_id": motion_id,
        "case": case,
        "source": {
            "base_env_config": base_env_config,
            "engine_config": engine_config,
            "capture_index_sha256": source_capture_index_sha256,
        },
        "coordinate_system": {
            "basis": "mimickit_training_xyz_z_up",
            "root_pos_units": "meters",
            "rotation": "quat_xyzw",
        },
        "camera": {"mode": "track", "projection": "perspective"},
        "ground": {
            "kind": "flat_grid_plane",
            "semantic_label": "mimickit_ground",
            "color_rgb": [0.017, 0.0153, 0.01275],
            "albedo_add": 10.0,
            "grid_spacing_m": 1.0,
            "major_grid_spacing_m": 5.0,
        },
        "lights": {
            "distant": {"intensity": 2000.0, "color_rgb": [0.8, 0.8, 0.8]},
            "dome": {"intensity": 800.0, "color_rgb": [0.7, 0.7, 0.7]},
        },
        "renderer": renderer,
        "color_space": "srgb",
        "debug_overlays": False,
        "seed": int(seed),
        "camera_samples": samples,
    }
    contract["scene_contract_sha256"] = stable_json_sha256(contract)
    return contract


def validate_body_world_replay(package_dir: Path) -> dict[str, Any]:
    pose_path = package_dir / "visual_replay" / "pose_dof_replay.jsonl"
    body_path = package_dir / "visual_replay" / "body_world_replay.jsonl"
    joint_path = package_dir / "joint_order.json"

    def read_jsonl(path: Path) -> list[dict[str, Any]]:
        if not path.is_file():
            return []
        rows: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                value = json.loads(line)
                if isinstance(value, dict):
                    rows.append(value)
        return rows

    pose_rows = read_jsonl(pose_path)
    body_rows = read_jsonl(body_path)
    joint_order = json.loads(joint_path.read_text(encoding="utf-8")) if joint_path.is_file() else {}
    body_order = [str(value) for value in joint_order.get("body_order", [])] if isinstance(joint_order, dict) else []
    pose_frames = [int(row.get("frame", -1)) for row in pose_rows]
    body_frames = [int(row.get("frame", -1)) for row in body_rows]
    finite_rows = True
    dimensions_ok = bool(body_order and body_rows)
    authoritative_source_ok = bool(body_rows)
    for row in body_rows:
        positions = row.get("body_pos_m", [])
        rotations = row.get("body_rot_xyzw", [])
        dimensions_ok = dimensions_ok and len(positions) == len(body_order) * 3 and len(rotations) == len(body_order) * 4
        finite_rows = finite_rows and all(math.isfinite(float(value)) for value in [*positions, *rotations])
        dimensions_ok = dimensions_ok and row.get("body_order") == body_order
        authoritative_source_ok = authoritative_source_ok and row.get("source") == "canonical_source_rig_fk_v3"
    checks = {
        "pose_replay_exists": pose_path.is_file(),
        "body_world_replay_exists": body_path.is_file(),
        "joint_order_exists": joint_path.is_file(),
        "frame_ids_match": bool(pose_frames) and pose_frames == body_frames,
        "body_order_and_dimensions_match": bool(dimensions_ok),
        "all_rows_finite": bool(finite_rows and body_rows),
        "authoritative_source_is_canonical_source_rig_fk_v3": bool(authoritative_source_ok),
    }
    return {
        "schema_version": 1,
        "data_binding_ok": all(checks.values()),
        "checks": checks,
        "row_count": len(body_rows),
        "body_count": len(body_order),
        "pose_dof_replay_sha256": sha256_file(pose_path),
        "body_world_replay_sha256": sha256_file(body_path),
        "joint_order_sha256": sha256_file(joint_path),
        "blocker": "" if all(checks.values()) else "body_world_replay_invalid",
    }
