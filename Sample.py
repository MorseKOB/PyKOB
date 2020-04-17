#!/usr/bin/env python

"""

Sample.py

Sends Morse code to a serial port and/or the speakers.

"""

from pykob import config, kob, morse
import time

PORT = config.Port # serial port for KOB interface
WPM = config.Speed  # code speed (words per minute)
AUDIO = config.Audio # whether to enable computer audio for sounder
TEXT = '~ The quick brown fox +'  # ~ opens the circuit, + closes it

myKOB = kob.KOB(PORT, audio=AUDIO)
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
