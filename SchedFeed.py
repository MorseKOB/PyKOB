#! python

"""

SchedFeed.py

Sends messages according to a time schedule.

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
from pykob import kob, internet, morse, log

log.log('SchedFeed 1.3')

AUDIO   = True  # False if you don't want to hear audio
PORT    = None  # 'COM3' for comm port 3, etc., for an attached sounder
WIRE    = 199  # 0 for no feed to internet
IDTEXT  = 'Test feed, XX'  # text to identify your feed, with office call
WPM     = 20  # code speed
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
    
myKOB = kob.KOB(port=PORT, audio=AUDIO)
if WIRE:
    myInternet = internet.Internet(IDTEXT)
    myInternet.connect(WIRE)
mySender = morse.Sender(WPM)

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
