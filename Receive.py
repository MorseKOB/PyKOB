#!/usr/bin/env python

"""
Receive

Monitors a KOB wire, sends the incoming Morse to a real and/or simulated
sounder, and displays decoded text on the system console.

Command line parameters:
    KOB wire no. (defaults to 101)
    approximate code speed of incoming Morse (defaults to 20)

Example:
    python Receive.py 110
"""

import sys
from time import sleep
from morsekob import VERSION, internet, sounder, morse
import config

WIRE     = 101  # default KOB wire to connect to
WPM      = 20  # approximate speed of incoming Morse (for decoder)
OFFICEID = 'MorseKOB 4.0 test, XX (listening)'

print('Python ' + sys.version + ' on ' + sys.platform)
print('MorseKOB ' + VERSION)

# get command line parameters, if any
if len(sys.argv) > 1:
    WIRE = int(sys.argv[1])
if len(sys.argv) > 2:
    WPM = int(sys.argv[2])

myInternet = internet.Internet(OFFICEID)
mySounder = sounder.Sounder(config.SERIALPORT, config.AUDIO)
myReader = morse.Reader(WPM)

myInternet.connect(WIRE)
sleep(0.5)
while True:
    code = myInternet.read()
    mySounder.sound(code)
    sys.stdout.write(myReader.decode(code))
    sys.stdout.flush()
