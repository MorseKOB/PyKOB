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

"""Receive.py

Monitors a KOB wire, and displays decoded text on the system console.

This reads the current configuration and supports the common option flags.
To maintain backward compatibility it also allows a positional command
line parameter:
    1. KOB wire no.

Example:
    python Receive.py 110
"""

from pykob import VERSION, config, log, kob, internet, morse

import argparse
import codecs
from distutils.util import strtobool
import sys
from time import sleep

THINSPACE = '\u202F'  # narrow (half width) non-breaking space

def readerCallback(char, spacing):
    halfSpaces = min(max(int(2 * spacing + 0.5), 0), 10)
    fullSpace = False
    if halfSpaces >= 2:
        fullSpace = True
        halfSpaces -= 2
    for i in range(halfSpaces):
        outFile.write(THINSPACE)
        print(THINSPACE, end='')
    if fullSpace:
        outFile.write(' ')
        print(' ', end='')
    outFile.write(char)
    outFile.flush()
    print(char, end='', flush=True)
    if char == '.':
        print()
    elif char == '=':
        print()

try:
    arg_parser = argparse.ArgumentParser(description="Monitors a KOB wire, and displays decoded text.", \
        parents=\
        [\
        config.serial_port_override, \
        config.gpio_override, \
        config.code_type_override, \
        config.interface_type_override, \
        config.sound_override, \
        config.sounder_override, \
        config.spacing_override, \
        config.station_override, \
        config.min_char_speed_override, \
        config.text_speed_override])
    arg_parser.add_argument('wire', nargs='?', default=config.wire, type=int,\
        help='Wire to monitor. If specified, this is used rather than the configured wire.')
    args = arg_parser.parse_args()

    port = args.serial_port # serial port for KOB interface
    useGpio = strtobool(args.gpio) # Use GPIO (Raspberry Pi)

    office_id = args.station # the Station/Office ID string to attach with
    code_type = config.codeTypeFromString(args.code_type)
    spacing = args.spacing
    min_char_speed = args.min_char_speed
    text_speed = args.text_speed  # text speed (words per minute)
    if (text_speed < 1) or(text_speed > 50):
        print("text_speed specified must be between 1 and 50")
        sys.exit(1)
    sound = strtobool(args.sound)
    sounder = strtobool(args.sounder)
    wire = args.wire # wire to connect to

    print('Python ' + sys.version + ' on ' + sys.platform)
    print('MorseKOB ' + VERSION)

    print('Receiving from wire: ' + str(wire))
    print('Connecting as Station/Office: ' + office_id)

    myInternet = internet.Internet(office_id)
    myReader = morse.Reader(wpm=text_speed, codeType=code_type, callback=readerCallback)
    myKOB = kob.KOB(portToUse=port, useGpio=useGpio, useAudio=sound)

    myInternet.connect(wire)
    outFile = codecs.open( "log.txt", "w", "utf-8" )
    sleep(0.5)
    while True:
        code = myInternet.read()
        myReader.decode(code)
        myKOB.soundCode(code)
except KeyboardInterrupt:
    print()
    print()
    sys.exit(0)     # Since the main program is an infinite loop, ^C is a normal, successful exit.
