#!/usr/bin/env python3
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
Disneyland dedication from Walt Disney (as displayed on plaque at Disneyland entrance  
and as sounded at the Frontierland station.)
"""
"""Sample.py

Sends Morse code to a serial port and/or the speakers.

Serial port, code speed, and audio preferences should be specified by running the
'configure.sh' script or executing 'python3 Configure.py'.
"""

from pykob import config, kob, morse

import argparse
import sys
import time
from pykob import config, kob, morse, log
from distutils.util import strtobool

__short_QBF = "The quick brown fox"
__full_QBF = "The quick brown fox jumps over the lazy dog"
__disneyland_dedication = "To all who come to this happy place; welcome. \
Disneyland is your land. Here age relives fond memories of the past... \
and here youth may savor the challenge and promise of the future. Disneyland \
is dedicated to the ideals, the dreams and the hard facts that have \
created America... \
with the hope that it will be a source of joy and inspiration to all the world."

__full = False
__DLW = False

try:
    arg_parser = argparse.ArgumentParser(description="Sample of the PyKOB functionality with a short Morse code text and options for longer texts.", \
        parents=\
        [\
        config.serial_port_override, \
        config.code_type_override, \
        config.interface_type_override, \
        config.sound_override, \
        config.sounder_override, \
        config.spacing_override, \
        config.min_char_speed_override, \
        config.text_speed_override])
    arg_parser.add_argument("-f", "--full", action='store_true', default=False, \
    help="Play full 'Quick Brown Fox...'", dest="full")
    arg_parser.add_argument("-d", "--di", action='store_true', default=False, \
    help="Play the Disneyland inauguration speech (as heard at the Frontierland Station)", dest="dd")

    args = arg_parser.parse_args()

    port = args.serial_port # serial port for KOB interface
    text_speed = args.text_speed  # text speed (words per minute)
    if (text_speed < 1) or(text_speed > 50):
        print("text_speed specified must be between 1 and 50")
        sys.exit(1)
    sound = strtobool(args.sound)

    myKOB = kob.KOB(port=port, audio=sound)
    mySender = morse.Sender(text_speed)

    # send HI at 20 wpm as an example
    print("HI")
    code = (-1000, +2, -1000, +60, -60, +60, -60, +60, -60, +60,
            -180, +60, -60, +60, -1000, +1)

    time.sleep(1)

    # then send the text
    __text = __full_QBF if args.full else __short_QBF
    if args.dd:
        __text = __disneyland_dedication
        print("From Disneyland Fronteer Land...")
    print(__text)
    myKOB.sounder(mySender.encode('~')) # Open the circuit
    time.sleep(0.200)
    for c in __text:
        code = mySender.encode(c, True)
        myKOB.sounder(code)
    time.sleep(0.350)
    myKOB.sounder(mySender.encode('+')) # Close the circuit
except KeyboardInterrupt:
    print()
    sys.exit(1)     # Indicate this was an abnormal exit
