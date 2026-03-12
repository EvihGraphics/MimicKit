import torch

import envs.amp_env as amp_env
import envs.base_env as base_env


class ASEGetupEnv(amp_env.AMPEnv):
    def __init__(self, env_config, engine_config, num_envs, device, visualize):
        self._recovery_episode_prob = float(env_config.get("recovery_episode_prob", 0.2))
        self._recovery_steps = int(env_config.get("recovery_steps", 60))
        self._fall_init_prob = float(env_config.get("fall_init_prob", 0.1))
        self._fall_state_steps = int(env_config.get("fall_state_steps", 150))

        super().__init__(env_config=env_config, engine_config=engine_config,
                         num_envs=num_envs, device=device, visualize=visualize)

        self._recovery_counter = torch.zeros(self.get_num_envs(), device=self._device, dtype=torch.int64)
        self._generate_fall_states()
        amp_env.AMPEnv._reset_envs(self, self._env_ids)
        return

    def _generate_fall_states(self):
        env_ids = self._env_ids
        char_id = self._get_char_id()

        root_pos = self._engine.get_root_pos(char_id).clone()
        root_rot = torch.randn_like(self._engine.get_root_rot(char_id))
        root_rot = torch.nn.functional.normalize(root_rot, dim=-1)
        dof_pos = self._engine.get_dof_pos(char_id).clone()

        self._engine.set_root_pos(env_ids, char_id, root_pos)
        self._engine.set_root_rot(env_ids, char_id, root_rot)
        self._engine.set_root_vel(env_ids, char_id, 0.0)
        self._engine.set_root_ang_vel(env_ids, char_id, 0.0)
        self._engine.set_dof_pos(env_ids, char_id, dof_pos)
        self._engine.set_dof_vel(env_ids, char_id, 0.0)
        self._reset_char_rigid_body_state(env_ids)

        action_low = self._action_bound_low
        action_high = self._action_bound_high
        for _ in range(self._fall_state_steps):
            rand_actions = torch.rand([self.get_num_envs(), action_low.shape[0]], device=self._device)
            rand_actions = action_low + (action_high - action_low) * rand_actions
            self._pre_physics_step(rand_actions)
            self._physics_step()

        self._fall_root_pos = self._engine.get_root_pos(char_id).clone()
        self._fall_root_rot = self._engine.get_root_rot(char_id).clone()
        self._fall_dof_pos = self._engine.get_dof_pos(char_id).clone()
        return

    def _update_misc(self):
        super()._update_misc()
        self._recovery_counter = torch.clamp_min(self._recovery_counter - 1, 0)
        return

    def _update_done(self):
        super()._update_done()
        is_recovery = self._recovery_counter > 0
        self._done_buf[is_recovery] = base_env.DoneFlags.NULL.value
        return

    def _reset_envs(self, env_ids):
        prev_done = self._done_buf[env_ids].clone()
        super()._reset_envs(env_ids)

        if (len(env_ids) == 0):
            return

        terminated_mask = prev_done == base_env.DoneFlags.FAIL.value
        recovery_mask = torch.bernoulli(torch.full([env_ids.shape[0]], self._recovery_episode_prob,
                                                   device=self._device)) == 1.0
        recovery_mask = torch.logical_and(recovery_mask, terminated_mask)
        recovery_ids = env_ids[recovery_mask]

        nonrecovery_ids = env_ids[torch.logical_not(recovery_mask)]
        fall_mask = torch.bernoulli(torch.full([nonrecovery_ids.shape[0]], self._fall_init_prob,
                                               device=self._device)) == 1.0
        fall_ids = nonrecovery_ids[fall_mask]
        default_ids = nonrecovery_ids[torch.logical_not(fall_mask)]

        if (len(recovery_ids) > 0):
            self._recovery_counter[recovery_ids] = self._recovery_steps

        if (len(fall_ids) > 0):
            char_id = self._get_char_id()
            fall_state_ids = torch.randint(low=0, high=self._fall_root_pos.shape[0],
                                           size=(fall_ids.shape[0],), device=self._device)
            self._engine.set_root_pos(fall_ids, char_id, self._fall_root_pos[fall_state_ids])
            self._engine.set_root_rot(fall_ids, char_id, self._fall_root_rot[fall_state_ids])
            self._engine.set_root_vel(fall_ids, char_id, 0.0)
            self._engine.set_root_ang_vel(fall_ids, char_id, 0.0)
            self._engine.set_dof_pos(fall_ids, char_id, self._fall_dof_pos[fall_state_ids])
            self._engine.set_dof_vel(fall_ids, char_id, 0.0)
            self._reset_char_rigid_body_state(fall_ids)
            self._recovery_counter[fall_ids] = self._recovery_steps

        if (len(default_ids) > 0):
            self._recovery_counter[default_ids] = 0

        self._reset_disc_hist(env_ids)
        return
