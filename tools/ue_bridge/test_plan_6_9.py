#!/usr/bin/env python3

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from build_full_chain_bridge_manifest import DEFAULT_REQUIRED_LABELS
from build_full_chain_bridge_manifest import case_report
import scripts.run_amp_keepalive as run_amp_keepalive
from build_mimickit_mesh_reference import finalize_manifest_gate_fields, localize_native_manifest_paths
from run_plan_6_9_bridge import PREREQUISITES, source_build_command
from visual_bridge_validation import build_scene_contract_v3, validate_body_world_replay


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
        }
        for frame in (0, 5)
    ]


class Plan69Test(unittest.TestCase):
    def test_source_manifest_exposes_independent_v3_gates(self) -> None:
        manifest = finalize_manifest_gate_fields(
            {
                "expected_image_count": 2,
                "render_summary": {
                    "mesh_reference_pass": True,
                    "expected_image_count": 2,
                    "image_count": 2,
                    "silhouette_image_count": 2,
                    "ground_mask_image_count": 2,
                    "mp4_ok": True,
                    "source_was_ppm_only": False,
                },
                "asset_export": {"ok": True, "asset_structure": {"ok": True}},
                "package_export": {"ok": True},
            }
        )
        self.assertTrue(manifest["capture_ok"])
        self.assertTrue(manifest["media_ok"])
        self.assertTrue(manifest["asset_ok"])
        self.assertTrue(manifest["package_ok"])

    def test_strict_scene_contract_rejects_null_fov(self) -> None:
        kwargs = {
            "root_name": "root",
            "case": "case",
            "motion_id": "motion",
            "width": 960,
            "height": 540,
            "frames": 10,
            "frame_stride": 5,
            "fps": 12,
            "seed": 7,
            "renderer": "isaaclab",
            "camera_samples": camera_samples(),
        }
        contract = build_scene_contract_v3(**kwargs)
        self.assertEqual(contract["schema_version"], 3)
        self.assertEqual(contract["timing"]["expected_frame_ids"], [0, 5])
        kwargs["camera_samples"][0]["fov_degrees"] = None
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
            frames=10,
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
                        "data_binding_ok": True,
                        "mesh_binding_pass": True,
                        "fk_compare_pass": True,
                        "scene_contract_compare_pass": True,
                        "scene_visual_metric_pass": True,
                        "visual_metric_pass": True,
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

    def test_full_chain_defaults_require_all_three_true_mesh_cases(self) -> None:
        self.assertEqual(DEFAULT_REQUIRED_LABELS, ("white-knight", "walk-exact", "stop-exact"))

    def test_plan_6_9_orchestrator_has_no_previous_gate_bypass(self) -> None:
        self.assertEqual(PREREQUISITES["white-knight"], "white-knight-smoke")
        self.assertEqual(PREREQUISITES["walk-exact"], "white-knight")
        self.assertEqual(PREREQUISITES["stop-exact"], "walk-exact")
        command = source_build_command("white-knight", Path("/python"))
        self.assertIn("--run-native-windows", command)
        self.assertIn("300", command)
        self.assertNotIn("--allow-unreviewed-next-gate", command)

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
            old_evih_root = run_amp_keepalive.EVIH_RESULTS_ROOT
            try:
                run_amp_keepalive.EVIH_RESULTS_ROOT = evih_root
                summary = run_amp_keepalive.render_summary(train_root, str(render_base))
            finally:
                run_amp_keepalive.EVIH_RESULTS_ROOT = old_evih_root
            self.assertEqual(summary["status"], "failed")
            self.assertEqual(summary["blocker"], "visual_review_missing_or_failed")
            self.assertIn("visual_review_missing_or_failed", summary["blockers"])

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
