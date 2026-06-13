#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from build_full_chain_bridge_manifest import DEFAULT_REQUIRED_LABELS
from build_full_chain_bridge_manifest import case_report
from build_full_chain_bridge_manifest import framework_renderer_provenance_valid
import build_mimickit_exact_mesh_reference as exact_builder
import build_mimickit_mesh_reference as white_knight_builder
import scripts.run_amp_keepalive as run_amp_keepalive
from build_mimickit_mesh_reference import finalize_manifest_gate_fields, localize_native_manifest_paths
from build_mimickit_mesh_reference import sync_native_workspace_scripts as sync_white_knight_native_scripts
from build_mimickit_exact_mesh_reference import sync_native_workspace_scripts as sync_exact_native_scripts
from run_plan_6_9_bridge import (
    FINAL_AUTOMATIC_CHECKS,
    FINAL_CASES,
    GENERATION_GATES,
    PREREQUISITES,
    REVIEW_PROMOTION_GATE,
    FRAMEWORK_PREFLIGHT_GATE,
    FRAMEWORK_RENDER_GATE,
    aggregate_prerequisite_blocker,
    evih_build_command,
    final_automatic_gate_pass,
    framework_capture_command,
    framework_results_command,
    preflight_report,
    review_promotion_command,
    source_build_command,
)
from visual_bridge_validation import V3_REQUIRED_FRAME_IDS, build_scene_contract_v3, validate_body_world_replay


def camera_samples() -> list[dict]:
    return [
        {
            "frame": frame,
            "eye": [0.0, -5.0, 3.0],
            "target": [0.0, 0.0, 1.0],
            "fov_degrees": 60.0,
            "fov_axis": "horizontal",
            "projection": "perspective",
            "near": 0.1,
            "far": 1000.0,
            "renderer_version": "test",
            "capture_settle_updates": 8,
            "visual_link_sync_ok": True,
            "visual_link_sync_count": 1,
        }
        for frame in V3_REQUIRED_FRAME_IDS
    ]


