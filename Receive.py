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

"""Receive.py

Monitors a KOB wire, and displays decoded text on the system console.

Command line parameters:
    KOB wire no. (defaults to 101)
    approximate code speed of incoming Morse (defaults to 20)

Code speed (WPM) should be specified by running the
'configure.sh' script or executing 'python3 Configure.py'.

Example:
    python Receive.py 110
"""

import sys
from time import sleep
from pykob import VERSION, config, internet, morse
import codecs

def readerCallback(char, spacing):
    halfSpaces = min(max(int(2 * spacing + 0.5), 0), 10)
    fullSpace = False
    if halfSpaces >= 2:
        fullSpace = True
        halfSpaces -= 2
    for i in range(halfSpaces):
        outFile.write(THINSPACE)
    if fullSpace:
        outFile.write(' ')
    outFile.write(char)
    outFile.flush()

try:
    WIRE     = 109  # default KOB wire to connect to
    WPM      = config.text_speed  # code speed (words per minute)
    OFFICEID = 'MorseKOB 4.0 test, AC (listening)'
    THINSPACE = '\u202F'  # narrow (half width) non-breaking space

    print('Python ' + sys.version + ' on ' + sys.platform)
    print('MorseKOB ' + VERSION)

    # get command line parameters, if any
    if len(sys.argv) > 1:
        WIRE = int(sys.argv[1])
    if len(sys.argv) > 2:
        WPM = int(sys.argv[2])

    myInternet = internet.Internet(OFFICEID)
    myReader = morse.Reader(callback=readerCallback)
    myInternet.connect(WIRE)
    outFile = codecs.open( "log.txt", "w", "utf-8" )
    sleep(0.5)
    while True:
        code = myInternet.read()
        myReader.decode(code)
except KeyboardInterrupt:
    print()
    sys.exit(0)     # Since the main program is an infinite loop, ^C is a normal, successful exit.
