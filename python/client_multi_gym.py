
import numpy as np
import socket
from enum import Enum
import random
from time import sleep

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
    self._register()
    self._status = Status.INIT
    self._total_reward = 0.0
    self._step_reward = 0.0
    self._sensor_readings = [0.0, 0.0, 0.0, 0.0, 0.0]
    self._speed = 0.0
    self._yaw = 0.0
    self._pos_x = 0.0
    self._pos_y = 0.0
    self._crash = False
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
    data = self._socket.recv(self._buffer_size)
  def close(self):
    if self._socket:
        command = "(HEAD:7)(CLOSE)"
        self._socket.send(command.encode('utf-8'))
        sleep(0.1)
        self._socket.close()
        print("Closing Socket")
    self._socket = None
    self._status = Status.INIT
  def get_episode_status(self):
    if self._total_reward < -200:
        return True
    if self._total_reward > 14000:
        return True
    if self._crash:
        return True
  def get_observation(self):
    observation = (self._sensor_readings[0], self._sensor_readings[1], self._sensor_readings[2], self._sensor_readings[3], self._sensor_readings[4], self._speed, self._yaw, self._pos_x, self._pos_y)
    return np.array(observation)
  def get_reward(self):
    return self._step_reward
  def get_status(self):
    return self._status
  def _reset_internal_states(self):
    self._status = Status.INIT
    self._total_reward = 0
  def reset(self):
    print("Resetting")
    self._total_reward = 0.0
    self._step_reward = 0.0
    self._crash = False
    command_body = "(RESET)"
    command_head = "(HEAD:{length:d})".format(length=len(command_body))
    command = command_head+command_body
    self._socket.send(command.encode('utf-8'))
  def set_control(self, control):
    command_body = "(CONTROL:{throttle:2.3f};{brake:2.3f};{steer:2.3f})".format(throttle=control[0], brake=control[1], steer=control[2])
    command_head = "(HEAD:{length:d})".format(length=len(command_body))
    command = command_head+command_body
    self._socket.send(command.encode('utf-8'))
    data = self._socket.recv(self._buffer_size).decode('utf-8').split(';')
    self._step_reward = float(data[0]) - self._total_reward
    self._total_reward += self._step_reward
    self._crash = data[1]
    self._sensor_readings = data[2:7]
    self._speed = data[7]
    self._yaw = data[8]
    self._pos_x = data[9]
    self._pos_y = data[10]

def step(client):
    throttle = float(0.5)
    brake = float(0.2)
    steer = float(random.uniform(-0.5, 0.5))
    control = np.array([throttle, brake, steer])
    client.set_control(control)
    status = client.get_status()
    reward = client.get_reward()
    observation = client.get_observation()
    episode_over = client.get_episode_status()

client1 = GodotCarHelperClient()
step(client1)
client1.close()

client1 = GodotCarHelperClient()
client2 = GodotCarHelperClient()

for i in range(100):
    step(client1)
    step(client2)

client1.reset()
client2.reset()
for i in range(100):
    step(client1)
    step(client2)

client1.close()
client2.close()
