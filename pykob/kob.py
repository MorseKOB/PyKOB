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
from enum import Enum, IntEnum, unique
from pykob import audio, config, log
try:
    import serial
    serialAvailable = True
except:
    log.log("pySerial not installed.")
    serialAvailable = False

DEBOUNCE  = 0.010  # time to ignore transitions due to contact bounce (sec)
CODESPACE = 0.120  # amount of space to signal end of code sequence (sec)
CKTCLOSE  = 0.75  # length of mark to signal circuit closure (sec)

if sys.platform == 'win32':
    from ctypes import windll
    windll.winmm.timeBeginPeriod(1)  # set clock resoluton to 1 ms (Windows only)

@unique
class CodeSource(IntEnum):
    local = 1
    wire = 2

class KOB:
    def __init__(
            self, port=None, interfaceType=config.interface_type.loop,
            audio=False, callback=None):
        self.t0 = -1.0  ### ZZZ Keep track of when the playback started
        self.callback = callback
        if port and serialAvailable:
            try:
                self.port = serial.Serial(port)
                self.port.dtr = True
            except:
                log.info("Interface for key and/or sounder on serial port '{}' not available. Key and sounder will not be used.".format(port))
                self.port = None
                self.callback = None
        else:
            self.port = None
            self.callback = None
        self.audio = audio
        self.interfaceType = interfaceType
        self.sdrState = False  # True: mark, False: space
        self.tLastSdr = time.time()  # time of last sounder transition
        self.setSounder(True)
        time.sleep(0.5)
        if self.port:
            self.keyState = self.port.dsr  # True: closed, False: open
            self.tLastKey = time.time()  # time of last key transition
            self.cktClose = self.keyState  # True: circuit latched closed
            if self.interfaceType == config.interface_type.key_sounder:
                self.setSounder(self.keyState)
        self.recorder = None
        if self.callback:
            callbackThread = threading.Thread(target=self.callbackRead)
            callbackThread.daemon = True
            callbackThread.start()

    @property
    def recorder(self):
        """ Recorder instance or None """
        return self.__recorder
    
    @recorder.setter
    def recorder(self, recorder):
        """ Recorder instance or None """
        self.__recorder = recorder

    def callbackRead(self):
        while True:
            code = self.key()
            self.callback(code)

    def key(self):
        code = ()
        while True:
            t = time.time()
            s = self.port.dsr
            if s != self.keyState:
                self.keyState = s
                dt = int((t - self.tLastKey) * 1000)
                self.tLastKey = t
                if self.interfaceType == config.interface_type.key_sounder:
                    self.setSounder(s)
                time.sleep(DEBOUNCE)
                if s:
                    code += (-dt,)
                elif self.cktClose:
                    code += (-dt, +2)  # unlatch closed circuit
                    self.cktClose = False
                    return code
                else:
                    code += (dt,)
            if not s and code and \
                    t > self.tLastKey + CODESPACE:
                return code
            if s and not self.cktClose and \
                    t > self.tLastKey + CKTCLOSE:
                code += (+1,)  # latch circuit closed
                self.cktClose = True
                return code
            if len(code) >= 50:  # code sequences can't have more than 50 elements
                return code
            time.sleep(0.001)

    def sounder(self, code, code_source=CodeSource.local):
        if self.t0 < 0:  ### ZZZ capture start time
            self.t0 = time.time()  ### ZZZ
##        print("KOB.sounder", round(time.time()-self.t0, 3), code)  ### ZZZ
        if self.__recorder:
            self.__recorder.record(code_source, code)
        for c in code:
            t = time.time()
            if c < -3000:  # long pause, change of senders, or missing packet
##                print("KOB.sounder long pause:", c, code)  ### ZZZ
                c = -1
                self.tLastSdr = t + 1.0
            if c > 0:  # start of mark
                self.setSounder(True)
            tNext = self.tLastSdr + abs(c) / 1000.
            dt = tNext - t
            if dt <= 0:
##                print(
##                        "KOB.sounder buffer empty:",
##                        round(time.time()-self.t0, 3),
##                        round(dt, 3), c, code)  ### ZZZ
                self.tLastSdr = t
            else:
                self.tLastSdr = tNext
                time.sleep(dt)
            if c > 1:  # end of (nonlatching) mark
                self.setSounder(False)

    def setSounder(self, state):
        if state != self.sdrState:
            self.sdrState = state
            if state:
                if self.port:
                    self.port.rts = True
                if self.audio:
                    audio.play(1)  # click
            else:
                if self.port:
                    self.port.rts = False
                if self.audio:
                    audio.play(0)  # clack

##windll.winmm.timeEndPeriod(1)
