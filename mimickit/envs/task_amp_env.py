import gymnasium.spaces as spaces
import numpy as np

import envs.amp_env as amp_env
import util.torch_util as torch_util


class TaskAMPEnv(amp_env.AMPEnv):
    """AMP task envs can expose the base humanoid obs for a frozen ASE LLC."""

    def compute_llc_obs(self, env_ids=None):
        return amp_env.AMPEnv._compute_obs(self, env_ids)

    def get_llc_obs_space(self):
        obs = self.compute_llc_obs()
        obs_shape = list(obs.shape[1:])
        obs_dtype = torch_util.torch_dtype_to_numpy(obs.dtype)
        return spaces.Box(low=-np.inf, high=np.inf, shape=obs_shape, dtype=obs_dtype)
