from isaaclab.app import AppLauncher

import carb

import numpy as np
import os
import json
import torch
import time

import engines.engine as engine
from util.logger import Logger
import util.torch_util as torch_util

ROT_WXYZ_TO_XYZW = [1, 2, 3, 0]
ROT_XYZW_TO_WXYZ = [3, 0, 1, 2]

ENV_PATH_TEMPLATE = "/World/envs/env_{}"
OBJ_PATH_TEMPLATE = "/World/envs/env_{}/obj_{}"
GROUND_PATH = "/World/ground"
LIGHT_PATH = "/World/Light"

def enable_kit_extension(extension_name):
    import omni.kit.app
    ext_manager = omni.kit.app.get_app().get_extension_manager()
    ext_manager.set_extension_enabled_immediate(extension_name, True)
    return


def str_to_key_code(key_str):
    key_name = key_str.upper()

    if (key_str == "ESC"):
        key_name = "ESCAPE"
    elif (key_str == "RETURN"):
        key_name = "ENTER"
    elif (key_str == "DELETE"):
        key_name = "DEL"
    elif (len(key_str) == 1 and key_str.isdigit()):
        key_name = "KEY_" + key_str
    
    key_code = getattr(carb.input.KeyboardInput, key_name)
    return key_code

class ObjCfg:
    def __init__(self, obj_type, asset_file, is_visual, enable_self_collisions, 
                fix_root, start_pos, start_rot, color, disable_motors):
        self.obj_type = obj_type
        self.asset_file = asset_file
        self.is_visual = is_visual
        self.enable_self_collisions = enable_self_collisions
        self.fix_root = fix_root
        self.start_pos = start_pos
        self.start_rot = start_rot
        self.color = color
        self.disable_motors = disable_motors
        return
    
    def is_valid_clone(self, other):
        is_same = self.obj_type == other.obj_type
        is_same &= self.asset_file == other.asset_file
        is_same &= self.is_visual == other.is_visual
        is_same &= self.enable_self_collisions == other.enable_self_collisions
        is_same &= self.fix_root == other.fix_root
        is_same &= self.disable_motors == other.disable_motors
        return is_same


