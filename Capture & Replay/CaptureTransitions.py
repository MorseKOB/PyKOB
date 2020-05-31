#!/usr/bin/env python3
"""
MIT License

Copyright (c) 2020 PyKOB - MorseKOB in Python

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

"""CaptureTransitions.py

Captures timing information from a key to a file for
later playback and analysis. All transitions are captured.
No contact debounce filter is applied.

Serial port should be specified by running the
'configure.sh' script or executing 'python3 Configure.py'.

Usage: python CaptureTransitions.py >filename.txt
"""

import sys
import time
import serial
from pykob import config

if sys.platform == 'win32':
    from ctypes import windll
    windll.winmm.timeBeginPeriod(1)  # set clock resoluton to 1 ms (Windows only)

VERSION = '1.1'
PORT = config.serial_port # serial port for KOB interface
N = 50

print('CaptureTransitions {} - {}'.format(VERSION, time.asctime()))
sys.stdout.flush()

port = serial.Serial(PORT)
port.setDTR(True)
s0 = port.getDSR()

t = [0] * N
t[0] = time.time()
n = 1
try:
    while True:
        s1 = port.getDSR()
        if s0 != s1:
            t[n] = time.time()
            n += 1
            if n >= N:
                break
            s0 = s1
except:
    pass
for i in range(1, n):
    dt = t[i] - t[0]
    ddt = t[i] - t[i - 1]
    print('{:8.3f} {:9,.1f}'.format(dt, 1000 * ddt))

