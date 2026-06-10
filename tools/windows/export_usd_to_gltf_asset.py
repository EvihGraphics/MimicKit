#!/usr/bin/env python3
"""Export a USD asset to GLB/GLTF through Omniverse asset_converter.

This helper is intended to run inside an Isaac Sim / Isaac Lab Python
environment where omni.kit.asset_converter is available.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from isaaclab.app import AppLauncher

ROOT = Path(__file__).resolve().parents[2]
UE_BRIDGE_DIR = ROOT / "tools" / "ue_bridge"
if str(UE_BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(UE_BRIDGE_DIR))

from visual_bridge_validation import inspect_glb  # noqa: E402


def utc_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def sha256_file(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as fp:
        for chunk in iter(lambda: fp.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export MimicKit USD to GLB/GLTF using Omniverse asset_converter.")
    parser.add_argument("--input-usd", required=True)
    parser.add_argument("--output-asset", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--ignore-cameras", action="store_true", default=True)
    parser.add_argument("--ignore-lights", action="store_true", default=True)
    parser.add_argument("--embed-textures", action="store_true", default=True)
    AppLauncher.add_app_launcher_args(parser)
    return parser.parse_args()


async def convert_asset(input_usd: Path, output_asset: Path) -> tuple[bool, str]:
    import omni.kit.app

    ext_manager = omni.kit.app.get_app().get_extension_manager()
    ext_manager.set_extension_enabled_immediate("omni.kit.asset_converter", True)
    import omni.kit.asset_converter

    def progress_callback(current_step: int, total: int) -> None:
        print(f"[asset_converter] {current_step}/{total}")

    context = omni.kit.asset_converter.AssetConverterContext()
    context.ignore_camera = True
    context.ignore_light = True
    context.embed_textures = True
    context.keep_all_materials = True
    context.export_preview_surface = True
    context.use_meter_as_world_unit = True

    output_asset.parent.mkdir(parents=True, exist_ok=True)
    manager = omni.kit.asset_converter.get_instance()
    task = manager.create_converter_task(str(input_usd), str(output_asset), progress_callback, context)
    success = await task.wait_until_finished()
    if success:
        return True, ""
    return False, str(task.get_error_message())


def _matrix_to_numpy(matrix: Any):
    import numpy as np

    return np.asarray([[float(matrix[row][col]) for col in range(4)] for row in range(4)], dtype=float).T


def _mesh_from_usd_prim(prim: Any):
    import numpy as np
    import trimesh
    from pxr import UsdGeom

    if prim.IsA(UsdGeom.Cube):
        size = float(UsdGeom.Cube(prim).GetSizeAttr().Get() or 2.0)
        return trimesh.creation.box(extents=[size, size, size])
    if prim.IsA(UsdGeom.Sphere):
        radius = float(UsdGeom.Sphere(prim).GetRadiusAttr().Get() or 1.0)
        return trimesh.creation.icosphere(subdivisions=2, radius=radius)
    if prim.IsA(UsdGeom.Cylinder):
        shape = UsdGeom.Cylinder(prim)
        radius = float(shape.GetRadiusAttr().Get() or 1.0)
        height = float(shape.GetHeightAttr().Get() or 2.0)
        mesh = trimesh.creation.cylinder(radius=radius, height=height, sections=24)
        axis = str(shape.GetAxisAttr().Get() or "Z").upper()
        if axis == "X":
            mesh.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2.0, [0.0, 1.0, 0.0]))
        elif axis == "Y":
            mesh.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2.0, [1.0, 0.0, 0.0]))
        return mesh
    if prim.IsA(UsdGeom.Capsule):
        shape = UsdGeom.Capsule(prim)
        radius = float(shape.GetRadiusAttr().Get() or 0.5)
        height = float(shape.GetHeightAttr().Get() or 1.0)
        mesh = trimesh.creation.capsule(radius=radius, height=height, count=[12, 24])
        axis = str(shape.GetAxisAttr().Get() or "Z").upper()
        if axis == "X":
            mesh.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2.0, [0.0, 1.0, 0.0]))
        elif axis == "Y":
            mesh.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2.0, [1.0, 0.0, 0.0]))
        return mesh
    if prim.IsA(UsdGeom.Mesh):
        shape = UsdGeom.Mesh(prim)
        vertices = np.asarray(shape.GetPointsAttr().Get() or [], dtype=float)
        counts = [int(value) for value in (shape.GetFaceVertexCountsAttr().Get() or [])]
        indices = [int(value) for value in (shape.GetFaceVertexIndicesAttr().Get() or [])]
        faces = []
        offset = 0
        for count in counts:
            polygon = indices[offset : offset + count]
            offset += count
            for index in range(1, max(1, count - 1)):
                if index + 1 < len(polygon):
                    faces.append([polygon[0], polygon[index], polygon[index + 1]])
        if len(vertices) and faces:
            return trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    return None


def export_usd_stage_to_rigid_glb(input_usd: Path, output_asset: Path) -> dict[str, Any]:
    import numpy as np
    import trimesh
    from pxr import Usd, UsdGeom, UsdPhysics

    stage = Usd.Stage.Open(str(input_usd))
    if stage is None:
        raise RuntimeError(f"failed to open USD stage: {input_usd}")

    meters_per_unit = float(UsdGeom.GetStageMetersPerUnit(stage))

    required_body_names = {
        "pelvis", "torso", "head", "right_upper_arm", "right_lower_arm",
        "right_hand", "sword", "left_upper_arm", "left_lower_arm", "shield",
        "left_hand", "right_thigh", "right_shin", "right_foot", "left_thigh",
        "left_shin", "left_foot",
    }
    by_body: dict[str, list[Any]] = {}
    body_world: dict[str, Any] = {}
    converted_prims = 0
    geometry_prim_count = 0
    for prim in Usd.PrimRange.Stage(stage, Usd.TraverseInstanceProxies()):
        mesh = _mesh_from_usd_prim(prim)
        if mesh is None:
            continue
        geometry_prim_count += 1
        body = prim
        while (
            body
            and body.IsValid()
            and not body.HasAPI(UsdPhysics.RigidBodyAPI)
            and str(body.GetName()) not in required_body_names
        ):
            body = body.GetParent()
        if not body or not body.IsValid():
            continue
        body_name = str(body.GetName())
        if body_name not in required_body_names:
            continue
        geom_world = _matrix_to_numpy(UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default()))
        current_body_world = _matrix_to_numpy(UsdGeom.Xformable(body).ComputeLocalToWorldTransform(Usd.TimeCode.Default()))
        local_transform = np.linalg.inv(current_body_world) @ geom_world
        mesh.apply_transform(local_transform)
        mesh.apply_transform(trimesh.transformations.scale_matrix(meters_per_unit))
        by_body.setdefault(body_name, []).append(mesh)
        
        scaled_body_world = current_body_world.copy()
        scaled_body_world[:3, 3] *= meters_per_unit
        body_world[body_name] = scaled_body_world
        converted_prims += 1

    if not by_body:
        raise RuntimeError(
            "USD stage contains no renderable mesh or primitive under character bodies "
            f"(geometry_prims={geometry_prim_count})"
        )

    scene = trimesh.Scene()
    for body_name, pieces in by_body.items():
        combined = trimesh.util.concatenate(pieces)
        scene.add_geometry(
            combined,
            node_name=body_name,
            geom_name=f"{body_name}_mesh",
            transform=body_world[body_name],
        )
    output_asset.parent.mkdir(parents=True, exist_ok=True)
    output_asset.write_bytes(scene.export(file_type="glb"))
    return {
        "method": "usd_stage_rigid_primitive_tessellation",
        "body_count": len(by_body),
        "body_names": sorted(by_body),
        "converted_primitive_count": converted_prims,
        "geometry_prim_count": geometry_prim_count,
    }


def main() -> int:
    args = parse_args()
    app_launcher = AppLauncher(args)
    simulation_app = app_launcher.app

    input_usd = Path(args.input_usd).resolve()
    output_asset = Path(args.output_asset).resolve()
    manifest_path = Path(args.manifest).resolve()
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "created_at_utc": utc_now(),
        "ok": False,
        "source_usd_file": str(input_usd),
        "source_usd_sha256": sha256_file(input_usd),
        "output_file": str(output_asset),
        "output_sha256": "",
        "glb_file": str(output_asset) if output_asset.suffix.lower() == ".glb" else "",
        "gltf_file": str(output_asset) if output_asset.suffix.lower() == ".gltf" else "",
        "error": "",
    }

    try:
        ok, error = asyncio.get_event_loop().run_until_complete(convert_asset(input_usd, output_asset))
        structure = inspect_glb(output_asset) if output_asset.suffix.lower() == ".glb" else {"ok": False, "blocker": "gltf_structure_validation_not_implemented"}
        manifest["export_method"] = "omni.kit.asset_converter"
        if output_asset.suffix.lower() == ".glb" and not structure.get("ok"):
            manifest["asset_converter_structure"] = structure
            manifest["usd_stage_export"] = export_usd_stage_to_rigid_glb(input_usd, output_asset)
            manifest["export_method"] = str(manifest["usd_stage_export"]["method"])
            structure = inspect_glb(output_asset)
            ok = bool(structure.get("ok"))
            error = "" if ok else str(structure.get("blocker", ""))
        manifest["asset_structure"] = structure
        manifest["asset_structure_manifest"] = str(output_asset.parent / "asset_structure_manifest.json")
        write_json(Path(manifest["asset_structure_manifest"]), structure)
        manifest["ok"] = bool(ok and structure.get("ok"))
        manifest["output_sha256"] = sha256_file(output_asset)
        manifest["error"] = (error or str(structure.get("blocker", ""))) if not manifest["ok"] else ""
        write_json(manifest_path, manifest)
        print(json.dumps(manifest, indent=2, ensure_ascii=False))
        return 0 if manifest["ok"] else 2
    except BaseException as exc:
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        manifest["error"] = f"{type(exc).__name__}: {exc}"
        write_json(manifest_path, manifest)
        print(json.dumps(manifest, indent=2, ensure_ascii=False))
        return 3
    finally:
        simulation_app.close()


if __name__ == "__main__":
    raise SystemExit(main())
