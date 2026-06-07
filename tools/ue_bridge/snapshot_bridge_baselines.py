#!/usr/bin/env python3
"""Snapshot preserved Walk/Stop geom baseline artifacts without modifying them."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from visual_bridge_validation import inspect_mp4, inspect_png, sha256_file, write_json


ROOT = Path(__file__).resolve().parents[2]
DEFAULTS = {
    "walk_long_geom": ROOT / "output" / "img" / "amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637" / "long_train" / "render",
    "stop_probe_geom": ROOT / "output" / "img" / "amp_StopBrain_dual_newton_hiutil_e1024_20260521_long01" / "probe_train" / "render",
}


def snapshot(label: str, render_dir: Path) -> dict:
    frames = sorted((render_dir / "frames").glob("frame_*.png"))
    frame_reports = [inspect_png(path) for path in frames]
    mp4_report = inspect_mp4(render_dir / "render.mp4")
    return {
        "label": label,
        "render_dir": str(render_dir),
        "png_count": len(frames),
        "png_all_valid": bool(frames) and all(item.get("ok") for item in frame_reports),
        "frame_sha256": {path.name: sha256_file(path) for path in frames},
        "mp4": mp4_report,
        "mp4_sha256": sha256_file(render_dir / "render.mp4"),
        "pass": len(frames) == 60 and all(item.get("ok") for item in frame_reports) and bool(mp4_report.get("ok")),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    cases = [snapshot(label, path) for label, path in DEFAULTS.items()]
    manifest = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "cases": cases,
        "baseline_protection_pass": all(item["pass"] for item in cases),
    }
    write_json(Path(args.out).resolve(), manifest)
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0 if manifest["baseline_protection_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
