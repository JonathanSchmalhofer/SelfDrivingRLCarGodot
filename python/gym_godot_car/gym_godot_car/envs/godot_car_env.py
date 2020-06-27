import gym
from gym import error, spaces, utils
from gym.utils import seeding

import numpy as np
import socket
from enum import Enum

class Status(Enum):
    INIT = 0
    RUNNING = 2
    WAITING = 3
    ERROR = 99

class GodotCarHelperClient():
  def __init__(self):
    self._ip = '127.0.0.1'
    self._port = 42424
    self._buffer_size = 1024
    self._socket = None
    self._connect()
    self._status = Status.INIT
    self._total_reward = 0
    self._observation = (0, 0, 0, 0, 0, 0, 0, 0, 0)
    self._id = ""
  def _connect(self):
    print("Connecting")
    if self._socket:
        print("Already socket created, closing first before connecting")
        self.close()
    self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    self._socket.settimeout(1) # seconds
    self._socket.connect((self._ip, self._port))
    self._status = Status.WAITING
  def _register(self):
    print("Registering")
    self._socket.send("(HEAD:10)(REGISTER)".encode('utf-8'))
    self._status = Status.RUNNING
    self._id = self._socket.recv(self._buffer_size).decode('utf-8')
  def close(self):
    if self._socket:
        self._socket.send("(HEAD:7)(CLOSE)".encode('utf-8'))
        self._socket.close()
        print("Closing Socket")
    self._socket = None
    self._status = Status.INIT
  def get_episode_status(self):
    # todo: implement
    if self._total_reward > 5:
        return True
    return False
  def get_observation(self):
    return np.array(self._observation)
  def get_reward(self):
    step_reward = 1 # todo: implement
    self._total_reward += step_reward
    return step_reward
  def get_status(self):
    return self._status
  def _reset_internal_states(self):
    self._status = Status.INIT
    self._total_reward = 0
  def reset(self):
    print("Resetting Socket")
    self._reset_internal_states()
    self._total_reward = 0
    self.close()
    self._connect()
    self._register()
  def set_control(self, control):
    command_body = "(CONTROL:{throttle:2.3f};{brake:2.3f};{steer:2.3f})".format(throttle=control[0], brake=control[1], steer=control[2])
    command_head = "(HEAD:{length:d})".format(length=len(command_body))
    command = command_head+command_body
    self._socket.send(command.encode('utf-8'))
    self._observation = self._socket.recv(self._buffer_size).decode('utf-8').split(';')

class GodotCarEnv(gym.Env):
  metadata = {'render.modes': ['human']}

  def __init__(self):
    self.client = GodotCarHelperClient()
    self.server_process = None # todo: set here
    self.godot_car_path = None # todo: set here
    
    self.min_sensor_distance = 0
    self.max_sensor_distance = np.inf
    self.min_speed = -np.inf
    self.max_speed = +np.inf
    self.min_yaw = -np.inf
    self.max_yaw = +np.inf
    self.min_pos_x = 0
    self.max_pos_x = np.inf
    self.min_pos_y = 0
    self.max_pos_y = np.inf
    self.low = np.array([self.min_sensor_distance,
                         self.min_sensor_distance,
                         self.min_sensor_distance,
                         self.min_sensor_distance,
                         self.min_sensor_distance,
                         self.min_speed,
                         self.min_yaw,
                         self.min_pos_x,
                         self.min_pos_y], dtype=np.float32)
    self.high = np.array([self.max_sensor_distance,
                         self.max_sensor_distance,
                         self.max_sensor_distance,
                         self.max_sensor_distance,
                         self.max_sensor_distance,
                         self.max_speed,
                         self.max_yaw,
                         self.max_pos_x,
                         self.max_pos_y], dtype=np.float32)
    self.observation_space = spaces.Box(self.low, self.high, dtype=np.float32)
    self.min_throttle = 0
    self.max_throttle = +1
    self.min_brake = 0
    self.max_brake = +1
    self.min_steer = -1
    self.max_steer = +1
    self.action_space = spaces.Box(np.array([self.min_throttle, self.min_brake, self.min_steer]),
                                   np.array([self.max_throttle, self.max_brake, self.max_steer]),
                                   dtype=np.float32)  # throttle, brake, steer
  def step(self, action):
    throttle = float(np.clip(action[0], self.min_throttle, self.max_throttle))
    brake = float(np.clip(action[1], self.min_brake, self.max_brake))
    steer = float(np.clip(action[2], self.min_steer, self.max_steer))
    control = np.array([throttle, brake, steer])
    self.client.set_control(control)
    status = self.client.get_status()
    reward = self.client.get_reward()
    observation = self.client.get_observation()
    episode_over = self.client.get_episode_status()
    return observation, reward, episode_over, {}
  def reset(self):
    self.client.reset()
    #return np.array(observation)
  def render(self, mode='human'):
    pass
  def close(self):
    if self.client:
        self.client.close()
        self.client = None