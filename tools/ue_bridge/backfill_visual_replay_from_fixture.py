#!/usr/bin/env python3
"""Build visual replay sidecars from existing UE export fixtures."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from _bridge_common import save_json


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fp:
        for row in rows:
            fp.write(json.dumps(row, ensure_ascii=False) + "\n")


def _as_float_list(value: Any) -> list[float]:
    if not isinstance(value, list):
        return []
    return [float(x) for x in value]


def _patch_manifest(package_dir: Path, replay_rel: str, meta_rel: str) -> None:
    brain_manifest_path = package_dir / "brain_manifest.json"
    if brain_manifest_path.exists():
        brain_manifest = _read_json(brain_manifest_path)
        brain_manifest["visual_replay_file"] = replay_rel
        brain_manifest["visual_replay_meta_file"] = meta_rel
        brain_manifest["visual_replay"] = {
            "pose_dof_replay": replay_rel,
            "pose_dof_meta": meta_rel,
        }
        save_json(brain_manifest_path, brain_manifest)

    package_manifest_path = package_dir / "export_package_manifest.json"
    if package_manifest_path.exists():
        package_manifest = _read_json(package_manifest_path)
        artifacts = package_manifest.setdefault("artifacts", {})
        artifacts["visual_replay"] = replay_rel
        artifacts["visual_replay_meta"] = meta_rel
        status = package_manifest.setdefault("status", {})
        status["visual_replay_ok"] = True
        save_json(package_manifest_path, package_manifest)


def build_visual_replay(package_dir: Path) -> dict[str, Any]:
    package_dir = package_dir.resolve()
    obs_rows = _read_jsonl(package_dir / "obs_fixture.jsonl")
    action_rows = _read_jsonl(package_dir / "ref_actions.jsonl")
    brain_manifest = _read_json(package_dir / "brain_manifest.json")
    joint_order = _read_json(package_dir / "joint_order.json")

    action_by_frame = {int(row.get("frame", idx)): row for idx, row in enumerate(action_rows)}
    policy_hz = int(brain_manifest.get("policy_hz") or 0)
    physics_hz = int(brain_manifest.get("physics_hz") or 0)
    dof_size = int(joint_order.get("dof_size") or 0)
    action_dim = int(brain_manifest.get("action_dim") or 0)
    policy_dt = 1.0 / policy_hz if policy_hz > 0 else 0.0

    replay_rows: list[dict[str, Any]] = []
    for idx, obs_row in enumerate(obs_rows):
        frame = int(obs_row.get("frame", idx))
        action_row = action_by_frame.get(frame, {})
        dof_pos = _as_float_list(obs_row.get("dof_pos") or obs_row.get("ref_action"))
        replay_rows.append(
            {
                "frame": frame,
                "episode": int(obs_row.get("episode", 0)),
                "time_seconds": float(frame * policy_dt),
                "root_pos_m": _as_float_list(obs_row.get("ref_root_pos")),
                "root_rot_xyzw": _as_float_list(obs_row.get("ref_root_rot")),
                "dof_pos": dof_pos,
                "policy_action": _as_float_list(action_row.get("action")),
            }
        )

    visual_dir = package_dir / "visual_replay"
    replay_path = visual_dir / "pose_dof_replay.jsonl"
    meta_path = visual_dir / "pose_dof_meta.json"
    _write_jsonl(replay_path, replay_rows)

    meta = {
        "schema_version": 1,
        "row_count": int(len(replay_rows)),
        "policy_hz": policy_hz,
        "physics_hz": physics_hz,
        "dof_size": dof_size,
        "root_pos_dim": len(replay_rows[0].get("root_pos_m", [])) if replay_rows else 0,
        "root_rot_dim": len(replay_rows[0].get("root_rot_xyzw", [])) if replay_rows else 0,
        "root_vel_dim": 0,
        "root_ang_vel_dim": 0,
        "dof_pos_dim": len(replay_rows[0].get("dof_pos", [])) if replay_rows else 0,
        "dof_vel_dim": 0,
        "action_dim": action_dim,
        "joint_order_file": "../joint_order.json",
        "coordinate_basis": str(brain_manifest.get("coordinate_basis", "")),
        "unit_scale": str(brain_manifest.get("unit_scale", "")),
        "rotation_convention": "quat_xyzw",
        "files": {
            "pose_dof_replay": str(replay_path.resolve()),
        },
    }
    save_json(meta_path, meta)
    _patch_manifest(package_dir, "visual_replay/pose_dof_replay.jsonl", "visual_replay/pose_dof_meta.json")
    return {
        "package_dir": str(package_dir),
        "rows": int(len(replay_rows)),
        "dof_pos_dim": int(meta["dof_pos_dim"]),
        "action_dim": int(meta["action_dim"]),
        "replay": str(replay_path),
        "meta": str(meta_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill visual_replay sidecars from existing obs/action fixtures")
    parser.add_argument("package_dirs", nargs="+", help="One or more ue_export/MimicKit package directories")
    args = parser.parse_args()

    for raw_dir in args.package_dirs:
        result = build_visual_replay(Path(raw_dir))
        print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
