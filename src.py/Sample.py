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
Disneyland dedication from Walt Disney (as displayed on plaque at Disneyland entrance  
and as sounded at the Frontierland station.)
"""
"""Sample.py

Sends Morse code to a serial port and/or the speakers.

Serial port, code speed, and audio preferences should be specified by running the
'configure.sh' script or executing 'python3 Configure.py'.
"""

from operator import truediv
from pykob import config, kob, morse

import argparse
import sys
import time
from pykob import config, kob, morse, log
from pykob.util import strtobool

__description = "Sample to test/demonstrate some of the Morse PyKOB functionality and your external sounder, if connected."
__short_QBF = "The quick brown fox"
__full_QBF = "The quick brown fox jumps over the lazy dog"
__disneyland_dedication = "To all who come to this happy place;  welcome. \
Disneyland is your land.   Here age relives fond memories of the past...  \
and here youth may savor the challenge and promise of the future.  Disneyland \
is dedicated to the ideals, the dreams and the hard facts that have \
created America...  \
with the hope that it will be a source of joy and inspiration to all the world."

__full = False
__DLW = False

try:
    arg_parser = argparse.ArgumentParser(description=__description, \
        parents=\
        [\
        config.use_serial_override, \
        config.serial_port_override, \
        config.use_gpio_override, \
        config.code_type_override, \
        config.interface_type_override, \
        config.sound_override, \
        config.sounder_override, \
        config.spacing_override, \
        config.min_char_speed_override, \
        config.text_speed_override])
    arg_parser.add_argument("-F", "--full", action='store_true', default=False, \
    help="Play the full 'Quick Brown Fox...'", dest="full")
    arg_parser.add_argument("-D", "--disneyland", action='store_true', default=False, \
    help="Play the Disneyland inauguration speech (as heard at the Frontierland Train Station)", dest="disneyland")
    arg_parser.add_argument("-R", "--repeat", action='store_true', default=False, \
    help="Repeat playing the text/code until ^C is pressed", dest="repeat")

    args = arg_parser.parse_args()

    port = args.serial_port # serial port for KOB interface
    repeat = args.repeat
    sound = strtobool(args.sound)
    text_speed = args.text_speed  # text speed (words per minute)
    if (text_speed < 1) or (text_speed > 50):
        print("text_speed specified must be between 1 and 50")
        sys.exit(1)
    useGpio = strtobool(args.gpio) # Use GPIO (Raspberry Pi)

    myKOB = kob.KOB(portToUse=port, useGpio=useGpio, useAudio=sound)
    mySender = morse.Sender(text_speed)

    # Print some info in case people don't use the help
    print(__description)
    print("use '-h' or '--help' to see all of the available options.")
    if not (args.full or args.disneyland):
         print("Try '-F'|'--full' or '-D'|'--disneyland' for more content.")
    print("")

    code = (-1000, +2, -1000, +60, -60, +60, -60, +60, -60, +60,
            -180, +60, -60, +60, -1000, +1) # HI at 20 wpm

    first_time = True
    while first_time or repeat:
        first_time = False
        time.sleep(1)

        # then send the text
        __text = __full_QBF if args.full else __short_QBF
        if args.disneyland:
            __text = __disneyland_dedication
            print("From Disneyland Frontierland...")
        print(__text)
        myKOB.soundCode(mySender.encode('~')) # Open the circuit
        time.sleep(0.350)
        for c in __text:
            code = mySender.encode(c, True)
            myKOB.soundCode(code)
        time.sleep(0.350)
        myKOB.soundCode(mySender.encode('+')) # Close the circuit
        print()
        if repeat:
            print("Repeating in 3 seconds. Press ^C to exit...")
            time.sleep(3)
    sys.exit(0)
except KeyboardInterrupt:
    print()
    if not repeat:
        sys.exit(1) # Indicate this was an abnormal exit
    sys.exit(0)     # Normal exit for ^C when repeating
