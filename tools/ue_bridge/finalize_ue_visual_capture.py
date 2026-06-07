#!/usr/bin/env python3
"""Finalize UE MimicKit visual captures into PNG frames and MP4 media."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image


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


def parse_frame_number(path: Path) -> int | None:
    stem = path.stem
    if not stem.startswith("frame_"):
        return None
    try:
        return int(stem.replace("frame_", "", 1))
    except ValueError:
        return None


def collect_source_frames(frames_dir: Path) -> list[Path]:
    by_frame: dict[int, Path] = {}
    # Prefer PNG if UE already emitted it, otherwise accept legacy PPM.
    for suffix in ("ppm", "png"):
        for path in sorted(frames_dir.glob(f"frame_*.{suffix}")):
            frame = parse_frame_number(path)
            if frame is None:
                continue
            by_frame[frame] = path
    return [by_frame[key] for key in sorted(by_frame)]


def convert_frames_to_png(source_frames: list[Path], png_dir: Path, force: bool) -> list[dict[str, Any]]:
    if force and png_dir.exists():
        shutil.rmtree(png_dir)
    png_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    for source in source_frames:
        frame = parse_frame_number(source)
        if frame is None:
            continue
        target = png_dir / f"frame_{frame:06d}.png"
        if target.exists() and not force:
            rows.append({"frame": frame, "source": str(source), "png": str(target), "reused": True})
            continue
        image = Image.open(source).convert("RGB")
        image.save(target)
        rows.append({"frame": frame, "source": str(source), "png": str(target), "reused": False})
    return rows


def build_mp4(png_dir: Path, mp4_file: Path, fps: int) -> tuple[bool, str]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return False, "ffmpeg not found"

    mp4_file.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-framerate",
        str(int(fps)),
        "-pattern_type",
        "glob",
        "-i",
        str(png_dir / "frame_*.png"),
        "-pix_fmt",
        "yuv420p",
        str(mp4_file),
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)
    if proc.returncode != 0:
        return False, proc.stdout.strip()
    return mp4_file.exists(), ""


def patch_capture_meta(capture_meta_path: Path, manifest: dict[str, Any]) -> None:
    meta = read_json(capture_meta_path)
    if not meta:
        return
    meta["media_manifest"] = str(Path(manifest["manifest_file"]).resolve())
    meta["png_frames_dir"] = str(Path(manifest["png_frames_dir"]).resolve())
    meta["mp4_file"] = str(Path(manifest["mp4_file"]).resolve())
    meta["media_status"] = {
        "png_ok": bool(manifest["png_ok"]),
        "mp4_ok": bool(manifest["mp4_ok"]),
        "png_count": int(manifest["png_count"]),
        "fps": int(manifest["fps"]),
    }
    write_json(capture_meta_path, meta)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ue-capture-dir", required=True, help="UE capture directory containing frames/ and capture_meta.json")
    parser.add_argument("--frames-dir", default="", help="Override source frames directory")
    parser.add_argument("--png-dir", default="", help="PNG sequence output directory")
    parser.add_argument("--mp4-file", default="", help="MP4 output file")
    parser.add_argument("--manifest", default="", help="Output media manifest path")
    parser.add_argument("--fps", type=int, default=12)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--no-patch-capture-meta", dest="patch_capture_meta", action="store_false", default=True)
    args = parser.parse_args()

    capture_dir = Path(args.ue_capture_dir).resolve()
    frames_dir = Path(args.frames_dir).resolve() if args.frames_dir else capture_dir / "frames"
    png_dir = Path(args.png_dir).resolve() if args.png_dir else capture_dir / "png_frames"
    mp4_file = Path(args.mp4_file).resolve() if args.mp4_file else capture_dir / "capture.mp4"
    manifest_path = Path(args.manifest).resolve() if args.manifest else capture_dir / "capture_media_manifest.json"

    if args.fps <= 0:
        parser.error("--fps must be > 0")
    if not frames_dir.exists():
        raise SystemExit(f"[ERROR] source frames dir does not exist: {frames_dir}")

    source_frames = collect_source_frames(frames_dir)
    if not source_frames:
        raise SystemExit(f"[ERROR] no frame_*.ppm or frame_*.png files found under {frames_dir}")
    direct_png_count = len(list(frames_dir.glob("frame_*.png")))
    legacy_ppm_count = len(list(frames_dir.glob("frame_*.ppm")))

    png_rows = convert_frames_to_png(source_frames, png_dir=png_dir, force=bool(args.force))
    mp4_ok, mp4_error = build_mp4(png_dir=png_dir, mp4_file=mp4_file, fps=int(args.fps))

    manifest = {
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "capture_dir": str(capture_dir),
        "source_frames_dir": str(frames_dir),
        "png_frames_dir": str(png_dir),
        "mp4_file": str(mp4_file),
        "manifest_file": str(manifest_path),
        "fps": int(args.fps),
        "source_count": int(len(source_frames)),
        "direct_png_count": int(direct_png_count),
        "legacy_ppm_count": int(legacy_ppm_count),
        "source_was_ppm_only": bool(legacy_ppm_count > 0 and direct_png_count == 0),
        "png_count": int(len(png_rows)),
        "png_ok": bool(len(png_rows) > 0),
        "mp4_ok": bool(mp4_ok),
        "mp4_error": mp4_error,
        "first_frame": int(png_rows[0]["frame"]) if png_rows else None,
        "last_frame": int(png_rows[-1]["frame"]) if png_rows else None,
        "frames": png_rows,
    }
    write_json(manifest_path, manifest)

    if args.patch_capture_meta:
        patch_capture_meta(capture_dir / "capture_meta.json", manifest)

    print(json.dumps(manifest, ensure_ascii=False))
    return 0 if manifest["png_ok"] and manifest["mp4_ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
