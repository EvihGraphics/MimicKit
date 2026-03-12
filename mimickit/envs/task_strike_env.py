import numpy as np
import torch

import engines.engine as engine
import envs.base_env as base_env
import envs.task_amp_env as task_amp_env
import util.torch_util as torch_util


class TaskStrikeEnv(task_amp_env.TaskAMPEnv):
    def __init__(self, env_config, engine_config, num_envs, device, visualize):
        self._strike_body_names = env_config["strike_body_names"]
        self._tar_dist_min = float(env_config.get("tar_dist_min", 0.5))
        self._tar_dist_max = float(env_config.get("tar_dist_max", 10.0))
        self._tar_height = float(env_config.get("tar_height", 0.9))
        self._near_dist = float(env_config.get("near_dist", 1.5))
        self._near_prob = float(env_config.get("near_prob", 0.5))

        super().__init__(env_config=env_config, engine_config=engine_config,
                         num_envs=num_envs, device=device, visualize=visualize)
        return

    def _build_envs(self, config, num_envs):
        self._target_ids = []
        super()._build_envs(config, num_envs)
        return

    def _build_env(self, env_id, config):
        super()._build_env(env_id, config)
        target_id = self._build_target(env_id)
        if (env_id == 0):
            self._target_ids.append(target_id)
        else:
            assert(self._target_ids[0] == target_id)
        return

    def _build_target(self, env_id):
        return self._engine.create_obj(env_id=env_id,
                                       obj_type=engine.ObjType.rigid,
                                       asset_file="data/assets/objects/strike_target.xml",
                                       name="strike_target",
                                       color=[0.6, 0.1, 0.1])

    def _get_target_id(self):
        return self._target_ids[0]

    def _build_sim_tensors(self, config):
        super()._build_sim_tensors(config)
        num_envs = self.get_num_envs()
        self._prev_root_pos = torch.zeros([num_envs, 3], device=self._device, dtype=torch.float32)

        char_id = self._get_char_id()
        strike_body_ids = []
        for body_name in self._strike_body_names:
            body_id = self._engine.find_obj_body_id(char_id, body_name)
            assert(body_id != -1), "Unknown strike body: {}".format(body_name)
            strike_body_ids.append(body_id)
        self._strike_body_ids = torch.tensor(strike_body_ids, device=self._device, dtype=torch.long)
        return

    def _pre_physics_step(self, actions):
        super()._pre_physics_step(actions)
        char_id = self._get_char_id()
        self._prev_root_pos[:] = self._engine.get_root_pos(char_id)
        return

    def _reset_envs(self, env_ids):
        super()._reset_envs(env_ids)
        if (len(env_ids) > 0):
            self._reset_target(env_ids)
        return

    def _reset_target(self, env_ids):
        n = env_ids.shape[0]
        if (n == 0):
            return

        target_id = self._get_target_id()
        char_id = self._get_char_id()
        root_pos = self._engine.get_root_pos(char_id)[env_ids]

        init_near = torch.rand([n], device=self._device) < self._near_prob
        dist_max = torch.full([n], self._tar_dist_max, device=self._device, dtype=torch.float32)
        dist_max[init_near] = self._near_dist
        rand_dist = (dist_max - self._tar_dist_min) * torch.rand([n], device=self._device) + self._tar_dist_min
        rand_theta = 2 * np.pi * torch.rand([n], device=self._device)

        target_pos = torch.zeros([n, 3], device=self._device, dtype=torch.float32)
        target_pos[:, 0] = root_pos[:, 0] + rand_dist * torch.cos(rand_theta)
        target_pos[:, 1] = root_pos[:, 1] + rand_dist * torch.sin(rand_theta)
        target_pos[:, 2] = self._tar_height

        axis = torch.zeros([n, 3], device=self._device, dtype=torch.float32)
        axis[:, 2] = 1.0
        rand_rot_theta = 2 * np.pi * torch.rand([n], device=self._device)
        target_rot = torch_util.axis_angle_to_quat(axis, rand_rot_theta)

        self._engine.set_root_pos(env_ids, target_id, target_pos)
        self._engine.set_root_rot(env_ids, target_id, target_rot)
        self._engine.set_root_vel(env_ids, target_id, 0.0)
        self._engine.set_root_ang_vel(env_ids, target_id, 0.0)
        return

    def _compute_obs(self, env_ids=None):
        obs = super()._compute_obs(env_ids)

        char_id = self._get_char_id()
        target_id = self._get_target_id()

        root_pos = self._engine.get_root_pos(char_id)
        root_rot = self._engine.get_root_rot(char_id)
        tar_pos = self._engine.get_root_pos(target_id)
        tar_rot = self._engine.get_root_rot(target_id)
        tar_vel = self._engine.get_root_vel(target_id)
        tar_ang_vel = self._engine.get_root_ang_vel(target_id)

        if (env_ids is not None):
            root_pos = root_pos[env_ids]
            root_rot = root_rot[env_ids]
            tar_pos = tar_pos[env_ids]
            tar_rot = tar_rot[env_ids]
            tar_vel = tar_vel[env_ids]
            tar_ang_vel = tar_ang_vel[env_ids]

        task_obs = compute_strike_observations(root_pos, root_rot, tar_pos, tar_rot, tar_vel, tar_ang_vel)
        return torch.cat([obs, task_obs], dim=-1)

    def _update_reward(self):
        char_id = self._get_char_id()
        target_id = self._get_target_id()

        target_pos = self._engine.get_root_pos(target_id)
        target_rot = self._engine.get_root_rot(target_id)
        root_state = torch.cat([self._engine.get_root_pos(char_id), self._engine.get_root_rot(char_id)], dim=-1)

        body_vel = self._engine.get_body_vel(char_id)
        strike_body_vel = body_vel[:, self._strike_body_ids[0], :]

        target_contact = self._engine.get_contact_forces(target_id)
        target_contact = torch.norm(target_contact, dim=-1)
        target_contact = torch.max(target_contact, dim=-1)[0]

        self._reward_buf[:] = compute_strike_reward(target_pos, target_rot, root_state,
                                                    self._prev_root_pos, strike_body_vel,
                                                    target_contact, self._engine.get_timestep())
        return

    def _update_done(self):
        super()._update_done()
        target_id = self._get_target_id()
        target_rot = self._engine.get_root_rot(target_id)
        tipped = compute_strike_success(target_rot)
        active = self._done_buf == base_env.DoneFlags.NULL.value
        self._done_buf[torch.logical_and(tipped, active)] = base_env.DoneFlags.SUCC.value
        return

    def _render_scene(self):
        super()._render_scene()
        self._render_strike_lines()
        return

    def _render_strike_lines(self):
        line_width = 2.0
        col = np.array([[0.0, 1.0, 0.0, 0.5]], dtype=np.float32)

        char_id = self._get_char_id()
        target_id = self._get_target_id()
        starts = self._engine.get_root_pos(char_id).cpu().numpy()
        ends = self._engine.get_root_pos(target_id).cpu().numpy()

        for i in range(self.get_num_envs()):
            self._engine.draw_lines(i, starts[i:i + 1], ends[i:i + 1], col, line_width)
        return


