import numpy as np
import torch

import learning.distribution_gaussian_diag as distribution_gaussian_diag
import learning.ppo_model as ppo_model
import util.torch_util as torch_util


class ASEHRLModel(ppo_model.PPOModel):
    def __init__(self, config, env):
        self._latent_dim = int(config["latent_dim"])
        super().__init__(config, env)
        return

    def get_latent_dim(self):
        return self._latent_dim

    def _build_action_distribution(self, config, env, input):
        in_size = torch_util.calc_layers_out_size(input)
        a_init_output_scale = config["actor_init_output_scale"]
        a_std_type = distribution_gaussian_diag.StdType[config["actor_std_type"]]
        a_std = config["action_std"]
        return distribution_gaussian_diag.DistributionGaussianDiagBuilder(in_size, self._latent_dim,
                                                                          std_type=a_std_type,
                                                                          init_std=a_std,
                                                                          init_output_scale=a_init_output_scale)
