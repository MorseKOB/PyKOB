#!/usr/bin/env python

"""

CaptureWire.py

Captures timing information from a KOB wire to a file for
later playback and analysis.

Usage: python CaptureWire.py wire-no >filename.txt

Examples:
    py CaptureWire.py 11 >Session.txt
    py CaptureWire.py 11 >"MTC Round Table.txt"

"""

from __future__ import print_function  # in case you want it to work with Python 2.7
import sys
import time
from pykob import internet

VERSION = '1.3'
ID = 'Office ID - monitoring'

wire = int(sys.argv[1])

myInternet = internet.Internet(ID)
myInternet.connect(wire)
time.sleep(1)

print('CaptureWire {}. {}'.format(VERSION, time.asctime()))
sys.stdout.flush()

while True:
    code = myInternet.read()
    print(*code)
    sys.stdout.flush()
