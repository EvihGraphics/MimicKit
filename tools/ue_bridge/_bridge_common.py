#!/usr/bin/env python3
"""Shared helpers for MimicKit <-> UE bridge tooling."""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import torch


SCRIPT_DIR = Path(__file__).resolve().parent
TOOLS_DIR = SCRIPT_DIR.parent
REPO_ROOT = TOOLS_DIR.parent
MIMICKIT_ROOT = REPO_ROOT / "mimickit"


if str(MIMICKIT_ROOT) not in sys.path:
    sys.path.insert(0, str(MIMICKIT_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from util.arg_parser import ArgParser  # noqa: E402
import util.mp_util as mp_util  # noqa: E402
import envs.env_builder as env_builder  # noqa: E402
import learning.agent_builder as agent_builder  # noqa: E402


DEFAULT_MASTER_PORT = 6071


@dataclass
class RuntimeContext:
    args: ArgParser
    env: Any
    agent: Any
    env_config: Dict[str, Any]
    engine_config: Dict[str, Any]
    agent_config: Dict[str, Any]
    device: str
    arg_file: Path



def _resolve_path(path: str) -> Path:
    raw = Path(path)
    if raw.is_absolute():
        return raw
    return (REPO_ROOT / raw).resolve()



def _maybe_override_arg(parser: ArgParser, key: str, value: Optional[str]) -> None:
    if value is None:
        return
    if value == "":
        return
    parser._table[key] = [value]



def load_runtime_args(arg_file: str, overrides: argparse.Namespace) -> ArgParser:
    parser = ArgParser()

    arg_file_path = _resolve_path(arg_file)
    if not arg_file_path.exists():
        raise FileNotFoundError(f"arg_file does not exist: {arg_file_path}")

    ok = parser.load_file(str(arg_file_path))
    if not ok:
        raise RuntimeError(f"failed to parse arg_file: {arg_file_path}")

    _maybe_override_arg(parser, "env_config", getattr(overrides, "env_config", None))
    _maybe_override_arg(parser, "engine_config", getattr(overrides, "engine_config", None))
    _maybe_override_arg(parser, "agent_config", getattr(overrides, "agent_config", None))
    _maybe_override_arg(parser, "model_file", getattr(overrides, "model_file", None))
    _maybe_override_arg(parser, "llc_model_file", getattr(overrides, "llc_model_file", None))

    if getattr(overrides, "num_envs", None) is not None:
        _maybe_override_arg(parser, "num_envs", str(int(overrides.num_envs)))

    # Match mimickit/run.py so agents that read the global parser
    # (for example ASEHRL LLC checkpoint wiring) can resolve runtime overrides.
    ArgParser.global_parser = parser
    return parser



def init_single_process_mp(device: str, master_port: int = DEFAULT_MASTER_PORT) -> None:
    if mp_util.get_num_procs() > 0:
        return
    mp_util.init(rank=0, num_procs=1, device=device, master_port=master_port)



def load_configs_from_args(args: ArgParser) -> tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    env_cfg_path = _resolve_path(args.parse_string("env_config"))
    eng_cfg_path = _resolve_path(args.parse_string("engine_config"))
    agent_cfg_raw = args.parse_string("agent_config", "")

    env_cfg, eng_cfg = env_builder.load_configs(str(env_cfg_path), str(eng_cfg_path))

    if agent_cfg_raw:
        agent_cfg_path = _resolve_path(agent_cfg_raw)
        agent_cfg = env_builder.load_config(str(agent_cfg_path))
    else:
        agent_cfg = {}

    return env_cfg or {}, eng_cfg or {}, agent_cfg or {}



def resolve_runtime_device(requested_device: str, engine_config: Dict[str, Any]) -> str:
    device = (requested_device or "").strip() or "cpu"
    if device != "cpu":
        return device

    engine_name = str((engine_config or {}).get("engine_name", "")).strip().lower()
    if engine_name == "newton" and torch.cuda.is_available():
        return "cuda:0"

    return device



def build_runtime_context(
    arg_file: str,
    overrides: argparse.Namespace,
    device: str,
    visualize: bool = False,
    load_model: bool = False,
) -> RuntimeContext:
    args = load_runtime_args(arg_file=arg_file, overrides=overrides)
    env_cfg, eng_cfg, agent_cfg = load_configs_from_args(args)
    runtime_device = resolve_runtime_device(device, eng_cfg)
    init_single_process_mp(device=runtime_device)

    num_envs = int(args.parse_int("num_envs", 1))
    env_file = _resolve_path(args.parse_string("env_config"))
    engine_file = _resolve_path(args.parse_string("engine_config"))
    agent_file_raw = args.parse_string("agent_config", "")
    agent_file = _resolve_path(agent_file_raw) if agent_file_raw else ""

    env = env_builder.build_env(str(env_file), str(engine_file), num_envs=num_envs, device=runtime_device, visualize=visualize)
    agent = agent_builder.build_agent(str(agent_file) if agent_file else "", env=env, device=runtime_device)

    model_file = args.parse_string("model_file", "")
    if load_model and model_file:
        model_path = _resolve_path(model_file)
        if not model_path.exists():
            raise FileNotFoundError(f"model_file does not exist: {model_path}")
        agent.load(str(model_path))

    return RuntimeContext(
        args=args,
        env=env,
        agent=agent,
        env_config=env_cfg,
        engine_config=eng_cfg,
        agent_config=agent_cfg,
        device=runtime_device,
        arg_file=_resolve_path(arg_file),
    )



def choose_export_dir(out_dir: str, model_file: str, default_leaf: str = "ue_export") -> Path:
    if out_dir:
        path = _resolve_path(out_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    if model_file:
        model_path = _resolve_path(model_file)
        parent = model_path.parent
        target = parent / default_leaf
        target.mkdir(parents=True, exist_ok=True)
        return target

    target = (REPO_ROOT / "output" / "train" / default_leaf).resolve()
    target.mkdir(parents=True, exist_ok=True)
    return target



def save_json(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fp:
        json.dump(obj, fp, ensure_ascii=False, indent=2)



def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)



def to_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    if torch.is_tensor(value):
        return value.detach().cpu().tolist()
    if isinstance(value, np.ndarray):
        return value.tolist()
    return [value]

