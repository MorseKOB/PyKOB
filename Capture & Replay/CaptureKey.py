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

"""
CaptureKey.py

Captures timing information from a key to a file for
later playback and analysis.

Serial port should be specified by running the
'configure.sh' script or executing 'python3 Configure.py'.

Usage: python CaptureKey.py >filename.txt

Example: py CaptureKey.py >TrainOrders.txt
"""

import sys
import time
from pykob import config,kob

VERSION = '1.3'
PORT = config.serial_port # serial port for KOB interface

myKOB = kob.KOB(PORT)

print('CaptureKey {} - {}'.format(VERSION, time.asctime()))
sys.stdout.flush()

while True:
    code = myKOB.key()
    print(*code)
    sys.stdout.flush()

