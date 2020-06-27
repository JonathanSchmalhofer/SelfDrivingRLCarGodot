#!/usr/bin/env python

import socket
import time

def DoEpisode():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1) # 1 second
    s.connect((TCP_IP, TCP_PORT))

    #print("   REGISTER");
    s.send("(HEAD:10)(REGISTER)".encode('utf-8'))
    data = s.recv(BUFFER_SIZE)
    print("   RESPONSE: {}".format(data))
    for i in range(0, 100):
        s.send("(HEAD:22)(CONTROL:0.3;0.1;-0.1)".encode('utf-8'))
        data = s.recv(BUFFER_SIZE).decode('utf-8').split(';')
        print("   RESPONSE: {}".format(data))
        print("{} {} {} {} {}".format(data[2],data[3],data[4],data[5],data[6]))
        if data[1] == "True":
            print("Crash")
            break
    for i in range(0, 100):
        s.send("(HEAD:22)(CONTROL:0.6;0.15;0.4)".encode('utf-8'))
        data = s.recv(BUFFER_SIZE).decode('utf-8').split(';')
        if data[1] == "True":
            print("Crash")
            break
        #print("   RESPONSE: {}".format(data))
    s.send("(HEAD:7)(CLOSE)".encode('utf-8'))
    s.close()
    s = None

TCP_IP = '127.0.0.1'
TCP_PORT = 42424
BUFFER_SIZE = 1024

for i in range(0, 100):
    print("Episode {}".format(i))
    DoEpisode()
