#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from build_full_chain_bridge_manifest import DEFAULT_REQUIRED_LABELS
from build_full_chain_bridge_manifest import case_report
import scripts.run_amp_keepalive as run_amp_keepalive
from build_mimickit_mesh_reference import finalize_manifest_gate_fields, localize_native_manifest_paths
from build_mimickit_mesh_reference import sync_native_workspace_scripts as sync_white_knight_native_scripts
from build_mimickit_exact_mesh_reference import sync_native_workspace_scripts as sync_exact_native_scripts
from run_plan_6_9_bridge import (
    GENERATION_GATES,
    PREREQUISITES,
    REVIEW_PROMOTION_GATE,
    FRAMEWORK_PREFLIGHT_GATE,
    FRAMEWORK_RENDER_GATE,
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
                        "framework_renderer_provenance": {"renderer": "test"},
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
                        "framework_renderer_provenance": {"renderer": "test"},
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
