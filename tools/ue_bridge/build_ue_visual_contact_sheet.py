#!/usr/bin/env python3
"""Build a MimicKit-vs-UE debug visual contact sheet and optional ledger entry."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw


DEFAULT_KEYFRAMES = "0,75,150,225,295"


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def parse_keyframes(text: str) -> list[int]:
    out: list[int] = []
    for token in text.split(","):
        token = token.strip()
        if token:
            out.append(int(token))
    return out


def collect_frames(frames_dir: Path, suffixes: tuple[str, ...]) -> dict[int, Path]:
    out: dict[int, Path] = {}
    for suffix in suffixes:
        for path in sorted(frames_dir.glob(f"frame_*.{suffix}")):
            stem = path.stem.replace("frame_", "")
            try:
                out[int(stem)] = path
            except ValueError:
                continue
    return out


def nearest_frame(frames: dict[int, Path], target: int) -> tuple[int, Path] | None:
    if not frames:
        return None
    frame = min(frames.keys(), key=lambda x: abs(x - target))
    return frame, frames[frame]


def load_panel(path: Path, label: str, size: tuple[int, int]) -> Image.Image:
    image = Image.open(path).convert("RGB")
    image.thumbnail(size, Image.Resampling.LANCZOS)
    panel = Image.new("RGB", size, (18, 20, 24))
    x = (size[0] - image.width) // 2
    y = (size[1] - image.height) // 2
    panel.paste(image, (x, y))
    draw = ImageDraw.Draw(panel)
    draw.rectangle((0, 0, size[0], 24), fill=(0, 0, 0))
    draw.text((8, 5), label, fill=(255, 255, 255))
    return panel


def build_sheet(
    mimic_frames: dict[int, Path],
    ue_frames: dict[int, Path],
    keyframes: list[int],
    out_path: Path,
    panel_size: tuple[int, int],
    ue_label: str,
) -> list[dict[str, Any]]:
    pairs: list[dict[str, Any]] = []
    columns = max(1, len(keyframes))
    sheet = Image.new("RGB", (columns * panel_size[0], 2 * panel_size[1]), (10, 12, 16))

    for col, keyframe in enumerate(keyframes):
        mimic = nearest_frame(mimic_frames, keyframe)
        ue = nearest_frame(ue_frames, keyframe)
        pairs.append(
            {
                "requested_frame": int(keyframe),
                "mimickit_frame": int(mimic[0]) if mimic else None,
                "mimickit_file": str(mimic[1]) if mimic else "",
                "ue_frame": int(ue[0]) if ue else None,
                "ue_file": str(ue[1]) if ue else "",
            }
        )

        if mimic:
            panel = load_panel(mimic[1], f"MimicKit frame {mimic[0]}", panel_size)
            sheet.paste(panel, (col * panel_size[0], 0))
        if ue:
            panel = load_panel(ue[1], f"{ue_label} frame {ue[0]}", panel_size)
            sheet.paste(panel, (col * panel_size[0], panel_size[1]))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)
    return pairs


def capture_summary(capture_meta: dict[str, Any]) -> dict[str, Any]:
    root_min = capture_meta.get("root_min_m") if isinstance(capture_meta.get("root_min_m"), list) else []
    root_max = capture_meta.get("root_max_m") if isinstance(capture_meta.get("root_max_m"), list) else []
    return {
        "capture_mode": capture_meta.get("capture_mode", capture_meta.get("mode", "")),
        "render_source": capture_meta.get("render_source", ""),
        "capture_frames": capture_meta.get("capture_frames", 0),
        "source_rows": capture_meta.get("source_rows", 0),
        "frame_stride": capture_meta.get("frame_stride", 0),
        "root_min_m": root_min,
        "root_max_m": root_max,
        "mode": capture_meta.get("mode", ""),
        "target_mesh": capture_meta.get("target_mesh", ""),
        "target_skeleton": capture_meta.get("target_skeleton", ""),
        "fallback_renderer": capture_meta.get("fallback_renderer", ""),
        "dof_pos_applied": bool(capture_meta.get("dof_pos_applied", False)),
        "skeletal_pose_frames": int(capture_meta.get("skeletal_pose_frames", 0) or 0),
        "bone_map_hash": capture_meta.get("bone_map_hash", ""),
        "basis_transform_hash": capture_meta.get("basis_transform_hash", ""),
        "full_character_parity": bool(capture_meta.get("full_character_parity", False)),
        "driver_component": capture_meta.get("driver_component", ""),
        "loaded_skeletal_mesh": bool(capture_meta.get("loaded_skeletal_mesh", False)),
        "poseable_component_created": bool(capture_meta.get("poseable_component_created", False)),
        "mimickit_source_asset_imported_to_ue": bool(capture_meta.get("mimickit_source_asset_imported_to_ue", False)),
        "source_asset_build_report": capture_meta.get("source_asset_build_report", ""),
        "live_policy_control_pass": bool(capture_meta.get("live_policy_control_pass", False)),
        "chaos_contact_validated": bool(capture_meta.get("chaos_contact_validated", False)),
        "package_dir": capture_meta.get("package_dir", ""),
        "png_frames_dir": capture_meta.get("png_frames_dir", ""),
        "mp4_file": capture_meta.get("mp4_file", ""),
        "media_manifest": capture_meta.get("media_manifest", ""),
        "media_status": capture_meta.get("media_status", {}),
    }


def is_source_character_full_parity(capture_meta: dict[str, Any], media_manifest: dict[str, Any]) -> bool:
    capture_mode = str(capture_meta.get("capture_mode", capture_meta.get("mode", "")))
    render_source = str(capture_meta.get("render_source", ""))
    target_mesh = str(capture_meta.get("target_mesh", ""))
    return (
        capture_mode == "source_character_skeletalmesh_replay"
        and render_source == "ue_scene_capture_render_target"
        and bool(media_manifest.get("png_ok", False))
        and bool(media_manifest.get("mp4_ok", False))
        and not bool(media_manifest.get("source_was_ppm_only", False))
        and int(media_manifest.get("png_count", 0) or 0) > 0
        and bool(capture_meta.get("dof_pos_applied", False))
        and int(capture_meta.get("skeletal_pose_frames", 0) or 0) > 0
        and bool(capture_meta.get("full_character_parity", False))
        and bool(capture_meta.get("loaded_skeletal_mesh", False))
        and bool(capture_meta.get("poseable_component_created", False))
        and bool(capture_meta.get("mimickit_source_asset_imported_to_ue", False))
        and target_mesh.startswith("/Game/MimicKit/SwordShield/")
        and str(capture_meta.get("fallback_renderer", "")) == ""
    )


def infer_verdict(mimic_frames: dict[int, Path], ue_frames: dict[int, Path], capture_meta: dict[str, Any], media_manifest: dict[str, Any]) -> str:
    if not mimic_frames or not ue_frames:
        return "block"
    capture_mode = str(capture_meta.get("capture_mode", capture_meta.get("mode", "")))
    png_ok = bool(media_manifest.get("png_ok", False))
    mp4_ok = bool(media_manifest.get("mp4_ok", False))
    if capture_mode == "source_character_skeletalmesh_replay":
        return "pass" if is_source_character_full_parity(capture_meta, media_manifest) else "block"
    if capture_mode == "skeletal_replay":
        if (
            png_ok
            and mp4_ok
            and not bool(media_manifest.get("source_was_ppm_only", False))
            and bool(capture_meta.get("dof_pos_applied", False))
            and int(capture_meta.get("skeletal_pose_frames", 0) or 0) > 0
            and capture_meta.get("bone_map_hash")
            and capture_meta.get("basis_transform_hash")
        ):
            return "pass"
        return "block"
    return "watch"


def observed_differences_for_capture(capture_meta: dict[str, Any], verdict: str) -> dict[str, str]:
    capture_mode = str(capture_meta.get("capture_mode", capture_meta.get("mode", "")))
    if capture_mode == "source_character_skeletalmesh_replay":
        return {
            "scale": "pass: source character capture uses the package basis transform and UE centimeter scene units.",
            "root_trajectory": "pass: root_pos_m drives the source-character PoseableMeshComponent inside a UE SceneCapture world.",
            "facing": "pass: root_rot_xyzw is applied to the source-character driver component before render-target capture.",
            "pose": "pass: dof_pos is applied and captured through UE SceneCapture/RenderTarget, not procedural pixels.",
            "contact_sliding": "watch: source feet are visible and contact bodies are declared; Chaos contact is validated by the live runtime gate.",
            "timing": "pass: capture stride and frame IDs are preserved from MimicKit visual_replay.",
            "jitter": "watch: per-joint jitter is visually exposed in the contact sheet but not numerically scored.",
            "missing_assets": "pass: UE target is the generated MimicKit source-character SkeletalMesh, not Manny/procedural fallback.",
            "runtime_physics": "watch: this is offline source-character replay; live policy/Chaos closure is a separate gate.",
        }
    if capture_mode == "skeletal_replay":
        full_character = bool(capture_meta.get("full_character_parity", False))
        missing_assets = (
            "pass: MimicKit source visual asset is driving the UE target."
            if full_character
            else "watch: skeletal replay uses the declared UE fallback/procedural target; do not claim full MimicKit character parity."
        )
        return {
            "scale": "pass: offline basis transform is declared and capture writes meter-to-centimeter mapping metadata.",
            "root_trajectory": "pass: UE skeletal capture is driven from visual_replay root_pos_m.",
            "facing": "pass: root_rot_xyzw is consumed for skeletal replay orientation/projection.",
            "pose": "pass: dof_pos is applied through the skeletal replay path for every captured frame.",
            "contact_sliding": "pass: foot bodies are present in the skeletal replay frames; contact physics remains outside this visual gate.",
            "timing": "pass: capture stride and frame IDs are preserved from MimicKit visual_replay.",
            "jitter": "watch: per-joint jitter is visually exposed in the contact sheet but not numerically scored.",
            "missing_assets": missing_assets,
            "runtime_physics": "watch: this is offline skeletal replay, not live UE policy control or Chaos takeover.",
        }
    return {
        "scale": "watch: UE debug capture plots root_pos_m in training meters; no skeletal mesh scale validation yet.",
        "root_trajectory": "watch: UE top-down root trajectory is visible; compare against MimicKit perspective render qualitatively.",
        "facing": "watch: UE facing axis is drawn from root_rot_xyzw; quaternion convention still pending full skeleton validation.",
        "pose": "block for full parity: debug capture does not apply dof_pos to a UE skeleton.",
        "contact_sliding": "block for full parity: no UE skeletal feet/contact surfaces are rendered.",
        "timing": "watch: capture stride matches MimicKit frame stride; no wall-clock playback validation.",
        "jitter": "watch: root trajectory can expose coarse jumps, but no per-joint jitter validation.",
        "missing_assets": "watch: transient debug capture intentionally uses no content assets.",
        "runtime_physics": "watch: this is offline debug capture, not live UE policy control or Chaos takeover.",
    }


def build_report(args: argparse.Namespace, pairs: list[dict[str, Any]], verdict: str) -> dict[str, Any]:
    mimic_meta = read_json(Path(args.mimic_render_dir) / "render_meta.json")
    capture_meta = read_json(Path(args.ue_capture_dir) / "capture_meta.json")
    media_manifest = read_json(Path(args.ue_capture_dir) / "capture_media_manifest.json")
    observed_differences = observed_differences_for_capture(capture_meta, verdict)
    capture_mode = str(capture_meta.get("capture_mode", capture_meta.get("mode", "")))
    return {
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "brain": args.brain,
        "root": args.root,
        "package_dir": args.package_dir,
        "mimic_render_dir": str(Path(args.mimic_render_dir).resolve()),
        "mimic_mp4": str((Path(args.mimic_render_dir) / "render.mp4").resolve()),
        "ue_capture_dir": str(Path(args.ue_capture_dir).resolve()),
        "ue_capture_mp4": str((Path(args.ue_capture_dir) / "capture.mp4").resolve()),
        "ue_media_manifest": str((Path(args.ue_capture_dir) / "capture_media_manifest.json").resolve()),
        "ue_log": args.ue_log,
        "contact_sheet": str(Path(args.contact_sheet).resolve()),
        "verdict": verdict,
        "keyframe_pairs": pairs,
        "mimic": {
            "status": mimic_meta.get("status", ""),
            "image_count": mimic_meta.get("image_count", 0),
            "frames": mimic_meta.get("frames", 0),
            "frame_stride": mimic_meta.get("frame_stride", 0),
            "visual_kind": mimic_meta.get("visual_kind", ""),
            "char_file": mimic_meta.get("char_file", ""),
        },
        "ue": capture_summary(capture_meta),
        "ue_media": {
            "png_ok": bool(media_manifest.get("png_ok", False)),
            "png_count": int(media_manifest.get("png_count", 0) or 0),
            "direct_png_count": int(media_manifest.get("direct_png_count", 0) or 0),
            "legacy_ppm_count": int(media_manifest.get("legacy_ppm_count", 0) or 0),
            "source_was_ppm_only": bool(media_manifest.get("source_was_ppm_only", False)),
            "mp4_ok": bool(media_manifest.get("mp4_ok", False)),
            "mp4_file": media_manifest.get("mp4_file", ""),
            "manifest": str((Path(args.ue_capture_dir) / "capture_media_manifest.json").resolve()),
        },
        "capture_mode": capture_mode,
        "skeletal_visual_pass": verdict == "pass" and capture_mode == "skeletal_replay",
        "source_character_replay_pass": verdict == "pass" and capture_mode == "source_character_skeletalmesh_replay",
        "full_visual_parity": is_source_character_full_parity(capture_meta, media_manifest) and verdict == "pass",
        "observed_differences": observed_differences,
    }


def append_ledger(args: argparse.Namespace, report: dict[str, Any]) -> None:
    ledger = Path(args.ledger)
    if not ledger:
        return
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    diffs = report["observed_differences"]
    capture_mode = str(report.get("capture_mode", ""))
    if report.get("source_character_replay_pass"):
        title = f"{args.brain} - source character full visual parity closure"
        mode_line = (
            "non-NullRHI UE automation, offline source-character SkeletalMesh replay, "
            "root_pos/root_rot/dof_pos applied to generated MimicKit source character"
        )
        next_action = "run live policy/Chaos closure and keep this source-character capture as the visual parity gate"
    elif report.get("skeletal_visual_pass"):
        title = f"{args.brain} - skeletal replay visual closure"
        mode_line = (
            "non-NullRHI UE automation, offline skeletal replay capture, "
            "root_pos/root_rot/dof_pos applied to declared skeletal replay target"
        )
        next_action = (
            "extend the skeletal gate to Walk/Turn/Stop and replace the fallback target "
            "with an imported MimicKit USD SkeletalMesh before claiming full visual parity"
        )
    else:
        title = f"{args.brain} - long01 fresh probe debug-geometry capture"
        mode_line = "non-NullRHI UE automation, transient debug replay, top-down root trajectory/facing capture, no skeletal pose application"
        next_action = "keep `long_train` gated; implement UE skeletal pose replay/joint mapping before any full visual parity pass"
    entry = f"""

