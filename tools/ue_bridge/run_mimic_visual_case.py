#!/usr/bin/env python3
"""Run MimicKit case inference + export chain and generate visualization artifacts."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import gymnasium.spaces as spaces

from _bridge_common import build_runtime_context, load_configs_from_args, load_runtime_args, resolve_runtime_device, save_json

ROOT = Path(__file__).resolve().parents[2]
RUN_PY = ROOT / 'mimickit' / 'run.py'
EXPORT_SCHEMA_PY = ROOT / 'tools' / 'ue_bridge' / 'export_schema.py'
EXPORT_ONNX_PY = ROOT / 'tools' / 'ue_bridge' / 'export_actor_onnx.py'
EXPORT_FIXTURE_PY = ROOT / 'tools' / 'ue_bridge' / 'export_obs_fixture.py'
EXPORT_DUMMY_PY = ROOT / 'tools' / 'ue_bridge' / 'export_dummy_fixture.py'
TRAIN_ROOT = ROOT / 'output' / 'train'
IMG_ROOT = ROOT / 'output' / 'img'

PACKAGE_SCHEMA_VERSION = 1

DEFAULT_UE_SKELETAL_TARGET = {
    'asset_strategy': 'manny_poseable_fallback_until_mimickit_usd_skeletal_import',
    'skeletal_mesh': '/GASPALS/Characters/UE5_Mannequins/Meshes/SKM_Manny.SKM_Manny',
    'skeleton': '/GASPALS/Characters/UE5_Mannequins/Meshes/SK_Mannequin.SK_Mannequin',
    'anim_blueprint': '',
    'control_rig': '/GASPALS/Characters/UE5_Mannequins/Rigs/CR_Mannequin_Body.CR_Mannequin_Body',
    'fallback_renderer': 'procedural_mimickit_skeletal_replay',
    'full_character_parity': False,
}

DEFAULT_MIMICKIT_TO_UE_BONE_MAP = {
    'pelvis': 'pelvis',
    'torso': 'spine_03',
    'head': 'head',
    'right_upper_arm': 'upperarm_r',
    'right_lower_arm': 'lowerarm_r',
    'right_hand': 'hand_r',
    'sword': 'hand_r',
    'left_upper_arm': 'upperarm_l',
    'left_lower_arm': 'lowerarm_l',
    'left_hand': 'hand_l',
    'shield': 'lowerarm_l',
    'right_thigh': 'thigh_r',
    'right_shin': 'calf_r',
    'right_foot': 'foot_r',
    'left_thigh': 'thigh_l',
    'left_shin': 'calf_l',
    'left_foot': 'foot_l',
}

DEFAULT_JOINT_AXIS_ORDER = {
    'spherical': {
        'dof_interpretation': 'exponential_map_xyz_radians',
        'component_order': ['x', 'y', 'z'],
        'local_axis_basis': 'mimickit_training_xyz',
    },
    'hinge': {
        'dof_interpretation': 'single_axis_radians',
        'default_axis': 'local_y',
        'joint_axis_overrides': {
            'right_elbow': 'local_y',
            'left_elbow': 'local_y',
            'right_knee': 'local_y',
            'left_knee': 'local_y',
        },
    },
    'fixed': {
        'dof_interpretation': 'no_dof_parent_space_attachment',
    },
}


def run_cmd(cmd: list[str], cwd: Path, log_path: Path) -> tuple[int, str]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open('w', encoding='utf-8') as fp:
        proc = subprocess.Popen(cmd, cwd=str(cwd), stdout=fp, stderr=subprocess.STDOUT)
        proc.wait()
    text = log_path.read_text(encoding='utf-8', errors='ignore') if log_path.exists() else ''
    return int(proc.returncode or 0), text


def load_action_rows(path: Path) -> list[list[float]]:
    rows: list[list[float]] = []
    if not path.exists():
        return rows
    for raw in path.read_text(encoding='utf-8', errors='ignore').splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if isinstance(obj, dict) and isinstance(obj.get('action', None), list):
            rows.append([float(x) for x in obj['action']])
    return rows


def write_heatmap_ppm(path: Path, actions: list[list[float]], max_frames: int = 256) -> bool:
    if not actions:
        return False

    frame_count = min(len(actions), max_frames)
    act_dim = min(len(actions[0]), 256)
    if frame_count <= 0 or act_dim <= 0:
        return False

    matrix: list[list[float]] = []
    for i in range(frame_count):
        row = actions[i][:act_dim]
        if len(row) < act_dim:
            row = row + [0.0] * (act_dim - len(row))
        matrix.append(row)

    flat = [v for row in matrix for v in row]
    lo = min(flat)
    hi = max(flat)
    span = hi - lo if hi > lo else 1.0

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as fp:
        fp.write(f'P3\n{act_dim} {frame_count}\n255\n')
        for row in matrix:
            px: list[str] = []
            for value in row:
                t = (value - lo) / span
                r = int(255 * t)
                g = int(255 * (1.0 - abs(t - 0.5) * 2.0))
                b = int(255 * (1.0 - t))
                px.append(f'{r} {g} {b}')
            fp.write(' '.join(px) + '\n')

    return True


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}


def sha256_file(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ''
    h = hashlib.sha256()
    with path.open('rb') as fp:
        for chunk in iter(lambda: fp.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def resolve_contract_path(path_text: str, env_config_path: Path | None = None) -> Path:
    raw = Path(str(path_text or '').strip())
    if raw.is_absolute():
        return raw.resolve()
    candidates: list[Path] = []
    if env_config_path is not None:
        candidates.append((env_config_path.parent / raw).resolve())
    candidates.append((ROOT / raw).resolve())
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[-1] if candidates else raw.resolve()


def visual_kind_for_char(path: Path) -> tuple[str, bool]:
    if not path.exists():
        return 'missing', False
    suffix = path.suffix.lower()
    if suffix == '.usd':
        return 'mesh', True
    if suffix in ('.xml', '.urdf'):
        text = path.read_text(encoding='utf-8', errors='ignore')
        has_mesh = ('type="mesh"' in text) or ('<mesh' in text)
        return ('mesh' if has_mesh else 'geom'), bool(has_mesh)
    return 'unknown', False


def _stable_json_sha256(obj: dict) -> str:
    payload = json.dumps(obj, ensure_ascii=True, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(payload).hexdigest()


def _build_bone_map(body_order: list[str]) -> dict:
    entries: list[dict] = []
    for body_name in body_order:
        ue_bone = DEFAULT_MIMICKIT_TO_UE_BONE_MAP.get(str(body_name), '')
        entries.append({
            'mimickit_body': str(body_name),
            'ue_bone': ue_bone,
            'required_for_skeletal_visual_pass': bool(ue_bone and body_name not in ('sword', 'shield')),
            'mapping_kind': 'bone' if body_name not in ('sword', 'shield') else 'attachment',
        })

    mapped_required = [entry for entry in entries if entry['required_for_skeletal_visual_pass'] and entry['ue_bone']]
    required_count = len([body for body in body_order if body not in ('sword', 'shield')])
    return {
        'map_name': 'mimickit_sword_shield_to_ue_manny_v1',
        'target_skeleton_family': 'UE5_Mannequin',
        'entries': entries,
        'mapped_required_count': len(mapped_required),
        'required_count': required_count,
        'complete_for_skeletal_visual_pass': len(mapped_required) == required_count and required_count > 0,
    }


def _build_skeletal_mapping_contract(joint_order: dict, preferred_visual_asset: Path | None) -> dict:
    body_order = [str(body) for body in joint_order.get('body_order', []) if str(body)]
    bone_map = _build_bone_map(body_order)
    basis_transform = {
        'name': 'mimickit_training_xyz_to_ue_xyz_cm_v1',
        'status': 'declared_for_offline_visual_replay',
        'position': {
            'input': 'root_pos_m[x,y,z]',
            'output': 'ue_location_cm[x*100,y*100,z*100]',
            'matrix_row_major_3x3': [
                [100.0, 0.0, 0.0],
                [0.0, 100.0, 0.0],
                [0.0, 0.0, 100.0],
            ],
        },
        'rotation': {
            'input': 'quat_xyzw',
            'output': 'quat_xyzw',
            'pre_rotation_xyzw': [0.0, 0.0, 0.0, 1.0],
            'post_rotation_xyzw': [0.0, 0.0, 0.0, 1.0],
        },
        'unit_scale': 'meters_to_ue_cm',
        'live_observation_control_status': 'not_validated_for_runtime_control',
    }
    attachments = {
        'sword': {
            'mimickit_body': 'sword',
            'attach_to_body': 'right_hand',
            'attach_to_ue_bone': DEFAULT_MIMICKIT_TO_UE_BONE_MAP['right_hand'],
            'ue_asset': '',
            'fallback': 'procedural_capsule_blade',
            'local_offset_m': [0.35, -0.02, 0.02],
            'local_rotation_xyzw': [0.0, 0.0, 0.0, 1.0],
        },
        'shield': {
            'mimickit_body': 'shield',
            'attach_to_body': 'left_lower_arm',
            'attach_to_ue_bone': DEFAULT_MIMICKIT_TO_UE_BONE_MAP['left_lower_arm'],
            'ue_asset': '',
            'fallback': 'procedural_disc',
            'local_offset_m': [0.05, 0.06, 0.02],
            'local_rotation_xyzw': [0.0, 0.0, 0.0, 1.0],
        },
    }
    contract = {
        'schema_version': 2,
        'contract_role': 'mimickit_to_ue_skeletal_replay_mapping',
        'ue_visual_target': {
            **DEFAULT_UE_SKELETAL_TARGET,
            'mimickit_preferred_visual_asset': str(preferred_visual_asset) if preferred_visual_asset else '',
            'mimickit_preferred_visual_asset_imported_to_ue': False,
        },
        'basis_transform': basis_transform,
        'bone_map': bone_map,
        'joint_axis_order': DEFAULT_JOINT_AXIS_ORDER,
        'attachments': attachments,
        'acceptance_thresholds': {
            'minimum_capture_frames': 1,
            'expected_capture_frames_for_stride_5_rows_300': 60,
            'requires_png_sequence': True,
            'requires_mp4': True,
            'requires_dof_pos_applied': True,
            'requires_skeletal_pose_frames': True,
            'requires_no_pose_block': True,
            'allows_manny_fallback_for_skeletal_visual_pass': True,
            'allows_full_character_parity_claim': False,
        },
    }
    contract['bone_map_hash'] = _stable_json_sha256(bone_map)
    contract['basis_transform_hash'] = _stable_json_sha256(basis_transform)
    return contract


def resolve_train_root(root_out: str) -> Path:
    raw = Path(root_out)
    if raw.is_absolute():
        return raw.resolve()
    return (TRAIN_ROOT / raw).resolve()


def resolve_amp_root_model(status: dict, root_dir: Path) -> str:
    stages = status.get('stages') or {}
    long_meta = stages.get('long_train') or {}
    probe_meta = stages.get('probe_train') or {}
    smoke_meta = stages.get('smoke_train') or {}
    candidates = [
        str(long_meta.get('latest_model', '')).strip(),
        str(status.get('best_scalar_checkpoint', {}).get('model_file', '')).strip(),
        str(probe_meta.get('latest_model', '')).strip(),
        str(smoke_meta.get('latest_model', '')).strip(),
        str(root_dir / 'long_train' / 'model.pt'),
        str(root_dir / 'probe_train' / 'model.pt'),
        str(root_dir / 'smoke_train' / 'model.pt'),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        curr = Path(candidate).resolve()
        if curr.exists():
            return str(curr)
    return ''


def infer_brain_name(case_id: str) -> str:
    stem = Path(case_id).stem
    stem = stem.replace('_args', '')
    parts = [part for part in stem.replace('-', '_').split('_') if part]
    probe = ' '.join(parts).lower()
    if 'stop' in parts or 'amp_stop' in probe:
        return 'StopBrain'
    if 'steering' in parts:
        return 'TurnBrain'
    if 'location' in parts:
        return 'WalkBrain'
    if not parts:
        return 'PolicyBrain'
    label = ''.join(part.capitalize() for part in parts[:3])
    return f'{label}Brain' if not label.endswith('Brain') else label


def configure_amp_root_defaults(args: argparse.Namespace) -> tuple[Path | None, dict]:
    source_root = None
    status: dict = {}
    if args.amp_root:
        source_root = resolve_train_root(args.amp_root)
        status = read_json(source_root / 'keepalive_status.json')
        if not status:
            raise SystemExit(f'[ERROR] missing or invalid keepalive_status.json under {source_root}')

        if not args.case_id:
            args.case_id = str(status.get('case_key', '')).strip() or source_root.name
        if not args.arg_file:
            args.arg_file = str(status.get('arg_file', '')).strip()
        if not args.model_file:
            args.model_file = resolve_amp_root_model(status, source_root)
        if not args.engine_config:
            args.engine_config = (
                str(status.get('current_engine_config', '')).strip()
                or str(status.get('engine_config', '')).strip()
            )
        if not args.env_config:
            args.env_config = str(status.get('current_env_config', '')).strip()
        if not args.agent_config:
            args.agent_config = str(status.get('current_agent_config', '')).strip()
        if not args.out_dir:
            args.out_dir = str(source_root / 'ue_export')
        if not args.brain_name:
            args.brain_name = str(status.get('brain', '')).strip()

    if not args.engine_config:
        args.engine_config = 'data/engines/newton_engine.yaml'

    if not args.case_id:
        raise SystemExit('[ERROR] --case-id is required unless inferred from --amp-root')
    if not args.arg_file:
        raise SystemExit('[ERROR] --arg-file is required unless inferred from --amp-root')
    if args.case_kind == 'policy' and not args.model_file:
        raise SystemExit('[ERROR] --model-file is required for policy cases unless inferred from --amp-root')
    if not args.out_dir:
        raise SystemExit('[ERROR] --out-dir is required unless inferred from --amp-root')

    if not args.brain_name:
        args.brain_name = infer_brain_name(args.case_id)

    return source_root, status


def _to_plain_list(value) -> list[float]:
    if hasattr(value, 'detach'):
        value = value.detach().cpu().tolist()
    elif hasattr(value, 'tolist'):
        value = value.tolist()
    return [float(x) for x in value]


def _collect_joint_order(ctx) -> dict:
    kin = ctx.env._kin_char_model
    body_names = list(kin.get_body_names())

    joints: list[dict] = []
    for joint_index in range(1, kin.get_num_joints()):
        joint = kin.get_joint(joint_index)
        dof_dim = int(joint.get_dof_dim())
        parent_index = int(kin.get_parent_id(joint_index))
        parent_name = body_names[parent_index] if parent_index >= 0 else ''
        dof_index = int(joint.dof_idx)
        joints.append(
            {
                'joint_index': int(joint_index - 1),
                'body_index': int(joint_index),
                'name': str(joint.name),
                'body_name': body_names[joint_index],
                'parent_body_name': parent_name,
                'joint_type': str(joint.joint_type.name).lower(),
                'dof_index': dof_index,
                'dof_dim': dof_dim,
                'dof_slice': [dof_index, dof_index + dof_dim],
            }
        )

    return {
        'schema_version': PACKAGE_SCHEMA_VERSION,
        'body_order': body_names,
        'dof_size': int(kin.get_dof_size()),
        'joints': joints,
    }


def _collect_normalization_stats(ctx, brain_name: str, schema: dict) -> dict:
    obs_norm = ctx.agent._obs_norm
    action_norm = ctx.agent._a_norm

    return {
        'schema_version': PACKAGE_SCHEMA_VERSION,
        'brain_name': brain_name,
        'observation': {
            'dim': int(schema['model']['obs_dim']),
            'count': int(obs_norm.get_count().item()),
            'clip': float(getattr(obs_norm, '_clip', 0.0)),
            'mean': _to_plain_list(obs_norm.get_mean()),
            'std': _to_plain_list(obs_norm.get_std()),
        },
        'action': {
            'dim': int(schema['model']['act_dim']),
            'space_type': schema['model']['action_space_type'],
            'count': int(action_norm.get_count().item()),
            'clip': float(getattr(action_norm, '_clip', 0.0)),
            'mean': _to_plain_list(action_norm.get_mean()),
            'std': _to_plain_list(action_norm.get_std()),
            'low': [float(x) for x in schema['model']['action_low']],
            'high': [float(x) for x in schema['model']['action_high']],
        },
    }


def _build_obs_action_spec(brain_name: str, schema: dict, fixture_meta: dict) -> dict:
    return {
        'schema_version': PACKAGE_SCHEMA_VERSION,
        'brain_name': brain_name,
        'observation': {
            'input_name': 'obs',
            'dim': int(schema['model']['obs_dim']),
            'layout_token': schema['env'].get('obs_layout_token', ''),
            'global_obs': bool(schema['env'].get('global_obs', True)),
            'root_height_obs': bool(schema['env'].get('root_height_obs', True)),
            'enable_tar_obs': bool(schema['env'].get('enable_tar_obs', False)),
            'tar_obs_steps': list(schema['env'].get('tar_obs_steps', [])),
            'fixture_file': 'obs_fixture.jsonl',
            'normalization_ref': 'normalization_stats.json#observation',
        },
        'action': {
            'output_name': 'action',
            'dim': int(schema['model']['act_dim']),
            'space_type': schema['model']['action_space_type'],
            'low': [float(x) for x in schema['model']['action_low']],
            'high': [float(x) for x in schema['model']['action_high']],
            'reference_action_file': 'ref_actions.jsonl',
            'normalization_ref': 'normalization_stats.json#action',
        },
        'control': {
            'policy_hz': int(schema['env'].get('control_freq', 0)),
            'physics_hz': int(schema['env'].get('sim_freq', 0)),
            'control_mode': schema['env'].get('control_mode', ''),
        },
        'reference_payload': {
            'fixture_frames': int(((fixture_meta.get('shape') or {}).get('count')) or 0),
            'ref_action_dim': int(((fixture_meta.get('shape') or {}).get('ref_action_dim')) or 0),
            'dof_pos_dim': int(((fixture_meta.get('shape') or {}).get('dof_pos_dim')) or 0),
            'dof_vel_dim': int(((fixture_meta.get('shape') or {}).get('dof_vel_dim')) or 0),
            'ref_root_pos_dim': int(((fixture_meta.get('shape') or {}).get('ref_root_pos_dim')) or 0),
            'ref_root_rot_dim': int(((fixture_meta.get('shape') or {}).get('ref_root_rot_dim')) or 0),
            'root_vel_dim': int(((fixture_meta.get('shape') or {}).get('root_vel_dim')) or 0),
            'root_ang_vel_dim': int(((fixture_meta.get('shape') or {}).get('root_ang_vel_dim')) or 0),
            'visual_replay_file': 'visual_replay/pose_dof_replay.jsonl',
            'visual_replay_meta_file': 'visual_replay/pose_dof_meta.json',
        },
        'files': {
            'schema': 'schema.json',
            'joint_order': 'joint_order.json',
            'brain_manifest': 'brain_manifest.json',
            'visual_replay': 'visual_replay/pose_dof_replay.jsonl',
            'visual_replay_meta': 'visual_replay/pose_dof_meta.json',
        },
    }


def _build_visual_alignment_contract(ctx, args: argparse.Namespace, source_root: Path | None, joint_order: dict) -> dict:
    env_config_path = Path(args.env_config).resolve() if args.env_config else None
    env_cfg = ctx.env_config if isinstance(ctx.env_config, dict) else {}
    char_declared = str(env_cfg.get('char_file', '')).strip()
    char_path = resolve_contract_path(char_declared, env_config_path) if char_declared else Path()
    visual_kind, mesh_detected = visual_kind_for_char(char_path)
    preferred_visual_asset = char_path.with_suffix('.usd') if char_declared and char_path.with_suffix('.usd').exists() else char_path
    skeletal_mapping = _build_skeletal_mapping_contract(joint_order, preferred_visual_asset if char_declared else None)

    return {
        'schema_version': 2,
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'brain_name': args.brain_name,
        'package_role': 'mimickit_to_ue_visual_alignment_contract',
        'character': {
            'declared_char_file': char_declared,
            'resolved_char_file': str(char_path) if char_declared else '',
            'char_file_exists': bool(char_path.exists()) if char_declared else False,
            'char_file_sha256': sha256_file(char_path) if char_declared else '',
            'visual_kind': visual_kind,
            'mesh_detected_in_declared_asset': bool(mesh_detected),
            'preferred_visual_asset': str(preferred_visual_asset) if char_declared else '',
            'preferred_visual_asset_exists': bool(preferred_visual_asset.exists()) if char_declared else False,
            'preferred_visual_asset_sha256': sha256_file(preferred_visual_asset) if char_declared else '',
            'key_bodies': list(env_cfg.get('key_bodies', [])) if isinstance(env_cfg.get('key_bodies', []), list) else [],
            'contact_bodies': list(env_cfg.get('contact_bodies', [])) if isinstance(env_cfg.get('contact_bodies', []), list) else [],
            'joint_order_file': 'joint_order.json',
            'dof_size': int(joint_order.get('dof_size') or 0),
        },
        'scene': {
            'mimickit_env_config': str(env_config_path) if env_config_path else '',
            'camera_mode': str(env_cfg.get('camera_mode', '')),
            'ground': 'mimickit_engine_default_flat_ground',
            'episode_length_seconds': float(env_cfg.get('episode_length', 0.0) or 0.0),
            'ref_char_offset_m': env_cfg.get('ref_char_offset', []),
            'init_pose': env_cfg.get('init_pose', []),
            'motion_file': str(env_cfg.get('motion_file', '')),
            'golden_render_refs': collect_render_refs(source_root),
        },
        'coordinate_contract': {
            'coordinate_basis': skeletal_mapping['basis_transform']['name'],
            'unit_scale': 'meters_to_ue_cm',
            'rotation_convention': 'quat_xyzw',
            'root_pos_units': 'meters',
            'ue_units': 'centimeters',
            'status': 'declared_for_offline_skeletal_visual_replay',
            'basis_transform_hash': skeletal_mapping['basis_transform_hash'],
            'runtime_control_status': 'blocked_until_live_observation_basis_validation',
        },
        'skeletal_mapping_contract_file': 'skeletal_mapping_contract.json',
        'skeletal_mapping_contract': skeletal_mapping,
        'ue_capture_requirements': {
            'required_outputs': ['png_frame_sequence', 'mp4', 'capture_meta.json', 'visual_diff_report.json'],
            'debug_geometry_is_smoke_only': True,
            'full_visual_parity_requires_skeletal_pose': True,
            'skeletal_visual_pass_requires': [
                'capture_mode=skeletal_replay',
                'dof_pos_applied=true',
                'bone_map_hash',
                'basis_transform_hash',
                'png_sequence',
                'mp4',
            ],
            'must_log_to': 'docs/memory/20260521_amp_ue_visual_diff_log.md',
        },
    }


def write_yaml_or_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import yaml  # type: ignore
    except Exception:
        path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')
        return

    with path.open('w', encoding='utf-8') as fp:
        yaml.safe_dump(obj, fp, sort_keys=False, allow_unicode=False)


def collect_render_refs(source_root: Path | None) -> dict:
    if source_root is None:
        return {}
    render_root = IMG_ROOT / source_root.name
    if not render_root.exists():
        return {'render_root': str(render_root), 'exists': False}

    mp4_files = sorted(str(path.resolve()) for path in render_root.rglob('*.mp4'))
    meta_files = sorted(str(path.resolve()) for path in render_root.rglob('render_meta.json'))
    return {
        'render_root': str(render_root.resolve()),
        'exists': True,
        'mp4_files': mp4_files,
        'render_meta_files': meta_files,
    }


def build_arc_package(
    args: argparse.Namespace,
    out_dir: Path,
    summary: dict,
    summary_path: Path,
    source_root: Path | None,
    amp_status: dict,
) -> dict:
    schema_path = out_dir / 'schema.json'
    onnx_path = out_dir / 'policy_actor.onnx'
    fixture_meta_path = out_dir / 'fixture_meta.json'
    ref_actions_path = out_dir / 'ref_actions.jsonl'
    obs_fixture_path = out_dir / 'obs_fixture.jsonl'
    onnx_meta_path = out_dir / 'onnx_export_meta.json'
    visual_replay_path = out_dir / 'visual_replay' / 'pose_dof_replay.jsonl'
    visual_replay_meta_path = out_dir / 'visual_replay' / 'pose_dof_meta.json'

    schema = read_json(schema_path)
    fixture_meta = read_json(fixture_meta_path)
    if not schema:
        raise RuntimeError(f'missing schema.json at {schema_path}')
    if not fixture_meta:
        raise RuntimeError(f'missing fixture_meta.json at {fixture_meta_path}')

    ctx = build_runtime_context(
        arg_file=args.arg_file,
        overrides=args,
        device=args.device,
        visualize=False,
        load_model=(args.case_kind == 'policy'),
    )

    joint_order = _collect_joint_order(ctx)
    normalization_stats = _collect_normalization_stats(ctx, args.brain_name, schema)
    obs_action_spec = _build_obs_action_spec(args.brain_name, schema, fixture_meta)

    brain_model_name = f'{args.brain_name}.onnx'
    brain_model_path = out_dir / brain_model_name
    if brain_model_path.resolve() != onnx_path.resolve():
        shutil.copy2(onnx_path, brain_model_path)

    joint_order_path = out_dir / 'joint_order.json'
    normalization_path = out_dir / 'normalization_stats.json'
    obs_action_spec_path = out_dir / 'obs_action_spec.yaml'
    visual_alignment_path = out_dir / 'visual_alignment_contract.json'
    skeletal_mapping_path = out_dir / 'skeletal_mapping_contract.json'
    brain_manifest_path = out_dir / 'brain_manifest.json'
    package_manifest_path = out_dir / 'export_package_manifest.json'

    save_json(joint_order_path, joint_order)
    save_json(normalization_path, normalization_stats)
    write_yaml_or_json(obs_action_spec_path, obs_action_spec)
    visual_alignment_contract = _build_visual_alignment_contract(ctx, args, source_root, joint_order)
    save_json(visual_alignment_path, visual_alignment_contract)
    save_json(skeletal_mapping_path, visual_alignment_contract['skeletal_mapping_contract'])

    brain_manifest = {
        'schema_version': PACKAGE_SCHEMA_VERSION,
        'brain_name': args.brain_name,
        'brain_role': 'arc_locomotion_policy',
        'model': brain_model_name,
        'policy_hz': int(schema['env'].get('control_freq', 0)),
        'physics_hz': int(schema['env'].get('sim_freq', 0)),
        'observation_dim': int(schema['model']['obs_dim']),
        'action_dim': int(schema['model']['act_dim']),
        'joint_order_file': joint_order_path.name,
        'normalization_file': normalization_path.name,
        'observation_spec_file': obs_action_spec_path.name,
        'schema_file': schema_path.name,
        'fixture_file': obs_fixture_path.name,
        'reference_action_file': ref_actions_path.name,
        'visual_replay_file': 'visual_replay/pose_dof_replay.jsonl',
        'visual_replay_meta_file': 'visual_replay/pose_dof_meta.json',
        'visual_alignment_contract_file': visual_alignment_path.name,
        'skeletal_mapping_contract_file': skeletal_mapping_path.name,
        'coordinate_basis': visual_alignment_contract['coordinate_contract']['coordinate_basis'],
        'unit_scale': 'meters_to_ue_cm',
        'runtime_control_basis_status': 'blocked_until_live_observation_basis_validation',
        'visual_replay': {
            'pose_dof_replay': 'visual_replay/pose_dof_replay.jsonl',
            'pose_dof_meta': 'visual_replay/pose_dof_meta.json',
        },
        'source': {
            'case_id': args.case_id,
            'case_kind': args.case_kind,
            'arg_file': str(Path(args.arg_file).resolve()),
            'model_file': str(Path(args.model_file).resolve()),
            'engine_config': str(Path(args.engine_config).resolve()) if args.engine_config else '',
            'env_config': str(Path(args.env_config).resolve()) if args.env_config else '',
            'agent_config': str(Path(args.agent_config).resolve()) if args.agent_config else '',
            'amp_root': str(source_root.resolve()) if source_root else '',
            'keepalive_status': str((source_root / 'keepalive_status.json').resolve()) if source_root else '',
        },
    }
    save_json(brain_manifest_path, brain_manifest)

    artifacts = {
        'policy_actor': onnx_path.name,
        'brain_model': brain_model_path.name,
        'schema': schema_path.name,
        'onnx_export_meta': onnx_meta_path.name,
        'obs_fixture': obs_fixture_path.name,
        'ref_actions': ref_actions_path.name,
        'visual_replay': 'visual_replay/pose_dof_replay.jsonl',
        'visual_replay_meta': 'visual_replay/pose_dof_meta.json',
        'fixture_meta': fixture_meta_path.name,
        'visual_alignment_contract': visual_alignment_path.name,
        'skeletal_mapping_contract': skeletal_mapping_path.name,
        'obs_action_spec': obs_action_spec_path.name,
        'normalization_stats': normalization_path.name,
        'joint_order': joint_order_path.name,
        'brain_manifest': brain_manifest_path.name,
        'summary': summary_path.name,
    }

    package_manifest = {
        'schema_version': PACKAGE_SCHEMA_VERSION,
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'brain_name': args.brain_name,
        'source_root': str(source_root.resolve()) if source_root else '',
        'amp_status_brain': str(amp_status.get('brain', '')).strip(),
        'artifacts': artifacts,
        'render_refs': collect_render_refs(source_root),
        'status': {
            'mimic_infer_ok': bool(summary.get('mimic_infer_ok')),
            'fixture_ok': bool(summary.get('fixture_ok')),
            'mimic_viz_ok': bool(summary.get('mimic_viz_ok')),
            'visual_replay_ok': visual_replay_path.exists() and visual_replay_meta_path.exists(),
            'visual_alignment_contract_ok': visual_alignment_path.exists(),
            'skeletal_mapping_contract_ok': skeletal_mapping_path.exists(),
        },
    }
    save_json(package_manifest_path, package_manifest)

    return {
        'package_ok': True,
        'brain_name': args.brain_name,
        'brain_model': str(brain_model_path),
        'obs_action_spec': str(obs_action_spec_path),
        'normalization_stats': str(normalization_path),
        'joint_order': str(joint_order_path),
        'brain_manifest': str(brain_manifest_path),
        'package_manifest': str(package_manifest_path),
        'visual_replay': str(visual_replay_path),
        'visual_replay_meta': str(visual_replay_meta_path),
        'visual_alignment_contract': str(visual_alignment_path),
        'skeletal_mapping_contract': str(skeletal_mapping_path),
    }


def build_dummy_visual_package(
    args: argparse.Namespace,
    out_dir: Path,
    summary: dict,
    summary_path: Path,
) -> dict:
    ctx = build_runtime_context(
        arg_file=args.arg_file,
        overrides=args,
        device=args.device,
        visualize=False,
        load_model=False,
    )
    joint_order = _collect_joint_order(ctx)
    visual_alignment_contract = _build_visual_alignment_contract(ctx, args, None, joint_order)
    joint_order_path = out_dir / "joint_order.json"
    visual_alignment_path = out_dir / "visual_alignment_contract.json"
    skeletal_mapping_path = out_dir / "skeletal_mapping_contract.json"
    brain_manifest_path = out_dir / "brain_manifest.json"
    package_manifest_path = out_dir / "export_package_manifest.json"
    save_json(joint_order_path, joint_order)
    save_json(visual_alignment_path, visual_alignment_contract)
    save_json(skeletal_mapping_path, visual_alignment_contract["skeletal_mapping_contract"])
    save_json(
        brain_manifest_path,
        {
            "schema_version": PACKAGE_SCHEMA_VERSION,
            "brain_name": args.brain_name,
            "brain_role": "visual_reference",
            "joint_order_file": joint_order_path.name,
            "visual_replay_file": "visual_replay/pose_dof_replay.jsonl",
            "visual_replay_meta_file": "visual_replay/pose_dof_meta.json",
            "visual_alignment_contract_file": visual_alignment_path.name,
            "skeletal_mapping_contract_file": skeletal_mapping_path.name,
        },
    )
    save_json(
        package_manifest_path,
        {
            "schema_version": PACKAGE_SCHEMA_VERSION,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "brain_name": args.brain_name,
            "artifacts": {
                "joint_order": joint_order_path.name,
                "visual_replay": "visual_replay/pose_dof_replay.jsonl",
                "visual_replay_meta": "visual_replay/pose_dof_meta.json",
                "visual_alignment_contract": visual_alignment_path.name,
                "skeletal_mapping_contract": skeletal_mapping_path.name,
                "summary": summary_path.name,
            },
            "status": {
                "fixture_ok": bool(summary.get("fixture_ok")),
                "visual_replay_ok": True,
                "visual_alignment_contract_ok": True,
                "skeletal_mapping_contract_ok": True,
            },
        },
    )
    return {
        "package_ok": True,
        "joint_order": str(joint_order_path),
        "brain_manifest": str(brain_manifest_path),
        "package_manifest": str(package_manifest_path),
        "visual_alignment_contract": str(visual_alignment_path),
        "skeletal_mapping_contract": str(skeletal_mapping_path),
    }


def build_common_export_args(args: argparse.Namespace, out_dir: Path) -> list[str]:
    out: list[str] = [
        '--arg-file',
        args.arg_file,
        '--engine-config',
        args.engine_config,
        '--out-dir',
        str(out_dir),
        '--device',
        args.device,
        '--num-envs',
        str(int(args.num_envs)),
    ]
    if args.env_config:
        out.extend(['--env-config', args.env_config])
    if args.agent_config:
        out.extend(['--agent-config', args.agent_config])
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description='Run MimicKit single-case inference/export and visualization artifacts')
    parser.add_argument('--amp-root', default='', help='AMP root under output/train or absolute path; infers arg/model/config/package paths')
    parser.add_argument('--brain-name', default='', help='ARC brain label for package outputs (default: inferred from amp root or case id)')
    parser.add_argument('--case-id', default='')
    parser.add_argument('--arg-file', default='')
    parser.add_argument('--model-file', default='')
    parser.add_argument('--engine-config', default='')
    parser.add_argument('--env-config', default='')
    parser.add_argument('--agent-config', default='')
    parser.add_argument('--case-kind', choices=['policy', 'dummy'], default='policy')
    parser.add_argument('--out-dir', default='')
    parser.add_argument('--device', default='cpu')
    parser.add_argument('--num-envs', type=int, default=1)
    parser.add_argument('--frames', type=int, default=300)
    parser.add_argument('--seed', type=int, default=7)
    parser.add_argument('--test-episodes', type=int, default=2)
    parser.add_argument('--skip-test', action='store_true')
    parser.add_argument('--skip-verify', action='store_true')
    args = parser.parse_args()

    source_root, amp_status = configure_amp_root_defaults(args)
    runtime_args = load_runtime_args(arg_file=args.arg_file, overrides=args)
    _, runtime_engine_cfg, _ = load_configs_from_args(runtime_args)
    requested_device = args.device
    args.device = resolve_runtime_device(args.device, runtime_engine_cfg)

    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    test_log = out_dir / 'mimic_test.log'
    export_log = out_dir / 'mimic_export.log'
    ref_actions = out_dir / 'ref_actions.jsonl'
    obs_fixture = out_dir / 'obs_fixture.jsonl'
    fixture_meta = out_dir / 'fixture_meta.json'
    visual_replay = out_dir / 'visual_replay' / 'pose_dof_replay.jsonl'
    visual_replay_meta = out_dir / 'visual_replay' / 'pose_dof_meta.json'
    schema_path = out_dir / 'schema.json'
    onnx_path = out_dir / 'policy_actor.onnx'
    visual_image = out_dir / 'mimic_action_heatmap.ppm'
    summary_path = out_dir / 'mimic_case_summary.json'

    test_rc = 0
    test_text = ''
    mimic_infer_ok = False

    if not args.skip_test:
        test_cmd = [
            sys.executable,
            str(RUN_PY),
            '--arg_file',
            args.arg_file,
            '--engine_config',
            args.engine_config,
            '--mode',
            'test',
            '--visualize',
            'false',
            '--devices',
            args.device,
            '--num_envs',
            str(int(args.num_envs)),
            '--test_episodes',
            str(int(args.test_episodes)),
        ]
        if args.env_config:
            test_cmd.extend(['--env_config', args.env_config])
        if args.agent_config:
            test_cmd.extend(['--agent_config', args.agent_config])
        if args.case_kind == 'policy':
            test_cmd.extend(['--model_file', args.model_file])

        test_rc, test_text = run_cmd(test_cmd, ROOT, test_log)
        if args.case_kind == 'policy':
            mimic_infer_ok = test_rc == 0 and ('Mean Return:' in test_text and 'Episodes:' in test_text)
        else:
            # Dummy path accepts successful test execution even without policy return signal.
            mimic_infer_ok = test_rc == 0
    else:
        mimic_infer_ok = True

    export_cmds: list[list[str]] = []
    common_args = build_common_export_args(args, out_dir)

    if args.case_kind == 'policy':
        export_cmds.append([
            sys.executable,
            str(EXPORT_SCHEMA_PY),
            *common_args,
            '--model-file',
            args.model_file,
        ])
        onnx_cmd = [
            sys.executable,
            str(EXPORT_ONNX_PY),
            *common_args,
            '--model-file',
            args.model_file,
            '--export-device',
            'cpu',
        ]
        if not args.skip_verify:
            onnx_cmd.append('--verify')
        export_cmds.append(onnx_cmd)
        export_cmds.append([
            sys.executable,
            str(EXPORT_FIXTURE_PY),
            *common_args,
            '--model-file',
            args.model_file,
            '--frames',
            str(int(args.frames)),
            '--seed',
            str(int(args.seed)),
        ])
    else:
        export_cmds.append([
            sys.executable,
            str(EXPORT_DUMMY_PY),
            *common_args,
            '--model-file',
            args.model_file,
            '--frames',
            str(int(args.frames)),
            '--seed',
            str(int(args.seed)),
        ])

    export_rc = 0
    export_texts: list[str] = []
    export_log.parent.mkdir(parents=True, exist_ok=True)
    with export_log.open('w', encoding='utf-8') as fp:
        for cmd in export_cmds:
            fp.write('[CMD] ' + ' '.join(cmd) + '\n')
            rc, txt = run_cmd(cmd, ROOT, out_dir / f'_tmp_export_{len(export_texts)}.log')
            export_texts.append(txt)
            fp.write(txt + '\n')
            if rc != 0:
                export_rc = rc
                break

    rows = load_action_rows(ref_actions)
    viz_ok = write_heatmap_ppm(visual_image, rows)

    fixture_ok = (
        export_rc == 0
        and ref_actions.exists()
        and obs_fixture.exists()
        and fixture_meta.exists()
        and visual_replay.exists()
        and visual_replay_meta.exists()
        and schema_path.exists()
        and onnx_path.exists()
    )

    summary = {
        'case_id': args.case_id,
        'case_kind': args.case_kind,
        'brain_name': args.brain_name,
        'amp_root': str(source_root) if source_root else '',
        'arg_file': args.arg_file,
        'engine_config': args.engine_config,
        'env_config': args.env_config,
        'agent_config': args.agent_config,
        'model_file': str(Path(args.model_file).resolve()),
        'requested_device': requested_device,
        'device': args.device,
        'mimic_infer_ok': bool(mimic_infer_ok),
        'mimic_viz_ok': bool(viz_ok),
        'fixture_ok': bool(fixture_ok),
        'test_exit_code': int(test_rc),
        'export_exit_code': int(export_rc),
        'mimic_test_log': str(test_log),
        'export_log': str(export_log),
        'obs_fixture': str(obs_fixture),
        'ref_actions': str(ref_actions),
        'visual_replay': str(visual_replay),
        'visual_replay_meta': str(visual_replay_meta),
        'fixture_meta': str(fixture_meta),
        'schema': str(schema_path),
        'onnx': str(onnx_path),
        'mimic_visual_image': str(visual_image),
    }

    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')

    package_ok = False
    if args.case_kind == 'policy' and fixture_ok:
        try:
            package_meta = build_arc_package(
                args=args,
                out_dir=out_dir,
                summary=summary,
                summary_path=summary_path,
                source_root=source_root,
                amp_status=amp_status,
            )
            summary.update(package_meta)
            package_ok = True
        except Exception as ex:
            summary['package_ok'] = False
            summary['package_error'] = str(ex)
    elif args.case_kind == "dummy" and fixture_ok:
        try:
            package_meta = build_dummy_visual_package(
                args=args,
                out_dir=out_dir,
                summary=summary,
                summary_path=summary_path,
            )
            summary.update(package_meta)
            package_ok = True
        except Exception as ex:
            summary["package_ok"] = False
            summary["package_error"] = str(ex)
    else:
        summary['package_ok'] = bool(package_ok)

    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False))

    if summary['mimic_infer_ok'] and summary['fixture_ok'] and summary['mimic_viz_ok'] and summary['package_ok']:
        return 0
    return 2


if __name__ == '__main__':
    raise SystemExit(main())

