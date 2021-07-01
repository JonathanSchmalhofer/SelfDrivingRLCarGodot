import logging
import os
import time
from datetime import datetime
from multiprocessing import Process, Queue

import numpy as np
import redis
import torch

import rainbowiqn_godot_car.constants as cst
from rainbowiqn_godot_car.learner import Learner
from rainbowiqn_godot_car.args import return_args
from rainbowiqn_godot_car.env import Env
from rainbowiqn_godot_car.redis_memory import ReplayRedisMemory


# Simple ISO 8601 timestamped logger
def log(s):
    formatted_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    print(f"[{formatted_time}] {s}")


def sample_in_thread(mp_queue_sample, mem_redis, batchsize, queue_size):
    while True:
        sample_factor = queue_size
        tree_idxs, tab_byte_transition, weights = mem_redis.sample_byte(batchsize * sample_factor)
        step_tree_idxs = int(len(tree_idxs) / sample_factor)
        step_tab_byte_transition = int(len(tab_byte_transition) / sample_factor)
        step_weights = int(len(weights) / sample_factor)

        for sample_factor_iter in range(sample_factor):

            mp_queue_sample.put(
                [
                    tree_idxs[
                        sample_factor_iter
                        * step_tree_idxs : (sample_factor_iter + 1)
                        * step_tree_idxs
                    ],
                    tab_byte_transition[
                        sample_factor_iter
                        * step_tab_byte_transition : (sample_factor_iter + 1)
                        * step_tab_byte_transition
                    ],
                    weights[
                        sample_factor_iter * step_weights : (sample_factor_iter + 1) * step_weights
                    ],
                ]
            )


def update_priorities_in_thread(mp_queue_update_priorities, mem_redis):
    while True:
        idxs, priorities = mp_queue_update_priorities.get()
        mem_redis.update_priorities(idxs, priorities)  # Update priorities of sampled transitions


def starting_actual_learning(mp_queue_sample, mem_learner, args, mp_queue_update_priorities):
    print("Starting actual learning")
    print("Starting the sample subprocess")
    p = Process(
        target=sample_in_thread,
        args=(mp_queue_sample, mem_learner, args.batch_size, args.queue_size),
    )
    p.daemon = True
    p.start()

    print("Starting the update priorities subprocess")
    p = Process(target=update_priorities_in_thread, args=(mp_queue_update_priorities, mem_learner))
    p.daemon = True
    p.start()


def main():

    args = return_args()

    print("os.environ[CUDA_VISIBLE_DEVICES] = ", os.environ["CUDA_VISIBLE_DEVICES"])

    redis_servor = None
    while True:
        try:
            redis_servor = redis.StrictRedis(host=args.host_redis, port=args.port_redis, db=0)
            redis_servor.set("foo", "bar")
            redis_servor.delete("foo")
            print("Connected to redis servor.")
            break

        except redis.exceptions.ConnectionError as error:
            logging.error(error)
            time.sleep(1)

    priority_weight_increase = (1 - args.priority_weight) / (args.T_max - args.learn_start)

    start_time = time.time()

    # We just create an env to get the action_space. A bit silly but its maybe the most proper way.
    env_tmp = Env(args)
    action_space = env_tmp.action_space()
    env_tmp.close()
    del env_tmp

    mem_learner = ReplayRedisMemory(args, redis_servor)
    mem_learner.transitions.initialize_redis_database()
    print("Starting training loop")
    # Training loop
    if args.continue_experiment:
        print(
            f"We are restarting a stopped experience with a model"
            f" trained for {args.step_learner_already_done} steps"
        )
        initial_T_learner = args.step_learner_already_done
        print("initial T learner equal ", initial_T_learner)
        # We fill the memory before learning when restarting an experiment (for a fair restart)
        capacity_before_learning = args.memory_capacity
    else:
        initial_T_learner = args.learn_start
        capacity_before_learning = args.learn_start

    T, done = initial_T_learner, True

    mem_learner.priority_weight = (
        mem_learner.priority_weight + (T - args.learn_start) * priority_weight_increase
    )

    memory_got_enough_experience = False

    learner = Learner(args, action_space, redis_servor)
    learner.train()
    learner.save_to_redis(T)

    # Queue filled by mem_learner.sample() and read to make the backprop...
    mp_queue_sample = Queue(args.queue_size)

    # Queue filled with priorities of batch and read to update them in the redis_database
    mp_queue_update_priorities = Queue(args.queue_size)

    buffer_idxs = []
    buffer_loss = []

    while T <= args.T_max:

        if T % args.log_interval == 0:
            log(f"T = {T} / {args.T_max}")
            duration = time.time() - start_time
            print(f"Time between 2 log_interval for learner ({duration:.3f} sec)")
            start_time = time.time()

        # Train and test
        if (
            memory_got_enough_experience
            or mem_learner.transitions.get_current_capacity() >= capacity_before_learning
        ):
            if not memory_got_enough_experience:
                starting_actual_learning(
                    mp_queue_sample, mem_learner, args, mp_queue_update_priorities
                )
                T = initial_T_learner
                memory_got_enough_experience = True

            # Just a small hack to set memory_full to True
            # because now we sample in another Thread...
            if T % cst.hack_set_full_capacity_to_true == 0:
                mem_learner.transitions.get_current_capacity()

            # Anneal importance sampling weight β to 1
            mem_learner.priority_weight = min(
                mem_learner.priority_weight + priority_weight_increase, 1
            )

            if T % args.replay_frequency == 0:
                # Train with n-step distributional double-Q learning
                idxs, loss = learner.learn(mem_learner, mp_queue_sample)
                buffer_idxs.append(idxs)
                buffer_loss.append(loss)
                if len(buffer_loss) == args.queue_size:
                    tab_idxs = np.concatenate(buffer_idxs)
                    tab_loss_gpu = torch.cat(buffer_loss)
                    tab_priorities_cpu = tab_loss_gpu.detach().cpu().numpy()
                    for batch_priorities_iter in range(args.queue_size):
                        mp_queue_update_priorities.put(
                            [
                                tab_idxs[
                                    batch_priorities_iter
                                    * args.batch_size : (batch_priorities_iter + 1)
                                    * args.batch_size
                                ],
                                tab_priorities_cpu[
                                    batch_priorities_iter
                                    * args.batch_size : (batch_priorities_iter + 1)
                                    * args.batch_size
                                ],
                            ]
                        )

                    buffer_idxs = []
                    buffer_loss = []

            if T % args.weight_synchro_frequency == 0:
                learner.save_to_redis(T)

            # Update target network
            if T % args.target_update == 0:
                learner.update_target_net()

        else:
            time_to_wait = 10
            print(
                f"not enough experience in memory, we wait {time_to_wait} "
                f"seconds before trying again"
            )
            time.sleep(time_to_wait)

        T += 1


if __name__ == "__main__":
    main()