@torch.jit.script
def compute_strike_observations(root_pos, root_rot, tar_pos, tar_rot, tar_vel, tar_ang_vel):
    # type: (Tensor, Tensor, Tensor, Tensor, Tensor, Tensor) -> Tensor
    heading_rot = torch_util.calc_heading_quat_inv(root_rot)

    local_tar_pos = tar_pos - root_pos
    local_tar_pos[..., -1] = tar_pos[..., -1]
    local_tar_pos = torch_util.quat_rotate(heading_rot, local_tar_pos)
    local_tar_vel = torch_util.quat_rotate(heading_rot, tar_vel)
    local_tar_ang_vel = torch_util.quat_rotate(heading_rot, tar_ang_vel)

    local_tar_rot = torch_util.quat_mul(heading_rot, tar_rot)
    local_tar_rot_obs = torch_util.quat_to_tan_norm(local_tar_rot)

    return torch.cat([local_tar_pos, local_tar_rot_obs, local_tar_vel, local_tar_ang_vel], dim=-1)


@torch.jit.script
def compute_strike_reward(tar_pos, tar_rot, root_state, prev_root_pos, strike_body_vel, target_contact, dt):
    # type: (Tensor, Tensor, Tensor, Tensor, Tensor, Tensor, float) -> Tensor
    tar_speed = 1.0
    vel_err_scale = 4.0

    tar_rot_w = 0.5
    vel_reward_w = 0.3
    contact_reward_w = 0.2

    up = torch.zeros_like(tar_pos)
    up[..., -1] = 1.0
    tar_up = torch_util.quat_rotate(tar_rot, up)
    tar_rot_err = torch.sum(up * tar_up, dim=-1)
    tar_rot_r = torch.clamp_min(1.0 - tar_rot_err, 0.0)

    root_pos = root_state[..., 0:3]
    tar_dir = tar_pos[..., 0:2] - root_pos[..., 0:2]
    tar_dir = torch.nn.functional.normalize(tar_dir, dim=-1)

    delta_root_pos = root_pos - prev_root_pos
    root_vel = delta_root_pos / dt
    tar_dir_speed = torch.sum(tar_dir * root_vel[..., :2], dim=-1)
    tar_vel_err = torch.clamp_min(tar_speed - tar_dir_speed, 0.0)
    vel_reward = torch.exp(-vel_err_scale * (tar_vel_err * tar_vel_err))
    vel_reward[tar_dir_speed <= 0] = 0.0

    strike_speed = torch.norm(strike_body_vel, dim=-1)
    contact_reward = torch.clamp(target_contact / 50.0, 0.0, 1.0) * torch.clamp(strike_speed / 6.0, 0.0, 1.0)

    reward = tar_rot_w * tar_rot_r + vel_reward_w * vel_reward + contact_reward_w * contact_reward
    success = tar_rot_err < 0.2
    reward = torch.where(success, torch.ones_like(reward), reward)
    return reward


@torch.jit.script
def compute_strike_success(tar_rot):
    # type: (Tensor) -> Tensor
    up = torch.zeros([tar_rot.shape[0], 3], device=tar_rot.device, dtype=tar_rot.dtype)
    up[:, 2] = 1.0
    tar_up = torch_util.quat_rotate(tar_rot, up)
    tar_rot_err = torch.sum(up * tar_up, dim=-1)
    return tar_rot_err < 0.2
