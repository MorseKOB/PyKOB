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
SchedFeed.py

Sends messages according to a time schedule.

Serial port, code speed, and audio preferences should be specified by running the
'configure.sh' script or executing 'python3 Configure.py'.

Change history:

SchedFeed 1.3  2016-02-04
- display each character as it's sent

SchedFeed 1.2  2016-01-11
- sort msgs by time and adjust for duplicate times

SchedFeed 1.1  2015-12-30
- changed msgs element structure from list to tuple

SchedFeed 1.0  2015-12-28
- initial release
"""

import time
from pykob import config, kob, internet, morse, log

log.log('SchedFeed 1.3')

PORT = config.serial_port # serial port for KOB interface
WPM = config.words_per_min_speed  # code speed (words per minute)
SOUND = config.sound # whether to enable computer sound for sounder
WIRE    = 199  # 0 for no feed to internet
IDTEXT  = 'Test feed, XX'  # text to identify your feed, with office call
msgs = [  # 24-hour clock, no leading zeros
    ( 822, '~ DS HN OS +     ~ GA +   ~ OS HN NO 18 D 822 HN +    ~ OK DS +'),
    (1201, '~ DS NB OS +    ~ GA +  ~ OS NB NO 18 BY 1159 NB +   ~ OK DS +'),
    (1528, '~ DS U OS +     ~ GA +   ~ OS U NO 18 BY 239 U +     ~ OK DS +')]
        # last entry ends with )] instead of ),

msgs.sort(key=lambda m: m[0])  # sort messages by time
for i in range(len(msgs) - 1):  # adjust duplicate times
    if msgs[i+1][0] <= msgs[i][0]:
        msgs[i+1] = (msgs[i][0] + 1, msgs[i+1][1])
#for m in msgs:
#    print(m[0], m[1])  # uncomment to display sorted message list
    
myKOB = kob.KOB(port=PORT, audio=SOUND)
if WIRE:
    myInternet = internet.Internet(IDTEXT)
    myInternet.connect(WIRE)
mySender = morse.Sender(WPM)

try:
    while True:
        for m in msgs:
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
                    if WIRE:
                        myInternet.write(code)
                    print(c, end='', flush=True)  # display each character
                print(flush=True)  # start new line after each message
        time.sleep(24*3600 - now)  # wait until midnight and start over
except KeyboardInterrupt:
    print()
    sys.exit(0)     # Since normal operation is an infinite loop, ^C is actually a normal exit.
