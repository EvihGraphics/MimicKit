#!/usr/bin/env python3
"""Build the final MimicKit -> EvihAnimation visual bridge closure manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from visual_bridge_validation import sha256_file, write_json

DEFAULT_REQUIRED_LABELS = ("white-knight", "walk-exact", "stop-exact")
FRAMEWORK_PROVENANCE_EXACT = {
    "ai4animation_mode": "CAPTURE",
    "actor_component": "ai4animation.Components.Actor.Actor",
    "mesh_component": "ai4animation.Standalone.RigidNodeMesh.RigidNodeMesh",
    "render_pipeline": "ai4animation.Standalone.RenderPipeline.RenderPipeline",
    "silhouette_derivation": "renderpipeline_semantic_character_with_ground_depth_occluder",
    "ground_mask_derivation": "complement_of_renderpipeline_semantic_character",
    "mesh_mode": "rigid_node",
    "rigid_node_update_mode": "actor_entity_world_dynamic_vertex_buffer",
}
FRAMEWORK_REQUIRED_CAPTURE_PASSES = {"blank", "character_only", "ground_only", "full_scene"}
FRAMEWORK_PROVENANCE_ARTIFACTS = (
    "framework_capture_script",
    "ai4animation_core_module",
    "entity_module",
    "actor_module",
    "rigid_node_mesh_module",
    "standalone_module",
    "render_pipeline_module",
    "replay_module",
    "basic_vertex_shader",
    "grid_shader",
    "mesh_asset",
    "pose_dof_replay",
    "body_world_replay",
    "mesh_binding_contract",
    "scene_contract",
    "rigid_node_transform_report",
)


def read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def parse_case_spec(text: str) -> dict[str, Path | str]:
    fields: dict[str, str] = {}
    for token in text.split(","):
        key, sep, value = token.partition("=")
        if sep:
            fields[key.strip()] = value.strip()
    if not fields.get("label") or not fields.get("mimic") or not fields.get("evih") or not fields.get("review"):
        raise ValueError("--case requires label=...,mimic=...,evih=...,review=...")
    return {key: (Path(value).resolve() if key != "label" else value) for key, value in fields.items()}


def framework_renderer_provenance_valid(provenance: dict[str, Any]) -> bool:
    if not provenance:
        return False
    if any(provenance.get(name) != value for name, value in FRAMEWORK_PROVENANCE_EXACT.items()):
        return False
    capture_passes = provenance.get("capture_passes", [])
    if (
        not isinstance(capture_passes, list)
        or set(str(value) for value in capture_passes) != FRAMEWORK_REQUIRED_CAPTURE_PASSES
        or len(capture_passes) != len(FRAMEWORK_REQUIRED_CAPTURE_PASSES)
    ):
        return False
    if not Path(str(provenance.get("python_executable", ""))).is_file():
        return False
    for name in FRAMEWORK_PROVENANCE_ARTIFACTS:
        value = str(provenance.get(name, "")).strip()
        path = Path(value) if value else None
        declared_hash = str(provenance.get(f"{name}_sha256", "")).strip()
        if not path or not path.is_file() or not declared_hash or sha256_file(path) != declared_hash:
            return False
    return True


def case_report(spec: dict[str, Path | str]) -> dict[str, Any]:
    mimic_path = Path(spec["mimic"])
    evih_path = Path(spec["evih"])
    review_path = Path(spec["review"])
    mimic = read_json(mimic_path)
    evih = read_json(evih_path)
    if not review_path.exists():
        write_json(
            review_path,
            {
                "schema_version": 1,
                "visual_review_pass": False,
                "checks": {
                    "character": False,
                    "sword": False,
                    "shield": False,
                    "pose": False,
                    "camera": False,
                    "ground": False,
                    "lighting": False,
                    "frame_pairing": False,
                    "no_obvious_penetration_or_drift": False,
                },
                "reviewer": "",
                "reviewed_at_utc": "",
                "notes": "Generated review template. Manual confirmation is required.",
            },
        )
    review = read_json(review_path)
    review_checks = review.get("checks", {}) if isinstance(review.get("checks"), dict) else {}
    review_evidence = review.get("evidence", {}) if isinstance(review.get("evidence"), dict) else {}
    mesh_report = evih.get("mesh_report", {}) if isinstance(evih.get("mesh_report"), dict) else {}
    evih_review_evidence = mesh_report.get("visual_review_evidence", {}) if isinstance(mesh_report.get("visual_review_evidence"), dict) else {}
    framework_provenance = (
        evih.get("framework_renderer_provenance", {})
        if isinstance(evih.get("framework_renderer_provenance"), dict)
        else {}
    )
    comparison_sheet = Path(str(evih.get("comparison_sheet", ""))) if str(evih.get("comparison_sheet", "")).strip() else None
    comparison_mp4 = Path(str(evih.get("comparison_mp4", ""))) if str(evih.get("comparison_mp4", "")).strip() else None
    review_checks_pass = all(bool(review_checks.get(name)) for name in (
        "character",
        "sword",
        "shield",
        "pose",
        "camera",
        "ground",
        "lighting",
        "frame_pairing",
        "no_obvious_penetration_or_drift",
    ))
    review_reviewer_present = bool(str(review.get("reviewer", "")).strip())
    review_timestamp_present = bool(str(review.get("reviewed_at_utc", "")).strip())
    review_pass = (
        bool(review.get("visual_review_pass"))
        and review_checks_pass
        and review_reviewer_present
        and review_timestamp_present
    )
    label = str(spec["label"]).strip().lower()
    checks = {
        "mimic_manifest_exists": mimic_path.exists(),
        "mimic_mesh_reference_pass": bool(mimic.get("mesh_reference_pass")),
        "mimic_capture_ok": bool(mimic.get("capture_ok")),
        "mimic_media_ok": bool(mimic.get("media_ok")),
        "mimic_asset_ok": bool(mimic.get("asset_ok")),
        "mimic_package_ok": bool(mimic.get("package_ok")),
        "mimic_blocker_empty": not bool(str(mimic.get("blocker", "")).strip()),
        "mimic_data_binding_ok": bool(mimic.get("data_binding_ok")),
        "mimic_dynamic_sequence_ok": bool(mimic.get("dynamic_sequence_ok")),
        "mimic_source_not_ppm_only": not bool(mimic.get("source_was_ppm_only")),
        "evih_manifest_exists": evih_path.exists(),
        "software_geometry_replay_pass": bool(evih.get("software_geometry_replay_pass")),
        "framework_api_used": bool(evih.get("framework_api_used")),
        "evih_framework_api_replay_pass": bool(evih.get("evih_framework_api_replay_pass")),
        "framework_scene_contract_compare_pass": bool(evih.get("framework_scene_contract_compare_pass")),
        "framework_visual_metric_pass": bool(evih.get("framework_visual_metric_pass")),
        "framework_scene_visual_metric_pass": bool(evih.get("framework_scene_visual_metric_pass")),
        "framework_dynamic_sequence_pass": bool(evih.get("framework_dynamic_sequence_pass")),
        "framework_media_ok": bool(evih.get("framework_media_ok")),
        "framework_renderer_provenance_present": bool(framework_provenance),
        "framework_renderer_provenance_valid": framework_renderer_provenance_valid(framework_provenance),
        "evih_mesh_replay_pass": bool(evih.get("evih_mesh_replay_pass")),
        "evih_data_binding_ok": bool(evih.get("data_binding_ok")),
        "mesh_binding_pass": bool(evih.get("mesh_binding_pass")),
        "fk_compare_pass": bool(evih.get("fk_compare_pass")),
        "scene_contract_compare_pass": bool(evih.get("scene_contract_compare_pass")),
        "scene_visual_metric_pass": bool(evih.get("scene_visual_metric_pass")),
        "visual_metric_pass": bool(evih.get("visual_metric_pass")),
        "evih_dynamic_sequence_pass": bool(evih.get("dynamic_sequence_pass")),
        "comparison_mp4_pass": bool(evih.get("comparison_mp4_pass")),
        "media_ok": bool(evih.get("media_ok")),
        "evih_blocker_empty": not bool(str(evih.get("blocker", "")).strip()),
        "visual_review_exists": review_path.exists(),
        "visual_review_checks_pass": review_checks_pass,
        "visual_review_reviewer_present": review_reviewer_present,
        "visual_review_timestamp_present": review_timestamp_present,
        "visual_review_evidence_matches_evih": bool(review_evidence) and review_evidence == evih_review_evidence,
        "visual_review_binds_current_mimic_manifest": (
            bool(review_evidence)
            and review_evidence.get("mimickit_mesh_reference_manifest_sha256") == sha256_file(mimic_path)
        ),
        "visual_review_binds_current_comparison_sheet": (
            bool(review_evidence)
            and comparison_sheet is not None
            and review_evidence.get("comparison_sheet_sha256") == sha256_file(comparison_sheet)
        ),
        "visual_review_binds_current_comparison_mp4": (
            bool(review_evidence)
            and comparison_mp4 is not None
            and review_evidence.get("comparison_mp4_sha256") == sha256_file(comparison_mp4)
        ),
        "visual_review_pass": review_pass,
    }
    if label == "white-knight-smoke":
        for name in (
            "software_geometry_replay_pass",
            "framework_api_used",
            "evih_framework_api_replay_pass",
            "framework_scene_contract_compare_pass",
            "framework_visual_metric_pass",
            "framework_scene_visual_metric_pass",
            "framework_dynamic_sequence_pass",
            "framework_media_ok",
            "framework_renderer_provenance_present",
            "framework_renderer_provenance_valid",
            "evih_mesh_replay_pass",
            "evih_blocker_empty",
        ):
            checks.pop(name)
    source_key = f"mimickit-evih-v3:{label}"
    bridge_case_id = hashlib.sha256(source_key.encode("utf-8")).hexdigest()[:20]
    blockers = [
        blocker
        for blocker in [str(mimic.get("blocker", "")).strip(), str(evih.get("blocker", "")).strip()]
        if blocker
    ]
    blockers.extend(f"gate_failed:{name}" for name, passed in checks.items() if not passed)
    return {
        "label": spec["label"],
        "bridge_case_id": bridge_case_id,
        "case_acceptance_pass": all(checks.values()),
        "checks": checks,
        "mimic_manifest": str(mimic_path),
        "mimic_manifest_sha256": sha256_file(mimic_path),
        "evih_manifest": str(evih_path),
        "evih_manifest_sha256": sha256_file(evih_path),
        "visual_review": str(review_path),
        "visual_review_sha256": sha256_file(review_path),
        "blockers": blockers,
    }


def write_case_manifest(report: dict[str, Any], mimic_manifest_path: Path) -> Path:
    bridge_case_manifest = mimic_manifest_path.parent / "bridge_case_manifest.json"
    write_json(
        bridge_case_manifest,
        {
            "schema_version": 1,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "label": report["label"],
            "bridge_case_id": report["bridge_case_id"],
            "case_acceptance_pass": report["case_acceptance_pass"],
            "blocker": report["blockers"][0] if report["blockers"] else "",
            "blockers": report["blockers"],
            "report": report,
        },
    )
    return bridge_case_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", action="append", default=[], help="label=...,mimic=...,evih=...,review=...")
    parser.add_argument("--required-label", action="append", default=[], help="Required case label. Defaults to White-Knight, Walk exact, and Stop exact.")
    parser.add_argument("--baseline-snapshot", default="")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    cases = []
    for text in args.case:
        spec = parse_case_spec(text)
        report = case_report(spec)
        cases.append(report)
        write_case_manifest(report, Path(spec["mimic"]))

    baseline_path = Path(args.baseline_snapshot).resolve() if args.baseline_snapshot else None
    baseline = read_json(baseline_path) if baseline_path else {}
    required_labels = [str(value).strip().lower() for value in (args.required_label or DEFAULT_REQUIRED_LABELS) if str(value).strip()]
    present_labels = {str(item.get("label", "")).strip().lower() for item in cases}
    missing_required_labels = [label for label in required_labels if label not in present_labels]
    baseline_pass = bool(baseline.get("baseline_protection_pass")) if baseline_path else False
    blockers = [f"missing_required_case:{label}" for label in missing_required_labels]
    blockers.extend(
        f"{item['label']}:{blocker}"
        for item in cases
        for blocker in item.get("blockers", [])
    )
    if not baseline_pass:
        blockers.append("preserved_geom_baseline_protection_failed")
    manifest = {
        "schema_version": 2,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "cases": cases,
        "baseline_snapshot": str(baseline_path) if baseline_path else "",
        "baseline_snapshot_sha256": sha256_file(baseline_path) if baseline_path else "",
        "preserved_geom_baselines": baseline.get("cases", []),
        "baseline_protection_pass": baseline_pass,
        "required_case_labels": required_labels,
        "missing_required_case_labels": missing_required_labels,
        "blockers": blockers,
        "full_chain_bridge_pass": (
            not missing_required_labels
            and bool(cases)
            and all(item["case_acceptance_pass"] for item in cases)
            and baseline_pass
        ),
    }
    manifest["blocker"] = "" if manifest["full_chain_bridge_pass"] else "full_chain_bridge_gate_failed"
    write_json(Path(args.out).resolve(), manifest)
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0 if manifest["full_chain_bridge_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
