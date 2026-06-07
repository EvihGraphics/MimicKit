#!/usr/bin/env python3
"""Build MimicKit render frame sequences from final_ok training cases."""

from __future__ import annotations

import argparse
import csv
import gc
import importlib.util
import inspect
import json
import os
import random
import shutil
import subprocess
import sys
import traceback
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import gymnasium.spaces as spaces
import numpy as np
import torch
import yaml

from _bridge_common import build_runtime_context
from visual_bridge_validation import (
    build_scene_contract_v2,
    inspect_mp4,
    inspect_png,
    sha256_file,
    write_json,
)
import learning.base_agent as base_agent


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TRAIN_ROOT = ROOT / "output" / "train"
DEFAULT_IMG_ROOT = ROOT / "output" / "img"
_HAS_ISAACGYM: bool | None = None

INDEX_FIELDS = [
    "root",
    "case",
    "variant",
    "case_type",
    "case_kind",
    "status",
    "visual_kind",
    "char_file",
    "mesh_detected",
    "frames",
    "frame_stride",
    "expected_image_count",
    "image_count",
    "resumed",
    "dry_run",
    "arg_file",
    "model_file",
    "env_config",
    "engine_config",
    "agent_config",
    "llc_model_file",
    "motion_id",
    "motion_file",
    "source_pack",
    "category",
    "train_enabled",
    "view_enabled",
    "out_dir",
    "out_dir_rel",
    "render_dir",
    "render_meta",
    "mp4_file",
    "mp4_ok",
    "mp4_error",
    "scene_contract_sha256",
    "motion_visible",
    "error",
]


def parse_csv_list(text: str) -> list[str]:
    out: list[str] = []
    for token in text.split(","):
        curr = token.strip()
        if curr:
            out.append(curr)
    return out


def normalize_case_name(name: str) -> str:
    base = os.path.basename(name.strip())
    if not base:
        return ""
    if not base.endswith(".txt"):
        base = f"{base}.txt"
    return base


def parse_arg_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out

    toks: list[str] = []
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        toks.extend(line.split())

    i = 0
    while i < len(toks):
        token = toks[i]
        if token.startswith("--"):
            key = token[2:]
            if i + 1 < len(toks) and not toks[i + 1].startswith("--"):
                out[key] = toks[i + 1]
                i += 2
            else:
                out[key] = "true"
                i += 1
        else:
            i += 1
    return out


def read_tsv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fp:
        return list(csv.DictReader(fp, delimiter="\t"))


def parse_bool_final_ok(row: dict[str, str]) -> bool:
    return str(row.get("final_ok", "")).strip() == "1"


def parse_roots(train_root: Path) -> list[tuple[str, Path, Path]]:
    out: list[tuple[str, Path, Path]] = []
    for best_by_case in sorted(train_root.glob("*/best_by_case.tsv")):
        root_dir = best_by_case.parent
        out.append((root_dir.name, root_dir, best_by_case))
    return out


def select_roots(
    roots: list[tuple[str, Path, Path]],
    scope: str,
    root_filters: set[str],
) -> list[tuple[str, Path, Path]]:
    selected = roots

    if scope == "latest":
        selected = [roots[-1]] if roots else []
    elif scope == "full_pass":
        full_pass: list[tuple[str, Path, Path]] = []
        for root_name, root_dir, best_tsv in roots:
            rows = read_tsv_rows(best_tsv)
            if rows and all(parse_bool_final_ok(r) for r in rows):
                full_pass.append((root_name, root_dir, best_tsv))
        selected = full_pass

    if root_filters:
        selected = [x for x in selected if x[0] in root_filters]

    return selected


def resolve_path(path_text: str, base: Path = ROOT) -> Path:
    curr = Path(path_text)
    if curr.is_absolute():
        return curr.resolve()
    return (base / curr).resolve()


def pick_existing(paths: list[Path | None]) -> Path | None:
    for path in paths:
        if path is not None and path.exists():
            return path
    return None


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def resolve_train_root(root_text: str, train_root: Path) -> Path:
    root = Path(root_text)
    if root.is_absolute():
        return root.resolve()
    return (train_root / root).resolve()


