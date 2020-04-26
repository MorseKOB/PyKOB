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
kob module

Handles external key and/or sounder.
"""

import sys
import threading
import time
from pykob import audio, log
try:
    import serial
    ok = True
except:
    log.log('pySerial not installed.')
    ok = False

DEBOUNCE  = 0.010  # time to ignore transitions due to contact bounce (sec)
CODESPACE = 0.120  # amount of space to signal end of code sequence (sec)
CKTCLOSE  = 0.75  # length of mark to signal circuit closure (sec)

if sys.platform == 'win32':
    from ctypes import windll
    windll.winmm.timeBeginPeriod(1)  # set clock resoluton to 1 ms (Windows only)

class KOB:
    def __init__(self, port=None, audio=False, echo=False, callback=None):
        if port and ok:
            try:
                self.port = serial.Serial(port)
                self.port.setDTR(True)
            except:
                log.err('Port {} not available.'.format(port))
                self.port = None
        else:
            self.port = None
        self.audio = audio
        self.echo = echo
        self.sdrState = False  # True: mark, False: space
        self.tLastSdr = time.time()  # time of last sounder transition
        self.setSounder(True)
        time.sleep(0.5)
        if self.port:
            self.keyState = self.port.getDSR()  # True: closed, False: open
            self.tLastKey = time.time()  # time of last key transition
            self.cktClose = self.keyState  # True: circuit latched closed
            if self.echo:
                self.setSounder(self.keyState)
        self.callback = callback
        if callback:
            callbackThread = threading.Thread(target=self.callbackRead)
            callbackThread.daemon = True
            callbackThread.start()

    def callbackRead(self):
        while True:
            code = self.key()
            self.callback(code)

    def key(self):
        code = ()
        while True:
            s = self.port.getDSR()
            if s != self.keyState:
                self.keyState = s
                t = time.time()
                dt = int((t - self.tLastKey) * 1000)
                self.tLastKey = t
                if self.echo:
                    self.setSounder(s)
                time.sleep(DEBOUNCE)  # MAYBE COMPUTE THIS BASED ON CURRENT TIME
                if s:
                    code += (-dt,)
                elif self.cktClose:
                    code += (-dt, +2)  # unlatch closed circuit
                    self.cktClose = False
                    return code
                else:
                    code += (dt,)
            if not s and code and \
                    time.time() > self.tLastKey + CODESPACE:
                return code
            if s and not self.cktClose and \
                    time.time() > self.tLastKey + CKTCLOSE:
                code += (+1,)  # latch circuit closed
                self.cktClose = True
                return code
            time.sleep(0.001)

    def sounder(self, code):
        for c in code:
            if c < -3000:
                c = -500
            if c == 1 or c > 2:
                self.setSounder(True)
            if c < 0 or c > 2:
                tNext = self.tLastSdr + abs(c) / 1000.
                t = time.time()
                dt = tNext - t
                if dt <= 0:
                    self.tLastSdr = t
                else:
                    self.tLastSdr = tNext
                    time.sleep(dt)
            if c > 1:
                self.setSounder(False)

    def setSounder(self, state):
        if state != self.sdrState:
            self.sdrState = state
            if state:
                if self.port:
                    self.port.setRTS(True)
                if self.audio:
                    audio.play(1)  # click
            else:
                if self.port:
                    self.port.setRTS(False)
                if self.audio:
                    audio.play(0)  # clack

##windll.winmm.timeEndPeriod(1)
