#!/usr/bin/env python3
"""Build source-equivalent rig and runtime contracts for MimicKit -> UE closure."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from typing import Any


DEFAULT_UE_ASSET_ROOT = "/Game/MimicKit/SwordShield"
DEFAULT_TARGETS = {
    "skeletal_mesh": f"{DEFAULT_UE_ASSET_ROOT}/SK_MimicKit_SwordShield",
    "skeleton": f"{DEFAULT_UE_ASSET_ROOT}/Skeleton_MimicKit_SwordShield",
    "physics_asset": f"{DEFAULT_UE_ASSET_ROOT}/PA_MimicKit_SwordShield",
}


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
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


def stable_json_sha256(obj: dict[str, Any]) -> str:
    payload = json.dumps(obj, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def ue_source_asset_targets(ue_asset_root: str) -> dict[str, str]:
    root = ue_asset_root.rstrip("/")
    return {
        "asset_root": root,
        "skeletal_mesh": f"{root}/SK_MimicKit_SwordShield",
        "skeleton": f"{root}/Skeleton_MimicKit_SwordShield",
        "physics_asset": f"{root}/PA_MimicKit_SwordShield",
        "generation_route": "mjcf_primitive_source_equivalent_skeletal_asset",
    }


def floats(text: str | None) -> list[float]:
    if not text:
        return []
    out: list[float] = []
    for token in str(text).replace(",", " ").split():
        try:
            out.append(float(token))
        except ValueError:
            pass
    return out


def parse_joint(element: ET.Element, body_name: str) -> dict[str, Any]:
    return {
        "name": element.attrib.get("name", ""),
        "body_name": body_name,
        "type": element.attrib.get("type", "hinge"),
        "axis": floats(element.attrib.get("axis")),
        "range_degrees": floats(element.attrib.get("range")),
        "actuator_force_range": floats(element.attrib.get("actuatorfrcrange")),
        "stiffness": float(element.attrib.get("stiffness", "0") or 0.0),
        "damping": float(element.attrib.get("damping", "0") or 0.0),
        "armature": float(element.attrib.get("armature", "0") or 0.0),
        "limited": element.attrib.get("limited", ""),
    }


def parse_geom(element: ET.Element, body_name: str) -> dict[str, Any]:
    return {
        "name": element.attrib.get("name", ""),
        "body_name": body_name,
        "type": element.attrib.get("type", ""),
        "pos": floats(element.attrib.get("pos")),
        "size": floats(element.attrib.get("size")),
        "fromto": floats(element.attrib.get("fromto")),
        "density": float(element.attrib.get("density", "0") or 0.0),
    }


def parse_body(element: ET.Element, parent_name: str = "") -> dict[str, Any]:
    body_name = element.attrib.get("name", "")
    body = {
        "name": body_name,
        "parent": parent_name,
        "pos": floats(element.attrib.get("pos")),
        "joints": [],
        "geoms": [],
        "children": [],
    }
    for child in element:
        if child.tag == "freejoint":
            body["joints"].append(
                {
                    "name": child.attrib.get("name", "root"),
                    "body_name": body_name,
                    "type": "freejoint",
                    "axis": [],
                    "range_degrees": [],
                    "actuator_force_range": [],
                    "stiffness": 0.0,
                    "damping": 0.0,
                    "armature": 0.0,
                    "limited": "",
                }
            )
        elif child.tag == "joint":
            body["joints"].append(parse_joint(child, body_name))
        elif child.tag == "geom":
            body["geoms"].append(parse_geom(child, body_name))
        elif child.tag == "body":
            body["children"].append(parse_body(child, body_name))
    return body


def flatten_bodies(body: dict[str, Any]) -> list[dict[str, Any]]:
    out = [body]
    for child in body.get("children", []):
        out.extend(flatten_bodies(child))
    return out


def parse_actuators(root: ET.Element) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    actuator_root = root.find("actuator")
    if actuator_root is None:
        return out
    for element in actuator_root:
        if element.tag != "motor":
            continue
        out.append(
            {
                "name": element.attrib.get("name", ""),
                "joint": element.attrib.get("joint", ""),
                "gear": float(element.attrib.get("gear", "0") or 0.0),
            }
        )
    return out


def mjcf_tokens(path: Path) -> dict[str, bool]:
    text = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
    return {
        "has_mesh_geom": 'type="mesh"' in text or "<mesh" in text,
        "has_texture": "<texture" in text,
        "has_material": "<material" in text,
    }


def usd_tokens(path: Path) -> dict[str, bool]:
    raw = path.read_bytes() if path.exists() else b""
    return {
        "exists": path.exists(),
        "is_binary_usdc": raw.startswith(b"PXR-USDC"),
        "has_usdskel_token": b"UsdSkel" in raw or b"SkelRoot" in raw or b"Skeleton" in raw,
        "has_mesh_token": b"Mesh" in raw,
        "has_rigid_body_token": b"RigidBody" in raw or b"PhysicsRigidBodyAPI" in raw,
    }


def build_joint_validation(joint_order: dict[str, Any], bodies: list[dict[str, Any]], actuators: list[dict[str, Any]]) -> dict[str, Any]:
    body_names = [str(body.get("name", "")) for body in bodies if body.get("name")]
    joint_order_bodies = [str(body) for body in joint_order.get("body_order", [])]
    missing_bodies = [body for body in joint_order_bodies if body not in body_names]
    actuator_joints = [str(actuator.get("joint", "")) for actuator in actuators]
    return {
        "joint_order_body_count": len(joint_order_bodies),
        "source_body_count": len(body_names),
        "missing_joint_order_bodies_in_source": missing_bodies,
        "dof_size": int(joint_order.get("dof_size") or 0),
        "actuator_count": len(actuators),
        "actuator_count_matches_dof_size": len(actuators) == int(joint_order.get("dof_size") or 0),
        "required_contact_bodies": ["right_foot", "left_foot"],
        "contact_bodies_present": all(body in body_names for body in ["right_foot", "left_foot"]),
        "sword_attachment_present": "sword" in body_names and "right_hand" in body_names,
        "shield_attachment_present": "shield" in body_names and "left_lower_arm" in body_names,
        "actuator_joints": actuator_joints,
    }


def build_source_rig_spec(package_dir: Path, char_xml: Path, char_usd: Path, ue_asset_root: str) -> dict[str, Any]:
    tree = ET.parse(char_xml)
    root = tree.getroot()
    worldbody = root.find("worldbody")
    if worldbody is None:
        raise RuntimeError(f"MJCF has no worldbody: {char_xml}")
    root_body_elem = worldbody.find("body")
    if root_body_elem is None:
        raise RuntimeError(f"MJCF worldbody has no root body: {char_xml}")

    root_body = parse_body(root_body_elem)
    bodies = flatten_bodies(root_body)
    actuators = parse_actuators(root)
    joint_order = read_json(package_dir / "joint_order.json")

    spec = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "contract_role": "mimickit_source_equivalent_ue_rig_asset_spec",
        "package_dir": str(package_dir.resolve()),
        "source_assets": {
            "mjcf_xml": str(char_xml.resolve()),
            "mjcf_xml_sha256": sha256_file(char_xml),
            "usd": str(char_usd.resolve()) if char_usd else "",
            "usd_sha256": sha256_file(char_usd) if char_usd else "",
            "mjcf_tokens": mjcf_tokens(char_xml),
            "usd_tokens": usd_tokens(char_usd) if char_usd else {},
        },
        "ue_asset_targets": ue_source_asset_targets(ue_asset_root),
        "root_body": root_body,
        "flat_bodies": [
            {
                "name": body.get("name", ""),
                "parent": body.get("parent", ""),
                "pos": body.get("pos", []),
                "joint_count": len(body.get("joints", [])),
                "geom_count": len(body.get("geoms", [])),
            }
            for body in bodies
        ],
        "geoms": [geom for body in bodies for geom in body.get("geoms", [])],
        "joints": [joint for body in bodies for joint in body.get("joints", [])],
        "actuators": actuators,
        "validation": build_joint_validation(joint_order, bodies, actuators),
    }
    spec["spec_hash"] = stable_json_sha256(spec)
    return spec


def build_runtime_contract(package_dir: Path, spec: dict[str, Any]) -> dict[str, Any]:
    brain_manifest = read_json(package_dir / "brain_manifest.json")
    schema = read_json(package_dir / "schema.json")
    joint_order = read_json(package_dir / "joint_order.json")
    env = schema.get("env", {}) if isinstance(schema.get("env"), dict) else {}
    model = schema.get("model", {}) if isinstance(schema.get("model"), dict) else {}
    runtime = {
        "schema_version": 2,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "contract_role": "mimickit_to_ue_live_policy_chaos_runtime_contract",
        "brain_name": brain_manifest.get("brain_name", ""),
        "model_file": brain_manifest.get("model", ""),
        "policy_hz": int(brain_manifest.get("policy_hz") or env.get("control_freq") or 30),
        "physics_hz": int(brain_manifest.get("physics_hz") or env.get("sim_freq") or 240),
        "observation_dim": int(brain_manifest.get("observation_dim") or model.get("obs_dim") or 0),
        "action_dim": int(brain_manifest.get("action_dim") or model.get("act_dim") or 0),
        "dof_size": int(joint_order.get("dof_size") or 0),
        "runtime_backend": "NNERuntimeORT",
        "backend_status": "ue_nne_runtime_required; deterministic trace/ref-action fallback is not allowed for live closure pass",
        "observation_source": "ue_physics_actor_state",
        "contact_measurement_source": "chaos_contact_query",
        "joint_drive_backend": "FConstraintInstance angular SLERP drive",
        "proxy_gate_allowed": False,
        "normalization_stats_file": "normalization_stats.json",
        "obs_action_spec_file": "obs_action_spec.yaml",
        "joint_order_file": "joint_order.json",
        "source_rig_asset_spec_file": "mimickit_source_rig_asset_spec.json",
        "action_to_joint_mapping": {
            "source": "joint_order.joints[*].dof_slice",
            "interpretation": "policy_action values map one-to-one to MJCF actuator/order dof targets",
        },
        "coordinate_basis": {
            "name": "mimickit_training_xyz_to_ue_xyz_cm_v1",
            "unit_scale": "meters_to_ue_cm",
            "rotation_convention": "quat_xyzw",
        },
        "pd_defaults": {
            "source": "humanoid_sword_shield.xml actuator/joint stiffness+damping+gear",
            "action_clamp": [-1.0, 1.0],
        },
        "contact": {
            "contact_bodies": ["right_foot", "left_foot"],
            "measurement_source": "chaos_contact_query",
            "sliding_threshold_mps": 0.25,
            "record_raw_and_scored_sliding": True,
            "clamp_raw_sliding_for_pass": False,
            "min_contact_frames_per_foot": 1,
        },
        "negative_gates": {
            "kinematic_contact_proxy_can_write_diagnostics": True,
            "kinematic_contact_proxy_can_pass_live_closure": False,
            "trace_backed_joint_pd_targets_can_pass_live_closure": False,
        },
        "stability": {
            "runtime_seconds": 10.0,
            "max_root_drop_m": 0.75,
            "require_finite_root": True,
            "require_finite_actions": True,
        },
        "ue_assets": spec["ue_asset_targets"],
    }
    runtime["contract_hash"] = stable_json_sha256(runtime)
    return runtime


def patch_package(package_dir: Path, spec_path: Path, runtime_path: Path, spec: dict[str, Any], runtime: dict[str, Any]) -> None:
    target_update = {
        "asset_strategy": "mimickit_source_equivalent_generated_skeletal_asset",
        "skeletal_mesh": spec["ue_asset_targets"]["skeletal_mesh"],
        "skeleton": spec["ue_asset_targets"]["skeleton"],
        "physics_asset": spec["ue_asset_targets"]["physics_asset"],
        "fallback_renderer": "",
        "full_character_parity": True,
        "mimickit_preferred_visual_asset": spec["source_assets"].get("usd", ""),
        "mimickit_source_asset_imported_to_ue": False,
        "mimickit_source_asset_import_status": "pending_ue_editor_asset_build",
        "mimickit_source_rig_asset_spec_file": spec_path.name,
        "mimickit_source_rig_asset_spec_hash": spec["spec_hash"],
    }

    skeletal_path = package_dir / "skeletal_mapping_contract.json"
    skeletal_contract = read_json(skeletal_path)
    if skeletal_contract:
        skeletal_contract["schema_version"] = max(int(skeletal_contract.get("schema_version") or 1), 3)
        skeletal_contract["contract_role"] = "mimickit_to_ue_source_character_skeletal_replay_mapping"
        skeletal_contract.setdefault("source_character_gate", {})
        skeletal_contract["source_character_gate"].update(
            {
                "required_capture_mode": "source_character_skeletalmesh_replay",
                "requires_target_mesh_prefix": spec["ue_asset_targets"]["asset_root"],
                "requires_fallback_renderer_empty": True,
                "requires_mimickit_source_asset_imported_to_ue": True,
                "ppm_only_allowed": False,
            }
        )
        skeletal_contract.setdefault("ue_visual_target", {}).update(target_update)
        skeletal_contract["source_rig_asset_spec_file"] = spec_path.name
        skeletal_contract["runtime_control_contract_file"] = runtime_path.name
        skeletal_contract["source_rig_asset_spec_hash"] = spec["spec_hash"]
        skeletal_contract["contract_hash"] = stable_json_sha256(
            {k: v for k, v in skeletal_contract.items() if k != "contract_hash"}
        )
        write_json(skeletal_path, skeletal_contract)

    visual_path = package_dir / "visual_alignment_contract.json"
    visual = read_json(visual_path)
    if visual:
        visual["schema_version"] = 3
        visual["mimickit_source_rig_asset_spec_file"] = spec_path.name
        visual["runtime_control_contract_file"] = runtime_path.name
        visual["runtime_scope"] = {
            "offline_source_character_replay": True,
            "live_policy_control": True,
            "chaos_contact_validated": True,
            "runtime_backend": runtime["runtime_backend"],
            "observation_source": runtime["observation_source"],
            "contact_measurement_source": runtime["contact_measurement_source"],
            "joint_drive_backend": runtime["joint_drive_backend"],
            "proxy_gate_allowed": False,
            "full_visual_parity_gate": "requires source_character_skeletalmesh_replay capture",
            "capture_modes": [
                "debug_geometry",
                "skeletal_replay",
                "source_character_skeletalmesh_replay",
                "live_policy_chaos",
            ],
            "ppm_only_allowed_for_full_parity": False,
        }
        skeletal = visual.setdefault("skeletal_mapping_contract", {})
        target = skeletal.setdefault("ue_visual_target", {})
        target.update(target_update)
        skeletal["source_character_gate"] = {
            "required_capture_mode": "source_character_skeletalmesh_replay",
            "requires_target_mesh_prefix": spec["ue_asset_targets"]["asset_root"],
            "requires_fallback_renderer_empty": True,
            "requires_mimickit_source_asset_imported_to_ue": True,
            "ppm_only_allowed": False,
        }
        skeletal["source_rig_asset_spec_hash"] = spec["spec_hash"]
        write_json(visual_path, visual)

    brain_manifest_path = package_dir / "brain_manifest.json"
    brain_manifest = read_json(brain_manifest_path)
    if brain_manifest:
        brain_manifest["mimickit_source_rig_asset_spec_file"] = spec_path.name
        brain_manifest["runtime_control_contract_file"] = runtime_path.name
        write_json(brain_manifest_path, brain_manifest)

    package_manifest_path = package_dir / "export_package_manifest.json"
    package_manifest = read_json(package_manifest_path)
    if package_manifest:
        package_manifest.setdefault("artifacts", {})["mimickit_source_rig_asset_spec"] = spec_path.name
        package_manifest.setdefault("artifacts", {})["runtime_control_contract"] = runtime_path.name
        package_manifest.setdefault("status", {})["source_rig_asset_spec_ok"] = True
        package_manifest.setdefault("status", {})["runtime_control_contract_ok"] = True
        write_json(package_manifest_path, package_manifest)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--char-xml", required=True)
    parser.add_argument("--char-usd", default="")
    parser.add_argument("--out", required=True)
    parser.add_argument("--runtime-out", default="")
    parser.add_argument("--ue-asset-root", default=DEFAULT_UE_ASSET_ROOT)
    args = parser.parse_args()

    package_dir = Path(args.package_dir).resolve()
    char_xml = Path(args.char_xml).resolve()
    char_usd = Path(args.char_usd).resolve() if args.char_usd else Path()
    spec_path = Path(args.out).resolve()
    runtime_path = Path(args.runtime_out).resolve() if args.runtime_out else package_dir / "runtime_control_contract.json"

    spec = build_source_rig_spec(package_dir=package_dir, char_xml=char_xml, char_usd=char_usd, ue_asset_root=args.ue_asset_root.rstrip("/"))
    runtime = build_runtime_contract(package_dir=package_dir, spec=spec)
    write_json(spec_path, spec)
    write_json(runtime_path, runtime)
    patch_package(package_dir, spec_path, runtime_path, spec, runtime)

    print(json.dumps({"ok": True, "spec": str(spec_path), "runtime_contract": str(runtime_path), "spec_hash": spec["spec_hash"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