def resolve_out_dir_rel(row: dict[str, str], root_dir: Path, case_name: str) -> str:
    out_dir_text = str(row.get("out_dir", "")).strip()
    variant = str(row.get("variant", "")).strip()
    num_envs = str(row.get("num_envs", "")).strip()
    case_stem = case_name.replace(".txt", "")

    if out_dir_text:
        out_dir = resolve_path(out_dir_text)
        try:
            rel = out_dir.relative_to(root_dir.resolve())
            return rel.as_posix()
        except Exception:
            pass

    candidates: list[str] = []
    if variant:
        candidates.append(f"runs/{case_stem}/{variant}")
        if num_envs and not variant.endswith(f"_e{num_envs}"):
            candidates.append(f"runs/{case_stem}/{variant}_e{num_envs}")
    if num_envs:
        candidates.append(f"runs/{case_stem}/default_e{num_envs}")
    candidates.append(f"runs/{case_stem}/default")

    seen: set[str] = set()
    uniq_candidates: list[str] = []
    for curr in candidates:
        if curr in seen:
            continue
        seen.add(curr)
        uniq_candidates.append(curr)

    for curr in uniq_candidates:
        if (root_dir / curr).exists():
            return curr

    return uniq_candidates[0]


def resolve_model_file(row: dict[str, str]) -> Path | None:
    candidates: list[Path] = []

    model_file = str(row.get("model_file", "")).strip()
    if model_file:
        candidates.append(resolve_path(model_file))

    for key in ("long_out_dir", "train_out_dir", "probe_out_dir"):
        curr = str(row.get(key, "")).strip()
        if curr:
            candidates.append(resolve_path(curr) / "model.pt")

    out_dir_text = str(row.get("out_dir", "")).strip()
    if out_dir_text:
        out_dir = resolve_path(out_dir_text)
        candidates.extend(
            [
                out_dir / "long_train" / "model.pt",
                out_dir / "train" / "model.pt",
                out_dir / "probe_train" / "model.pt",
            ]
        )

    return pick_existing(candidates)


def resolve_status_model(status: dict[str, Any], root_dir: Path, stage: str) -> Path | None:
    stages = status.get("stages") if isinstance(status.get("stages"), dict) else {}
    stage_meta = stages.get(stage) if isinstance(stages.get(stage), dict) else {}
    best_meta = status.get("best_scalar_checkpoint") if isinstance(status.get("best_scalar_checkpoint"), dict) else {}
    candidates = [
        str(stage_meta.get("latest_model", "")).strip(),
        str(best_meta.get("model_file", "")).strip() if str(best_meta.get("stage", "")).strip() == stage else "",
        str(root_dir / stage / "model.pt"),
    ]
    return pick_existing([resolve_path(curr) for curr in candidates if curr])


def first_existing_status_path(status: dict[str, Any], keys: list[str], root_dir: Path, stage: str, filename: str) -> Path | None:
    candidates: list[Path | None] = []
    for key in keys:
        text = str(status.get(key, "")).strip()
        if text:
            candidates.append(resolve_path(text))
    candidates.append(root_dir / stage / filename)
    return pick_existing(candidates)


def resolve_case_configs(
    row: dict[str, str],
    case_name: str,
    model_file: Path | None,
) -> tuple[Path, Path | None, Path | None, Path | None]:
    arg_file = (ROOT / "args" / normalize_case_name(case_name)).resolve()
    arg_table = parse_arg_file(arg_file)

    model_dir = model_file.parent if model_file is not None else None

    def maybe_text_to_path(key: str) -> Path | None:
        text = str(row.get(key, "")).strip()
        if not text:
            return None
        return resolve_path(text)

    def maybe_arg_to_path(key: str) -> Path | None:
        text = str(arg_table.get(key, "")).strip()
        if not text:
            return None
        return resolve_path(text)

    local_env = model_dir / "env_config.yaml" if model_dir is not None else None
    local_engine = model_dir / "engine_config.yaml" if model_dir is not None else None
    local_agent = model_dir / "agent_config.yaml" if model_dir is not None else None

    env_cfg = pick_existing([local_env, maybe_text_to_path("env_config"), maybe_arg_to_path("env_config")])
    engine_cfg = pick_existing([local_engine, maybe_text_to_path("engine_config"), maybe_arg_to_path("engine_config")])

    # Fall back to Newton only for Isaac Gym roots when isaacgym is unavailable.
    # Isaac Lab / USD cases should keep their requested engine so missing runtime
    # dependencies surface as an explicit error instead of silently switching to Newton.
    if engine_cfg is not None and "isaac_gym" in engine_cfg.name.lower():
        global _HAS_ISAACGYM
        if _HAS_ISAACGYM is None:
            _HAS_ISAACGYM = importlib.util.find_spec("isaacgym") is not None
        if not _HAS_ISAACGYM:
            newton_engine_cfg = (ROOT / "data" / "engines" / "newton_engine.yaml").resolve()
            if newton_engine_cfg.exists():
                engine_cfg = newton_engine_cfg

    agent_cfg = pick_existing([local_agent, maybe_text_to_path("agent_config"), maybe_arg_to_path("agent_config")])

    return arg_file, env_cfg, engine_cfg, agent_cfg


