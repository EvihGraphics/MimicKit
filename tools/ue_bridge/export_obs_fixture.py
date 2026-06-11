#!/usr/bin/env python3
"""Export UE-facing observation fixture and reference actions from MimicKit model."""

from __future__ import annotations

import argparse
import inspect
import json
from pathlib import Path

import numpy as np
import torch
import gymnasium.spaces as spaces

from _bridge_common import build_runtime_context, choose_export_dir, save_json


class ActorPolicyExportWrapper(torch.nn.Module):
    """raw_obs -> obs_norm -> model.eval_actor(mode) -> action_unnorm"""

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


def _to_numpy_row(tensor: torch.Tensor) -> np.ndarray:
    return tensor.detach().cpu().numpy().reshape(-1).astype(np.float32, copy=False)


def _try_get_char_tensor_row(env, getter_name: str) -> np.ndarray | None:
    try:
        if not hasattr(env, "_get_char_id"):
            return None
        char_id = env._get_char_id()
        getter = getattr(env._engine, getter_name, None)
        if getter is None:
            return None
        value = getter(char_id)
        if not torch.is_tensor(value):
            return None
        if value.ndim < 2 or value.shape[0] <= 0:
            return None
        return _to_numpy_row(value[0:1])
    except Exception:
        return None


def _try_get_kinematic_body_world_from_env(env) -> tuple[np.ndarray | None, np.ndarray | None]:
    try:
        char_id = env._get_char_id()
        root_pos = env._engine.get_root_pos(char_id)
        root_rot = env._engine.get_root_rot(char_id)
        dof_pos = env._engine.get_dof_pos(char_id)
        joint_rot = env._kin_char_model.dof_to_rot(dof_pos)
        body_pos, body_rot = env._kin_char_model.forward_kinematics(root_pos, root_rot, joint_rot)
        return _to_numpy_row(body_pos[0:1]), _to_numpy_row(body_rot[0:1])
    except Exception:
        return None, None


def _try_get_dof_pos_from_env(env) -> np.ndarray | None:
    """Extract current character DoF position for visual replay."""
    return _try_get_char_tensor_row(env, "get_dof_pos")


def _try_get_root_pose_from_env(env) -> tuple[np.ndarray | None, np.ndarray | None]:
    """Extract current root position/rotation for UE world-space playback alignment."""
    return _try_get_char_tensor_row(env, "get_root_pos"), _try_get_char_tensor_row(env, "get_root_rot")


def _try_get_visual_replay_state_from_env(env) -> dict[str, np.ndarray]:
    state: dict[str, np.ndarray] = {}
    getters = {
        "root_pos_m": "get_root_pos",
        "root_rot_xyzw": "get_root_rot",
        "root_vel_mps": "get_root_vel",
        "root_ang_vel_radps": "get_root_ang_vel",
        "dof_pos": "get_dof_pos",
        "dof_vel": "get_dof_vel",
        "body_pos_m": "get_body_pos",
        "body_rot_xyzw": "get_body_rot",
    }
    for field, getter_name in getters.items():
        value = _try_get_char_tensor_row(env, getter_name)
        if value is not None and value.size > 0:
            state[field] = value
    body_pos, body_rot = _try_get_kinematic_body_world_from_env(env)
    if body_pos is not None and body_rot is not None:
        state["engine_body_pos_m"] = state.get("body_pos_m", np.asarray([], dtype=np.float32))
        state["engine_body_rot_xyzw"] = state.get("body_rot_xyzw", np.asarray([], dtype=np.float32))
        state["body_pos_m"] = body_pos
        state["body_rot_xyzw"] = body_rot
    return state


def _np_list(value: np.ndarray) -> list[float]:
    return [float(x) for x in value.tolist()]


def _engine_hz(ctx, key: str, fallback: int = 0) -> int:
    try:
        return int((ctx.engine_config or {}).get(key))
    except Exception:
        return fallback



