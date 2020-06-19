#!/usr/bin/env python

import socket
import time

def DoEpisode():
	s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	s.settimeout(1) # 1 second
	s.connect((TCP_IP, TCP_PORT))

	s.send("(HEAD:10)(REGISTER)".encode('utf-8'))
	for i in range(0, 5):
		s.send("(HEAD:22)(CONTROL:0.3;0.1;-0.1)".encode('utf-8'))
		data = s.recv(BUFFER_SIZE)
	for i in range(0, 5):
		s.send("(HEAD:22)(CONTROL:0.6;0.15;0.4)".encode('utf-8'))
		data = s.recv(BUFFER_SIZE)
	s.send("(HEAD:7)(CLOSE)".encode('utf-8'))
	s.close()
	s = None

TCP_IP = '127.0.0.1'
TCP_PORT = 42424
BUFFER_SIZE = 1024
MESSAGE = "Hello, World!"

print("Episode 1")
DoEpisode()
print("Episode 2")
DoEpisode()
print("Episode 3")
DoEpisode()
