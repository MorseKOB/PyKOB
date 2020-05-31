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

"""Time.py

Sends time signals to a KOB wire and/or to a sounder or speakers. The time
signals can be sent hourly, daily at 12:00 noon EST, or continuously (every
five minutes).

Optional command line parameters:
    mode - Continuous, Hourly, or Daily (can be lowercase, only need first
            letter, default: continuous)
    wire - KOB wire no. (default: no connection to KOB server)
    idText - office call, etc.

If wire is specified, then idText is required. Only sends over the wire if
someone is listening.

Serial port and audio preferences should be specified by running the
'configure.sh' script or executing 'python3 Configure.py'.

Examples:
    python Time.py
    python Time.py d 102 "Time signals, AC" 

Change history:

Time 1.5  2020-05-28
- changed header to `#!/usr/bin/env python3`

Time 1.4  2020-02-13
- removed #!/usr/bin/env python header, which fails with Windows 10

Time 1.3  2019-02-13
- converted from legacy morsekob module to use pykob module
- discontinued use of separate config file
"""

def send(code):
    if wire and time.time() < myInternet.tLastListener + TIMEOUT:
        myInternet.write(code)
    myKOB.sounder(code)

try:
    import sys
    import time
    import threading
    from pykob import config,log, kob, internet

    VERSION = '1.5'
    PORT    = config.serial_port # serial port for KOB interface
    SOUND   = config.sound # whether to enable computer sound for sounder
    TIMEOUT = 30.0  # time to send after last indication of live listener (sec)
    TICK    = (-1, +1, -200, +1, -200, +2) + 3 * (-200, +2)
    NOTICK  = 5 * (-200, +2)
    MARK    = (-1, +1) + 9 * (-200, +1) + (-200, +2)

    log.log('Starting Time {0}'.format(VERSION))

    nargs = len(sys.argv)
    mode = sys.argv[1][0] if nargs > 1 else 'c'
    if nargs > 2:
        wire = int(sys.argv[2])
        idText = sys.argv[3]
    else:
        wire = None

    myKOB = kob.KOB(PORT, SOUND)

    if wire:
        myInternet = internet.Internet(idText)
        myInternet.connect(wire)
        time.sleep(1)

        def checkForListener():
            while True:
                myInternet.read()  # activate the reader to get tLastListener updates
            
        listenerThread = threading.Thread(target=checkForListener)
        listenerThread.daemon = True
        listenerThread.start()

    while True:
        now = time.gmtime()
        hh = now.tm_hour
        mm = now.tm_min
        ss = now.tm_sec
        time.sleep(60 - ss)  # wait for the top of the minute
        nn = (mm + 1) % 5  # nn: minute 0 to minute 5
        if mode == 'c' or mode == 'h' and mm == 59 or \
                mode == 'd' and hh == 16 and mm >= 55:
            if mode == 'h':
                send(MARK)
            elif nn == 0:
                send(MARK)
                for i in range(7):
                    send(NOTICK)
                send((-1, +1))  # close the circuit
            elif nn == 1:
                time.sleep(55)
                send((-1, +2))  # open the circuit
            else:
                for i in range(29):
                    send(TICK)
                send(NOTICK)
                for i in range(21):
                    send(TICK)
                if nn == 2:
                    for i in range(2):
                        send(TICK)
                    send(NOTICK)
                    for i in range(2):
                        send(TICK)
                elif nn == 3:
                    for i in range(2):
                        send(TICK)
                    for i in range(2):
                        send(NOTICK)
                    send(TICK)
                elif nn == 4:
                    for i in range(5):
                        send(NOTICK)
except KeyboardInterrupt:
    print()
    sys.exit(0)     # Since the main program is an infinite loop, ^C is a normal, successful exit.