def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fp:
        for row in rows:
            fp.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Export MimicKit obs fixture + reference actions for UE parity")
    parser.add_argument("--arg-file", required=True)
    parser.add_argument("--model-file", required=True)
    parser.add_argument("--env-config", default="", help="Override env config path")
    parser.add_argument("--engine-config", default="", help="Override engine config path")
    parser.add_argument("--agent-config", default="", help="Override agent config path")
    parser.add_argument("--out-dir", default="", help="Output directory")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--num-envs", type=int, default=1)
    parser.add_argument("--frames", type=int, default=300)
    parser.add_argument("--seed", type=int, default=7)

    args = parser.parse_args()

    if args.frames <= 0:
        raise ValueError("--frames must be > 0")

    np.random.seed(int(args.seed))
    torch.manual_seed(int(args.seed))

    ctx = build_runtime_context(
        arg_file=args.arg_file,
        overrides=args,
        device=args.device,
        visualize=False,
        load_model=True,
    )

    wrapper = ActorPolicyExportWrapper(ctx.agent)
    wrapper.eval()

    action_low_tensor = None
    action_high_tensor = None
    action_space = ctx.env.get_action_space()
    if isinstance(action_space, spaces.Box):
        action_low_tensor = torch.from_numpy(np.asarray(action_space.low, dtype=np.float32).reshape(1, -1))
        action_high_tensor = torch.from_numpy(np.asarray(action_space.high, dtype=np.float32).reshape(1, -1))

    obs, info = ctx.env.reset(None)
    if obs.ndim != 2:
        raise RuntimeError(f"unexpected obs rank: {obs.shape}")

    obs_rows: list[dict] = []
    action_rows: list[dict] = []
    visual_replay_rows: list[dict] = []

    episode_index = 0
    policy_dt = float(ctx.env._engine.get_timestep())
    policy_hz = int(round(1.0 / policy_dt)) if policy_dt > 0 else _engine_hz(ctx, "control_freq")
    physics_hz = _engine_hz(ctx, "sim_freq")

    with torch.no_grad():
        for frame_index in range(int(args.frames)):
            curr_obs = obs[0:1]
            action = wrapper(curr_obs)
            if action_low_tensor is not None and action_high_tensor is not None:
                action = torch.maximum(action, action_low_tensor.to(device=action.device, dtype=action.dtype))
                action = torch.minimum(action, action_high_tensor.to(device=action.device, dtype=action.dtype))

            obs_np = _to_numpy_row(curr_obs)
            act_np = _to_numpy_row(action)
            visual_state = _try_get_visual_replay_state_from_env(ctx.env)

            obs_rows.append(
                {
                    "frame": frame_index,
                    "episode": episode_index,
                    "obs": _np_list(obs_np),
                }
            )

            dof_pos_np = visual_state.get("dof_pos")
            if dof_pos_np is not None and dof_pos_np.size > 0:
                obs_rows[-1]["dof_pos"] = _np_list(dof_pos_np)
                # Legacy alias kept for existing AI4/UE parity consumers.
                obs_rows[-1]["ref_action"] = _np_list(dof_pos_np)

            root_pos_np, root_rot_np = _try_get_root_pose_from_env(ctx.env)
            if root_pos_np is not None and root_pos_np.size > 0:
                obs_rows[-1]["ref_root_pos"] = _np_list(root_pos_np)
            if root_rot_np is not None and root_rot_np.size > 0:
                obs_rows[-1]["ref_root_rot"] = _np_list(root_rot_np)

            action_rows.append(
                {
                    "frame": frame_index,
                    "episode": episode_index,
                    "action": _np_list(act_np),
                }
            )

            visual_row = {
                "frame": frame_index,
                "episode": episode_index,
                "time_seconds": float(frame_index * policy_dt),
                "policy_action": _np_list(act_np),
            }
            for field, value in visual_state.items():
                visual_row[field] = _np_list(value)
            visual_replay_rows.append(visual_row)

            next_obs, reward, done, next_info = ctx.env.step(action)
            obs = next_obs
            info = next_info

            if done.shape[0] > 0 and bool(done[0].item()):
                episode_index += 1
                obs, info = ctx.env.reset(None)

    obs_dim = len(obs_rows[0]["obs"]) if obs_rows else 0
    act_dim = len(action_rows[0]["action"]) if action_rows else 0
    ref_action_dim = 0
    dof_pos_dim = 0
    dof_vel_dim = 0
    ref_root_pos_dim = 0
    ref_root_rot_dim = 0
    root_vel_dim = 0
    root_ang_vel_dim = 0
    if obs_rows and isinstance(obs_rows[0].get("ref_action", None), list):
        ref_action_dim = len(obs_rows[0]["ref_action"])
    if visual_replay_rows and isinstance(visual_replay_rows[0].get("dof_pos", None), list):
        dof_pos_dim = len(visual_replay_rows[0]["dof_pos"])
    if visual_replay_rows and isinstance(visual_replay_rows[0].get("dof_vel", None), list):
        dof_vel_dim = len(visual_replay_rows[0]["dof_vel"])
    if obs_rows and isinstance(obs_rows[0].get("ref_root_pos", None), list):
        ref_root_pos_dim = len(obs_rows[0]["ref_root_pos"])
    if obs_rows and isinstance(obs_rows[0].get("ref_root_rot", None), list):
        ref_root_rot_dim = len(obs_rows[0]["ref_root_rot"])
    if visual_replay_rows and isinstance(visual_replay_rows[0].get("root_vel_mps", None), list):
        root_vel_dim = len(visual_replay_rows[0]["root_vel_mps"])
    if visual_replay_rows and isinstance(visual_replay_rows[0].get("root_ang_vel_radps", None), list):
        root_ang_vel_dim = len(visual_replay_rows[0]["root_ang_vel_radps"])

    out_dir = choose_export_dir(out_dir=args.out_dir, model_file=args.model_file)

    obs_path = Path(out_dir) / "obs_fixture.jsonl"
    act_path = Path(out_dir) / "ref_actions.jsonl"
    meta_path = Path(out_dir) / "fixture_meta.json"
    visual_dir = Path(out_dir) / "visual_replay"
    visual_replay_path = visual_dir / "pose_dof_replay.jsonl"
    body_world_replay_path = visual_dir / "body_world_replay.jsonl"
    visual_meta_path = visual_dir / "pose_dof_meta.json"

    _write_jsonl(obs_path, obs_rows)
    _write_jsonl(act_path, action_rows)
    _write_jsonl(visual_replay_path, visual_replay_rows)
    body_order = [str(value) for value in ctx.env._kin_char_model.get_body_names()]
    body_world_rows = [
        {
            "frame": int(row["frame"]),
            "episode": int(row["episode"]),
            "time_seconds": float(row["time_seconds"]),
            "body_order": body_order,
            "source": "kin_char_model_fk",
            "body_pos_m": row.get("body_pos_m", []),
            "body_rot_xyzw": row.get("body_rot_xyzw", []),
            "engine_body_pos_m": row.get("engine_body_pos_m", []),
            "engine_body_rot_xyzw": row.get("engine_body_rot_xyzw", []),
        }
        for row in visual_replay_rows
    ]
    _write_jsonl(body_world_replay_path, body_world_rows)

    visual_meta = {
        "schema_version": 1,
        "row_count": int(len(visual_replay_rows)),
        "policy_hz": int(policy_hz),
        "physics_hz": int(physics_hz),
        "dof_size": int(dof_pos_dim),
        "root_pos_dim": int(ref_root_pos_dim),
        "root_rot_dim": int(ref_root_rot_dim),
        "root_vel_dim": int(root_vel_dim),
        "root_ang_vel_dim": int(root_ang_vel_dim),
        "dof_pos_dim": int(dof_pos_dim),
        "dof_vel_dim": int(dof_vel_dim),
        "body_count": int(len(body_order)),
        "action_dim": int(act_dim),
        "joint_order_file": "../joint_order.json",
        "coordinate_basis": "training_basis_pending_explicit_contract",
        "unit_scale": "meters_to_ue_cm",
        "rotation_convention": "quat_xyzw",
        "body_world_source": "kin_char_model_fk",
        "files": {
            "pose_dof_replay": str(visual_replay_path.resolve()),
            "body_world_replay": str(body_world_replay_path.resolve()),
        },
    }
    save_json(visual_meta_path, visual_meta)

    meta = {
        "source": {
            "arg_file": str(ctx.arg_file),
            "model_file": str(Path(args.model_file).resolve()),
            "env_config": ctx.args.parse_string("env_config", ""),
            "engine_config": ctx.args.parse_string("engine_config", ""),
            "agent_config": ctx.args.parse_string("agent_config", ""),
        },
        "runtime": {
            "device": args.device,
            "frames": int(args.frames),
            "seed": int(args.seed),
            "episodes_recorded": int(episode_index + 1),
        },
        "shape": {
            "obs_dim": int(obs_dim),
            "act_dim": int(act_dim),
            "ref_action_dim": int(ref_action_dim),
            "dof_pos_dim": int(dof_pos_dim),
            "dof_vel_dim": int(dof_vel_dim),
            "ref_root_pos_dim": int(ref_root_pos_dim),
            "ref_root_rot_dim": int(ref_root_rot_dim),
            "root_vel_dim": int(root_vel_dim),
            "root_ang_vel_dim": int(root_ang_vel_dim),
            "count": int(len(obs_rows)),
        },
        "files": {
            "obs_fixture": str(obs_path.resolve()),
            "ref_actions": str(act_path.resolve()),
            "visual_replay": str(visual_replay_path.resolve()),
            "body_world_replay": str(body_world_replay_path.resolve()),
            "visual_replay_meta": str(visual_meta_path.resolve()),
        },
    }

    save_json(meta_path, meta)

    print(f"[OK] obs fixture exported: {obs_path}")
    print(f"[OK] reference actions exported: {act_path}")
    print(f"[OK] visual replay exported: {visual_replay_path}")
    print(f"[OK] metadata: {meta_path}")
    print(
        f"     count={meta['shape']['count']} "
        f"obs_dim={meta['shape']['obs_dim']} act_dim={meta['shape']['act_dim']} "
        f"root_pos_dim={meta['shape']['ref_root_pos_dim']} root_rot_dim={meta['shape']['ref_root_rot_dim']}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