def detect_visual_kind(env_cfg: Path | None) -> tuple[str, str, bool]:
    if env_cfg is None or not env_cfg.exists():
        return "unknown", "", False

    try:
        env_data = yaml.safe_load(env_cfg.read_text(encoding="utf-8"))
    except Exception:
        return "unknown", "", False

    if not isinstance(env_data, dict):
        return "unknown", "", False

    char_file_text = str(env_data.get("char_file", "")).strip()
    if not char_file_text:
        return "unknown", "", False

    char_path = resolve_path(char_file_text)
    if not char_path.exists():
        alt = (env_cfg.parent / char_file_text).resolve()
        if alt.exists():
            char_path = alt
        else:
            return "unknown", str(char_path), False

    ext = char_path.suffix.lower()
    if ext == ".usd":
        return "mesh", str(char_path), True

    if ext in (".xml", ".urdf"):
        text = char_path.read_text(encoding="utf-8", errors="ignore")
        has_mesh = ('type="mesh"' in text) or ("<mesh" in text)
        return ("mesh" if has_mesh else "geom"), str(char_path), bool(has_mesh)

    return "unknown", str(char_path), False


def build_amp_root_job(args: argparse.Namespace) -> dict[str, Any]:
    train_root = Path(args.train_root).resolve()
    img_root = Path(args.img_root).resolve()
    root_dir = resolve_train_root(args.amp_root, train_root)
    status = read_json(root_dir / "keepalive_status.json")
    if not status:
        raise RuntimeError(f"missing or invalid keepalive_status.json under {root_dir}")

    stage = str(args.amp_stage or "").strip()
    if not stage:
        stage = str(status.get("current_train_stage", "") or status.get("current_stage", "")).strip()
    if not stage:
        stage = "probe_train"

    model_file = resolve_status_model(status, root_dir, stage)
    arg_file_text = str(status.get("arg_file", "")).strip()
    arg_file = resolve_path(arg_file_text) if arg_file_text else ROOT / "args" / "amp_stop_humanoid_sword_shield_args.txt"
    case_name = normalize_case_name(arg_file.name)

    env_cfg = first_existing_status_path(status, ["current_env_config"], root_dir, stage, "env_config.yaml")
    engine_cfg = first_existing_status_path(status, ["current_engine_config", "engine_config"], root_dir, stage, "engine_config.yaml")
    agent_cfg = first_existing_status_path(status, ["current_agent_config"], root_dir, stage, "agent_config.yaml")

    if model_file is None or not model_file.exists():
        raise RuntimeError(f"missing model for {root_dir.name}/{stage}")
    if env_cfg is None or not env_cfg.exists():
        raise RuntimeError(f"missing env_config.yaml for {root_dir.name}/{stage}")
    if engine_cfg is None or not engine_cfg.exists():
        raise RuntimeError(f"missing engine_config.yaml for {root_dir.name}/{stage}")
    if agent_cfg is None or not agent_cfg.exists():
        raise RuntimeError(f"missing agent_config.yaml for {root_dir.name}/{stage}")

    visual_kind, char_file, mesh_detected = detect_visual_kind(env_cfg)
    render_dir = (img_root / root_dir.name / stage / "render").resolve()
    case_key = str(status.get("case_key", "")).strip() or case_name.replace("_args.txt", "")

    return {
        "root": root_dir.name,
        "case": case_name,
        "variant": stage,
        "case_type": "trainable",
        "case_kind": "policy",
        "visual_kind": visual_kind,
        "char_file": char_file,
        "mesh_detected": int(mesh_detected),
        "arg_file": str(arg_file.resolve()) if arg_file.exists() else str(arg_file),
        "model_file": str(model_file.resolve()),
        "env_config": str(env_cfg.resolve()),
        "engine_config": str(engine_cfg.resolve()),
        "agent_config": str(agent_cfg.resolve()),
        "llc_model_file": "",
        "motion_id": "",
        "motion_file": "",
        "source_pack": root_dir.name,
        "category": case_key,
        "train_enabled": "true",
        "view_enabled": "true",
        "out_dir": str((root_dir / stage).resolve()),
        "out_dir_rel": stage,
        "render_dir": str(render_dir),
    }


