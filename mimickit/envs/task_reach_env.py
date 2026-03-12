import numpy as np
import torch

import engines.engine as engine
import envs.base_env as base_env
import envs.task_amp_env as task_amp_env
import util.torch_util as torch_util


class TaskReachEnv(task_amp_env.TaskAMPEnv):
    def __init__(self, env_config, engine_config, num_envs, device, visualize):
        self._tar_speed = float(env_config["tar_speed"])
        self._tar_change_time_min = float(env_config["tar_change_time_min"])
        self._tar_change_time_max = float(env_config["tar_change_time_max"])
        self._tar_dist_max = float(env_config["tar_dist_max"])
        self._tar_height_min = float(env_config["tar_height_min"])
        self._tar_height_max = float(env_config["tar_height_max"])
        self._reach_body_name = env_config["reach_body_name"]

        super().__init__(env_config=env_config, engine_config=engine_config,
                         num_envs=num_envs, device=device, visualize=visualize)
        return

    def _build_envs(self, config, num_envs):
        if (self._visualize):
            self._marker_ids = []
        super()._build_envs(config, num_envs)
        return

    def _build_env(self, env_id, config):
        super()._build_env(env_id, config)
        if (self._visualize):
            marker_id = self._build_marker(env_id)
            if (env_id == 0):
                self._marker_ids.append(marker_id)
            else:
                assert(self._marker_ids[0] == marker_id)
        return

    def _build_marker(self, env_id):
        return self._engine.create_obj(env_id=env_id,
                                       obj_type=engine.ObjType.rigid,
                                       asset_file="data/assets/objects/location_marker.xml",
                                       name="reach_marker",
                                       is_visual=True,
                                       fix_root=True,
                                       color=[0.8, 0.0, 0.0])

    def _build_sim_tensors(self, config):
        super()._build_sim_tensors(config)
        num_envs = self.get_num_envs()
        self._tar_pos = torch.zeros([num_envs, 3], device=self._device, dtype=torch.float32)
        self._tar_change_times = torch.zeros([num_envs], device=self._device, dtype=torch.float32)

        char_id = self._get_char_id()
        self._reach_body_id = self._engine.find_obj_body_id(char_id, self._reach_body_name)
        assert(self._reach_body_id != -1), "Unknown reach body: {}".format(self._reach_body_name)
        return

    def _pre_physics_step(self, actions):
        super()._pre_physics_step(actions)
        return

    def _get_marker_id(self):
        return self._marker_ids[0]

    def _update_marker(self, env_ids):
        marker_id = self._get_marker_id()
        rot = torch.tensor([0.0, 0.0, 0.0, 1.0], device=self._device, dtype=torch.float32)

        self._engine.set_root_pos(env_ids, marker_id, self._tar_pos[env_ids])
        self._engine.set_root_rot(env_ids, marker_id, rot)
        self._engine.set_root_vel(env_ids, marker_id, 0.0)
        self._engine.set_root_ang_vel(env_ids, marker_id, 0.0)
        return

    def _update_task(self):
        reset_task_mask = self._time_buf >= self._tar_change_times
        reset_env_ids = reset_task_mask.nonzero(as_tuple=False).flatten()
        if (len(reset_env_ids) > 0):
            self._reset_task(reset_env_ids)
        return

    def _reset_envs(self, env_ids):
        super()._reset_envs(env_ids)
        if (len(env_ids) > 0):
            self._reset_task(env_ids)
        return

    def _reset_task(self, env_ids):
        self._reset_tar(env_ids)

        rand_dt = torch.rand(env_ids.shape[0], device=self._device, dtype=torch.float32)
        rand_dt = (self._tar_change_time_max - self._tar_change_time_min) * rand_dt + self._tar_change_time_min
        self._tar_change_times[env_ids] = self._time_buf[env_ids] + rand_dt

        if (self._visualize):
            self._update_marker(env_ids)
        return

    def _reset_tar(self, env_ids):
        char_id = self._get_char_id()
        root_pos = self._engine.get_root_pos(char_id)
        char_root_pos = root_pos[env_ids]

        rand_pos = torch.rand([env_ids.shape[0], 3], device=self._device, dtype=torch.float32)
        rand_pos[..., 0:2] = self._tar_dist_max * (2.0 * rand_pos[..., 0:2] - 1.0)
        rand_pos[..., 2] = (self._tar_height_max - self._tar_height_min) * rand_pos[..., 2] + self._tar_height_min
        rand_pos[..., 0:2] += char_root_pos[..., 0:2]

        self._tar_pos[env_ids] = rand_pos
        return

    def _compute_obs(self, env_ids=None):
        obs = super()._compute_obs(env_ids)

        char_id = self._get_char_id()
        char_root_pos = self._engine.get_root_pos(char_id)
        char_root_rot = self._engine.get_root_rot(char_id)
        tar_pos = self._tar_pos

        if (env_ids is not None):
            char_root_pos = char_root_pos[env_ids]
            char_root_rot = char_root_rot[env_ids]
            tar_pos = tar_pos[env_ids]

        task_obs = compute_reach_observations(char_root_pos, char_root_rot, tar_pos)
        return torch.cat([obs, task_obs], dim=-1)

    def _update_reward(self):
        char_id = self._get_char_id()
        body_pos = self._engine.get_body_pos(char_id)
        reach_body_pos = body_pos[:, self._reach_body_id, :]
        self._reward_buf[:] = compute_reach_reward(reach_body_pos, self._tar_pos)
        return

    def _update_misc(self):
        super()._update_misc()
        self._update_task()
        return

    def _update_done(self):
        super()._update_done()
        char_id = self._get_char_id()
        body_pos = self._engine.get_body_pos(char_id)
        reach_body_pos = body_pos[:, self._reach_body_id, :]
        success = torch.norm(self._tar_pos - reach_body_pos, dim=-1) < 0.15
        active = self._done_buf == base_env.DoneFlags.NULL.value
        self._done_buf[torch.logical_and(success, active)] = base_env.DoneFlags.SUCC.value
        return

    def _render_scene(self):
        super()._render_scene()
        self._render_reach_lines()
        return

    def _render_reach_lines(self):
        line_width = 2.0
        col = np.array([[1.0, 0.0, 0.0, 0.5]], dtype=np.float32)

        char_id = self._get_char_id()
        body_pos = self._engine.get_body_pos(char_id)
        starts = body_pos[:, self._reach_body_id, :].cpu().numpy()
        ends = self._tar_pos.cpu().numpy()

        for i in range(self.get_num_envs()):
            self._engine.draw_lines(i, starts[i:i + 1], ends[i:i + 1], col, line_width)
        return


@torch.jit.script
def compute_reach_observations(root_pos, root_rot, tar_pos):
    # type: (Tensor, Tensor, Tensor) -> Tensor
    heading_rot = torch_util.calc_heading_quat_inv(root_rot)
    local_tar_pos = torch_util.quat_rotate(heading_rot, tar_pos - root_pos)
    return local_tar_pos


@torch.jit.script
def compute_reach_reward(reach_body_pos, tar_pos):
    # type: (Tensor, Tensor) -> Tensor
    pos_err_scale = 4.0
    pos_diff = tar_pos - reach_body_pos
    pos_err = torch.sum(pos_diff * pos_diff, dim=-1)
    pos_reward = torch.exp(-pos_err_scale * pos_err)
    success = pos_err < 0.15 * 0.15
    pos_reward = torch.where(success, torch.ones_like(pos_reward), pos_reward)
    return pos_reward
