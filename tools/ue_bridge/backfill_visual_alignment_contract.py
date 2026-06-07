#!/usr/bin/env python3
"""Write visual/model/scene alignment contracts into existing MimicKit UE packages."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - optional dependency in bridge repair environments
    yaml = None


ROOT = Path(__file__).resolve().parents[2]
IMG_ROOT = ROOT / "output" / "img"

DEFAULT_UE_SKELETAL_TARGET = {
    "asset_strategy": "manny_poseable_fallback_until_mimickit_usd_skeletal_import",
    "skeletal_mesh": "/GASPALS/Characters/UE5_Mannequins/Meshes/SKM_Manny.SKM_Manny",
    "skeleton": "/GASPALS/Characters/UE5_Mannequins/Meshes/SK_Mannequin.SK_Mannequin",
    "anim_blueprint": "",
    "control_rig": "/GASPALS/Characters/UE5_Mannequins/Rigs/CR_Mannequin_Body.CR_Mannequin_Body",
    "fallback_renderer": "procedural_mimickit_skeletal_replay",
    "full_character_parity": False,
}

DEFAULT_MIMICKIT_TO_UE_BONE_MAP = {
    "pelvis": "pelvis",
    "torso": "spine_03",
    "head": "head",
    "right_upper_arm": "upperarm_r",
    "right_lower_arm": "lowerarm_r",
    "right_hand": "hand_r",
    "sword": "hand_r",
    "left_upper_arm": "upperarm_l",
    "left_lower_arm": "lowerarm_l",
    "left_hand": "hand_l",
    "shield": "lowerarm_l",
    "right_thigh": "thigh_r",
    "right_shin": "calf_r",
    "right_foot": "foot_r",
    "left_thigh": "thigh_l",
    "left_shin": "calf_l",
    "left_foot": "foot_l",
}

DEFAULT_JOINT_AXIS_ORDER = {
    "spherical": {
        "dof_interpretation": "exponential_map_xyz_radians",
        "component_order": ["x", "y", "z"],
        "local_axis_basis": "mimickit_training_xyz",
    },
    "hinge": {
        "dof_interpretation": "single_axis_radians",
        "default_axis": "local_y",
        "joint_axis_overrides": {
            "right_elbow": "local_y",
            "left_elbow": "local_y",
            "right_knee": "local_y",
            "left_knee": "local_y",
        },
    },
    "fixed": {"dof_interpretation": "no_dof_parent_space_attachment"},
}


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    if yaml is None:
        out: dict[str, Any] = {}
        for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.split("#", 1)[0].strip()
            if not line or ":" not in line or line.startswith("-"):
                continue
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            if not key:
                continue
            if not value:
                out[key] = ""
                continue
            try:
                out[key] = ast.literal_eval(value)
            except Exception:
                if value in {"True", "False"}:
                    out[key] = value == "True"
                else:
                    try:
                        out[key] = float(value)
                    except ValueError:
                        out[key] = value.strip("\"'")
        return out
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def write_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def sha256_file(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    h = hashlib.sha256()
    with path.open("rb") as fp:
        for chunk in iter(lambda: fp.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve_path(text: str, env_config_path: Path | None = None) -> Path:
    raw = Path(str(text or "").strip())
    if raw.is_absolute():
        return raw.resolve()
    candidates: list[Path] = []
    if env_config_path is not None:
        candidates.append((env_config_path.parent / raw).resolve())
    candidates.append((ROOT / raw).resolve())
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[-1] if candidates else raw.resolve()


def visual_kind_for_char(path: Path) -> tuple[str, bool]:
    if not path.exists():
        return "missing", False
    suffix = path.suffix.lower()
    if suffix == ".usd":
        return "mesh", True
    if suffix in {".xml", ".urdf"}:
        text = path.read_text(encoding="utf-8", errors="ignore")
        has_mesh = ('type="mesh"' in text) or ("<mesh" in text)
        return ("mesh" if has_mesh else "geom"), has_mesh
    return "unknown", False


def sibling_asset(path: Path, suffix: str) -> Path | None:
    candidate = path.with_suffix(suffix)
    return candidate if candidate.exists() else None


def stable_json_sha256(obj: dict[str, Any]) -> str:
    payload = json.dumps(obj, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def build_bone_map(body_order: list[str]) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for body_name in body_order:
        ue_bone = DEFAULT_MIMICKIT_TO_UE_BONE_MAP.get(str(body_name), "")
        entries.append(
            {
                "mimickit_body": str(body_name),
                "ue_bone": ue_bone,
                "required_for_skeletal_visual_pass": bool(ue_bone and body_name not in ("sword", "shield")),
                "mapping_kind": "bone" if body_name not in ("sword", "shield") else "attachment",
            }
        )

    required_count = len([body for body in body_order if body not in ("sword", "shield")])
    mapped_required = [entry for entry in entries if entry["required_for_skeletal_visual_pass"] and entry["ue_bone"]]
    return {
        "map_name": "mimickit_sword_shield_to_ue_manny_v1",
        "target_skeleton_family": "UE5_Mannequin",
        "entries": entries,
        "mapped_required_count": len(mapped_required),
        "required_count": required_count,
        "complete_for_skeletal_visual_pass": len(mapped_required) == required_count and required_count > 0,
    }


def build_skeletal_mapping_contract(joint_order: dict[str, Any], preferred_visual_asset: Path | None) -> dict[str, Any]:
    body_order = [str(body) for body in joint_order.get("body_order", []) if str(body)]
    bone_map = build_bone_map(body_order)
    basis_transform = {
        "name": "mimickit_training_xyz_to_ue_xyz_cm_v1",
        "status": "declared_for_offline_visual_replay",
        "position": {
            "input": "root_pos_m[x,y,z]",
            "output": "ue_location_cm[x*100,y*100,z*100]",
            "matrix_row_major_3x3": [
                [100.0, 0.0, 0.0],
                [0.0, 100.0, 0.0],
                [0.0, 0.0, 100.0],
            ],
        },
        "rotation": {
            "input": "quat_xyzw",
            "output": "quat_xyzw",
            "pre_rotation_xyzw": [0.0, 0.0, 0.0, 1.0],
            "post_rotation_xyzw": [0.0, 0.0, 0.0, 1.0],
        },
        "unit_scale": "meters_to_ue_cm",
        "live_observation_control_status": "not_validated_for_runtime_control",
    }
    attachments = {
        "sword": {
            "mimickit_body": "sword",
            "attach_to_body": "right_hand",
            "attach_to_ue_bone": DEFAULT_MIMICKIT_TO_UE_BONE_MAP["right_hand"],
            "ue_asset": "",
            "fallback": "procedural_capsule_blade",
            "local_offset_m": [0.35, -0.02, 0.02],
            "local_rotation_xyzw": [0.0, 0.0, 0.0, 1.0],
        },
        "shield": {
            "mimickit_body": "shield",
            "attach_to_body": "left_lower_arm",
            "attach_to_ue_bone": DEFAULT_MIMICKIT_TO_UE_BONE_MAP["left_lower_arm"],
            "ue_asset": "",
            "fallback": "procedural_disc",
            "local_offset_m": [0.05, 0.06, 0.02],
            "local_rotation_xyzw": [0.0, 0.0, 0.0, 1.0],
        },
    }
    contract = {
        "schema_version": 2,
        "contract_role": "mimickit_to_ue_skeletal_replay_mapping",
        "ue_visual_target": {
            **DEFAULT_UE_SKELETAL_TARGET,
            "mimickit_preferred_visual_asset": str(preferred_visual_asset) if preferred_visual_asset else "",
            "mimickit_preferred_visual_asset_imported_to_ue": False,
        },
        "basis_transform": basis_transform,
        "bone_map": bone_map,
        "joint_axis_order": DEFAULT_JOINT_AXIS_ORDER,
        "attachments": attachments,
        "acceptance_thresholds": {
            "minimum_capture_frames": 1,
            "expected_capture_frames_for_stride_5_rows_300": 60,
            "requires_png_sequence": True,
            "requires_mp4": True,
            "requires_dof_pos_applied": True,
            "requires_skeletal_pose_frames": True,
            "requires_no_pose_block": True,
            "allows_manny_fallback_for_skeletal_visual_pass": True,
            "allows_full_character_parity_claim": False,
        },
    }
    contract["bone_map_hash"] = stable_json_sha256(bone_map)
    contract["basis_transform_hash"] = stable_json_sha256(basis_transform)
    return contract


def collect_render_refs(source_root: str) -> dict[str, Any]:
    if not source_root:
        return {}
    root_name = Path(source_root).name
    render_root = IMG_ROOT / root_name
    if not render_root.exists():
        return {"render_root": str(render_root), "exists": False}
    return {
        "render_root": str(render_root.resolve()),
        "exists": True,
        "mp4_files": [str(path.resolve()) for path in sorted(render_root.rglob("*.mp4"))],
        "render_meta_files": [str(path.resolve()) for path in sorted(render_root.rglob("render_meta.json"))],
        "frames_dirs": [str(path.parent.resolve()) for path in sorted(render_root.rglob("frames/index.json"))],
    }


def build_contract(package_dir: Path) -> dict[str, Any]:
    brain_manifest = read_json(package_dir / "brain_manifest.json")
    package_manifest = read_json(package_dir / "export_package_manifest.json")
    joint_order = read_json(package_dir / "joint_order.json")
    visual_meta = read_json(package_dir / "visual_replay" / "pose_dof_meta.json")

    source = brain_manifest.get("source") if isinstance(brain_manifest.get("source"), dict) else {}
    env_config_path = Path(str(source.get("env_config", ""))).resolve() if source.get("env_config") else None
    env_cfg = read_yaml(env_config_path) if env_config_path is not None else {}

    char_declared = str(env_cfg.get("char_file", "")).strip()
    char_path = resolve_path(char_declared, env_config_path) if char_declared else Path()
    visual_kind, mesh_detected = visual_kind_for_char(char_path)
    usd_path = sibling_asset(char_path, ".usd") if char_declared else None
    preferred_visual_asset = usd_path.resolve() if usd_path else char_path if char_declared else None
    skeletal_mapping = build_skeletal_mapping_contract(joint_order, preferred_visual_asset)

    source_root = str(package_manifest.get("source_root", "") or source.get("amp_root", "")).strip()
    return {
        "schema_version": 2,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "brain_name": brain_manifest.get("brain_name", ""),
        "package_dir": str(package_dir.resolve()),
        "character": {
            "declared_char_file": char_declared,
            "resolved_char_file": str(char_path) if char_declared else "",
            "char_file_exists": bool(char_path.exists()) if char_declared else False,
            "char_file_sha256": sha256_file(char_path) if char_declared else "",
            "visual_kind": visual_kind,
            "mesh_detected_in_declared_asset": bool(mesh_detected),
            "preferred_visual_asset": str(preferred_visual_asset) if preferred_visual_asset else "",
            "preferred_visual_asset_exists": bool(preferred_visual_asset.exists()) if preferred_visual_asset else False,
            "preferred_visual_asset_sha256": sha256_file(preferred_visual_asset) if preferred_visual_asset else "",
            "key_bodies": env_cfg.get("key_bodies", []),
            "contact_bodies": env_cfg.get("contact_bodies", []),
            "joint_order_file": "joint_order.json",
            "dof_size": int(joint_order.get("dof_size") or 0),
        },
        "scene": {
            "mimickit_env_config": str(env_config_path) if env_config_path else "",
            "camera_mode": str(env_cfg.get("camera_mode", "")),
            "ground": "mimickit_engine_default_flat_ground",
            "episode_length_seconds": float(env_cfg.get("episode_length", 0.0) or 0.0),
            "ref_char_offset_m": env_cfg.get("ref_char_offset", []),
            "init_pose": env_cfg.get("init_pose", []),
            "motion_file": str(env_cfg.get("motion_file", "")),
            "golden_render_refs": collect_render_refs(source_root),
        },
        "coordinate_contract": {
            "coordinate_basis": skeletal_mapping["basis_transform"]["name"],
            "unit_scale": brain_manifest.get("unit_scale", ""),
            "rotation_convention": visual_meta.get("rotation_convention", "quat_xyzw"),
            "root_pos_units": "meters",
            "ue_units": "centimeters",
            "status": "declared_for_offline_skeletal_visual_replay",
            "basis_transform_hash": skeletal_mapping["basis_transform_hash"],
            "runtime_control_status": "blocked_until_live_observation_basis_validation",
        },
        "skeletal_mapping_contract_file": "skeletal_mapping_contract.json",
        "skeletal_mapping_contract": skeletal_mapping,
        "ue_capture_requirements": {
            "required_outputs": ["png_frame_sequence", "mp4", "capture_meta.json", "visual_diff_report.json"],
            "debug_geometry_is_smoke_only": True,
            "full_visual_parity_requires_skeletal_pose": True,
            "skeletal_visual_pass_requires": [
                "capture_mode=skeletal_replay",
                "dof_pos_applied=true",
                "bone_map_hash",
                "basis_transform_hash",
                "png_sequence",
                "mp4",
            ],
            "must_log_to": "docs/memory/20260521_amp_ue_visual_diff_log.md",
        },
    }


def patch_manifests(package_dir: Path, contract_rel: str, skeletal_mapping_rel: str, contract: dict[str, Any]) -> None:
    brain_manifest_path = package_dir / "brain_manifest.json"
    brain_manifest = read_json(brain_manifest_path)
    if brain_manifest:
        brain_manifest["visual_alignment_contract_file"] = contract_rel
        brain_manifest["skeletal_mapping_contract_file"] = skeletal_mapping_rel
        brain_manifest["coordinate_basis"] = contract["coordinate_contract"]["coordinate_basis"]
        brain_manifest["runtime_control_basis_status"] = "blocked_until_live_observation_basis_validation"
        write_json(brain_manifest_path, brain_manifest)

    package_manifest_path = package_dir / "export_package_manifest.json"
    package_manifest = read_json(package_manifest_path)
    if package_manifest:
        package_manifest.setdefault("artifacts", {})["visual_alignment_contract"] = contract_rel
        package_manifest.setdefault("artifacts", {})["skeletal_mapping_contract"] = skeletal_mapping_rel
        package_manifest.setdefault("status", {})["visual_alignment_contract_ok"] = True
        package_manifest.setdefault("status", {})["skeletal_mapping_contract_ok"] = True
        write_json(package_manifest_path, package_manifest)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package_dirs", nargs="+", help="One or more ue_export/MimicKit package directories")
    args = parser.parse_args()

    ok = 0
    for raw_package_dir in args.package_dirs:
        package_dir = Path(raw_package_dir).resolve()
        contract = build_contract(package_dir)
        contract_path = package_dir / "visual_alignment_contract.json"
        skeletal_mapping_path = package_dir / "skeletal_mapping_contract.json"
        write_json(contract_path, contract)
        write_json(skeletal_mapping_path, contract["skeletal_mapping_contract"])
        patch_manifests(package_dir, contract_path.name, skeletal_mapping_path.name, contract)
        ok += 1
        print(json.dumps({"package_dir": str(package_dir), "contract": str(contract_path), "skeletal_mapping": str(skeletal_mapping_path), "ok": True}, ensure_ascii=False))
    return 0 if ok == len(args.package_dirs) else 2


if __name__ == "__main__":
    raise SystemExit(main())
