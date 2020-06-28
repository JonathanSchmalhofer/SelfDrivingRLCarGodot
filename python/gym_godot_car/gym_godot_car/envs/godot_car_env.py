import gym
from gym import error, spaces, utils
from gym.utils import seeding

import numpy as np
import socket
from enum import Enum
import math

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
    self._Connect()
    self._status = Status.INIT
    self._step_reward = 0.0
    self._total_reward = 0.0
    self._crash = False
    self._observation = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    self._id = ""
    self._debug = False
  def _DebugPrint(self, msg):
    if self._debug:
      self._DebugPrint(msg)
  def _Connect(self):
    if self._socket:
        self._DebugPrint("Already socket created, closing first before connecting")
        self.Close()
    self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    self._socket.settimeout(1) # seconds
    self._socket.connect((self._ip, self._port))
    self._status = Status.WAITING
  def _Register(self):
    self._DebugPrint("Registering")
    self._socket.send("(HEAD:10)(REGISTER)".encode('utf-8'))
    self._status = Status.RUNNING
    self._id = self._socket.recv(self._buffer_size).decode('utf-8')
  def Close(self):
    if self._socket:
        self._socket.send("(HEAD:7)(CLOSE)".encode('utf-8'))
        self._socket.close()
        self._DebugPrint("Closing Socket")
    self._socket = None
    self._status = Status.INIT
  def GetEpisodeStatus(self):
    #if self._crash:
    #  print("C R A S H")
    if self._total_reward < -25 or self._total_reward > 14000 or self._crash:
        return True
    return False
  def GetObservation(self):
    return np.array(self._observation)
  def GetReward(self):
    return self._step_reward
  def GetStatus(self):
    return self._status
  def _ResetInternalStates(self):
    self._status = Status.INIT
    self._step_reward = 0.0
    self._total_reward = 0.0
    self._crash = False
    self._observation = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
  def Reset(self):
    self._DebugPrint("Resetting Socket")
    self._ResetInternalStates()
    self.Close()
    self._Connect()
    self._Register()
  def SetControl(self, control):
    command_body = "(CONTROL:{throttle:2.3f};{brake:2.3f};{steer:2.3f})".format(throttle=control[0], brake=control[1], steer=control[2])
    command_head = "(HEAD:{length:d})".format(length=len(command_body))
    command = command_head+command_body
    self._socket.send(command.encode('utf-8'))
    data = self._socket.recv(self._buffer_size).decode('utf-8').split(';')
    self._step_reward = float(data[0]) - self._total_reward
    self._total_reward += self._step_reward
    self._crash = bool(data[1] == 'True')
    self._observation[0] = float(data[2])
    self._observation[1] = float(data[3])
    self._observation[2] = float(data[4])
    self._observation[3] = float(data[5])
    self._observation[4] = float(data[6])
    self._observation[5] = float(data[7])
    self._observation[6] = float(data[8])
    self._observation[7] = float(data[9])
    self._observation[8] = float(data[10])

class GodotCarEnv(gym.Env):
  metadata = {'render.modes': ['human']}

  def __init__(self):
    self.client = GodotCarHelperClient()
    self.server_process = None # todo: set here
    self.godot_car_path = None # todo: set here
    
    self.min_sensor_distance = 0
    self.max_sensor_distance = 100
    self.min_speed =    0
    self.max_speed = +100
    self.min_yaw = -math.pi
    self.max_yaw = +math.pi
    self.min_pos_x = 0
    self.max_pos_x = 1280
    self.min_pos_y = 0
    self.max_pos_y = 600
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
    self.min_steer = -0.8
    self.max_steer = +0.8
    self.action_space = spaces.Box(np.array([self.min_throttle, self.min_brake, self.min_steer]),
                                   np.array([self.max_throttle, self.max_brake, self.max_steer]),
                                   dtype=np.float32)  # throttle, brake, steer
  def step(self, action):
    throttle = float(np.clip(action[0], self.min_throttle, self.max_throttle))
    brake = float(np.clip(action[1], self.min_brake, self.max_brake))
    steer = float(np.clip(action[2], self.min_steer, self.max_steer))
    control = np.array([throttle, brake, steer])
    self.client.SetControl(control)
    status = self.client.GetStatus()
    reward = self.client.GetReward()
    observation = self.client.GetObservation()
    episode_over = self.client.GetEpisodeStatus()
    return observation, reward, episode_over, {}
  def reset(self):
    self.client.Reset()
    return self.client.GetObservation()
  def render(self, mode='human'):
    pass
  def close(self):
    if self.client:
        self.client.Close()
        self.client = None
