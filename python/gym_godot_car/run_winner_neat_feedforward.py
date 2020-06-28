"""
Self Driving Car (Godot) experiment using a feed-forward neural network.
This is based on the single-pole balancing example from neat-python package.
"""

from __future__ import print_function

import os
import sys
import time
import pickle
import math

import gym
from gym import wrappers, logger
import gym_godot_car
import neat

runs_per_net = 1

def get_scaled_observation(observation):
    """Get full observation, scaled into (approximately) [0, 1]."""
    # observation = sensor_readings[0], sensor_readings[1], sensor_readings[2], sensor_readings[3], sensor_readings[4], velocity_longitudinal, psi, position.x, position.y
    max_pos_x = 1280.0
    max_pos_y = 600.0
    max_sensor_range = 100.0
    min_velocity =    0.0
    max_velocity = +100.0
    min_psi = -math.pi
    max_psi = +math.pi
    return [observation[0]/max_sensor_range,
            observation[1]/max_sensor_range,
            observation[2]/max_sensor_range,
            observation[3]/max_sensor_range,
            observation[4]/max_sensor_range,
            (observation[5]-min_velocity)/(max_velocity-min_velocity),
            (observation[6]-min_psi)/(max_psi-min_psi),
            observation[7]/max_pos_x,
            observation[8]/max_pos_y]

def get_scaled_action(action):
    """Get full action, scaled from [0, 1] to the maximum values allowed by the environment/simulator/car."""
    # action = throttle, brake, steering
    min_steer = -1.0
    max_steer = +1.0
    return [action[0],
            action[1],
            (action[2]*(max_steer-min_steer))+min_steer]

def run(config_path):
    # Load configuration.
    config = neat.Config(neat.DefaultGenome, neat.DefaultReproduction,
                         neat.DefaultSpeciesSet, neat.DefaultStagnation,
                         config_path)

    # Save the winner.
    with open('winner-feedforward', 'rb') as f:
    	winner = pickle.load(f)

    # Display the winning genome.
    print('\nBest genome:\n{!s}'.format(winner))

    net = neat.nn.FeedForwardNetwork.create(winner, config)
    env = gym.make('godot-car-v0')
    env = wrappers.Monitor(env, directory="/tmp/random-godot-car-agent-results", force=True)
    env.seed(0)
    observation = env.reset()

    # Run the simulation until it is being stopped by the simulator
    fitness = 0.0
    done = False
    while True:
        action = net.activate(get_scaled_observation(observation))
        observation, reward, done, _ = env.step(get_scaled_action(action))
        fitness += reward
        if done:
            break
    # Close the env
    env.close()

if __name__ == '__main__':
    # Determine path to configuration file. This path manipulation is
    # here so that the script will run successfully regardless of the
    # current working directory.
    local_dir = os.path.dirname(__file__)
    config_path = os.path.join(local_dir, 'config-feedforward')
    run(config_path)