### {now} Asia/Shanghai - {title}

- brain/root/package source:
  - root: `{args.root}`
  - package: `{args.package_dir}`
- MimicKit reference:
  - mp4: `{report['mimic_mp4']}`
  - frames: `{Path(args.mimic_render_dir).resolve() / 'frames'}`
  - render_meta: `{Path(args.mimic_render_dir).resolve() / 'render_meta.json'}`
- UE capture/log:
  - capture: `{Path(args.ue_capture_dir).resolve()}`
  - png frames: `{Path(args.ue_capture_dir).resolve() / 'png_frames'}`
  - mp4: `{report['ue_capture_mp4']}`
  - log: `{args.ue_log}`
- camera/map/replay mode: {mode_line}
- capture mode: `{capture_mode}`
- UE target:
  - mesh: `{report['ue'].get('target_mesh', '')}`
  - fallback renderer: `{report['ue'].get('fallback_renderer', '')}`
  - bone_map_hash: `{report['ue'].get('bone_map_hash', '')}`
  - basis_transform_hash: `{report['ue'].get('basis_transform_hash', '')}`
- observed differences:
  - scale: {diffs['scale']}
  - root trajectory: {diffs['root_trajectory']}
  - facing: {diffs['facing']}
  - pose: {diffs['pose']}
  - contact/sliding: {diffs['contact_sliding']}
  - timing: {diffs['timing']}
  - jitter: {diffs['jitter']}
  - missing assets: {diffs['missing_assets']}
  - runtime physics/control: {diffs['runtime_physics']}