class IsaacLabEngine(engine.Engine):
    def __init__(self, config, num_envs, device, visualize):
        super().__init__()

        self._device = device
        sim_freq = config.get("sim_freq", 60)
        control_freq = config.get("control_freq", 10)
        assert(sim_freq >= control_freq and sim_freq % control_freq == 0), \
            "Simulation frequency must be a multiple of the control frequency"

        self._timestep = 1.0 / control_freq
        self._sim_steps = int(sim_freq / control_freq)
        sim_timestep = 1.0 / sim_freq

        self._create_simulator(sim_timestep, visualize)

        self._env_spacing = config["env_spacing"]
        self._obj_cfgs = []
        self._obj_control_modes = []
        
        if ("control_mode" in config):
            self._control_mode = engine.ControlMode[config["control_mode"]]
        else:
            self._control_mode = engine.ControlMode.none

        self._build_ground()
        self._env_offsets = self._compute_env_offsets(num_envs)

        if (visualize):
            self._prev_frame_time = 0.0
            self._build_lights()
            self._build_camera()
            self._build_draw_interface()
            self._setup_keyboard()

        return
    
    def get_name(self):
        return "isaac_lab"
    
    def create_env(self):
        env_id = len(self._obj_cfgs)
        assert(env_id < self.get_num_envs())

        self._obj_cfgs.append([])
        return env_id
    
    def initialize_sim(self):
        from isaacsim.core.cloner import Cloner

        self._validate_envs()
        self._cloner = Cloner(self._stage)

        self._build_envs()
        self._build_objs()
        self._build_ground_contact_sensors()
        self._filter_env_collisions()

        Logger.print("Initializing simulation...")
        self._sim.reset()
        
        self._build_order_tensors()
        self._build_sim_tensors()
        return
    
    def step(self):
        self._update_reset_objs()
        
        for i in range(self._sim_steps):
            self._pre_sim_step()
            self._sim_step()
            self._post_sim_step()
            
        self._clear_forces()
        return

    def create_obj(self, env_id, obj_type, asset_file, name, is_visual=False, enable_self_collisions=True, 
                   fix_root=False, start_pos=None, start_rot=None, 
                   color=None, disable_motors=False):
        if (start_rot is None):
            start_rot = np.array([1.0, 0.0, 0.0, 0.0])
        else:
            start_rot = start_rot[ROT_XYZW_TO_WXYZ]

        if (start_pos is None):
            start_pos = np.array([0.0, 0.0, 0.0])
        else:
            start_pos = start_pos.copy()
        
        start_pos[0] += self._env_offsets[env_id, 0]
        start_pos[1] += self._env_offsets[env_id, 1]

        obj_cfg = ObjCfg(obj_type=obj_type,
                         asset_file=asset_file, 
                         is_visual=is_visual, 
                         enable_self_collisions=enable_self_collisions,
                         fix_root=fix_root, 
                         start_pos=start_pos, 
                         start_rot=start_rot,
                         color=color, 
                         disable_motors=disable_motors)
        
        obj_id = len(self._obj_cfgs[env_id])
        self._obj_cfgs[env_id].append(obj_cfg)
        
        return obj_id
    
    def set_cmd(self, obj_id, cmd):
        obj = self._objs[obj_id]
        dof_order_common2sim = self._dof_order_common2sim[obj_id]
        sim_cmd = cmd[:, dof_order_common2sim]

        if (self._control_mode == engine.ControlMode.none):
            pass
        elif (self._control_mode == engine.ControlMode.pos):
            obj.set_joint_position_target(sim_cmd)
        elif (self._control_mode == engine.ControlMode.vel):
            obj.set_joint_velocity_target(sim_cmd)
        elif (self._control_mode == engine.ControlMode.torque):
            obj.set_joint_effort_target(sim_cmd)
        elif (self._control_mode == engine.ControlMode.pd_explicit):
            obj.set_joint_position_target(sim_cmd)
        else:
            assert(False), "Unsupported control mode: {}".format(self._control_mode)
        return
    
    def set_camera_pose(self, pos, look_at):
        env_offset = self._env_offsets[0].cpu().numpy()
        cam_pos = pos.copy()
        cam_look_at = look_at.copy()

        cam_pos[:2] += env_offset
        cam_look_at[:2] += env_offset
        self._sim.set_camera_view(eye=cam_pos, target=cam_look_at)
        return
    
    def get_camera_pos(self):
        cam_state_pos = self._camera_state.position_world
        env_offset = self._env_offsets[0].cpu().numpy()
        cam_pos = np.array([cam_state_pos[0] - env_offset[0], 
                            cam_state_pos[1] - env_offset[1], 
                            cam_state_pos[2]])
        return cam_pos
    
    def get_camera_dir(self):
        cam_state_pos = self._camera_state.position_world
        cam_state_target = self._camera_state.target_world
        cam_delta = np.array([cam_state_target[0] - cam_state_pos[0],
                              cam_state_target[1] - cam_state_pos[1],
                              cam_state_target[2] - cam_state_pos[2]])
        cam_dir = cam_delta / np.linalg.norm(cam_delta)
        return cam_dir
    
    def render(self):
        self._sim.render()
        self._draw_interface.clear_lines()

        now = time.time()
        delta = now - self._prev_frame_time
        time_step = self.get_timestep()

        if (delta < time_step):
            time.sleep(time_step - delta)

        self._prev_frame_time = time.time()
        return

    def capture_frame(self, width, height, include_silhouette=True):
        import omni.replicator.core as rep

        visual_link_sync = self._sync_capture_visual_links()
        capture_settle_updates = max(1, min(64, int(os.environ.get("MIMICKIT_CAPTURE_SETTLE_UPDATES", "8"))))
        resolution = (int(width), int(height))
        if getattr(self, "_capture_resolution", None) != resolution:
            self.release_capture()
            self._capture_render_product = rep.create.render_product("/OmniverseKit_Persp", resolution)
            self._capture_annotator = rep.AnnotatorRegistry.get_annotator("rgb")
            self._capture_annotator.attach([self._capture_render_product])
            if include_silhouette:
                self._capture_semantic_annotator = rep.AnnotatorRegistry.get_annotator(
                    "semantic_segmentation",
                    init_params={"colorize": False},
                )
                self._capture_semantic_annotator.attach([self._capture_render_product])
            self._capture_resolution = resolution

        rgba = None
        silhouette = None
        ground_mask = None
        last_error = "capture did not become ready"
        for _attempt in range(6):
            visual_link_sync = self._sync_capture_visual_links()
            # Let the RTX render product converge after a pose/camera update.
            # Without this, the first captured frame can contain a partially
            # initialized ground-grid shader while later frames are settled.
            for _ in range(capture_settle_updates):
                self._sim.render()
                self._app_launcher.app.update()
            data = self._capture_annotator.get_data()
            candidate_rgba = np.asarray(data.get("data") if isinstance(data, dict) else data)
            if candidate_rgba.size == 0:
                last_error = "IsaacLab headless capture returned no pixels"
                continue
            if candidate_rgba.ndim != 3 or candidate_rgba.shape[0] != resolution[1] or candidate_rgba.shape[1] != resolution[0]:
                last_error = f"IsaacLab capture shape mismatch: {candidate_rgba.shape} expected={(resolution[1], resolution[0])}"
                continue
            if not np.any(np.ptp(candidate_rgba[..., :3], axis=(0, 1)) > 0):
                last_error = "IsaacLab headless capture returned a black/static frame"
                continue

            candidate_silhouette = None
            candidate_ground_mask = None
            if include_silhouette:
                semantic_payload = self._capture_semantic_annotator.get_data()
                semantic = np.asarray(semantic_payload.get("data") if isinstance(semantic_payload, dict) else semantic_payload)
                semantic = np.squeeze(semantic)
                if semantic.shape != (resolution[1], resolution[0]):
                    last_error = f"IsaacLab silhouette shape mismatch: {semantic.shape}"
                    continue
                target_ids = []
                ground_ids = []
                semantic_info = semantic_payload.get("info", {}) if isinstance(semantic_payload, dict) else {}
                id_to_labels = semantic_info.get("idToLabels", {}) if isinstance(semantic_info, dict) else {}
                if isinstance(id_to_labels, dict):
                    for raw_id, labels in id_to_labels.items():
                        label_text = json.dumps(labels, ensure_ascii=True).lower()
                        if "mimickit_character" in label_text:
                            try:
                                target_ids.append(int(raw_id))
                            except (TypeError, ValueError):
                                pass
                        if "mimickit_ground" in label_text:
                            try:
                                ground_ids.append(int(raw_id))
                            except (TypeError, ValueError):
                                pass
                if not target_ids:
                    last_error = "IsaacLab semantic capture is missing mimickit_character"
                    continue
                if not ground_ids:
                    last_error = "IsaacLab semantic capture is missing mimickit_ground"
                    continue
                candidate_silhouette = np.isin(semantic, target_ids).astype(np.uint8) * 255
                candidate_ground_mask = np.isin(semantic, ground_ids).astype(np.uint8) * 255
                nonzero = int(np.count_nonzero(candidate_silhouette))
                if nonzero <= 0 or nonzero >= candidate_silhouette.size:
                    last_error = "IsaacLab semantic silhouette is empty or full-frame"
                    continue
                ground_nonzero = int(np.count_nonzero(candidate_ground_mask))
                if ground_nonzero <= 0 or ground_nonzero >= candidate_ground_mask.size:
                    last_error = "IsaacLab semantic ground mask is empty or full-frame"
                    continue

            rgba = candidate_rgba
            silhouette = candidate_silhouette
            ground_mask = candidate_ground_mask
            break
        if rgba is None:
            raise RuntimeError(last_error)
        camera_eye = self.get_camera_pos()
        camera_target = np.array(self._camera_state.target_world, dtype=np.float64)
        env_offset = self._env_offsets[0].cpu().numpy()
        camera_target[:2] -= env_offset
        projection = "perspective"
        fov_degrees = 45.0
        fov_axis = "horizontal"
        near = 0.1
        far = 1000.0
        try:
            from pxr import UsdGeom

            camera = UsdGeom.Camera(self._stage.GetPrimAtPath("/OmniverseKit_Persp"))
            focal_length = float(camera.GetFocalLengthAttr().Get())
            horizontal_aperture = float(camera.GetHorizontalApertureAttr().Get())
            clipping = camera.GetClippingRangeAttr().Get()
            if focal_length > 0.0 and horizontal_aperture > 0.0:
                fov_degrees = float(np.degrees(2.0 * np.arctan(horizontal_aperture / (2.0 * focal_length))))
            if clipping is not None:
                near, far = float(clipping[0]), float(clipping[1])
            projection = str(camera.GetProjectionAttr().Get() or "perspective")
        except Exception:
            pass
        return engine.CaptureFrame(
            rgba=rgba,
            silhouette=silhouette,
            width=resolution[0],
            height=resolution[1],
            camera_eye=camera_eye.tolist(),
            camera_target=camera_target.tolist(),
            fov_degrees=fov_degrees,
            fov_axis=fov_axis,
            projection=projection,
            near=near,
            far=far,
            ground_mask=ground_mask,
            renderer_version="isaaclab+usd-link-sync-v2-settled",
            visual_link_sync_ok=visual_link_sync["ok"],
            visual_link_sync_max_pos_error_m=visual_link_sync["max_pos_error_m"],
            visual_link_sync_max_rot_error_rad=visual_link_sync["max_rot_error_rad"],
            visual_link_sync_count=visual_link_sync["link_count"],
            capture_settle_updates=capture_settle_updates,
        )

    def _sync_capture_visual_links(self):
        from isaaclab.assets import Articulation
        import isaaclab.sim as sim_utils
        from isaacsim.core.prims import XFormPrim
        from pxr import UsdGeom, UsdPhysics

        if not hasattr(self, "_capture_link_views"):
            self._capture_link_views = {}

        max_pos_error_m = 0.0
        max_rot_error_rad = 0.0
        link_count = 0
        for obj_id, obj in enumerate(self._objs):
            if not isinstance(obj, Articulation):
                continue

            body_names = list(obj.root_physx_view.shared_metatype.link_names)
            link_views = self._capture_link_views.get(obj_id)
            if link_views is None:
                root_path = OBJ_PATH_TEMPLATE.format(0, obj_id)
                rigid_prims = sim_utils.get_all_matching_child_prims(
                    root_path,
                    predicate=lambda prim: prim.HasAPI(UsdPhysics.RigidBodyAPI),
                    stage=self._stage,
                    traverse_instance_prims=True,
                )
                paths_by_name = {}
                for prim in rigid_prims:
                    paths_by_name.setdefault(prim.GetName(), []).append(prim.GetPath().pathString)
                missing = [name for name in body_names if len(paths_by_name.get(name, [])) != 1]
                if missing:
                    raise RuntimeError(
                        "IsaacLab capture cannot uniquely map articulation links to USD prims: "
                        f"missing_or_ambiguous={missing} root={root_path}"
                    )
                link_views = [
                    XFormPrim(
                        prim_paths_expr=paths_by_name[name][0],
                        name=f"mimickit_capture_link_{obj_id}_{name}",
                        reset_xform_properties=False,
                        usd=True,
                    )
                    for name in body_names
                ]
                self._capture_link_views[obj_id] = link_views

            body_poses_raw = obj.data.body_link_pose_w[0]
            if torch.is_tensor(body_poses_raw):
                body_poses = body_poses_raw.detach().cpu().numpy()
            else:
                body_poses = np.asarray(body_poses_raw)
            if body_poses.shape != (len(link_views), 7):
                raise RuntimeError(
                    "IsaacLab capture body pose shape mismatch: "
                    f"actual={body_poses.shape} expected={(len(link_views), 7)}"
                )

            # Simulator link order is parent-before-child. Updating each view in
            # that order lets set_world_poses compute the correct child-local pose.
            for link_view, body_pose in zip(link_views, body_poses):
                link_view.set_world_poses(
                    positions=torch.as_tensor(body_pose[:3], dtype=torch.float32, device=self._device).unsqueeze(0),
                    orientations=torch.as_tensor(body_pose[3:7], dtype=torch.float32, device=self._device).unsqueeze(0),
                    usd=True,
                )

            for link_view, body_pose in zip(link_views, body_poses):
                prim = self._stage.GetPrimAtPath(link_view.prim_paths[0])
                world = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(0)
                stage_pos = np.asarray(world.ExtractTranslation(), dtype=np.float64)
                stage_quat_gf = world.ExtractRotationQuat()
                stage_quat = np.asarray(
                    [stage_quat_gf.GetReal(), *stage_quat_gf.GetImaginary()],
                    dtype=np.float64,
                )
                expected_pos = np.asarray(body_pose[:3], dtype=np.float64)
                expected_quat = np.asarray(body_pose[3:7], dtype=np.float64)
                max_pos_error_m = max(max_pos_error_m, float(np.linalg.norm(stage_pos - expected_pos)))
                stage_quat /= max(float(np.linalg.norm(stage_quat)), 1e-12)
                expected_quat /= max(float(np.linalg.norm(expected_quat)), 1e-12)
                quat_dot = float(np.clip(abs(np.dot(stage_quat, expected_quat)), 0.0, 1.0))
                max_rot_error_rad = max(max_rot_error_rad, float(2.0 * np.arccos(quat_dot)))
                link_count += 1

        ok = link_count > 0 and max_pos_error_m <= 1e-5 and max_rot_error_rad <= 1e-5
        if not ok:
            raise RuntimeError(
                "IsaacLab capture visual links are not synchronized: "
                f"links={link_count} max_pos_error_m={max_pos_error_m} "
                f"max_rot_error_rad={max_rot_error_rad}"
            )
        return {
            "ok": True,
            "link_count": int(link_count),
            "max_pos_error_m": float(max_pos_error_m),
            "max_rot_error_rad": float(max_rot_error_rad),
        }

    def release_capture(self):
        for name in ("_capture_annotator", "_capture_semantic_annotator"):
            annotator = getattr(self, name, None)
            if annotator is not None:
                try:
                    annotator.detach()
                except Exception:
                    pass
                setattr(self, name, None)
        render_product = getattr(self, "_capture_render_product", None)
        if render_product is not None:
            try:
                render_product.destroy()
            except Exception:
                pass
            self._capture_render_product = None
        self._capture_resolution = None
        return
    
    def get_timestep(self):
        return self._timestep
    
    def get_sim_timestep(self):
        dt = self._sim.get_physics_dt()
        return dt
    
    def get_num_envs(self):
        return self._env_offsets.shape[0]
    
    def get_objs_per_env(self):
        return len(self._obj_cfgs[0])
    
    def get_root_pos(self, obj_id):
        obj = self._objs[obj_id]
        root_pos = obj.data.root_link_pose_w[:, :3].clone()
        root_pos[:, 0:2] -= self._env_offsets
        return root_pos
    
    def get_root_rot(self, obj_id):
        obj = self._objs[obj_id]
        root_rot_wxyz = obj.data.root_link_pose_w[:, 3:]
        root_rot_xyzw = root_rot_wxyz[:, ROT_WXYZ_TO_XYZW]
        return root_rot_xyzw
    
    def get_root_vel(self, obj_id):
        obj = self._objs[obj_id]
        root_vel = obj.data.root_link_vel_w[:, :3]
        return root_vel
    
    def get_root_ang_vel(self, obj_id):
        obj = self._objs[obj_id]
        root_ang_vel = obj.data.root_link_vel_w[:, 3:]
        return root_ang_vel
    
    def get_dof_pos(self, obj_id):
        obj = self._objs[obj_id]
        dof_pos = obj.data.joint_pos

        dof_order_sim2common = self._dof_order_sim2common[obj_id]
        dof_pos = dof_pos[:, dof_order_sim2common]
        return dof_pos
    
    def get_dof_vel(self, obj_id):
        obj = self._objs[obj_id]
        dof_vel = obj.data.joint_vel

        dof_order_sim2common = self._dof_order_sim2common[obj_id]
        dof_vel = dof_vel[:, dof_order_sim2common]
        return dof_vel
    
    def get_dof_forces(self, obj_id):
        obj = self._objs[obj_id]
        dof_forces = obj.data.applied_torque

        dof_order_sim2common = self._dof_order_sim2common[obj_id]
        dof_forces = dof_forces[:, dof_order_sim2common]
        return dof_forces
    
    def get_body_pos(self, obj_id):
        obj = self._objs[obj_id]
        body_pos = obj.data.body_link_pose_w[:, :, :3].clone()

        body_order_sim2common = self._body_order_sim2common[obj_id]
        body_pos = body_pos[:, body_order_sim2common, :]

        env_offsets = self._env_offsets.unsqueeze(-2)
        body_pos[:, :, 0:2] -= env_offsets
        return body_pos
    
    def get_body_rot(self, obj_id):
        obj = self._objs[obj_id]
        body_rot = obj.data.body_link_pose_w[:, :, 3:]

        body_order_sim2common = self._body_order_sim2common[obj_id]
        body_rot_wxyz = body_rot[:, body_order_sim2common, :]
        body_rot_xyzw = body_rot_wxyz[:, :, ROT_WXYZ_TO_XYZW]
        return body_rot_xyzw
    
    def get_body_vel(self, obj_id):
        obj = self._objs[obj_id]
        body_vel = obj.data.body_link_vel_w[:, :, :3]

        body_order_sim2common = self._body_order_sim2common[obj_id]
        body_vel = body_vel[:, body_order_sim2common, :]
        return body_vel
    
    def get_body_ang_vel(self, obj_id):
        obj = self._objs[obj_id]
        body_ang_vel = obj.data.body_link_vel_w[:, :, 3:]

        body_order_sim2common = self._body_order_sim2common[obj_id]
        body_ang_vel = body_ang_vel[:, body_order_sim2common, :]
        return body_ang_vel
    
    def get_contact_forces(self, obj_id):
        sensor = self._ground_contact_sensors[obj_id]
        forces = sensor.data.net_forces_w
        return forces
    
    def get_ground_contact_forces(self, obj_id):
        sensor = self._ground_contact_sensors[obj_id]
        forces = sensor.data.force_matrix_w
        forces = forces.sum(dim=-2)
        return forces
    
    def set_root_pos(self, env_id, obj_id, root_pos):
        obj = self._objs[obj_id]
        root_pos = root_pos.clone()

        if (env_id is None):
            obj.data.root_link_pose_w[:, :3] = root_pos
            obj.data.root_link_pose_w[:, :2] += self._env_offsets
        else:
            obj.data.root_link_pose_w[env_id, :3] = root_pos
            obj.data.root_link_pose_w[env_id, :2] += self._env_offsets[env_id]
        
        self._flag_obj_needs_reset(env_id, obj_id)
        return
    
    def set_root_rot(self, env_id, obj_id, root_rot):
        obj = self._objs[obj_id]
        root_rot_wxyz = root_rot[..., ROT_XYZW_TO_WXYZ]

        if (env_id is None):
            obj.data.root_link_pose_w[:, 3:] = root_rot_wxyz
        else:
            obj.data.root_link_pose_w[env_id, 3:] = root_rot_wxyz
        
        self._flag_obj_needs_reset(env_id, obj_id)
        return
    
    def set_root_vel(self, env_id, obj_id, root_vel):
        obj = self._objs[obj_id]

        if (env_id is None):
            obj.data.root_link_vel_w[:, :3] = root_vel
        else:
            obj.data.root_link_vel_w[env_id, :3] = root_vel
        
        self._flag_obj_needs_reset(env_id, obj_id)
        return
    
    def set_root_ang_vel(self, env_id, obj_id, root_ang_vel):
        obj = self._objs[obj_id]

        if (env_id is None):
            obj.data.root_link_vel_w[:, 3:] = root_ang_vel
        else:
            obj.data.root_link_vel_w[env_id, 3:] = root_ang_vel
        
        self._flag_obj_needs_reset(env_id, obj_id)
        return
    
    def set_dof_pos(self, env_id, obj_id, dof_pos):
        obj = self._objs[obj_id]

        if (not np.isscalar(dof_pos)):
            dof_order_common2sim = self._dof_order_common2sim[obj_id]
            dof_pos = dof_pos[..., dof_order_common2sim]

        if (env_id is None):
            obj.data.joint_pos[:, :] = dof_pos
        else:
            obj.data.joint_pos[env_id, :] = dof_pos
        
        self._flag_obj_needs_reset(env_id, obj_id)
        return
    
    def set_dof_vel(self, env_id, obj_id, dof_vel):
        obj = self._objs[obj_id]

        if (not np.isscalar(dof_vel)):
            dof_order_common2sim = self._dof_order_common2sim[obj_id]
            dof_vel = dof_vel[..., dof_order_common2sim]

        if (env_id is None):
            obj.data.joint_vel[:, :] = dof_vel
        else:
            obj.data.joint_vel[env_id, :] = dof_vel
        
        self._flag_obj_needs_reset(env_id, obj_id)
        return
    
    def set_body_pos(self, env_id, obj_id, body_pos):
        obj = self._objs[obj_id]
        body_order_common2sim = self._body_order_common2sim[obj_id]
        body_pos = body_pos[..., body_order_common2sim, :]
        
        if (env_id is None):
            obj.data.body_link_pose_w[:, :, :3] = body_pos
            obj.data.body_link_pose_w[:, :, :2] += self._env_offsets.unsqueeze(-2)
        else:
            obj.data.body_link_pose_w[env_id, :, :3] = body_pos
            obj.data.body_link_pose_w[env_id, :, :2] += self._env_offsets[env_id].unsqueeze(-2)

        # don't need to flag reset after setting body states since those 
        # do not directly affect the simulator
        return
    
    def set_body_rot(self, env_id, obj_id, body_rot):
        obj = self._objs[obj_id]
        body_order_common2sim = self._body_order_common2sim[obj_id]
        body_rot = body_rot[..., body_order_common2sim, :]
        body_rot_wxyz = body_rot[..., ROT_XYZW_TO_WXYZ]
        
        if (env_id is None):
            obj.data.body_link_pose_w[:, :, 3:] = body_rot_wxyz
        else:
            obj.data.body_link_pose_w[env_id, :, 3:] = body_rot_wxyz
        return
    
    def set_body_vel(self, env_id, obj_id, body_vel):
        obj = self._objs[obj_id]

        if (not np.isscalar(body_vel)):
            body_order_common2sim = self._body_order_common2sim[obj_id]
            body_vel = body_vel[..., body_order_common2sim, :]
        
        if (env_id is None):
            obj.data.body_link_vel_w[:, :, :3] = body_vel
        else:
            obj.data.body_link_vel_w[env_id, :, :3] = body_vel
        return
    
    def set_body_ang_vel(self, env_id, obj_id, body_ang_vel):
        obj = self._objs[obj_id]
        body_order_common2sim = self._body_order_common2sim[obj_id]

        if (not np.isscalar(body_ang_vel)):
            body_order_common2sim = self._body_order_common2sim[obj_id]
            body_ang_vel = body_ang_vel[..., body_order_common2sim, :]
        
        if (env_id is None):
            obj.data.body_link_vel_w[:, :, 3:] = body_ang_vel
        else:
            obj.data.body_link_vel_w[env_id, :, 3:] = body_ang_vel
        return
    
    def set_body_forces(self, env_id, obj_id, body_id, forces):
        if (env_id is None or len(env_id) > 0):
            assert(len(forces.shape) == 2)
            
            obj = self._objs[obj_id]
            obj_type = self.get_obj_type(obj_id)
            
            if (obj_type == engine.ObjType.articulated):
                forces = forces.unsqueeze(-2)

            torques = torch.zeros_like(forces)
            sim_body_id = self._body_order_sim2common[obj_id][body_id]

            obj.set_external_force_and_torque(forces=forces,
                                              torques=torques,
                                              positions=None,
                                              env_ids=env_id,
                                              body_ids=sim_body_id,
                                              is_global=True)
        return
    
    def get_obj_torque_limits(self, env_id, obj_id):
        obj = self._objs[obj_id]
        torque_lim = obj.root_physx_view.get_dof_max_forces()[env_id]

        dof_order_sim2common = self._dof_order_sim2common[obj_id].cpu()
        torque_lim = torque_lim[dof_order_sim2common]
        return torque_lim.cpu().numpy()
    
    def get_obj_dof_limits(self, env_id, obj_id):
        obj = self._objs[obj_id]
        dof_limits = obj.root_physx_view.get_dof_limits()[env_id]
        dof_low = dof_limits[:, 0]
        dof_high = dof_limits[:, 1]

        dof_order_sim2common = self._dof_order_sim2common[obj_id].cpu()
        dof_low = dof_low[dof_order_sim2common]
        dof_high = dof_high[dof_order_sim2common]

        return dof_low.numpy(), dof_high.numpy()
    
    def find_obj_body_id(self, obj_id, body_name):
        obj = self._objs[obj_id]
        meta_data = obj.root_physx_view.shared_metatype
        body_names = meta_data.link_names
        sim_body_id = body_names.index(body_name)
        body_id = self._body_order_common2sim[obj_id][sim_body_id]
        return  body_id
    
    def get_obj_type(self, obj_id):
        obj_type = self._obj_cfgs[0][obj_id].obj_type
        return obj_type
    
    def get_obj_num_bodies(self, obj_id):
        obj = self._objs[obj_id]
        num_bodies = obj.num_bodies
        return num_bodies
    
    def get_obj_num_dofs(self, obj_id):
        obj_type = self.get_obj_type(obj_id)
        if (obj_type == engine.ObjType.articulated):
            obj = self._objs[obj_id]
            num_dofs = obj.root_physx_view.max_dofs
        else:
            num_dofs = 0
        return num_dofs
    
    def get_obj_body_names(self, obj_id):
        obj = self._objs[obj_id]
        meta_data = obj.root_physx_view.shared_metatype
        body_names = meta_data.link_names
        body_order_sim2common = self._body_order_sim2common[obj_id]

        body_names = [body_names[i] for i in body_order_sim2common.tolist()]
        return body_names
    
    def calc_obj_mass(self, env_id, obj_id):
        obj = self._objs[obj_id]
        masses = obj.root_physx_view.get_masses()[env_id]
        total_mass = masses.sum().item()
        return total_mass
    
    def get_control_mode(self):
        return self._control_mode
    
    def draw_lines(self, env_id, start_verts, end_verts, cols, line_width):
        env_offset = self._env_offsets[env_id].cpu().numpy()
        start_pts = start_verts.copy()
        end_pts = end_verts.copy()

        start_pts[:, :2] += env_offset
        end_pts[:, :2] += env_offset
        line_widths = [line_width] * start_pts.shape[0]

        self._draw_interface.draw_lines(start_pts.tolist(), end_pts.tolist(), cols.tolist(), line_widths)
        return

    def register_keyboard_callback(self, key_str, callback_func):
        key_code = str_to_key_code(key_str)
        assert(key_code not in self._keyboard_callbacks)
        self._keyboard_callbacks[key_code] = callback_func
        return

    def _build_ground(self):
        import isaaclab.sim as sim_utils
        from isaaclab.sim.spawners.from_files import GroundPlaneCfg, spawn_ground_plane
        import omni.kit.commands
        from pxr import UsdPhysics

        ground_col = np.array([1.0, 0.9, 0.75])
        ground_col *= 0.017
        ground_path = GROUND_PATH

        physics_material = sim_utils.RigidBodyMaterialCfg(static_friction=1.0, dynamic_friction=1.0,
                                                          restitution=0.0)
        plane_cfg = GroundPlaneCfg(physics_material=physics_material, color=ground_col)
        self._ground = spawn_ground_plane(prim_path=ground_path, cfg=plane_cfg)
        try:
            from isaacsim.core.utils.semantics import add_update_semantics

            add_update_semantics(self._stage.GetPrimAtPath(ground_path), "mimickit_ground", "class")
        except Exception:
            pass

        # add rigid body schema to terrain to enable contact sensors
        UsdPhysics.RigidBodyAPI.Apply(self._stage.GetPrimAtPath(ground_path))
        UsdPhysics.RigidBodyAPI.Get(self._stage, ground_path).GetKinematicEnabledAttr().Set(True)

        shader_path = ground_path + "/Looks/theGrid/Shader"
        shader_prim = self._stage.GetPrimAtPath(shader_path)
        shader_prim.GetAttribute("inputs:albedo_add").Set(10.0)
        return
    
    def _compute_env_offsets(self, num_envs):
        env_ids = torch.arange(num_envs, device=self._device)

        num_rows = int(np.ceil(np.sqrt(num_envs)))
        num_cols = int(np.ceil(num_envs / num_rows))
        col = torch.floor(env_ids / num_rows)
        row = torch.remainder(env_ids, num_rows)

        env_spacing = self._get_env_spacing()
        row_offset = 0.5 * env_spacing * (num_rows - 1)
        col_offset = 0.5 * env_spacing * (num_cols - 1)

        offsets = torch.zeros([num_envs, 2], device=self._device, dtype=torch.float)
        offsets[:, 0] = row * env_spacing - row_offset
        offsets[:, 1] = col * env_spacing - col_offset
        return offsets
    
    def _build_lights(self):
        import isaaclab.sim as sim_utils
        import isaacsim.core.utils.prims as prim_utils
        from pxr import Gf

        light_quat = torch_util.euler_xyz_to_quat(torch.tensor(0.7),
                                                  torch.tensor(0.0), 
                                                  torch.tensor(0.6))
        light_quat = light_quat.tolist()
        distant_light_path = LIGHT_PATH + "/distant_light_xform"
        light_xform = prim_utils.create_prim(distant_light_path, "Xform")

        gf_quatf = Gf.Quatd()
        gf_quatf.SetReal(light_quat[-1])
        gf_quatf.SetImaginary(tuple(light_quat[:-1]))
        light_xform.GetAttribute("xformOp:orient").Set(gf_quatf)

        distant_light_cfg = sim_utils.DistantLightCfg(intensity=2000.0, color=(0.8, 0.8, 0.8))
        self._distant_light = distant_light_cfg.func(distant_light_path + "/distant_light", distant_light_cfg)

        dome_light_cfg = sim_utils.DomeLightCfg(intensity=800.0, color=(0.7, 0.7, 0.7))
        self._dome_light = dome_light_cfg.func(LIGHT_PATH + "/dome_light", dome_light_cfg)
        return
    
    def _build_camera(self):
        enable_kit_extension("omni.kit.viewport.utility")
        from omni.kit.viewport.utility.camera_state import ViewportCameraState
        self._camera_state = ViewportCameraState("/OmniverseKit_Persp")
        return
    
    def _build_draw_interface(self):
        enable_kit_extension("isaacsim.util.debug_draw")
        from isaacsim.util.debug_draw import _debug_draw
        self._draw_interface = _debug_draw.acquire_debug_draw_interface()
        return
    
    def _setup_keyboard(self):
        import omni
        enable_kit_extension("omni.appwindow")
        import omni.appwindow

        self._input = carb.input.acquire_input_interface()
        self._keyboard = omni.appwindow.get_default_app_window().get_keyboard()
        self._sub_keyboard = self._input.subscribe_to_keyboard_events(self._keyboard, self._on_keyboard_event)

        self._keyboard_callbacks = dict()
        return
    
    def _create_simulator(self, sim_timestep, visualize):
        # Sequence rendering in WSL/headless sessions should use Isaac Lab's
        # offscreen rendering experience instead of a viewport-backed window.
        viewer_headless = os.getenv("MIMICKIT_VIEWER_HEADLESS", "0") == "1"
        headless_render = visualize and viewer_headless
        launcher_cfg = {
            "headless": (not visualize) or headless_render,
            "device": self._device,
            "enable_cameras": visualize,
            # Our MimicKit paths run a single render/sim device at a time.
            # Explicitly disable multi-GPU so Isaac Sim does not probe all
            # adapters in WSL dual-GPU setups and mis-detect duplicate ICDs.
            "multi_gpu": False,
            "kit_args": '--/app/extensions/excluded=["omni.physx.fabric"]',
        }
        if headless_render:
            launcher_cfg["experience"] = "isaaclab.python.headless.rendering.kit"

        self._app_launcher = AppLauncher(launcher_cfg)

        import isaaclab.sim as sim_utils
        from isaacsim.core.utils.stage import get_current_stage
        
        sim_cfg = sim_utils.SimulationCfg(device=self._device, dt=sim_timestep,
                                          render_interval=self._sim_steps)
        sim_cfg.use_fabric = False
        
        sim_cfg.physx.bounce_threshold_velocity = 0.2
        sim_cfg.physx.max_position_iteration_count = 4
        sim_cfg.physx.max_velocity_iteration_count = 0
        sim_cfg.physx.gpu_max_rigid_contact_count = 8 * 1024 * 1024
        sim_cfg.physics_material.static_friction = 1.0
        sim_cfg.physics_material.dynamic_friction = 1.0
        
        self._sim = sim_utils.SimulationContext(sim_cfg)
        self._stage = get_current_stage()
        
        # disable delays during rendering
        carb_settings = carb.settings.get_settings()
        carb_settings.set_bool("/app/runLoops/main/rateLimitEnabled", False)
        return
    
    def _get_env_spacing(self):
        return self._env_spacing
    
    def _parse_usd_path(self, asset_file):
        asset_root, asset_ext = os.path.splitext(asset_file)
        if (asset_ext != "usd" and asset_ext != "usda"):
            asset_file = asset_root + ".usd"
        return asset_file
    
    def _build_actuator_cfg(self, control_mode):
        from isaaclab.actuators import ImplicitActuatorCfg, IdealPDActuatorCfg

        if (control_mode == engine.ControlMode.none):
            actuator_cfg = IdealPDActuatorCfg(joint_names_expr=[".*"], stiffness=0, damping=0, effort_limit=0)
        elif (control_mode == engine.ControlMode.pos):
            actuator_cfg = ImplicitActuatorCfg(joint_names_expr=[".*"], stiffness=None, damping=None, effort_limit=None)
        elif (control_mode == engine.ControlMode.vel):
            actuator_cfg = ImplicitActuatorCfg(joint_names_expr=[".*"], stiffness=0, damping=None, effort_limit=None)
        elif (control_mode == engine.ControlMode.torque):
            actuator_cfg = IdealPDActuatorCfg(joint_names_expr=[".*"], stiffness=0, damping=0, effort_limit=None)
        elif (control_mode == engine.ControlMode.pd_explicit):
            actuator_cfg = IdealPDActuatorCfg(joint_names_expr=[".*"], stiffness=None, damping=None, effort_limit=None)
        else:
            assert(False), "Unsupported control mode: {}".format(self._control_mode)

        return actuator_cfg

    def _pre_sim_step(self):
        num_objs = self.get_objs_per_env()
        for obj_id in range(num_objs):
            obj = self._objs[obj_id]
            obj.write_data_to_sim()
        return

    def _sim_step(self):
        self._sim.step(render=False)
        return

    def _post_sim_step(self):
        sim_timestep = self.get_sim_timestep()
        
        for obj in self._objs:
            obj.update(sim_timestep)
            
        for sensor in self._ground_contact_sensors:
            if (sensor is not None):
                sensor.update(sim_timestep)
        return

    def _clear_forces(self):
        for obj in self._objs:
            if (obj.has_external_wrench):
                forces = torch.zeros([1, 3], dtype=torch.float, device=self._device)
                torques = torch.zeros([1, 3], dtype=torch.float, device=self._device)
                obj.set_external_force_and_torque(forces=forces, torques=torques,
                                                  positions=None, env_ids=None,
                                                  body_ids=None, is_global=True)
        return
    
    def _validate_envs(self):
        num_envs = self.get_num_envs()
        objs_per_env = self.get_objs_per_env()

        for i in range(0, num_envs):
            curr_objs = self._obj_cfgs[i]
            num_objs = len(curr_objs)
            assert(num_objs == objs_per_env), "All envs must have the same number of objects."
        return
    
    def _build_envs(self):
        num_envs = self.get_num_envs()
        source_env_path = ENV_PATH_TEMPLATE.format(0)
        self._stage.DefinePrim(source_env_path, "Xform")

        clone_paths = [ENV_PATH_TEMPLATE.format(i) for i in range(1, num_envs)]
        self._cloner.clone(source_prim_path=source_env_path,
                           prim_paths=clone_paths,
                           replicate_physics=False,
                           copy_from_source=True)
        return
    
    def _build_objs(self):
        self._objs = []
        objs_per_env = self.get_objs_per_env()

        for obj_id in range(objs_per_env):
            obj = self._build_obj(obj_id)
            self._objs.append(obj)
        return
    
    def _build_obj(self, obj_id):
        num_envs = self.get_num_envs()
        created = [False for i in range(num_envs)]
        num_created = 0

        for env_id in range(num_envs):
            if (not created[env_id]):
                obj_cfg = self._obj_cfgs[env_id][obj_id]
                asset_file = obj_cfg.asset_file
                clone_envs = []

                for j in range(env_id + 1, num_envs):
                    if (not created[j]):
                        other_obj_cfg = self._obj_cfgs[j][obj_id]
                        other_asset_file = other_obj_cfg.asset_file

                        if (other_asset_file == asset_file):
                            assert(obj_cfg.is_valid_clone(other_obj_cfg)), "Cloning requires all objects that share the same asset file to have the same configurations."
                            clone_envs.append(j)
                
                self._build_obj_prim(env_id=env_id, obj_id=obj_id, obj_cfg=obj_cfg)
                created[env_id] = True
                
                num_clones = len(clone_envs)
                if (num_clones > 0):
                    self._clone_obj_prim(source_env_id=env_id, obj_id=obj_id, clone_env_ids=clone_envs)

                    for clone_env_id in clone_envs:
                        created[clone_env_id] = True
                
                num_created += num_clones + 1
                Logger.print("Building Obj:{:d} in {:d}/{:d} envs".format(obj_id, num_created, num_envs), end='\r')

        Logger.print("")

        # build a object to wrap all of the objects in the parallel envs
        obj_cfg = self._obj_cfgs[0][obj_id]
        multi_obj_prim = self._build_multi_obj_prim(obj_id, obj_cfg)

        return multi_obj_prim
    
    def _build_obj_prim(self, env_id, obj_id, obj_cfg):
        obj_type = obj_cfg.obj_type
        if (obj_type == engine.ObjType.rigid):
            multi_obj_prim = self._build_rigid_prim(env_id, obj_id, obj_cfg)
        elif (obj_type == engine.ObjType.articulated):
            multi_obj_prim = self._build_articulated_prim(env_id, obj_id, obj_cfg)
        else:
            assert(False), "Unsupported obj type: {}".format(obj_type.name)
        return multi_obj_prim

    def _build_rigid_prim(self, env_id, obj_id, obj_cfg):
        import isaaclab.sim as sim_utils
        from isaaclab.assets import RigidObject, RigidObjectCfg
        
        color = obj_cfg.color
        if (color is not None):
            visual_material = sim_utils.PreviewSurfaceCfg(diffuse_color=(color[0], color[1], color[2]), metallic=0.5)
        else:
            visual_material = None

        rigid_props = sim_utils.RigidBodyPropertiesCfg(kinematic_enabled=obj_cfg.fix_root,
                                                       max_depenetration_velocity=10.0,
                                                       angular_damping=0.01,
                                                       max_linear_velocity=1000.0,
                                                       max_angular_velocity=1000.0)
        usd_asset_file = self._parse_usd_path(obj_cfg.asset_file)
        usd_cfg = sim_utils.UsdFileCfg(usd_path=usd_asset_file, 
                                       visual_material=visual_material, 
                                       rigid_props=rigid_props)
        
        prim_path = OBJ_PATH_TEMPLATE.format(env_id, obj_id)
        init_state = RigidObjectCfg.InitialStateCfg(pos=obj_cfg.start_pos, rot=obj_cfg.start_rot)
        
        rigid_cfg = RigidObjectCfg(prim_path=prim_path, spawn=usd_cfg, collision_group=0,
                                 init_state=init_state)
        prim = RigidObject(rigid_cfg)

        if (obj_cfg.is_visual):
            self._disable_prim_collisions(prim_path)

        return prim
    
    def _build_articulated_prim(self, env_id, obj_id, obj_cfg):
        import isaaclab.sim as sim_utils
        from isaaclab.assets import Articulation, ArticulationCfg

        color = obj_cfg.color
        if (color is not None):
            visual_material = sim_utils.PreviewSurfaceCfg(diffuse_color=(color[0], color[1], color[2]), metallic=0.5)
        else:
            visual_material = None

        articulation_props = sim_utils.ArticulationRootPropertiesCfg(
                    enabled_self_collisions=obj_cfg.enable_self_collisions, 
                    fix_root_link=obj_cfg.fix_root)
        
        rigid_props = sim_utils.RigidBodyPropertiesCfg(max_depenetration_velocity=10.0,
                                                       angular_damping=0.01,
                                                       max_linear_velocity=1000.0,
                                                       max_angular_velocity=1000.0)
        usd_asset_file = self._parse_usd_path(obj_cfg.asset_file)
        usd_cfg = sim_utils.UsdFileCfg(usd_path=usd_asset_file, 
                                       visual_material=visual_material,
                                       articulation_props=articulation_props,
                                       rigid_props=rigid_props,
                                       semantic_tags=[("class", "mimickit_character")],
                                       activate_contact_sensors=True)

        if (obj_cfg.disable_motors):
            control_mode = engine.ControlMode.none
        else:
            control_mode = self.get_control_mode()

        actuator_cfg = self._build_actuator_cfg(control_mode)

        prim_path = OBJ_PATH_TEMPLATE.format(env_id, obj_id)
        init_state = ArticulationCfg.InitialStateCfg(pos=obj_cfg.start_pos, rot=obj_cfg.start_rot)
        
        art_cfg = ArticulationCfg(prim_path=prim_path, spawn=usd_cfg, collision_group=0,
                                  init_state=init_state,
                                  actuator_value_resolution_debug_print=False,
                                  actuators={"actuators": actuator_cfg})
        prim = Articulation(art_cfg)

        if (obj_cfg.is_visual):
            self._disable_prim_collisions(prim_path)

        return prim
    
    def _build_multi_obj_prim(self, obj_id, obj_cfg):
        obj_type = obj_cfg.obj_type
        if (obj_type == engine.ObjType.rigid):
            multi_obj_prim = self._build_multi_rigid_prim(obj_id)
        elif (obj_type == engine.ObjType.articulated):
            multi_obj_prim = self._build_multi_articulated_prim(obj_id, obj_cfg)
        else:
            assert(False), "Unsupported obj type: {}".format(obj_type.name)
        return multi_obj_prim

    def _build_multi_rigid_prim(self, obj_id):
        from isaaclab.assets import RigidObject, RigidObjectCfg

        regex = OBJ_PATH_TEMPLATE.format(".*", obj_id)
        multi_obj_cfg = RigidObjectCfg(prim_path=regex, spawn=None)
        multi_obj_prim = RigidObject(multi_obj_cfg)

        return multi_obj_prim

    def _build_multi_articulated_prim(self, obj_id, obj_cfg):
        from isaaclab.assets import Articulation, ArticulationCfg

        if (obj_cfg.disable_motors):
            control_mode = engine.ControlMode.none
        else:
            control_mode = self.get_control_mode()

        actuator_cfg = self._build_actuator_cfg(control_mode)

        regex = OBJ_PATH_TEMPLATE.format(".*", obj_id)
        multi_obj_cfg = ArticulationCfg(prim_path=regex, spawn=None, actuators={"actuators": actuator_cfg})
        multi_obj_prim = Articulation(multi_obj_cfg)

        return multi_obj_prim
    
    def _clone_obj_prim(self, source_env_id, obj_id, clone_env_ids):
        clone_paths = []
        clone_positions = []
        clone_rotations = []

        for clone_env_id in clone_env_ids:
            clone_cfg = self._obj_cfgs[clone_env_id][obj_id]
            clone_rot = clone_cfg.start_rot
            clone_pos = clone_cfg.start_pos

            clone_path = OBJ_PATH_TEMPLATE.format(clone_env_id, obj_id)
            clone_paths.append(clone_path)
            clone_positions.append(clone_pos)
            clone_rotations.append(clone_rot)

        clone_positions = np.stack(clone_positions)
        clone_rotations = np.stack(clone_rotations)
        
        source_path = OBJ_PATH_TEMPLATE.format(source_env_id, obj_id)
        self._cloner.clone(source_prim_path=source_path,
                           prim_paths=clone_paths,
                           positions=clone_positions,
                           orientations=clone_rotations,
                           copy_from_source=True)
        return
    
    def _disable_prim_collisions(self, prim_path):
        import isaaclab.sim as sim_utils

        child_prims = sim_utils.get_all_matching_child_prims(prim_path, traverse_instance_prims=True)
        for col_prim in child_prims:
            if (col_prim.IsInstanceable()):
                col_prim.SetInstanceable(False)

        collision_props = sim_utils.CollisionPropertiesCfg(collision_enabled=False)
        sim_utils.schemas.modify_collision_properties(prim_path, collision_props)
        return
    
    def _build_order_tensors(self):
        self._body_order_sim2common = []
        self._body_order_common2sim = []
        self._dof_order_sim2common = []
        self._dof_order_common2sim = []

        objs_per_env = self.get_objs_per_env()
        for obj_id in range(objs_per_env):
            obj_type = self.get_obj_type(obj_id)
            if (obj_type == engine.ObjType.articulated):
                obj = self._objs[obj_id]
                body_order_sim2common, body_order_common2sim, dof_order_sim2common, dof_order_common2sim = self._build_body_order(obj)

                body_order_sim2common = torch.tensor(body_order_sim2common, device=self._device, dtype=torch.long)
                body_order_common2sim = torch.tensor(body_order_common2sim, device=self._device, dtype=torch.long)
                dof_order_sim2common = torch.tensor(dof_order_sim2common, device=self._device, dtype=torch.long)
                dof_order_common2sim = torch.tensor(dof_order_common2sim, device=self._device, dtype=torch.long)
            else:
                body_order_sim2common = torch.zeros(1, device=self._device, dtype=torch.long)
                body_order_common2sim = torch.zeros(1, device=self._device, dtype=torch.long)
                dof_order_sim2common = torch.zeros(1, device=self._device, dtype=torch.long)
                dof_order_common2sim = torch.zeros(1, device=self._device, dtype=torch.long)
            
            self._body_order_sim2common.append(body_order_sim2common)
            self._body_order_common2sim.append(body_order_common2sim)
            self._dof_order_sim2common.append(dof_order_sim2common)
            self._dof_order_common2sim.append(dof_order_common2sim)

        return
    
    def _build_ground_contact_sensors(self):
        from isaaclab.sensors import ContactSensorCfg, ContactSensor

        ground_prim_paths = [GROUND_PATH + ".*"]
        
        self._ground_contact_sensors = []
        objs_per_env = self.get_objs_per_env()
        timestep = self.get_timestep()

        for obj_id in range(objs_per_env):
            # find child primitive that contains ContactReportAPI
            obj_path = OBJ_PATH_TEMPLATE.format(0, obj_id)
            contact_prim_path = self._find_contact_prim_path(obj_path)

            if (contact_prim_path is not None):
                contact_prim_name = os.path.basename(contact_prim_path)
                sensor_regex = OBJ_PATH_TEMPLATE.format(".*", obj_id) + "/{:s}/.*".format(contact_prim_name)

                sensor_cfg = ContactSensorCfg(prim_path=sensor_regex, 
                                              update_period=timestep,
                                              filter_prim_paths_expr=ground_prim_paths)
                sensor = ContactSensor(sensor_cfg)
            else:
                sensor = None
        
            self._ground_contact_sensors.append(sensor)
        return
    
    def _build_body_order(self, obj):
        meta_data = obj.root_physx_view.shared_metatype
        link_names = list(meta_data.link_names)
        required_body_order_raw = os.environ.get("MIMICKIT_REQUIRED_BODY_ORDER_JSON", "").strip()
        required_body_order = []
        if required_body_order_raw:
            try:
                parsed_body_order = json.loads(required_body_order_raw)
                if isinstance(parsed_body_order, list):
                    required_body_order = [str(name) for name in parsed_body_order]
            except Exception as exc:
                raise RuntimeError(f"invalid MIMICKIT_REQUIRED_BODY_ORDER_JSON: {exc}") from exc

        # Isaac Sim exposes slightly different metatype field names across versions.
        if hasattr(meta_data, "link_parent_indices"):
            link_parent_indices = meta_data.link_parent_indices
        elif hasattr(meta_data, "link_parents"):
            link_parent_indices = meta_data.link_parents
        else:
            link_parent_indices = None

        if hasattr(meta_data, "joint_dof_counts"):
            joint_dof_counts = list(meta_data.joint_dof_counts)
        elif hasattr(meta_data, "dof_counts"):
            joint_dof_counts = list(meta_data.dof_counts)
        else:
            raise AttributeError("Unsupported Isaac Sim metatype: missing joint dof counts")

        if hasattr(meta_data, "joint_dof_offsets"):
            joint_dof_offsets = list(meta_data.joint_dof_offsets)
        elif hasattr(meta_data, "dof_offsets"):
            joint_dof_offsets = list(meta_data.dof_offsets)
        else:
            raise AttributeError("Unsupported Isaac Sim metatype: missing joint dof offsets")

        num_links = len(link_names)
        if required_body_order:
            if len(required_body_order) != num_links or set(required_body_order) != set(link_names):
                raise RuntimeError(
                    "required body order does not exactly match IsaacLab articulation: "
                    f"required={required_body_order} sim={link_names}"
                )
            body_order_sim2common = [link_names.index(name) for name in required_body_order]
            Logger.print(f"[BRIDGE] Applied explicit body order mapping: {required_body_order}")
        elif link_parent_indices is None:
            # Isaac Sim 4.5 metatype does not expose parent indices.
            # Try to recover mapping from link name -> simulator link id.
            body_order_sim2common = []
            if hasattr(meta_data, "link_indices"):
                link_indices = meta_data.link_indices
                if isinstance(link_indices, dict):
                    body_order_sim2common = [int(link_indices[name]) for name in link_names if name in link_indices]
                else:
                    try:
                        # Some bindings expose this as array-like aligned to link_names.
                        body_order_sim2common = [int(i) for i in list(link_indices)]
                    except Exception:
                        body_order_sim2common = []

            # Final fallback: simulator-native link ordering.
            if len(body_order_sim2common) != num_links:
                body_order_sim2common = list(range(num_links))
        else:
            link_children = [[] for i in range(num_links)]

            root_link_id = 0
            if isinstance(link_parent_indices, dict):
                for link_id, link_name in enumerate(link_names):
                    if link_name not in link_parent_indices:
                        continue
                    parent_id = int(link_parent_indices[link_name])
                    if parent_id >= 0:
                        link_children[parent_id].append(link_id)
                    else:
                        root_link_id = link_id
            else:
                link_parent_indices = list(link_parent_indices)
                for link_id, parent_id in enumerate(link_parent_indices):
                    parent_id = int(parent_id)
                    if parent_id >= 0:
                        link_children[parent_id].append(link_id)
                    else:
                        root_link_id = link_id

            body_order_sim2common = []

            def _dfs_children_links(link_id):
                body_order_sim2common.append(link_id)
                child_ids = link_children[link_id]
                for child_id in child_ids:
                    _dfs_children_links(child_id)

            _dfs_children_links(root_link_id)

        dof_order_sim2common = []
        for link_id in body_order_sim2common[1:]:
            # Some versions expose dof arrays indexed by link_id - 1 (excluding root),
            # while others are indexed directly by link_id.
            joint_idx = link_id - 1
            if joint_idx >= len(joint_dof_offsets):
                joint_idx = link_id
            if joint_idx < 0 or joint_idx >= len(joint_dof_offsets):
                continue

            dof_offset = int(joint_dof_offsets[joint_idx])
            dof_count = int(joint_dof_counts[joint_idx])
            dof_indices = list(range(dof_offset, dof_offset + dof_count))
            dof_order_sim2common += dof_indices

        body_order_common2sim = [body_order_sim2common.index(i) for i in range(len(body_order_sim2common))]
        dof_order_common2sim = [dof_order_sim2common.index(i) for i in range(len(dof_order_sim2common))]

        return body_order_sim2common, body_order_common2sim, dof_order_sim2common, dof_order_common2sim

    def _build_sim_tensors(self):
        num_envs = self.get_num_envs()
        num_objs = self.get_objs_per_env()
        self._objs_need_reset = torch.zeros([num_envs, num_objs], device=self._device, dtype=torch.bool)
        return
    
    def _filter_env_collisions(self):
        num_envs = self.get_num_envs()
        physics_scene_path = self._physics_scene_path()
        env_prim_paths = [ENV_PATH_TEMPLATE.format(i) for i in range(num_envs)]

        self._cloner.filter_collisions(physics_scene_path, "/World/collisions",
                                       env_prim_paths, global_paths=[])
        return
    
    def _flag_obj_needs_reset(self, env_id, obj_id):
        if (env_id is None):
            self._objs_need_reset[:, obj_id] = True
        elif (len(env_id) > 0):
            self._objs_need_reset[env_id, obj_id] = True
        return
    
    def _update_reset_objs(self):
        num_objs = self.get_objs_per_env()

        for obj_id in range(num_objs):
            reset_flags = self._objs_need_reset[:, obj_id]
            env_ids = reset_flags.nonzero(as_tuple=False)
            env_ids = env_ids.type(torch.int32).flatten()

            if (len(env_ids) > 0):
                self._reset_obj(obj_id, env_ids)
                self._objs_need_reset[:, obj_id] = False
        return
    
    def _reset_obj(self, obj_id, env_ids):
        obj = self._objs[obj_id]
        obj_type = self.get_obj_type(obj_id)

        root_pose_data = obj.data.root_link_pose_w[env_ids]
        root_vel_data = obj.data.root_link_vel_w[env_ids]
        obj.write_root_link_pose_to_sim(root_pose_data, env_ids)
        obj.write_root_link_velocity_to_sim(root_vel_data, env_ids)

        if (obj_type == engine.ObjType.articulated):
            dof_pos_data = obj.data.joint_pos[env_ids]
            dof_vel_data = obj.data.joint_vel[env_ids]
            obj.write_joint_position_to_sim(dof_pos_data, env_ids=env_ids)
            obj.write_joint_velocity_to_sim(dof_vel_data, env_ids=env_ids)

        obj.reset(env_ids)

        ground_contact_sensor = self._ground_contact_sensors[obj_id]
        if (ground_contact_sensor is not None):
            ground_contact_sensor.reset(env_ids)
        return
    
    def _physics_scene_path(self):
        from pxr import PhysxSchema

        physics_scene_path = None
        for prim in self._stage.Traverse():
            if prim.HasAPI(PhysxSchema.PhysxSceneAPI):
                physics_scene_path = prim.GetPrimPath().pathString
                break

        if (physics_scene_path is None):
            assert(False), "No physics scene found! Please make sure one exists."
        
        return physics_scene_path
    
    def _find_contact_prim_path(self, obj_path):
        from pxr import PhysxSchema

        obj_prim = self._stage.GetPrimAtPath(obj_path)
        prim_children = obj_prim.GetAllChildren()
                
        contact_prim_path = None
        for prim_child in prim_children:
            prim_grandchildren = prim_child.GetAllChildren()
                
            if (len(prim_grandchildren) > 0):
                prim_grandchild = prim_grandchildren[0]
                has_contact_api = prim_grandchild.HasAPI(PhysxSchema.PhysxContactReportAPI)
                    
                if (has_contact_api):
                    contact_prim_path = prim_child.GetPrimPath().pathString
                    break
        
        return contact_prim_path
    
    def _on_keyboard_event(self, event):
        if (event.type == carb.input.KeyboardEventType.KEY_PRESS):
            if (event.input in self._keyboard_callbacks):
                callback = self._keyboard_callbacks[event.input]
                callback()
        return
