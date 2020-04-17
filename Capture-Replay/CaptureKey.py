#! python

"""

CaptureKey.py

Captures timing information from a key to a file for
later playback and analysis.

Usage: python CaptureKey.py >filename.txt

Example: py CaptureKey.py >TrainOrders.txt

"""

from __future__ import print_function  # in case you want it to work with Python 2.7
import sys
import time
from pykob import kob

VERSION = '1.3'
PORT = 'COM4'
#PORT = '/dev/ttyUSB0'

myKOB = kob.KOB(PORT)

print('CaptureKey {} - {}'.format(VERSION, time.asctime()))
sys.stdout.flush()

while True:
    code = myKOB.key()
    print(*code)
    sys.stdout.flush()

