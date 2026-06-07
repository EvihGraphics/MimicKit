#!/usr/bin/env python3

from __future__ import annotations

import json
import struct
import tempfile
import unittest
from pathlib import Path

from visual_bridge_validation import build_scene_contract_v2, inspect_glb


def write_glb(path: Path, payload: dict) -> None:
    json_chunk = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    json_chunk += b" " * ((4 - len(json_chunk) % 4) % 4)
    total = 12 + 8 + len(json_chunk)
    path.write_bytes(struct.pack("<4sII", b"glTF", 2, total) + struct.pack("<II", len(json_chunk), 0x4E4F534A) + json_chunk)


class VisualBridgeValidationTest(unittest.TestCase):
    def test_rejects_structurally_empty_glb(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "empty.glb"
            write_glb(path, {"asset": {"version": "2.0"}, "materials": [{}]})
            report = inspect_glb(path)
            self.assertFalse(report["ok"])
            self.assertEqual(report["blocker"], "mesh_asset_structure_invalid")

    def test_accepts_renderable_sword_shield_glb(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "valid.glb"
            write_glb(
                path,
                {
                    "asset": {"version": "2.0"},
                    "buffers": [{"byteLength": 12}],
                    "accessors": [{"count": 3}],
                    "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}],
                    "nodes": [{"name": "sword", "mesh": 0}, {"name": "shield", "mesh": 0}],
                },
            )
            report = inspect_glb(path)
            self.assertTrue(report["ok"])
            self.assertEqual(report["mesh_mode"], "rigid_node")

    def test_scene_contract_hash_is_stable(self):
        kwargs = dict(
            root_name="root",
            case="case",
            motion_id="motion",
            width=960,
            height=540,
            frames=300,
            frame_stride=5,
            fps=12,
            seed=7,
            renderer="isaac_lab",
        )
        self.assertEqual(
            build_scene_contract_v2(**kwargs)["scene_contract_sha256"],
            build_scene_contract_v2(**kwargs)["scene_contract_sha256"],
        )


if __name__ == "__main__":
    unittest.main()
