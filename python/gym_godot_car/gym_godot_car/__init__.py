from gym.envs.registration import register

register(id='godot-car-v0',
    entry_point='gym_godot_car.envs:GodotCarEnv',
)

#register(
#    id='godot-car-v0',
#    entry_point='gym_godot_car.envs:GodotCarEnv',
#    kwargs={'num_agents': 1}
#)