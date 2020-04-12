#!/usr/bin/env python

"""

Sample.py

Sends Morse code to a serial port and/or the speakers.

"""

from pykob import kob, morse
import time

PORT = None
#PORT = 'COM3'  # typical for Windows
#PORT = '/dev/ttyUSB0'  # typical for Linux
WPM = 20  # code speed
TEXT = '~ The quick brown fox +'  # ~ opens the circuit, + closes it

myKOB = kob.KOB(PORT, audio=True)
mySender = morse.Sender(WPM)

# send HI at 20 wpm as an example
print("HI");
code = (-1000, +2, -1000, +60, -60, +60, -60, +60, -60, +60,
        -180, +60, -60, +60, -1000, +1)
myKOB.sounder(code)
time.sleep(2)

# then send the text
print(TEXT);
for c in TEXT:
    code = mySender.encode(c)
    myKOB.sounder(code)

time.sleep(1)
