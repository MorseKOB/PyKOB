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

"""Replay.py

Replays Morse captured to a file.

Serial port and audio preferences should be specified by running the
'configure.sh' script or executing 'python3 Configure.py'.

Usage: python Replay.py <filename.txt

Example: py Replay.py <"Train orders.txt"
"""

import time
from pykob import config, kob, log, morse

VERSION = '1.4'
PORT = config.serial_port # serial port for KOB interface
SOUND = config.sound # whether to enable computer sound for sounder
WPM = config.text_speed # speed of code in Words-Per-Minute
CODE_TYPE = config.code_type # the code type - American or International

codes = ''
myKOB = kob.KOB(port=PORT, audio=SOUND)
myReader = morse.Reader(wpm=WPM, codeType=CODE_TYPE)
time = time.gmtime
rcvdSeqNo = -1
code = []

line = 0
while True:
    buf = input()
    print("Line: {0}".format(line))
    line++
    print(buf)
    nBytes = len(buf)
    if nBytes == 2:
        print("<<ACK>>")
        pass  # ignore Ack packet
    elif nBytes == 496:  # code or ID packet
        cp = codePacketFormat.unpack(buf)
        cmd, byts, stnID, seqNo, code = cp[0], cp[1], cp[2], cp[3], cp[4:]
        stnID, sep, fill = stnID.decode(encoding='ascii').partition(NUL)
        n = code[51]
        if n == 0:  # ID packet
            print(stnID)
            if seqNo == rcvdSeqNo + 2:
                rcvdSeqNo = seqNo  # update sender's seq no, ignore others
            pass # sequence set, don't sound this
        elif n > 0 and seqNo != rcvdSeqNo:  # code packet
            if seqNo != rcvdSeqNo + 1:  # sequence break
                code = (-0x7fff,) + code[1:n]
            else:
                code = code[:n]
            rcvdSeqNo = seqNo
    else:
        log.log("PyKOB.internet received invalid record length: {0}".
                format(nBytes))
    # codes += '[' + s + '] '
    # code = [int(x) for x in s.split()]
    # Sound the code
    myKOB.sounder(code)