class DeterministicPolicyWrapper(torch.nn.Module):
    """raw_obs -> obs_norm -> actor(mode) -> action_unnorm"""

    def __init__(self, agent):
        super().__init__()
        self.obs_norm = agent._obs_norm
        self.action_norm = agent._a_norm
        self.model = agent._model

        signature = inspect.signature(self.model.eval_actor)
        self._eval_actor_arity = len(signature.parameters)

        if self._eval_actor_arity > 1:
            if hasattr(agent, "_latent_buf") and torch.is_tensor(agent._latent_buf) and agent._latent_buf.numel() > 0:
                z0 = agent._latent_buf[0:1].detach().clone().to(dtype=torch.float32)
            elif hasattr(self.model, "get_latent_dim"):
                z_dim = int(self.model.get_latent_dim())
                z0 = torch.zeros((1, z_dim), dtype=torch.float32)
            else:
                raise RuntimeError("actor requires latent input but latent dimension is unavailable")
            self.register_buffer("_latent_seed", z0)
        else:
            self.register_buffer("_latent_seed", torch.zeros((1, 0), dtype=torch.float32))

    def _deterministic_action(self, norm_obs: torch.Tensor) -> torch.Tensor:
        if self._eval_actor_arity > 1:
            z = self._latent_seed.expand(norm_obs.shape[0], -1)
            dist = self.model.eval_actor(norm_obs, z)
        else:
            dist = self.model.eval_actor(norm_obs)

        if hasattr(dist, "mode"):
            return dist.mode
        if hasattr(dist, "sample"):
            return dist.sample()
        raise RuntimeError(f"unsupported actor distribution output: {type(dist)}")

    def forward(self, obs: torch.Tensor) -> torch.Tensor:
        norm_obs = self.obs_norm.normalize(obs)
        norm_action = self._deterministic_action(norm_obs)
        return self.action_norm.unnormalize(norm_action)


def build_action_fn(case_kind: str, agent, action_space, device: str):
    if case_kind == "policy":
        wrapper = DeterministicPolicyWrapper(agent).to(device=device)
        wrapper.eval()

        low_tensor = None
        high_tensor = None
        if isinstance(action_space, spaces.Box):
            low_tensor = torch.from_numpy(np.asarray(action_space.low, dtype=np.float32).reshape(1, -1)).to(device=device)
            high_tensor = torch.from_numpy(np.asarray(action_space.high, dtype=np.float32).reshape(1, -1)).to(device=device)

        def policy_action(obs: torch.Tensor) -> torch.Tensor:
            act = wrapper(obs)
            if low_tensor is not None and high_tensor is not None:
                act = torch.maximum(act, low_tensor)
                act = torch.minimum(act, high_tensor)
            return act

        return policy_action

    if isinstance(action_space, spaces.Box):
        act_dim = int(np.prod(action_space.shape))
        a_dtype = torch.from_numpy(np.asarray(action_space.low, dtype=np.float32)).dtype
        low_tensor = torch.from_numpy(np.asarray(action_space.low, dtype=np.float32).reshape(1, -1)).to(device=device)
        high_tensor = torch.from_numpy(np.asarray(action_space.high, dtype=np.float32).reshape(1, -1)).to(device=device)

        def dummy_box_action(obs: torch.Tensor) -> torch.Tensor:
            n = int(obs.shape[0])
            act = torch.zeros((n, act_dim), device=device, dtype=a_dtype)
            act = torch.maximum(act, low_tensor)
            act = torch.minimum(act, high_tensor)
            return act

        return dummy_box_action

    if isinstance(action_space, spaces.Discrete):
        a_dtype = torch.float32

        def dummy_discrete_action(obs: torch.Tensor) -> torch.Tensor:
            n = int(obs.shape[0])
            return torch.zeros((n, 0), device=device, dtype=a_dtype)

        return dummy_discrete_action

    raise TypeError(f"unsupported action space: {type(action_space)}")


def write_tsv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def maybe_patch_pyglet_msaa_config() -> None:
    """Force non-MSAA fallback on stacks where MSAA context bootstrap fails."""
    try:
        import pyglet  # noqa: PLC0415
    except Exception:
        return

    try:
        gl_mod = pyglet.gl
        window_mod = pyglet.window
    except Exception:
        return

    try:
        config_ctor = getattr(gl_mod, "Config", None)
    except Exception:
        return
    if config_ctor is None:
        return
    if getattr(config_ctor, "_mimickit_msaa_patch", False):
        return

    no_such_cfg = window_mod.NoSuchConfigException
    orig_config_ctor = config_ctor

    def patched_config_ctor(*args, **kwargs):
        if int(kwargs.get("sample_buffers", 0) or 0) > 0:
            raise no_such_cfg("MimicKit render sequence: force non-MSAA fallback")
        return orig_config_ctor(*args, **kwargs)

    patched_config_ctor._mimickit_msaa_patch = True
    gl_mod.Config = patched_config_ctor


