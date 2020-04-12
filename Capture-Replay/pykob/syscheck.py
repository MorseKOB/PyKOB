#!/usr/bin/env python

"""

syscheck.py

Displays version numbers of Python-related software and the names of
available serial ports.

"""

import sys
print('Python ' + sys.version)

try:
    import pykob
    print('PyKOB ' + pykob.VERSION)
except:
    print('PyKOB not installed')

try:
    import serial
    print('pySerial ' + serial.VERSION)
    import serial.tools.list_ports
    for p in serial.tools.list_ports.comports():
        print(p[1])
except:
    print('pySerial not installed')

try:
    import pyaudio
    pa = pyaudio.PyAudio()
    print('PyAudio ' + pyaudio.get_portaudio_version_text())
except:
    print('PyAudio not installed')

