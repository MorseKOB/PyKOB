#! python

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
Clock.py

Cuckoo clock substitute.
"""

import time
from pykob import kob, morse, log

log.log('Starting Clock')

AUDIO   = False
PORT = '/dev/ttyUSB0'
WPM     = 20  # code speed
MSGS = [
    ( 900, 'The time is nine oclock     L  L  L  L  L  L  L  L  L'),
    (1000, 'The time is ten oclock     L  L  L  L  L  L  L  L  L  L'),
    (1100, 'The time is eleven oclock     L  L  L  L  L  L  L  L  L  L  L'),
    (1200, 'The time is twelve oclock     L  L  L  L  L  L  L  L  L  L  L  L'),
    (1300, 'The time is one oclock     L'),
    (1400, 'The time is two oclock     L  L'),
    (1500, 'The time is three oclock     L  L  L'),
    (1600, 'The time is four oclock     L  L  L  L'),
    (1700, 'The time is five oclock     L  L  L  L  L'),
    (1800, 'The time is six oclock     L  L  L  L  L  L'),
    (1900, 'The time is seven oclock     L  L  L  L  L  L  L'),
    (2000, 'The time is eight oclock     L  L  L  L  L  L  L  L'),
    (2100, 'The time is nine oclock     L  L  L  L  L  L  L  L  L'),
    (2200, 'The time is ten oclock     L  L  L  L  L  L  L  L  L  L')]

myKOB = kob.KOB(port=PORT, audio=AUDIO)
mySender = morse.Sender(WPM)

while True:
    for m in MSGS:
        t0 = time.localtime()
        now = t0.tm_hour*3600 + t0.tm_min*60 + t0.tm_sec  # current time (sec)
        t1, s = m
        tMsg = 3600*(t1//100) + 60*(t1%100)  # time to send message
        dt = tMsg - now  # time to wait
        if dt > 0:
            time.sleep(dt)
            for c in s:
                code = mySender.encode(c)
                myKOB.sounder(code)  # to pace the code sent to the wire
    time.sleep(24*3600 - now)  # wait until midnight and start over