def maybe_reexec_with_xvfb(args: argparse.Namespace) -> int | None:
    if args.dry_run:
        return None

    if str(os.environ.get("MIMICKIT_SKIP_XVFB", "")).strip().lower() in ("1", "true", "yes", "on"):
        return None

    if os.environ.get("DISPLAY"):
        return None

    xvfb = shutil.which("xvfb-run")
    if not xvfb:
        raise RuntimeError("DISPLAY is not set and xvfb-run was not found in PATH")

    if os.environ.get("_MIMICKIT_XVFB_WRAPPED", "") == "1":
        raise RuntimeError("DISPLAY is still missing inside xvfb-run wrapper")

    cmd = [xvfb, "-a", "-s", "screen 0 1280x720x24", sys.executable, *sys.argv]
    env = dict(os.environ)
    env["_MIMICKIT_XVFB_WRAPPED"] = "1"
    print("[INFO] DISPLAY not found, re-exec via xvfb-run")
    print("[CMD] " + " ".join(cmd))
    return subprocess.call(cmd, env=env, cwd=str(ROOT))


def expected_image_count(frames: int, stride: int) -> int:
    return len(range(0, max(0, int(frames)), max(1, int(stride))))


def count_frame_images(frames_dir: Path) -> int:
    if not frames_dir.exists():
        return 0
    return len(list(frames_dir.glob("frame_*.png")))


def should_retry_render_error(error_text: str) -> bool:
    text = str(error_text)
    return ("GLException" in text) or ("Invalid operation" in text)


def build_render_mp4(render_dir: Path, fps: int) -> tuple[bool, str]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return False, "ffmpeg not found"

    frames_dir = render_dir / "frames"
    mp4_path = render_dir / "render.mp4"
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
        str(frames_dir / "frame_*.png"),
        "-pix_fmt",
        "yuv420p",
        str(mp4_path),
    ]
    proc = subprocess.run(cmd, cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)
    if proc.returncode != 0:
        return False, proc.stdout.strip()
    return mp4_path.exists(), ""


