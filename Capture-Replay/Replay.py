#! python

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