def valid_framework_provenance(root: Path) -> dict:
    provenance = {
        "ai4animation_mode": "CAPTURE",
        "actor_component": "ai4animation.Components.Actor.Actor",
        "mesh_component": "ai4animation.Standalone.RigidNodeMesh.RigidNodeMesh",
        "render_pipeline": "ai4animation.Standalone.RenderPipeline.RenderPipeline",
        "capture_passes": ["blank", "character_only", "ground_only", "full_scene"],
        "silhouette_derivation": "renderpipeline_semantic_character_with_ground_depth_occluder",
        "ground_mask_derivation": "complement_of_renderpipeline_semantic_character",
        "mesh_mode": "rigid_node",
        "rigid_node_update_mode": "actor_entity_world_dynamic_vertex_buffer",
        "python_executable": sys.executable,
    }
    for name in (
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
    ):
        path = root / name
        path.write_text(name, encoding="utf-8")
        provenance[name] = str(path)
        provenance[f"{name}_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    return provenance


class Plan69Test(unittest.TestCase):
    def test_native_script_sync_includes_body_world_export_and_verifies_hashes(self) -> None:
        for sync in (sync_white_knight_native_scripts, sync_exact_native_scripts):
            with tempfile.TemporaryDirectory() as directory:
                workspace = Path(directory)
                args = type("Args", (), {"windows_workspace_wsl": str(workspace)})()
                report = sync(args)
                self.assertTrue(report["ok"], report)
                exports = [item for item in report["copied"] if item["rel_path"] == "tools/ue_bridge/export_obs_fixture.py"]
                self.assertEqual(len(exports), 1)
                self.assertTrue(exports[0]["hash_match"])
                self.assertEqual(exports[0]["src_sha256"], exports[0]["dst_sha256"])
                self.assertFalse(report["mismatches"])
                self.assertEqual(report["blocker"], "")

    def test_native_script_sync_fails_closed_for_missing_source_and_hash_drift(self) -> None:
        for module, sync in (
            (white_knight_builder, sync_white_knight_native_scripts),
            (exact_builder, sync_exact_native_scripts),
        ):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                workspace = root / "workspace"
                workspace.mkdir()
                args = type("Args", (), {"windows_workspace_wsl": str(workspace)})()
                with patch.object(module, "ROOT", root / "missing-source-root"):
                    missing = sync(args)
                self.assertFalse(missing["ok"])
                self.assertTrue(missing["missing"])
                self.assertTrue(missing["blocker"].startswith("native_workspace_script_missing:"))

            with tempfile.TemporaryDirectory() as directory:
                workspace = Path(directory)
                args = type("Args", (), {"windows_workspace_wsl": str(workspace)})()
                real_copy2 = shutil.copy2

                def corrupt_copy(src, dst):
                    result = real_copy2(src, dst)
                    Path(dst).write_bytes(Path(dst).read_bytes() + b"\nhash-drift")
                    return result

                with patch.object(module.shutil, "copy2", side_effect=corrupt_copy):
                    drift = sync(args)
                self.assertFalse(drift["ok"])
                self.assertTrue(drift["mismatches"])
                self.assertTrue(drift["blocker"].startswith("native_workspace_script_hash_mismatch:"))

    def test_source_manifest_exposes_independent_v3_gates(self) -> None:
        manifest = finalize_manifest_gate_fields(
            {
                "expected_image_count": len(V3_REQUIRED_FRAME_IDS),
                "render_summary": {
                    "mesh_reference_pass": True,
                    "expected_image_count": len(V3_REQUIRED_FRAME_IDS),
                    "image_count": len(V3_REQUIRED_FRAME_IDS),
                    "silhouette_image_count": len(V3_REQUIRED_FRAME_IDS),
                    "ground_mask_image_count": len(V3_REQUIRED_FRAME_IDS),
                    "frame_ids": list(V3_REQUIRED_FRAME_IDS),
                    "expected_frame_ids": list(V3_REQUIRED_FRAME_IDS),
                    "unique_rgb_frame_count": 6,
                    "unique_silhouette_frame_count": 6,
                    "mp4_unique_frame_count": 6,
                    "motion_visible": True,
                    "mp4_ok": True,
                    "source_was_ppm_only": False,
                },
                "asset_export": {"ok": True, "asset_structure": {"ok": True}},
                "package_export": {"ok": True},
            }
        )
        self.assertTrue(manifest["capture_ok"])
        self.assertTrue(manifest["media_ok"])
        self.assertTrue(manifest["dynamic_sequence_ok"])
        self.assertTrue(manifest["asset_ok"])
        self.assertTrue(manifest["package_ok"])

    def test_strict_scene_contract_rejects_null_fov(self) -> None:
        kwargs = {
            "root_name": "root",
            "case": "case",
            "motion_id": "motion",
            "width": 960,
            "height": 540,
            "frames": 300,
            "frame_stride": 5,
            "fps": 12,
            "seed": 7,
            "renderer": "isaaclab",
            "camera_samples": camera_samples(),
        }
        contract = build_scene_contract_v3(**kwargs)
        self.assertEqual(contract["schema_version"], 3)
        self.assertEqual(contract["timing"]["expected_frame_ids"], list(V3_REQUIRED_FRAME_IDS))
        kwargs["frames"] = 10
        with self.assertRaises(ValueError):
            build_scene_contract_v3(**kwargs)
        kwargs["frames"] = 300
        kwargs["camera_samples"][0]["fov_degrees"] = None
        with self.assertRaises(ValueError):
            build_scene_contract_v3(**kwargs)
        kwargs["camera_samples"][0]["fov_degrees"] = 60.0
        kwargs["camera_samples"][0]["capture_settle_updates"] = 0
        with self.assertRaises(ValueError):
            build_scene_contract_v3(**kwargs)

    def test_body_world_replay_requires_exact_frames_and_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory)
            visual = package / "visual_replay"
            visual.mkdir()
            (package / "joint_order.json").write_text(json.dumps({"body_order": ["pelvis"]}), encoding="utf-8")
            (visual / "pose_dof_replay.jsonl").write_text('{"frame":0}\n{"frame":5}\n', encoding="utf-8")
            missing = validate_body_world_replay(package)
            self.assertFalse(missing["data_binding_ok"])
            self.assertFalse(missing["checks"]["body_world_replay_exists"])
            self.assertEqual(missing["blocker"], "body_world_replay_invalid")
            rows = [
                {
                    "frame": frame,
                    "source": "canonical_source_rig_fk_v3",
                    "body_order": ["pelvis"],
                    "body_pos_m": [0, 0, 0],
                    "body_rot_xyzw": [0, 0, 0, 1],
                }
                for frame in (0, 5)
            ]
            (visual / "body_world_replay.jsonl").write_text(
                "".join(json.dumps(row) + "\n" for row in rows),
                encoding="utf-8",
            )
            self.assertTrue(validate_body_world_replay(package)["data_binding_ok"])
            rows[-1]["frame"] = 6
            (visual / "body_world_replay.jsonl").write_text(
                "".join(json.dumps(row) + "\n" for row in rows),
                encoding="utf-8",
            )
            self.assertFalse(validate_body_world_replay(package)["data_binding_ok"])

    def test_native_manifest_localization_preserves_hashed_scene_contract(self) -> None:
        contract = build_scene_contract_v3(
            root_name="root",
            case="case",
            motion_id="motion",
            frames=300,
            renderer="isaaclab",
            base_env_config=r"D:\MimicKitNative\workspace\MimicKit\output\train\root\env.yaml",
            engine_config=r"D:\MimicKitNative\workspace\MimicKit\data\engines\isaac_lab_engine.yaml",
            camera_samples=camera_samples(),
        )
        manifest = {
            "scene_contract_v3_file": r"D:\MimicKitNative\workspace\MimicKit\output\train\root\scene_contract_v3.json",
            "scene_contract_v3": contract,
        }
        localized = localize_native_manifest_paths(manifest, Path("/tmp/train"), Path("/tmp/img"), "root")
        self.assertEqual(localized["scene_contract_v3"], contract)
        self.assertNotEqual(localized["scene_contract_v3_file"], manifest["scene_contract_v3_file"])

    def test_case_manifest_requires_all_v3_gates_and_generates_review_template(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mimic = root / "mesh_reference_manifest.json"
            evih = root / "visual_result_manifest.json"
            review = root / "visual_review.json"
            mimic.write_text(
                json.dumps(
                    {
                        "mesh_reference_pass": True,
                        "capture_ok": True,
                        "media_ok": True,
                        "asset_ok": True,
                        "package_ok": True,
                        "data_binding_ok": True,
                        "dynamic_sequence_ok": True,
                        "source_was_ppm_only": False,
                        "blocker": "",
                    }
                ),
                encoding="utf-8",
            )
            evih.write_text(
                json.dumps(
                    {
                        "evih_mesh_replay_pass": True,
                        "software_geometry_replay_pass": True,
                        "framework_api_used": True,
                        "evih_framework_api_replay_pass": True,
                        "framework_scene_contract_compare_pass": True,
                        "framework_visual_metric_pass": True,
                        "framework_scene_visual_metric_pass": True,
                        "framework_dynamic_sequence_pass": True,
                        "framework_media_ok": True,
                        "framework_renderer_provenance": valid_framework_provenance(root),
                        "data_binding_ok": True,
                        "mesh_binding_pass": True,
                        "fk_compare_pass": True,
                        "scene_contract_compare_pass": True,
                        "scene_visual_metric_pass": True,
                        "visual_metric_pass": True,
                        "dynamic_sequence_pass": True,
                        "comparison_mp4_pass": True,
                        "media_ok": True,
                        "blocker": "",
                    }
                ),
                encoding="utf-8",
            )
            report = case_report({"label": "white-knight", "mimic": mimic, "evih": evih, "review": review})
            self.assertFalse(report["case_acceptance_pass"])
            self.assertTrue(review.exists())
            self.assertTrue(report["bridge_case_id"])
            first_id = report["bridge_case_id"]
            mimic.write_text(mimic.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            self.assertEqual(
                first_id,
                case_report({"label": "white-knight", "mimic": mimic, "evih": evih, "review": review})["bridge_case_id"],
            )
            mimic_data = json.loads(mimic.read_text(encoding="utf-8"))
            mimic_data["capture_ok"] = False
            mimic.write_text(json.dumps(mimic_data), encoding="utf-8")
            failed_source = case_report({"label": "white-knight", "mimic": mimic, "evih": evih, "review": review})
            self.assertIn("gate_failed:mimic_capture_ok", failed_source["blockers"])

            mimic_data["capture_ok"] = True
            mimic.write_text(json.dumps(mimic_data), encoding="utf-8")
            evih_data = json.loads(evih.read_text(encoding="utf-8"))
            for field, failed_value, expected_gate in (
                ("framework_renderer_provenance", {}, "framework_renderer_provenance_present"),
                ("framework_dynamic_sequence_pass", False, "framework_dynamic_sequence_pass"),
                ("framework_media_ok", False, "framework_media_ok"),
            ):
                original = evih_data[field]
                evih_data[field] = failed_value
                evih.write_text(json.dumps(evih_data), encoding="utf-8")
                failed_framework = case_report(
                    {"label": "white-knight", "mimic": mimic, "evih": evih, "review": review}
                )
                self.assertIn(f"gate_failed:{expected_gate}", failed_framework["blockers"])
                evih_data[field] = original
            evih_data["framework_renderer_provenance"] = {"renderer": "test"}
            evih.write_text(json.dumps(evih_data), encoding="utf-8")
            invalid_provenance = case_report(
                {"label": "white-knight", "mimic": mimic, "evih": evih, "review": review}
            )
            self.assertIn("gate_failed:framework_renderer_provenance_valid", invalid_provenance["blockers"])

    def test_case_manifest_rejects_stale_visual_review_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mimic = root / "mesh_reference_manifest.json"
            evih = root / "visual_result_manifest.json"
            review = root / "visual_review.json"
            sheet = root / "comparison.png"
            comparison_mp4 = root / "comparison.mp4"
            sheet.write_bytes(b"sheet")
            comparison_mp4.write_bytes(b"comparison-video")
            mimic_payload = {
                "mesh_reference_pass": True,
                "capture_ok": True,
                "media_ok": True,
                "asset_ok": True,
                "package_ok": True,
                "data_binding_ok": True,
                "dynamic_sequence_ok": True,
                "source_was_ppm_only": False,
                "blocker": "",
            }
            mimic.write_text(json.dumps(mimic_payload), encoding="utf-8")
            evidence = {
                "mimickit_mesh_reference_manifest_sha256": hashlib.sha256(mimic.read_bytes()).hexdigest(),
                "comparison_sheet_sha256": hashlib.sha256(sheet.read_bytes()).hexdigest(),
                "comparison_mp4_sha256": hashlib.sha256(comparison_mp4.read_bytes()).hexdigest(),
            }
            review.write_text(
                json.dumps(
                    {
                        "visual_review_pass": True,
                        "reviewer": "test-reviewer",
                        "reviewed_at_utc": "2026-06-12T00:00:00Z",
                        "checks": {
                            "character": True,
                            "sword": True,
                            "shield": True,
                            "pose": True,
                            "camera": True,
                            "ground": True,
                            "lighting": True,
                            "frame_pairing": True,
                            "no_obvious_penetration_or_drift": True,
                        },
                        "evidence": evidence,
                    }
                ),
                encoding="utf-8",
            )
            evih.write_text(
                json.dumps(
                    {
                        "evih_mesh_replay_pass": True,
                        "software_geometry_replay_pass": True,
                        "framework_api_used": True,
                        "evih_framework_api_replay_pass": True,
                        "framework_scene_contract_compare_pass": True,
                        "framework_visual_metric_pass": True,
                        "framework_scene_visual_metric_pass": True,
                        "framework_dynamic_sequence_pass": True,
                        "framework_media_ok": True,
                        "framework_renderer_provenance": valid_framework_provenance(root),
                        "data_binding_ok": True,
                        "mesh_binding_pass": True,
                        "fk_compare_pass": True,
                        "scene_contract_compare_pass": True,
                        "scene_visual_metric_pass": True,
                        "visual_metric_pass": True,
                        "dynamic_sequence_pass": True,
                        "comparison_mp4_pass": True,
                        "media_ok": True,
                        "blocker": "",
                        "comparison_sheet": str(sheet),
                        "comparison_mp4": str(comparison_mp4),
                        "mesh_report": {"visual_review_evidence": evidence},
                    }
                ),
                encoding="utf-8",
            )
            current = case_report({"label": "white-knight", "mimic": mimic, "evih": evih, "review": review})
            self.assertTrue(current["case_acceptance_pass"], current)
            mimic_payload["new_generation"] = True
            mimic.write_text(json.dumps(mimic_payload), encoding="utf-8")
            stale = case_report({"label": "white-knight", "mimic": mimic, "evih": evih, "review": review})
            self.assertFalse(stale["case_acceptance_pass"])
            self.assertIn("gate_failed:visual_review_binds_current_mimic_manifest", stale["blockers"])

    def test_full_chain_defaults_require_all_three_true_mesh_cases(self) -> None:
        self.assertEqual(DEFAULT_REQUIRED_LABELS, ("white-knight", "walk-exact", "stop-exact"))

    def test_plan_6_9_orchestrator_has_no_previous_gate_bypass(self) -> None:
        self.assertEqual(PREREQUISITES["white-knight"], "white-knight-smoke")
        self.assertEqual(PREREQUISITES["walk-exact"], "white-knight")
        self.assertEqual(PREREQUISITES["stop-exact"], "walk-exact")
        self.assertIn("white-knight-smoke", GENERATION_GATES)
        self.assertEqual(REVIEW_PROMOTION_GATE, "promote-review")
        self.assertEqual(FRAMEWORK_PREFLIGHT_GATE, "framework-preflight")
        self.assertEqual(FRAMEWORK_RENDER_GATE, "framework-render")
        promotion = review_promotion_command("white-knight-smoke", Path("/evih"), Path("/python"))
        self.assertIn("build_visual_results.py", promotion[1])
        self.assertIn("--framework-api", promotion)
        self.assertIn("--review-only", promotion)
        self.assertNotIn("build_mimickit_mesh_reference.py", " ".join(promotion))
        smoke_command = source_build_command("white-knight-smoke", Path("/python"))
        self.assertIn("build_mimickit_mesh_reference.py", smoke_command[1])
        self.assertIn("300", smoke_command)
        command = source_build_command("white-knight", Path("/python"))
        self.assertIn("--run-native-windows", command)
        self.assertIn("300", command)
        self.assertNotIn("--allow-unreviewed-next-gate", command)
        for case_name in FINAL_CASES:
            final_command = evih_build_command(case_name, Path("/evih"), Path("/python"), framework_api=True)
            self.assertIn("--framework-api", final_command)
        smoke_evih_command = evih_build_command("white-knight-smoke", Path("/evih"), Path("/python"))
        self.assertNotIn("--framework-api", smoke_evih_command)
        capture_command = framework_capture_command("white-knight", Path("/evih"), Path("/framework-python"))
        self.assertIn("framework_capture.py", capture_command[1])
        self.assertNotIn("build_visual_results.py", " ".join(capture_command))
        results_command = framework_results_command("white-knight", Path("/evih"), Path("/python"))
        self.assertIn("--framework-results-only", results_command)
        self.assertNotIn("--framework-api", results_command)

    def test_final_automatic_gate_requires_every_non_review_framework_check(self) -> None:
        checks = {name: True for name in FINAL_AUTOMATIC_CHECKS}
        self.assertTrue(final_automatic_gate_pass({"checks": checks}))
        checks["framework_renderer_provenance_present"] = False
        self.assertFalse(final_automatic_gate_pass({"checks": checks}))
        self.assertFalse(final_automatic_gate_pass({"checks": {}}))

    def test_framework_provenance_requires_exact_components_passes_and_artifact_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            provenance = valid_framework_provenance(root)
            self.assertTrue(framework_renderer_provenance_valid(provenance))
            provenance["render_pipeline"] = "fake"
            self.assertFalse(framework_renderer_provenance_valid(provenance))
            provenance = valid_framework_provenance(root)
            provenance["capture_passes"] = ["full_scene"]
            self.assertFalse(framework_renderer_provenance_valid(provenance))
            provenance = valid_framework_provenance(root)
            Path(provenance["body_world_replay"]).write_text("drift", encoding="utf-8")
            self.assertFalse(framework_renderer_provenance_valid(provenance))

    def test_aggregate_refuses_before_all_cases_are_accepted(self) -> None:
        with patch("run_plan_6_9_bridge.next_gate_status", return_value=("walk-exact", "gate_not_accepted:walk-exact")):
            self.assertEqual(
                aggregate_prerequisite_blocker(Path("/evih")),
                "aggregate_requires_accepted_case:walk-exact",
            )
        with patch("run_plan_6_9_bridge.next_gate_status", return_value=("aggregate", "")):
            self.assertEqual(aggregate_prerequisite_blocker(Path("/evih")), "")

    def test_plan_6_9_preflight_reports_missing_environment(self) -> None:
        report = preflight_report(Path("/definitely/missing/evih"), Path("/definitely/missing/python"))
        self.assertFalse(report["preflight_pass"])
        self.assertIn("preflight_failed:python_exists", report["blockers"])
        self.assertIn("preflight_failed:evih_builder_exists", report["blockers"])

    def test_dashboard_external_evih_blocker_is_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            train_root = root / "amp_test_root"
            render_base = root / "render"
            render_root = render_base / train_root.name
            evih_root = root / "evih"
            train_root.mkdir()
            render_root.mkdir(parents=True)
            evih_case = evih_root / "case"
            evih_case.mkdir(parents=True)
            (evih_case / "visual_result_manifest.json").write_text(
                json.dumps({"mimickit_package_dir": str(train_root), "blocker": "visual_review_missing_or_failed"}),
                encoding="utf-8",
            )
            comparison = evih_case / "evih_mesh_replay" / "comparison_sheet.md"
            review = evih_case / "evih_mesh_replay" / "visual_review.json"
            metric = evih_case / "evih_mesh_replay" / "visual_metric_report.json"
            comparison_video = evih_case / "evih_mesh_replay" / "mimickit_vs_evih_dynamic.mp4"
            comparison.parent.mkdir()
            comparison.write_text("# comparison", encoding="utf-8")
            review.write_text("{}", encoding="utf-8")
            metric.write_text("{}", encoding="utf-8")
            comparison_video.write_bytes(b"video")
            old_evih_root = run_amp_keepalive.EVIH_RESULTS_ROOT
            try:
                run_amp_keepalive.EVIH_RESULTS_ROOT = evih_root
                summary = run_amp_keepalive.render_summary(train_root, str(render_base))
            finally:
                run_amp_keepalive.EVIH_RESULTS_ROOT = old_evih_root
            self.assertEqual(summary["status"], "failed")
            self.assertEqual(summary["blocker"], "visual_review_missing_or_failed")
            self.assertIn("visual_review_missing_or_failed", summary["blockers"])
            self.assertEqual(summary["comparison_markdown_files"], [str(comparison)])
            self.assertEqual(summary["visual_review_files"], [str(review)])
            self.assertEqual(summary["metric_report_files"], [str(metric)])
            self.assertEqual(summary["comparison_video_files"], [str(comparison_video)])

    def test_dashboard_single_case_acceptance_is_not_full_chain_ready(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            train_root = root / "amp_test_root"
            render_base = root / "render"
            render_root = render_base / train_root.name
            train_root.mkdir()
            render_root.mkdir(parents=True)
            (render_root / "bridge_case_manifest.json").write_text(
                json.dumps({"case_acceptance_pass": True, "blocker": "", "blockers": []}),
                encoding="utf-8",
            )
            summary = run_amp_keepalive.render_summary(train_root, str(render_base))
            self.assertNotEqual(summary["status"], "available")
            self.assertTrue(summary["case_acceptance_detected"])
            self.assertFalse(summary["full_chain_bridge_pass"])

    def test_dashboard_framework_pass_count_requires_valid_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            train_root = root / "amp_test_root"
            render_base = root / "render"
            render_root = render_base / train_root.name
            evih_root = root / "evih"
            train_root.mkdir()
            render_root.mkdir(parents=True)
            for name, provenance_valid in (("valid", True), ("invalid", False)):
                case = evih_root / name
                case.mkdir(parents=True)
                (case / "visual_result_manifest.json").write_text(
                    json.dumps(
                        {
                            "mimickit_package_dir": str(train_root),
                            "evih_framework_api_replay_pass": True,
                            "framework_renderer_provenance_valid": provenance_valid,
                            "blocker": "" if provenance_valid else "framework_renderer_provenance_invalid",
                        }
                    ),
                    encoding="utf-8",
                )
            old_evih_root = run_amp_keepalive.EVIH_RESULTS_ROOT
            try:
                run_amp_keepalive.EVIH_RESULTS_ROOT = evih_root
                summary = run_amp_keepalive.render_summary(train_root, str(render_base))
            finally:
                run_amp_keepalive.EVIH_RESULTS_ROOT = old_evih_root
            self.assertEqual(summary["framework_api_pass_count"], 1)
            self.assertIn("framework_renderer_provenance_invalid", summary["blockers"])

    def test_dashboard_surfaces_plan_6_9_execution_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            train_root = root / "amp_test_root"
            render_base = root / "render"
            render_root = render_base / train_root.name
            train_root.mkdir()
            render_root.mkdir(parents=True)
            bridge_root = render_base / "mimickit_evih_bridge_v3"
            bridge_root.mkdir()
            execution = bridge_root / "plan_6_9_execution_manifest.json"
            execution.write_text(
                json.dumps({"blockers": ["previous_gate_not_accepted:white-knight-smoke"]}),
                encoding="utf-8",
            )
            summary = run_amp_keepalive.render_summary(train_root, str(render_base))
            self.assertEqual(summary["status"], "failed")
            self.assertIn("previous_gate_not_accepted:white-knight-smoke", summary["blockers"])
            self.assertEqual(summary["bridge_execution_manifest_files"], [str(execution)])


if __name__ == "__main__":
    unittest.main()
