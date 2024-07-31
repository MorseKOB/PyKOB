#!/usr/bin/env python3
"""
MIT License

Copyright (c) 2020-24 PyKOB - MorseKOB in Python

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
KeyTest.py

Reads the key and prints the code value (used to encode/send Morse).
"""
import sys
from pykob import kob
from pykob import config

myKOB = None
try:
    use_serial = config.use_serial
    port = config.serial_port
    use_gpio = config.use_gpio
    hwtype = config.interface_type
    sound = config.sound
    sounder = config.sounder
    audio_type = config.audio_type

    myKOB = kob.KOB(useAudio=sound, audioType=audio_type, useSounder=sounder, useSerial=use_serial, portToUse=port, useGpio=use_gpio, interfaceType=hwtype)
    while True:
        print(myKOB.key())
except KeyboardInterrupt:
    if myKOB:
        myKOB.exit()
    print()
    print("Thank you for using the Key-Test!\n~73")
    sys.exit(0)     # Indicate this was a normal exit
