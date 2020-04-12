#!/usr/bin/env python

"""SysCheck.py

Displays version numbers of Python-related software and the names of
available serial ports.
"""

import sys
import pygame
import serial
import morsekob
import serial.tools.list_ports

print('Python ' + sys.version + ' on ' + sys.platform)
print('pygame ' + pygame.version.ver)
print('pySerial ' + serial.VERSION)
print('MorseKOB ' + morsekob.VERSION)
for p in serial.tools.list_ports.comports():
    print(p[1])
