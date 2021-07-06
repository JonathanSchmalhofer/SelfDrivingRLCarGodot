import math
from collections import deque

import gym
from gym import error, spaces, utils
from gym.utils import seeding
import socket
from enum import Enum
from time import sleep

import cv2  # Note that importing cv2 before torch may cause segfaults?
import numpy as np


class Status(Enum):
    INIT = 0
    RUNNING = 2
    WAITING = 3
    ERROR = 99


class GodotCarHelperClient():
    def __init__(self):
        self._debug = False
        self._ip = '127.0.0.1'
        self._port = 42424
        self._window_width = 84
        self._window_height = 84
        self._window_depth = 3
        self._buffer_size = self._window_width * self._window_height * self._window_depth
        self._socket = None
        self._Connect()
        self._Register()
        self._status = Status.INIT
        self._step_reward = 0.0
        self._total_reward = 0.0
        self._crash = False
        self._observation = []
        self._id = ""

    def _DebugPrint(self, msg):
        if self._debug:
            self._DebugPrint(msg)

    def _Connect(self):
        if self._socket:
            self._DebugPrint("Already socket created, closing first before connecting")
            self.Close()
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.settimeout(1)  # seconds
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
            sleep(0.1)
            self._socket.close()
            self._DebugPrint("Closing Socket")
        self._socket = None
        self._status = Status.INIT

    def GetEpisodeStatus(self):
        # if self._crash:
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
        self._observation = []

    def Reset(self):
        self._DebugPrint("Resetting Socket")
        self._ResetInternalStates()
        command_body = "(RESET)"
        command_head = "(HEAD:{length:d})".format(length=len(command_body))
        command = command_head + command_body
        self._socket.send(command.encode('utf-8'))
        self.SendSense()

    def _SetObservationFromData(self, data):
        data = np.fromstring(data, dtype='uint8')
        self._observation = cv2.cvtColor(data.reshape((self._window_width, self._window_height, self._window_depth)),
                                         cv2.COLOR_BGR2GRAY)
        # cv2.imshow('SERVER', self._observation)
        # cv2.waitKey(0)
        # print("SENDSENSE DONE")

    def SendSense(self):
        command_body = "(SENSE)"
        command_head = "(HEAD:{length:d})".format(length=len(command_body))
        command = command_head + command_body
        self._socket.send(command.encode('utf-8'))
        data = self._socket.recv(self._buffer_size)
        self._SetObservationFromData(data)


    def SetControl(self, control):
        command_body = "(CONTROL:{throttle:2.3f};{brake:2.3f};{steer:2.3f})".format(throttle=control[0],
                                                                                    brake=control[1], steer=control[2])
        command_head = "(HEAD:{length:d})".format(length=len(command_body))
        command = command_head + command_body
        self._socket.send(command.encode('utf-8'))
        data = self._socket.recv(self._buffer_size)
        self._SetObservationFromData(data)
        # todo: check how to send these additional information
        #self._step_reward = float(data[0]) - self._total_reward
        #self._total_reward += self._step_reward
        #self._crash = bool(data[1] == 'True')
        #self._observation = []

    def SetAction(self, action):
        command_body = "(ACTION:{:d})".format(action)
        command_head = "(HEAD:{length:d})".format(length=len(command_body))
        command = command_head + command_body
        self._socket.send(command.encode('utf-8'))
        data = self._socket.recv(self._buffer_size)
        self._SetObservationFromData(data)
        # todo: check how to send these additional information
        # self._step_reward = float(data[0]) - self._total_reward
        # self._total_reward += self._step_reward
        # self._crash = bool(data[1] == 'True')
        # self._observation = []


class Env:
    def __init__(self, args):
        self.client = GodotCarHelperClient()
        self.min_sensor_distance = 0
        self.max_sensor_distance = 100
        self.min_speed = 0
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
        self.num_bins_steering = 3
        self.num_bins_throttle = 2
        self.nums_bins_brake = 2
        self.actions  = np.array([i for i in range(self.num_bins_steering * self.num_bins_throttle * self.nums_bins_brake)], dtype=np.int32)

        self.device = args.device
        self.window = args.history_length  # Number of frames to concatenate
        self.state_buffer = deque([], maxlen=args.history_length)
        self.action_repeat = args.action_repeat

        self.SABER_mode = not args.disable_SABER_mode
        if self.SABER_mode:
            # We need to divide time by action repeat to get the max_step_stuck
            self.max_step_stuck_SABER = int(args.max_frame_stuck_SABER / self.action_repeat)
            self.SABER_mode_count = 0

    def _get_state(self):
        return self.client.GetObservation()

    def _reset_buffer(self):
        self.client.Reset()
        for _ in range(self.window):
            self.state_buffer.append(np.zeros((84, 84)))

    def reset(self):
        # Reset internals
        self._reset_buffer()

        # Process and return "initial" state
        self.state_buffer.append(self.client.GetObservation())

        if self.SABER_mode:
            self.SABER_mode_count = 0

        return list(self.state_buffer)

    def step(self, action):
        self.client.SetAction(action)
        status = self.client.GetStatus()
        reward = self.client.GetReward()
        observation = self.client.GetObservation()
        done = self.client.GetEpisodeStatus()

        self.state_buffer.append(observation)

        # In SABER mode we track how much time without receiving any rewards
        # If stuck for more than 5 minutes, we end the episode
        if self.SABER_mode:
            if reward == 0:
                self.SABER_mode_count += 1
            else:
                self.SABER_mode_count = 0

            if self.SABER_mode_count > self.max_step_stuck_SABER:
                # We didn't receive any reward for 5 minutes, probably game stuck.
                # Let's end this episode
                done = True

        # Return state, reward, done
        return list(self.state_buffer), reward, done

    def action_space(self):
        return len(self.actions)

    def render(self):
        # cv2.imshow("screen", self.ale.getScreenRGB()[:, :, ::-1])
        # cv2.waitKey(1)
        pass

    def close(self):
        # cv2.destroyAllWindows()
        self.client.Close()
        pass
