import random
import time
from collections import namedtuple

import numpy as np
import redlock
import torch

import rainbowiqn_godot_car.constants as cst

Transition = namedtuple("Transition", ("timestep", "state", "action", "reward", "nonterminal"))
blank_trans = Transition(0, np.zeros((84, 84), dtype=np.uint8), None, 0, False)


class RedisSegmentTree:
    """Segment tree data structure where parent node values are sum of children node values"""

    def __init__(
        self,
        actor_capacity,
        nb_actor,
        redis_server,
        host_redis,
        port_redis,
        synchronize_actors_with_learner,
    ):
        self.actor_capacity = actor_capacity
        self.nb_actor = nb_actor
        self.full_capacity = nb_actor * actor_capacity
        self.actor_full = False  # Used to track if actor memory is full, only for each actor...
        self.memory_full = False  # Used to track actual capacity, only for the learner...
        self.redis_server = redis_server
        self.synchronise_actors_with_learner = synchronize_actors_with_learner
        if self.synchronise_actors_with_learner:
            redlock_manager = redlock.Redlock([{"host": host_redis, "port": port_redis, "db": 0}])
            redlock_manager.retry_count = cst.RETRY_COUNT
            redlock_manager.retry_delay = cst.RETRY_DELAY
            self.redlock_manager = redlock_manager

    def acquire_redlock(self):
        red_lock = False
        redlock_manager = self.redlock_manager
        while not red_lock:
            red_lock = redlock_manager.lock(cst.NAME_REDLOCK, cst.LOCK_LIFE_LONG)
            time.sleep(cst.RETRY_DELAY)
        return red_lock, redlock_manager

    def acquire_redlock_debug(self):
        """ADD A cst.RETRY_COUNT ONLY FOR DEBUG, TOO SEE HOW
        MUCH TIME LOCK IS TRYING TO BE ACQUIRE
        """
        red_lock = False
        retry_count = 0
        redlock_manager = self.redlock_manager
        while not red_lock:
            red_lock = redlock_manager.lock(cst.NAME_REDLOCK, cst.LOCK_LIFE_LONG)
            time.sleep(cst.RETRY_DELAY)
            retry_count += 1
        return red_lock, redlock_manager, retry_count

    def initialize_redis_database(self):
        """
        This fonction is called once at the beginning of the training, it initialized the redis
        memory with all priorities to 0, the step for each actor to 0
        and the step for learner to 0. The max priority is not important.
        We set it to 1 and is used only for the few transitions
        from actors that we can't compute priorities (because we reach end of the buffer
        and we don't get the n-next steps)
        """
        redis_server = self.redis_server
        print("we flush the database! This destroy everything in redis-memory")
        redis_server.flushdb()

        print("initializing sum_tree with all priorities to 0")
        start_time = time.time()
        pipe = redis_server.pipeline()
        for index_priorities in range(2 * self.full_capacity - 1):
            pipe.set(cst.PRIORITIES_STR + str(index_priorities), 0)
        print("initializing all actor_index to 0")
        for id_actor in range(self.nb_actor):
            pipe.set(cst.INDEX_ACTOR_STR + str(id_actor), 0)
            pipe.set(cst.STEP_ACTOR_STR + str(id_actor), 0)
            pipe.set(cst.IS_FULL_ACTOR_STR + str(id_actor), 0)
        print("initializing initial max priority to 1")
        pipe.set(cst.MAX_PRIORITY_STR, 1)
        pipe.set(cst.STEP_LEARNER_STR, 0)
        pipe.execute()
        end_time = time.time()
        print(
            "finished to initiliaze the sum_tree in redis server, time taken is %f "
            % (end_time - start_time)
        )

    def _propagate_multiple_values(self, pipe, indexes, diff_values):
        """Propagates multiple values up tree given a list of tree indexes"""
        while np.max(indexes) > 0:
            for current_indice in range(len(indexes)):
                index = indexes[current_indice]
                diff_value = diff_values[current_indice]
                if index != 0:
                    pipe.incrbyfloat(cst.PRIORITIES_STR + str(index), diff_value)
            indexes = (indexes - 1) // 2
        pipe.incrbyfloat(
            cst.PRIORITIES_STR + str(0), np.sum(diff_values)
        )  # Index is 0 there... we update the root of the sumtree

    def check_sumtree_correct(self):
        """
        We check if sumtree is correct! This is not used in the
        code but it's a good way to debug.
        Sumtree nodes should be sum of child nodes
        """
        print("we check if SumTree is correct, TODO TO REMOVE")
        start_time = time.time()

        maximum = 0
        pipe = self.redis_server.pipeline()
        for index_test in range(2 * self.full_capacity - 1):

            pipe.get(cst.PRIORITIES_STR + str(index_test))

        tab_byte_priorities = pipe.execute()

        for index_test in range(self.full_capacity - 1):

            b_parent = tab_byte_priorities[index_test]
            b_left = tab_byte_priorities[2 * index_test + 1]
            b_right = tab_byte_priorities[2 * index_test + 2]
            current_test = abs(float(b_left) + float(b_right) - float(b_parent))
            if current_test > 1e-1:
                print("PROBLEM WITH SUMTREE at index ", index_test)
            maximum = max(maximum, current_test)

        end_time = time.time()
        print("SumTree correct, time used : %f " % (end_time - start_time))
        print("max difference was equal to ", maximum)

    # We update multiple value of priorities in place indeces in the sum tree
    def update_multiple_value(self, pipe, indeces, priorities):
        pipe.get(cst.MAX_PRIORITY_STR)
        for idx in indeces:
            pipe.get(cst.PRIORITIES_STR + str(idx))
        b_tab_old_values = pipe.execute()
        b_max = b_tab_old_values.pop(
            0
        )  # CARE we remove first element because we want to know the max priorities

        self._propagate_multiple_values(pipe, indeces, priorities - np.float64(b_tab_old_values))

        if np.float64(max(priorities)) > np.float64(b_max):
            pipe.set(cst.MAX_PRIORITY_STR, np.float64(max(priorities)))

    def append_actor_buffer(
        self, actor_buffer, actor_index_in_replay_memory, id_actor, priorities, T_actor
    ):
        """
        This function add the actor buffer (consisting of multiple consecutive transitions)
        at the right location in the redis-server
        """
        indexes = (
            np.arange(
                actor_index_in_replay_memory, actor_index_in_replay_memory + len(actor_buffer)
            )
            % self.actor_capacity
        ) + (id_actor * self.actor_capacity)

        pipe = self.redis_server.pipeline()

        # red_lock, redlock_manager, retry_count = self.acquire_redlock_debug()

        if self.synchronise_actors_with_learner:
            red_lock, redlock_manager = self.acquire_redlock()

        self.update_multiple_value(pipe, indexes + self.full_capacity - 1, priorities)

        for [timestep, np_state, action, reward, done] in actor_buffer:
            nonterminal = not done
            true_index_in_replay_memory = (
                id_actor * self.actor_capacity
            ) + actor_index_in_replay_memory

            str_state = np_state.ravel().tostring()

            pipe.hmset(
                cst.TRANSITIONS_STR + str(true_index_in_replay_memory),
                {
                    "timestep": timestep,
                    "state": str_state,
                    "action": action,
                    "reward": reward,
                    "nonterminal": int(nonterminal),
                },
            )

            actor_index_in_replay_memory = (actor_index_in_replay_memory + 1) % self.actor_capacity

        pipe.set(cst.INDEX_ACTOR_STR + str(id_actor), actor_index_in_replay_memory)
        pipe.set(cst.STEP_ACTOR_STR + str(id_actor), T_actor)
        pipe.execute()

        if self.synchronise_actors_with_learner:
            redlock_manager.unlock(red_lock)

    # Searches for the location of a value in sum tree
    def _retrieve_multiple_values(self, indexes, values):
        pipe = self.redis_server.pipeline()
        lefts, rights = 2 * indexes + 1, 2 * indexes + 2
        if np.min(lefts) >= 2 * self.full_capacity - 1:
            return indexes
        else:
            for left in lefts:
                pipe.get(cst.PRIORITIES_STR + str(left))

        tab_b_sum_tree_left = pipe.execute()
        for current_indice in range(len(tab_b_sum_tree_left)):

            # This correct a bug when the tree is not a exact 2^n number, YOU DONT ITERATE
            # same number of time for each index (think about a small example with size = 5,
            # some index got only 1 floor of parent while other got 2...)
            if lefts[current_indice] < (2 * self.full_capacity - 1):
                sum_tree_left = float(tab_b_sum_tree_left[current_indice])
                value = values[current_indice]
                if value <= sum_tree_left:
                    indexes[current_indice] = lefts[current_indice]
                else:
                    indexes[current_indice] = rights[current_indice]
                    values[current_indice] = values[current_indice] - sum_tree_left

        return self._retrieve_multiple_values(indexes, values)

    # This is a function to handle not valid indexes (i.e. indexes to close from current
    # actor_indexes, in which we can't make "good" transitions)
    # In that case, I just push the index slightly to the left or right (to get far
    # enough from the actor_indexes)
    # In the original code, he was sampling over and over until he got a valid index (and
    # in fact we almost never had to resample), but this is hard to make with multi actor
    # each with one actor_index...
    # We don't really care anymore about probs being equal to 0, it suppose to never happen,
    # and if it happen sometimes, we just retry until we got all probs superior to 0..
    # Actually I thought a lot about how to make this perfect, and I realize that this was
    # totaly useless and didn't want to spend that much time for a case which happen almost never.
    def transform_to_valid_tree_indexes(
        self, tree_indexes, tab_index_actor, history_length, n_step_length
    ):
        data_indexes = tree_indexes - self.full_capacity + 1

        for ind_data_index in range(len(data_indexes)):
            data_index = data_indexes[ind_data_index]
            id_current_actor = data_index // self.actor_capacity
            dist_to_actor_index = (data_index % self.actor_capacity) - tab_index_actor[
                id_current_actor
            ]

            if dist_to_actor_index >= 0 and dist_to_actor_index <= history_length:
                data_indexes[ind_data_index] = (
                    data_index + history_length - dist_to_actor_index + 1
                ) % self.actor_capacity + id_current_actor * self.actor_capacity

            elif dist_to_actor_index < 0 and dist_to_actor_index >= -n_step_length:
                data_indexes[ind_data_index] = (
                    data_index - n_step_length - dist_to_actor_index - 1
                ) % self.actor_capacity + id_current_actor * self.actor_capacity

        return data_indexes + self.full_capacity - 1

    # Searches for multiple values in sum tree and returns values, data indexes and tree indexes
    def find_multiple_values(self, history_length, n_step_length, batch_size):

        # red_lock, redlock_manager, retry_count = self.acquire_redlock_debug()

        if self.synchronise_actors_with_learner:
            red_lock, redlock_manager = self.acquire_redlock()

        p_total = (
            self.total()
        )  # Retrieve sum of all priorities (used to create a normalised probability distribution)

        segment = p_total / batch_size

        # Uniformly sample an element in each segment
        samples = np.array(
            [random.uniform(i * segment, (i + 1) * segment) for i in range(batch_size)]
        )

        # Every day I'm shuffling! The idea is to get shuffled indexes from redis memory,
        # like that we can get many batch at the same time without any bias...
        np.random.shuffle(samples)

        samples_copy = (
            samples.copy()
        )  # I remember it was to keep samples for debugging, maybe it's not usefull
        # but it's totally free in computation so let's keep it... 28/11/2018

        tree_indexes = self._retrieve_multiple_values(
            np.zeros(len(samples), dtype=int), samples_copy
        )  # Search for index of item from root

        pipe = self.redis_server.pipeline()

        # We handle index to close from any actor_index by pushing it slightly away from this
        # actor_index (it should be far away by self.history and self.n to get valid transitions)
        for actor_id in range(self.nb_actor):
            pipe.get(cst.INDEX_ACTOR_STR + str(actor_id))
        tab_b_index_actor = pipe.execute()
        tab_index_actor = np.array([int(b_index_actor) for b_index_actor in tab_b_index_actor])

        tree_indexes = self.transform_to_valid_tree_indexes(
            tree_indexes, tab_index_actor, history_length, n_step_length
        )

        data_indexes = tree_indexes - self.full_capacity + 1

        # We get priorities from the tree_indexes and return them

        for tree_index in tree_indexes:
            pipe.get(cst.PRIORITIES_STR + str(tree_index))

        tab_b_value_priorities = pipe.execute()
        tab_value_priorities = np.array(
            [float(b_value_priority) for b_value_priority in tab_b_value_priorities]
        )

        if self.synchronise_actors_with_learner:
            redlock_manager.unlock(red_lock)

        return (
            tab_value_priorities,
            data_indexes,
            tree_indexes,
            p_total,
        )  # Return value, data index, tree index

    def total(self):
        b_sum_tree_total = self.redis_server.get(cst.PRIORITIES_STR + str(0))
        return float(b_sum_tree_total)

    def _byte_data_to_transition(self, b_data):
        [b_timestep, str_state, b_action, b_reward, b_nonterminal] = b_data
        if str_state is None:
            return None  # We are getting a transition not filled yet...
        np_state = np.frombuffer(str_state, dtype=np.uint8).reshape(84, 84)
        transition = Transition(
            int(b_timestep), np_state, int(b_action), float(b_reward), bool(int(b_nonterminal))
        )
        return transition

    def get_byte_multiple_transition(self, tab_indeces, history_length, n_step_length):
        length_transitions = history_length + n_step_length  # How much states in each transitions
        pipe = self.redis_server.pipeline()
        for index in tab_indeces:
            id_current_actor = index // self.actor_capacity
            for index_current_transition in range(length_transitions):
                pipe.hmget(
                    cst.TRANSITIONS_STR
                    + str(
                        (
                            (index_current_transition + index - history_length + 1)
                            % self.actor_capacity
                        )
                        + id_current_actor * self.actor_capacity
                    ),
                    "timestep",
                    "state",
                    "action",
                    "reward",
                    "nonterminal",
                )

        return pipe.execute()

    def get_current_capacity(self):
        if self.memory_full:
            # memory is full so we return full capacity without computation
            return self.full_capacity
        pipe = self.redis_server.pipeline()
        is_memory_full = True
        for id_actor in range(self.nb_actor):
            pipe.get(cst.IS_FULL_ACTOR_STR + str(id_actor))
            pipe.get(cst.INDEX_ACTOR_STR + str(id_actor))

        tab_b_full_index_actor = pipe.execute()
        capacity = 0
        for id_actor in range(self.nb_actor):
            if int(tab_b_full_index_actor[2 * id_actor]):
                capacity += self.actor_capacity
            else:
                capacity += int(tab_b_full_index_actor[2 * id_actor + 1])
                is_memory_full = False
        self.memory_full = is_memory_full
        return capacity


