import os
import yaml

import torch

import learning.ase_agent as ase_agent
import learning.ase_hrl_model as ase_hrl_model
import learning.base_agent as base_agent
import learning.normalizer as normalizer
import learning.ppo_agent as ppo_agent
import util.arg_parser as arg_parser
import util.torch_util as torch_util


class _LLCEnvAdapter:
    def __init__(self, env):
        self._env = env
        return

    def set_mode(self, mode):
        if (hasattr(self._env, "set_mode")):
            self._env.set_mode(mode)
        return

    def get_num_envs(self):
        return self._env.get_num_envs()

    def get_obs_space(self):
        return self._env.get_llc_obs_space()

    def get_action_space(self):
        return self._env.get_action_space()

    def get_disc_obs_space(self):
        return self._env.get_disc_obs_space()


class ASEHRLAgent(ppo_agent.PPOAgent):
    def __init__(self, config, env, device):
        super().__init__(config, env, device)
        self._build_llc_agent()
        return

    def _load_params(self, config):
        super()._load_params(config)
        self._llc_steps = int(config.get("llc_steps", 5))
        self._task_reward_weight = float(config.get("task_reward_weight", 0.9))
        self._disc_reward_weight = float(config.get("disc_reward_weight", 0.1))
        self._latent_dim = int(config["model"]["latent_dim"])
        self._default_llc_agent_config = config.get("llc_agent_config", "data/agents/ase_humanoid_agent.yaml")
        return

    def _build_model(self, config):
        self._model = ase_hrl_model.ASEHRLModel(config["model"], self._env)
        return

    def _build_normalizers(self):
        obs_space = self._env.get_obs_space()
        obs_dtype = torch_util.numpy_dtype_to_torch(obs_space.dtype)
        self._obs_norm = normalizer.Normalizer(obs_space.shape, clip=10.0, device=self._device, dtype=obs_dtype)

        latent_shape = torch.Size([self._latent_dim])
        self._a_norm = normalizer.Normalizer(latent_shape,
                                             device=self._device,
                                             init_mean=torch.zeros(latent_shape, device=self._device),
                                             init_std=torch.ones(latent_shape, device=self._device),
                                             dtype=torch.float32)
        return

    def _build_llc_agent(self):
        parser = arg_parser.ArgParser.global_parser
        llc_model_file = ""
        llc_agent_file = self._default_llc_agent_config
        if (parser is not None):
            llc_model_file = parser.parse_string("llc_model_file", "")
            llc_agent_file = parser.parse_string("llc_agent_config", llc_agent_file)

        assert(llc_model_file != ""), "ASEHRL requires --llc_model_file"
        assert(os.path.exists(llc_model_file)), "ASEHRL LLC checkpoint not found: {}".format(llc_model_file)
        assert(os.path.exists(llc_agent_file)), "ASEHRL LLC agent config not found: {}".format(llc_agent_file)

        with open(llc_agent_file, "r") as stream:
            llc_config = yaml.safe_load(stream)

        llc_env = _LLCEnvAdapter(self._env)
        self._llc_agent = ase_agent.ASEAgent(config=llc_config, env=llc_env, device=self._device)
        self._llc_agent.load(llc_model_file)
        self._llc_agent.eval()
        self._llc_agent.set_mode(base_agent.AgentMode.TEST)

        for param in self._llc_agent.parameters():
            param.requires_grad_(False)
        return

    def _compute_action_bound_loss(self, norm_a_dist):
        return None

    def _decide_action(self, obs, info):
        norm_obs = self._obs_norm.normalize(obs)
        norm_action_dist = self._model.eval_actor(norm_obs)

        if (self._mode == base_agent.AgentMode.TRAIN):
            norm_a_rand = norm_action_dist.sample()
            norm_a_mode = norm_action_dist.mode

            exp_prob = self._get_exp_prob()
            exp_prob = torch.full([norm_a_rand.shape[0], 1], exp_prob, device=self._device, dtype=torch.float32)
            rand_action_mask = torch.bernoulli(exp_prob)
            norm_a = torch.where(rand_action_mask == 1.0, norm_a_rand, norm_a_mode)
            rand_action_mask = rand_action_mask.squeeze(-1)
        elif (self._mode == base_agent.AgentMode.TEST):
            norm_a = norm_action_dist.mode
            rand_action_mask = torch.zeros_like(norm_a[..., 0])
        else:
            assert(False), "Unsupported agent mode: {}".format(self._mode)

        norm_a_logp = norm_action_dist.log_prob(norm_a)
        norm_a = norm_a.detach()
        norm_a_logp = norm_a_logp.detach()
        a = self._a_norm.unnormalize(norm_a)

        a_info = {
            "a_logp": norm_a_logp,
            "rand_action_mask": rand_action_mask,
        }
        return a, a_info

    def _step_env(self, action):
        z = torch.nn.functional.normalize(action, dim=-1)
        num_envs = self.get_num_envs()
        total_reward = torch.zeros([num_envs], device=self._device, dtype=torch.float32)
        done = torch.zeros([num_envs], device=self._device, dtype=torch.int32)
        final_obs = None
        final_info = {}

        for _ in range(self._llc_steps):
            active = done == 0
            if (not torch.any(active)):
                break

            llc_obs = self._env.compute_llc_obs()
            llc_action = self._compute_llc_action(llc_obs, z)
            next_obs, task_reward, step_done, step_info = self._env.step(llc_action)
            disc_reward = self._compute_llc_disc_reward(step_info["disc_obs"])
            step_reward = self._task_reward_weight * task_reward + self._disc_reward_weight * disc_reward
            total_reward = total_reward + step_reward * active.float()

            newly_done = torch.logical_and(active, step_done != 0)
            done[newly_done] = step_done[newly_done]

            final_obs = next_obs
            final_info = step_info

        if (final_obs is None):
            final_obs = self._env._obs_buf
            final_info = self._env._info

        return final_obs, total_reward, done, final_info

    def _compute_llc_action(self, llc_obs, z):
        with torch.no_grad():
            norm_obs = self._llc_agent._obs_norm.normalize(llc_obs)
            norm_action_dist = self._llc_agent._model.eval_actor(norm_obs, z)
            norm_action = norm_action_dist.mode
            action = self._llc_agent._a_norm.unnormalize(norm_action)
        return action

    def _compute_llc_disc_reward(self, disc_obs):
        with torch.no_grad():
            norm_disc_obs = self._llc_agent._disc_obs_norm.normalize(disc_obs)
            disc_reward = self._llc_agent._calc_disc_rewards(norm_disc_obs)
        return disc_reward
