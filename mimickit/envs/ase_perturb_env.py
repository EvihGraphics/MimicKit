import numpy as np
import torch

import engines.engine as engine
import envs.amp_env as amp_env


class ASEPerturbEnv(amp_env.AMPEnv):
    def __init__(self, env_config, engine_config, num_envs, device, visualize):
        self._perturb_interval = int(env_config.get("perturb_interval", 45))
        self._projectile_speed_min = float(env_config.get("projectile_speed_min", 20.0))
        self._projectile_speed_max = float(env_config.get("projectile_speed_max", 30.0))
        self._projectile_dist_min = float(env_config.get("projectile_dist_min", 3.0))
        self._projectile_dist_max = float(env_config.get("projectile_dist_max", 5.0))
        self._projectile_height_min = float(env_config.get("projectile_height_min", 0.5))
        self._projectile_height_max = float(env_config.get("projectile_height_max", 1.8))

        super().__init__(env_config=env_config, engine_config=engine_config,
                         num_envs=num_envs, device=device, visualize=visualize)
        return

    def _build_envs(self, config, num_envs):
        self._projectile_ids = []
        super()._build_envs(config, num_envs)
        return

    def _build_env(self, env_id, config):
        super()._build_env(env_id, config)

        proj_specs = [
            ("data/assets/objects/block_projectile.xml", "proj_small0"),
            ("data/assets/objects/block_projectile.xml", "proj_small1"),
            ("data/assets/objects/block_projectile_large.xml", "proj_large0"),
            ("data/assets/objects/block_projectile.xml", "proj_small2"),
        ]

        env_proj_ids = []
        for asset_file, name in proj_specs:
            proj_id = self._engine.create_obj(env_id=env_id,
                                              obj_type=engine.ObjType.rigid,
                                              asset_file=asset_file,
                                              name=name,
                                              color=[0.8, 0.1, 0.1])
            env_proj_ids.append(proj_id)

        if (env_id == 0):
            self._projectile_ids = env_proj_ids
        else:
            assert(self._projectile_ids == env_proj_ids)
        return

    def _reset_envs(self, env_ids):
        super()._reset_envs(env_ids)
        if (len(env_ids) > 0):
            self._reset_projectiles(env_ids)
        return

    def _update_misc(self):
        super()._update_misc()
        self._launch_projectiles()
        return

    def _update_reward(self):
        self._reward_buf[:] = 0.0
        return

    def _reset_projectiles(self, env_ids):
        for proj_id in self._projectile_ids:
            far_pos = torch.zeros([env_ids.shape[0], 3], device=self._device, dtype=torch.float32)
            far_pos[:, 0] = 200.0
            far_pos[:, 1] = torch.arange(env_ids.shape[0], device=self._device, dtype=torch.float32)
            far_pos[:, 2] = 1.0
            self._engine.set_root_pos(env_ids, proj_id, far_pos)
            self._engine.set_root_rot(env_ids, proj_id, torch.tensor([0.0, 0.0, 0.0, 1.0], device=self._device, dtype=torch.float32))
            self._engine.set_root_vel(env_ids, proj_id, 0.0)
            self._engine.set_root_ang_vel(env_ids, proj_id, 0.0)
        return

    def _launch_projectiles(self):
        if (self._perturb_interval <= 0):
            return

        launch_mask = torch.remainder(self._timestep_buf, self._perturb_interval) == 0
        launch_env_ids = launch_mask.nonzero(as_tuple=False).flatten()
        if (len(launch_env_ids) == 0):
            return

        proj_slot = int((int(torch.max(self._timestep_buf).item()) // self._perturb_interval) % len(self._projectile_ids))
        proj_id = self._projectile_ids[proj_slot]

        char_id = self._get_char_id()
        root_pos = self._engine.get_root_pos(char_id)[launch_env_ids]

        rand_theta = 2 * np.pi * torch.rand([launch_env_ids.shape[0]], device=self._device)
        rand_dist = (self._projectile_dist_max - self._projectile_dist_min) * torch.rand([launch_env_ids.shape[0]], device=self._device) + self._projectile_dist_min
        pos_z = (self._projectile_height_max - self._projectile_height_min) * torch.rand([launch_env_ids.shape[0]], device=self._device) + self._projectile_height_min

        proj_pos = torch.zeros([launch_env_ids.shape[0], 3], device=self._device, dtype=torch.float32)
        proj_pos[:, 0] = root_pos[:, 0] + rand_dist * torch.cos(rand_theta)
        proj_pos[:, 1] = root_pos[:, 1] + rand_dist * torch.sin(rand_theta)
        proj_pos[:, 2] = pos_z

        launch_dir = root_pos - proj_pos
        launch_dir += 0.1 * torch.randn_like(launch_dir)
        launch_dir = torch.nn.functional.normalize(launch_dir, dim=-1)
        launch_speed = (self._projectile_speed_max - self._projectile_speed_min) * torch.rand([launch_env_ids.shape[0], 1], device=self._device) + self._projectile_speed_min
        launch_vel = launch_speed * launch_dir

        self._engine.set_root_pos(launch_env_ids, proj_id, proj_pos)
        self._engine.set_root_rot(launch_env_ids, proj_id, torch.tensor([0.0, 0.0, 0.0, 1.0], device=self._device, dtype=torch.float32))
        self._engine.set_root_vel(launch_env_ids, proj_id, launch_vel)
        self._engine.set_root_ang_vel(launch_env_ids, proj_id, 0.0)
        return