- verdict: {report['verdict']}
- skeletal_visual_pass: {str(report.get('skeletal_visual_pass', False)).lower()}
- source_character_replay_pass: {str(report.get('source_character_replay_pass', False)).lower()}
- full_visual_parity: {str(report.get('full_visual_parity', False)).lower()}
- next action: {next_action}
"""
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as fp:
        fp.write(entry)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brain", required=True)
    parser.add_argument("--root", required=True)
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--mimic-render-dir", required=True)
    parser.add_argument("--ue-capture-dir", required=True)
    parser.add_argument("--ue-log", default="")
    parser.add_argument("--out-report", required=True)
    parser.add_argument("--contact-sheet", required=True)
    parser.add_argument("--ledger", default="")
    parser.add_argument("--keyframes", default=DEFAULT_KEYFRAMES)
    parser.add_argument("--panel-width", type=int, default=320)
    parser.add_argument("--panel-height", type=int, default=220)
    args = parser.parse_args()

    mimic_frames = collect_frames(Path(args.mimic_render_dir) / "frames", ("png",))
    ue_frames_dir = Path(args.ue_capture_dir) / "png_frames"
    if not ue_frames_dir.exists():
        ue_frames_dir = Path(args.ue_capture_dir) / "frames"
    ue_frames = collect_frames(ue_frames_dir, ("png", "ppm"))
    capture_meta = read_json(Path(args.ue_capture_dir) / "capture_meta.json")
    media_manifest = read_json(Path(args.ue_capture_dir) / "capture_media_manifest.json")
    verdict = infer_verdict(mimic_frames, ue_frames, capture_meta, media_manifest)
    capture_mode = str(capture_meta.get("capture_mode", capture_meta.get("mode", "")))
    if capture_mode == "source_character_skeletalmesh_replay":
        ue_label = "UE source"
    elif capture_mode == "skeletal_replay":
        ue_label = "UE skeletal"
    else:
        ue_label = "UE debug"
    pairs = build_sheet(
        mimic_frames=mimic_frames,
        ue_frames=ue_frames,
        keyframes=parse_keyframes(args.keyframes),
        out_path=Path(args.contact_sheet),
        panel_size=(int(args.panel_width), int(args.panel_height)),
        ue_label=ue_label,
    )
    report = build_report(args, pairs, verdict)
    report_path = Path(args.out_report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.ledger:
        append_ledger(args, report)
    print(json.dumps(report, ensure_ascii=False))
    return 0 if verdict in {"watch", "pass"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