def run_job(job: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    render_dir = Path(job["render_dir"])
    frames_dir = render_dir / "frames"
    silhouette_dir = render_dir / "silhouettes"
    meta_path = render_dir / "render_meta.json"
    expected = expected_image_count(args.frames, args.frame_stride)

    row = dict(job)
    row.update(
        {
            "frames": int(args.frames),
            "frame_stride": int(args.frame_stride),
            "expected_image_count": int(expected),
            "image_count": 0,
            "resumed": 0,
            "dry_run": int(args.dry_run),
            "status": "pending",
            "width": int(args.width),
            "height": int(args.height),
            "motion_visible": 0,
            "error": "",
            "render_meta": str(meta_path),
        }
    )

    if args.resume and (not args.force) and meta_path.exists():
        try:
            old = json.loads(meta_path.read_text(encoding="utf-8"))
            existing_images = count_frame_images(frames_dir)
            if (
                str(old.get("status", "")) == "ok"
                and int(old.get("image_count", 0)) >= expected
                and existing_images >= expected
                and int(old.get("frames", -1)) == int(args.frames)
                and int(old.get("frame_stride", -1)) == int(args.frame_stride)
            ):
                row["status"] = "skipped_resume"
                row["resumed"] = 1
                row["image_count"] = int(existing_images)
                row["mp4_file"] = str(render_dir / "render.mp4")
                row["mp4_ok"] = int((render_dir / "render.mp4").exists())
                row["mp4_error"] = ""
                return row
        except Exception:
            pass

    if args.dry_run:
        row["status"] = "dry_run"
        return row

    render_dir.mkdir(parents=True, exist_ok=True)
    if frames_dir.exists():
        shutil.rmtree(frames_dir)
    frames_dir.mkdir(parents=True, exist_ok=True)
    if silhouette_dir.exists():
        shutil.rmtree(silhouette_dir)
    silhouette_dir.mkdir(parents=True, exist_ok=True)

    random.seed(int(args.seed))
    np.random.seed(int(args.seed))
    torch.manual_seed(int(args.seed))
    os.environ.setdefault("MIMICKIT_VIEWER_HEADLESS", "1")
    maybe_patch_pyglet_msaa_config()

    overrides = SimpleNamespace(
        env_config=str(job["env_config"]) if job["env_config"] else "",
        engine_config=str(job["engine_config"]) if job["engine_config"] else "",
        agent_config=str(job["agent_config"]) if job["agent_config"] else "",
        model_file=str(job["model_file"]) if (job["model_file"] and job["case_kind"] == "policy") else "",
        llc_model_file=str(job["llc_model_file"]) if job.get("llc_model_file") else "",
        num_envs=int(args.num_envs),
    )

    max_attempts = 2
    attempt = 0
    while attempt < max_attempts:
        attempt += 1
        ctx = None
        try:
            if frames_dir.exists():
                shutil.rmtree(frames_dir)
            frames_dir.mkdir(parents=True, exist_ok=True)

            if job["case_kind"] == "policy" and not job["model_file"]:
                raise RuntimeError("missing model file for policy case")
            if not job["arg_file"] or not Path(job["arg_file"]).exists():
                raise RuntimeError("arg_file not found")
            if not job["env_config"] or not Path(job["env_config"]).exists():
                raise RuntimeError("env_config not found")
            if not job["engine_config"] or not Path(job["engine_config"]).exists():
                raise RuntimeError("engine_config not found")

            ctx = build_runtime_context(
                arg_file=str(job["arg_file"]),
                overrides=overrides,
                device=args.device,
                visualize=True,
                load_model=(job["case_kind"] == "policy"),
            )

            action_space = ctx.env.get_action_space()
            action_fn = build_action_fn(job["case_kind"], ctx.agent, action_space, args.device)

            agent_loop = bool(job["case_kind"] == "policy" and hasattr(ctx.agent, "_decide_action") and hasattr(ctx.agent, "_step_env"))
            if agent_loop:
                ctx.agent.eval()
                ctx.agent.set_mode(base_agent.AgentMode.TEST)
                obs, info = ctx.agent._reset_envs(None)
            else:
                obs, info = ctx.env.reset(None)

            captures: list[dict[str, Any]] = []
            image_count = 0
            frame_hashes: list[str] = []

            with torch.no_grad():
                for frame_idx in range(int(args.frames)):
                    if agent_loop:
                        action, _action_info = ctx.agent._decide_action(obs, info)
                        _next_obs, _reward, done, _next_info = ctx.agent._step_env(action)
                    else:
                        action = action_fn(obs)
                        _next_obs, _reward, done, _next_info = ctx.env.step(action)

                    if frame_idx % int(args.frame_stride) == 0:
                        capture = ctx.env._engine.capture_frame(
                            int(args.width),
                            int(args.height),
                            include_silhouette=True,
                        )
                        frame_path = frames_dir / f"frame_{frame_idx:06d}.png"
                        silhouette_path = silhouette_dir / f"frame_{frame_idx:06d}.png"
                        from PIL import Image

                        rgba = np.asarray(capture.rgba)
                        if rgba.dtype != np.uint8:
                            rgba = np.clip(rgba * (255.0 if float(np.max(rgba)) <= 1.0 else 1.0), 0, 255).astype(np.uint8)
                        Image.fromarray(rgba).save(frame_path)
                        if capture.silhouette is not None:
                            Image.fromarray(np.asarray(capture.silhouette).astype(np.uint8), mode="L").save(silhouette_path)
                        frame_report = inspect_png(frame_path, int(args.width), int(args.height))
                        if not frame_report.get("ok"):
                            raise RuntimeError(f"captured PNG failed validation: {frame_report}")
                        frame_hashes.append(sha256_file(frame_path))
                        captures.append(
                            {
                                "frame": int(frame_idx),
                                "file": frame_path.name,
                                "silhouette_file": silhouette_path.name if silhouette_path.exists() else "",
                                "sha256": frame_hashes[-1],
                                "camera_eye": capture.camera_eye,
                                "camera_target": capture.camera_target,
                                "fov_degrees": capture.fov_degrees,
                            }
                        )
                        image_count += 1

                    if agent_loop:
                        obs, info = ctx.agent._reset_done_envs(done)
                    else:
                        done_ids = torch.nonzero(done != 0, as_tuple=False).flatten() if torch.is_tensor(done) else torch.tensor([], dtype=torch.long)
                        if int(done_ids.numel()) > 0:
                            _next_obs, _reset_info = ctx.env.reset(done_ids)
                        obs = _next_obs

            index_path = frames_dir / "index.json"
            write_json(
                index_path,
                {
                    "frames": int(args.frames),
                    "frame_stride": int(args.frame_stride),
                    "expected_image_count": int(expected),
                    "image_count": int(image_count),
                    "captures": captures,
                },
            )
            scene_contract = build_scene_contract_v2(
                root_name=str(job["root"]),
                case=str(job["case"]),
                motion_id=str(job.get("motion_id", "")),
                width=int(args.width),
                height=int(args.height),
                frames=int(args.frames),
                frame_stride=int(args.frame_stride),
                fps=int(args.mp4_fps),
                seed=int(args.seed),
                renderer=str(ctx.env._engine.get_name()),
                camera_samples=[
                    {
                        "frame": item["frame"],
                        "eye": item["camera_eye"],
                        "target": item["camera_target"],
                        "fov_degrees": item["fov_degrees"],
                    }
                    for item in captures
                ],
            )
            scene_contract_path = render_dir / "scene_contract_v2.json"
            write_json(scene_contract_path, scene_contract)

            row["image_count"] = int(image_count)
            row["resumed"] = 0
            row["error"] = ""
            row["frame_ids"] = [item["frame"] for item in captures]
            row["motion_visible"] = int(len(set(frame_hashes)) > 1)
            row["scene_contract_file"] = str(scene_contract_path)
            row["scene_contract_sha256"] = scene_contract["scene_contract_sha256"]
            mp4_ok, mp4_error = build_render_mp4(render_dir, int(args.mp4_fps))
            row["mp4_file"] = str(render_dir / "render.mp4")
            mp4_probe = inspect_mp4(render_dir / "render.mp4", int(args.mp4_fps), int(expected))
            row["mp4_probe"] = mp4_probe
            row["mp4_ok"] = int(mp4_ok and bool(mp4_probe.get("ok")))
            row["mp4_error"] = mp4_error or str(mp4_probe.get("blocker", ""))
            row["status"] = "ok" if (
                image_count == expected
                and bool(row["mp4_ok"])
                and bool(row["motion_visible"])
            ) else "error"
            if row["status"] != "ok":
                row["error"] = "render_media_validation_failed"
            break

        except BaseException as err:
            if isinstance(err, (KeyboardInterrupt, SystemExit)):
                raise

            err_text = f"{type(err).__name__}: {err}"
            row["status"] = "error"
            row["error"] = err_text
            trace_path = render_dir / ("render_error.log" if attempt == max_attempts else f"render_error_attempt_{attempt}.log")
            trace_path.write_text(traceback.format_exc(), encoding="utf-8")

            if attempt >= max_attempts or not should_retry_render_error(err_text):
                break

            print(f"[WARN] retrying render job after viewer error attempt={attempt} case={job['case']} variant={job['variant']}")

        finally:
            ctx = None
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

    meta_path.write_text(json.dumps(row, ensure_ascii=False, indent=2), encoding="utf-8")

    return row


def build_jobs(args: argparse.Namespace) -> list[dict[str, Any]]:
    train_root = Path(args.train_root).resolve()
    img_root = Path(args.img_root).resolve()
    root_filters = {Path(x).name for x in parse_csv_list(args.roots)}
    case_filters = {normalize_case_name(x) for x in parse_csv_list(args.cases)}

    if str(args.amp_root or "").strip():
        return [build_amp_root_job(args)]

    roots = parse_roots(train_root)
    selected_roots = select_roots(roots, args.root_scope, root_filters)

    jobs: list[dict[str, Any]] = []
    for root_name, root_dir, best_tsv in selected_roots:
        rows = read_tsv_rows(best_tsv)
        for row in rows:
            if not parse_bool_final_ok(row):
                continue

            case_name = normalize_case_name(str(row.get("case", "")).strip())
            if not case_name:
                continue
            if case_filters and case_name not in case_filters:
                continue

            out_dir_rel = resolve_out_dir_rel(row, root_dir, case_name)
            render_dir = (img_root / root_name / out_dir_rel / "render").resolve()
            model_file = resolve_model_file(row)
            arg_file, env_cfg, engine_cfg, agent_cfg = resolve_case_configs(row, case_name, model_file)

            has_agent_cfg = agent_cfg is not None and agent_cfg.exists()
            has_model = model_file is not None and model_file.exists()
            case_kind = "policy" if (has_agent_cfg and has_model) else "dummy"
            case_type = str(row.get("case_type", "")).strip() or ("trainable" if case_kind == "policy" else "nontrainable")
            variant = str(row.get("variant", "")).strip()
            if not variant:
                variant = Path(out_dir_rel).name

            visual_kind, char_file, mesh_detected = detect_visual_kind(env_cfg)

            jobs.append(
                {
                    "root": root_name,
                    "case": case_name,
                    "variant": variant,
                    "case_type": case_type,
                    "case_kind": case_kind,
                    "visual_kind": visual_kind,
                    "char_file": char_file,
                    "mesh_detected": int(mesh_detected),
                    "arg_file": str(arg_file.resolve()) if arg_file.exists() else str(arg_file),
                    "model_file": str(model_file.resolve()) if model_file is not None else "",
                    "env_config": str(env_cfg.resolve()) if env_cfg is not None else "",
                    "engine_config": str(engine_cfg.resolve()) if engine_cfg is not None else "",
                    "agent_config": str(agent_cfg.resolve()) if agent_cfg is not None else "",
                    "llc_model_file": str(row.get("llc_model_file", "")).strip(),
                    "motion_id": str(row.get("motion_id", "")).strip(),
                    "motion_file": str(row.get("motion_file", "")).strip(),
                    "source_pack": str(row.get("source_pack", "")).strip(),
                    "category": str(row.get("category", "")).strip(),
                    "train_enabled": str(row.get("train_enabled", "")).strip(),
                    "view_enabled": str(row.get("view_enabled", "")).strip(),
                    "out_dir": str(row.get("out_dir", "")).strip(),
                    "out_dir_rel": out_dir_rel,
                    "render_dir": str(render_dir),
                }
            )

    jobs.sort(key=lambda x: (x["root"], x["case"], x["variant"]))
    if args.max_cases > 0:
        jobs = jobs[: int(args.max_cases)]
    return jobs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build MimicKit render frame sequences from final_ok cases")
    parser.add_argument("--train-root", default=str(DEFAULT_TRAIN_ROOT))
    parser.add_argument("--img-root", default=str(DEFAULT_IMG_ROOT))
    parser.add_argument("--root-scope", choices=["all", "latest", "full_pass"], default="all")
    parser.add_argument("--amp-root", default="", help="Explicit AMP root under output/train or absolute path; bypasses best_by_case.tsv discovery")
    parser.add_argument("--amp-stage", default="", help="Stage under --amp-root to render, default current_train_stage/current_stage")
    parser.add_argument("--frames", type=int, default=300)
    parser.add_argument("--frame-stride", type=int, default=5)
    parser.add_argument("--mp4-fps", type=int, default=12)
    parser.add_argument("--width", type=int, default=960)
    parser.add_argument("--height", type=int, default=540)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--num-envs", type=int, default=1)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--resume", dest="resume", action="store_true", default=True)
    parser.add_argument("--no-resume", dest="resume", action="store_false")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--roots", default="")
    parser.add_argument("--cases", default="")
    parser.add_argument("--max-cases", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.frames <= 0:
        parser.error("--frames must be > 0")
    if args.frame_stride <= 0:
        parser.error("--frame-stride must be > 0")
    if args.num_envs <= 0:
        parser.error("--num-envs must be > 0")
    if args.mp4_fps <= 0:
        parser.error("--mp4-fps must be > 0")
    if args.width <= 0 or args.height <= 0:
        parser.error("--width/--height must be > 0")
    return args


def main() -> int:
    args = parse_args()

    xvfb_rc = maybe_reexec_with_xvfb(args)
    if xvfb_rc is not None:
        return int(xvfb_rc)

    jobs = build_jobs(args)
    print(f"[INFO] jobs_selected={len(jobs)} root_scope={args.root_scope} dry_run={int(args.dry_run)}")

    rows: list[dict[str, Any]] = []
    img_root = Path(args.img_root).resolve()
    img_root.mkdir(parents=True, exist_ok=True)

    for i, job in enumerate(jobs, 1):
        print(f"[CASE {i}/{len(jobs)}] {job['root']} :: {job['case']} :: {job['variant']}")
        row = run_job(job, args)
        rows.append(row)
        print(f"  [RESULT] status={row['status']} visual_kind={row['visual_kind']} image_count={row.get('image_count', 0)}")

    rows_by_root: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        rows_by_root.setdefault(str(row["root"]), []).append(row)

    for root_name, root_rows in rows_by_root.items():
        root_index = (img_root / root_name / "infer_viz_index.tsv").resolve()
        write_tsv(root_index, root_rows, INDEX_FIELDS)
        print(f"[INDEX] {root_index} rows={len(root_rows)}")

    global_index = (img_root / "render_all_roots.tsv").resolve()
    write_tsv(global_index, rows, INDEX_FIELDS)
    print(f"[INDEX] {global_index} rows={len(rows)}")

    ok = sum(1 for row in rows if row.get("status") in ("ok", "skipped_resume", "dry_run"))
    total = len(rows)
    print(f"[DONE] ok={ok}/{total}")
    return 0 if ok == total else 2


if __name__ == "__main__":
    raise SystemExit(main())
