import io
import torch

import rainbowiqn_godot_car.constants as cst
from rainbowiqn_godot_car.agent import Agent


class Learner(Agent):
    """This class just handle learner specific methods"""

    def __init__(self, args, action_space, redis_server):
        super().__init__(args, action_space, redis_server)

    def learn(self, mem_redis, mp_queue):
        # Sample transitions
        sample = mem_redis.get_sample_from_mp_queue(mp_queue)
        idxs, states, actions, returns, next_states, nonterminals, weights = sample
        loss = self.compute_loss_actor_or_learner(
            states, actions, returns, next_states, nonterminals
        )

        self.online_net.zero_grad()
        (weights * loss).mean().backward()  # Importance weight losses
        self.optimiser.step()

        return idxs, loss

    def save_to_redis(self, T_learner):
        """Store weight into redis server"""

        save_bytesIO = io.BytesIO()
        torch.save(self.online_net.state_dict(), save_bytesIO)
        pipe = self.redis_server.pipeline()
        pipe.set(cst.MODEL_WEIGHT_STR, save_bytesIO.getvalue())
        pipe.set(cst.STEP_LEARNER_STR, T_learner)
        pipe.execute()
