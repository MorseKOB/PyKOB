#! python
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
Replay.py

Replays Morse captured to a file.

Usage: python Replay.py <filename.txt

Example: py Replay.py <"Train orders.txt"
"""

import time
from pykob import kob

VERSION = '1.4'
#PORT = 'COM4'
#PORT = '/dev/ttyUSB0'
PORT = None
#AUDIO = False
AUDIO = True

codes = ''
myKOB = kob.KOB(port=PORT, audio=AUDIO)
s = input()
print(s)
while True:
    s = input()
    codes += '[' + s + '] '
    code = [int(x) for x in s.split()]
    myKOB.sounder(code)