class ReplayRedisMemory:
    def __init__(self, args, redis_server):
        self.device = args.device
        self.capacity = args.actor_capacity * args.nb_actor
        self.history = args.history_length
        self.discount = args.discount
        self.n = args.multi_step
        self.priority_weight = (
            args.priority_weight
        )  # Initial importance sampling weight β, annealed to 1 over course of training
        self.priority_exponent = args.priority_exponent
        self.t = 0  # Internal episode timestep counter
        self.transitions = RedisSegmentTree(
            args.actor_capacity,
            args.nb_actor,
            redis_server,
            args.host_redis,
            args.port_redis,
            args.synchronize_actors_with_learner,
        )
        # Store transition in a wrap-around cyclic buffer within a sum tree for querying priorities

    # DEBUG, we check if 2 transition are the same
    def _check_equality_transitions(self, old_transition, new_transition):
        assert torch.min(old_transition.state == new_transition.state) == 1
        assert old_transition.timestep == new_transition.timestep
        assert old_transition.action == new_transition.action
        assert old_transition.reward == new_transition.reward
        assert old_transition.nonterminal == new_transition.nonterminal

    # Returns a valid sample from all segments in form of byte (to be added to the redis-server)
    def _get_byte_sample_from_all_segment(self, batch_size):

        tab_probs, data_indexes, tree_indexes, p_total = self.transitions.find_multiple_values(
            self.history, self.n, batch_size
        )  # Retrieve sample from tree with un-normalised probability

        # This is a weird bug I didn't succeed to find, probably error from float32 precision.
        # Lets just try to find again to obtain proba > 0
        if np.min(tab_probs) <= 0:
            for retry_find in range(10):
                tab_probs, data_indexes, tree_indexes, p_total = self.transitions.find_multiple_values(
                    self.history, self.n, batch_size
                )
                if np.min(tab_probs) > 0:
                    break

        # If still not find then set all prob <= 0 to 1/memory_capacity as it was
        # uniform distribution for those transitions
        # (this never happened in my experiments)
        if np.min(tab_probs) <= 0:
            tab_indices_with_proba_0 = (tab_probs <= 0)
            if len(tab_indices_with_proba_0) > batch_size/10:
                # We only print this message when the situation is really critical
                # i.e. when many samples got proba inferior to 0 (I never encountered
                # this case in the experiments on 60 Atari games)
                print("We don't succeed to find transitions with all proba > 0, this "
                      "is probably because of float32 precision."
                      "Let's set proba to uniform distribution."
                      "This is suppose to never happen (never encountered "
                      "in my experiments)."
                      "If this happen too often, this is probably because"
                      "your replay memory capacity is set to a really small value")
            tab_probs[tab_indices_with_proba_0] = 1/self.transitions.get_current_capacity()

        tab_byte_transition = self.transitions.get_byte_multiple_transition(
            data_indexes, self.history, self.n
        )

        return tab_probs, data_indexes, tree_indexes, tab_byte_transition, p_total

    # Returns a valid sample from all segments in form of byte (to be added to the redis-server)
    def sample_byte(self, batch_size):
        byte_sample = self._get_byte_sample_from_all_segment(batch_size)
        probs, idxs, tree_idxs, tab_byte_transition, p_total = byte_sample
        probs = probs / p_total  # Calculate normalised probabilities
        capacity = self.transitions.get_current_capacity()
        weights = (
            capacity * probs
        ) ** -self.priority_weight  # Compute importance-sampling weights w
        weights = weights / weights.max()  # Normalise by max importance-sampling weight from batch

        return tree_idxs, tab_byte_transition, weights

    # This retrieve the original tensor that were first added to the redis-server.
    # The input is byte and we want to get all tensors of states, actions, rewards etc...
    def get_torch_tensor_from_byte_transition(self, tab_byte_transition, batch_size):
        tab_transitions = []
        history_length = self.history
        n_step_length = self.n
        length_transitions = history_length + n_step_length

        for num_transitions in range(batch_size):
            current_transitions = [None] * length_transitions
            for ind_b_transition in range(length_transitions):
                current_transitions[ind_b_transition] = self.transitions._byte_data_to_transition(
                    tab_byte_transition[(num_transitions * length_transitions) + ind_b_transition]
                )
            tab_transitions.append(current_transitions)

        for transitions in tab_transitions:
            for t in range(history_length - 2, -1, -1):  # e.g. 2 1 0
                if transitions[t + 1].timestep == 0:
                    transitions[t] = blank_trans  # If future frame has timestep 0
            for t in range(history_length, history_length + n_step_length):  # e.g. 4 5 6
                if not transitions[t - 1].nonterminal:
                    transitions[t] = blank_trans  # If prev (next) frame is terminal

        tab_state = []
        tab_action = []
        tab_reward = []
        tab_next_state = []
        tab_nonterminal = []

        # Create un-discretised state and nth next state
        for transition in tab_transitions:
            state = np.stack([trans.state for trans in transition[:history_length]])
            next_state = np.stack(
                [trans.state for trans in transition[self.n : self.n + self.history]]
            )

            # Calculate truncated n-step discounted return R^n = Σ_k=0->n-1
            # (γ^k)R_t+k+1 (note that invalid nth next states have reward 0)
            reward = sum(
                self.discount ** n * transition[self.history + n - 1].reward for n in range(self.n)
            )
            # Mask for non-terminal nth next states

            tab_state.append(state)
            tab_action.append(transition[self.history - 1].action)
            tab_reward.append(reward)
            tab_next_state.append(next_state)
            tab_nonterminal.append(transition[self.history + self.n - 1].nonterminal)

        states = (
            torch.from_numpy(np.stack(tab_state))
            .to(dtype=torch.float32, device=self.device)
            .div_(255)
        )
        next_states = (
            torch.from_numpy(np.stack(tab_next_state))
            .to(dtype=torch.float32, device=self.device)
            .div_(255)
        )
        actions = torch.tensor(tab_action, dtype=torch.int64, device=self.device)
        returns = torch.tensor(tab_reward, dtype=torch.float32, device=self.device)
        nonterminals = torch.tensor(tab_nonterminal, dtype=torch.float32, device=self.device)

        return states, actions, returns, next_states, nonterminals

    # This retrieve the original tensor that were first added to the redis-server.
    # The input is byte and we want to get all tensors of states, actions, rewards etc...
    def get_sample_from_mp_queue(self, mp_queue):
        tree_idxs, tab_byte_transition, weights = mp_queue.get()
        assert len(tree_idxs) == len(weights)
        batch_size = len(tree_idxs)
        torch_tensors = self.get_torch_tensor_from_byte_transition(tab_byte_transition, batch_size)
        states, actions, returns, next_states, nonterminals = torch_tensors

        weights = torch.tensor(weights, dtype=torch.float32, device=self.device)

        return tree_idxs, states, actions, returns, next_states, nonterminals, weights

    # We update multiple value of priorities in place indeces in the sum tree
    def update_priorities(self, idxs, priorities):

        # priorities.pow_(self.priority_exponent)
        priorities = np.power(priorities, self.priority_exponent)

        pipe = self.transitions.redis_server.pipeline()

        # red_lock, redlock_manager, retry_count = self.transitions.acquire_redlock_debug()

        if self.transitions.synchronise_actors_with_learner:
            red_lock, redlock_manager = self.transitions.acquire_redlock()

        self.transitions.update_multiple_value(pipe, idxs, priorities)
        pipe.execute()

        if self.transitions.synchronise_actors_with_learner:
            redlock_manager.unlock(red_lock)
