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

Handles external key and/or sounder and the virtual sounder (computer audio).

The interface type controls certain aspects of how the physical sounder is driven.
If the interface type is LOOP then the sounder is energized when the key-closer is 
open. This allows the sounder to follow the key as it closes and opens. In that case 
calls to drive (energize/de-energize) the (general) sounder do not change the state of the 
physical sounder, only the virtual sounder.
"""

import sys
import threading
import time
from enum import Enum, IntEnum, unique
from pykob import audio, config, log

DEBOUNCE  = 0.015  # time to ignore transitions due to contact bounce (sec)
CODESPACE = 0.120  # amount of space to signal end of code sequence (sec)
CKTCLOSE  = 0.75  # length of mark to signal circuit closure (sec)

if sys.platform == 'win32':
    from ctypes import windll
    windll.winmm.timeBeginPeriod(1)  # set clock resoluton to 1 ms (Windows only)

@unique
class CodeSource(IntEnum):
    local = 1
    wire = 2
    player = 3

class KOB:
    def __init__(
            self, interfaceType=config.interface_type.loop, portToUse=None,
            useGpio=False, audio=False, callback=None):
        # Conditionally load GPIO or Serial library if requested.
        #  GPIO takes priority if both are requested.
        gpioModuleAvailable = False
        serialModuleAvailable = False
        if useGpio:
            try:
                from gpiozero import LED, Button
                gpioModuleAvailable = True
            except:
                log.err("Module 'gpiozero' is not available. GPIO interface cannot be used.")
        if portToUse and not gpioModuleAvailable:
            try:
                import serial
                serialModuleAvailable = True
            except:
                log.err("Module pySerial is not available. Serial interface cannot be used.")

        self.t0 = -1.0  ### ZZZ Keep track of when the playback started
        self.useGpioIn = False # Set to True if we establish GPIO input (Key state read)
        self.useGpioOut = False # Set to True if we establish GPIO output (Sounder drive)
        self.useSerialIn = False # Set to True if we establish Serial input (Key state read)
        self.useSerialOut = False # Set to True if we establish Serial output (Sounder drive)
        self.callback = None # Set to the passed in value once we establish an interface
        self.audio = audio
        self.interfaceType = interfaceType
        self.keyHasCloser = False # We will determine once the interface is configured
        self.sdrState = False  # True: mark/energized, False: space/unenergized
        #
        # Set up the external interface to the key and sounder.
        #  GPIO takes priority if it is requested and available.
        #  Then, serial is used if Port is set and PySerial is available.
        #
        # The reason for some repeated code in these two sections is to perform the Key read 
        # and Sounder set within the section so the error can be reported with an appropriate 
        # message and the interface availability can be set knowing that both operations 
        # have been performed.
        if useGpio and gpioModuleAvailable:
            try:
                self.gpi = Button(21, pull_up=True)  # GPIO21 is key input.
                self.gpo = LED(26)  # GPIO26 used to drive sounder.
                self.callback = callback
                self.useGpioOut = True
                self.energizeSounder(True)
                self.useGpioIn = True
                self.keyState = self.getKeyState()
                self.keyHasCloser = self.keyState # If True (circuit closed) when we start, assume key has a closer
                print("The GPIO interface is available/active and will be used.")
            except:
                self.useGpioIn = False
                self.useGpioOut = False
                log.info("Interface for key and/or sounder on GPIO not available. Key and sounder will not function.")
        elif portToUse and serialModuleAvailable:
            try:
                self.port = serial.Serial(portToUse)
                self.port.dtr = True
                self.callback = callback
                self.useSerialOut = True
                self.energizeSounder(True)
                self.useSerialIn = True
                self.keyState = self.getKeyState()
                self.keyHasCloser = self.keyState # If True (circuit closed) when we start, assume key has a closer
                self.useSerial = True
                print("The serial interface is available/active and will be used.")
            except:
                self.useSerialIn = False
                self.useSerialOut = False
                log.info("Interface for key and/or sounder on serial port '{}' not available. Key and sounder will not function.".format(portToUse))
        self.tLastSdr = time.time()  # time of last sounder transition
        time.sleep(0.5)  # ZZZ Why is this here?
        self.keyState = self.getKeyState()
        self.tLastKey = time.time()  # time of last key transition
        self.cktClose = self.keyState  # True: circuit latched closed
        self.recorder = None
        if self.callback:
            keyreadThread = threading.Thread(name='KOB-KeyRead', daemon=True, target=self.callbackRead)
            keyreadThread.start()

    @property
    def recorder(self):
        """ Recorder instance or None """
        return self.__recorder
    
    @recorder.setter
    def recorder(self, recorder):
        """ Recorder instance or None """
        self.__recorder = recorder

    @property
    def keyCloserIsOpen(self):
        return self.__keyCloserIsOpen

    def callbackRead(self):
        """
        Called by the KeyRead thread `run` to read code from the key.
        """
        while True:
            code = self.key()
            self.callback(code)

    def getKeyState(self) -> bool:
        """
        Return the current key state.
        True = DOWN
        False = UP

        Return
        ------
        ks : bool
            current key state
        """
        ks = False
        if self.useGpioIn:
            try:
                ks = not (self.gpi.is_pressed)
            except(OSError):
                log.err("GPIO key interface not available.")
                raise
        elif self.useSerialIn:
            try:
                ks = self.port.dsr
            except(OSError):
                log.err("Serial key interface not available.")
                raise
        # Invert key state if configured to do so (ex: input is from a modem)
        if config.invert_key_input:
            ks = not ks
        return ks

    def setSounder(self, state):
        if state != self.sdrState:
            self.sdrState = state
            if self.useGpioOut:
                try:
                    if state:
                        self.gpo.on() # Pin goes high and energizes sounder
                    else:
                        self.gpo.off() # Pin goes low and deenergizes sounder
                except(OSError):
                    log.err("GPIO output error setting sounder state")
            if self.useSerialOut:
                try:
                    if state:
                        self.port.rts = True
                    else:
                        self.port.rts = False
                except(OSError):
                    log.err("Serial RTS error setting sounder state")
            if self.audio:
                try:
                    if state:
                        audio.play(1) # click
                    else:
                        audio.play(0) # clack
                except:
                    log.err("System audio error playing sounder state")
        
    def key(self):
        code = ()
        while self.useGpioIn or self.useSerialIn:
            try:
                s = self.keyIsCurrentlyClosed()
            except(OSError):
                return "" # Stop trying to process the key
            t = time.time()
            if s != self.keyState:
                self.keyState = s
                dt = int((t - self.tLastKey) * 1000)
                self.tLastKey = t
                if self.interfaceType == config.interface_type.key_sounder:
                    self.energizeSounder(s)
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
        return ""

    def keyIsCurrentlyClosed(self):
        '''
        Get the current key state.

        Return: True=closed, False=open
        '''
        if not self.port:
            return False
        ks = self.port.dsr
        if config.invert_key_input:
            ks = not ks # invert for RS-323 modem signal
        return ks

    def sounder(self, code, code_source=CodeSource.local):
        if self.t0 < 0:  ### ZZZ capture start time
            self.t0 = time.time()  ### ZZZ
        if self.__recorder and not code_source == CodeSource.player:
            self.__recorder.record(code_source, code)
        for c in code:
            t = time.time()
            if c < -3000:  # long pause, change of senders, or missing packet
                c = -1
##                self.tLastSdr = t + 1.0
            if c == 1 or c > 2:  # start of mark
                self.energizeSounder(True)
            tNext = self.tLastSdr + abs(c) / 1000.
            dt = tNext - t
            if dt <= 0:
                self.tLastSdr = t
            else:
                self.tLastSdr = tNext
                time.sleep(dt)
            if c > 1:  # end of (nonlatching) mark
                self.energizeSounder(False)

    def keyCloserOpen(self, open):
        '''
        Track the physical key closer. This controlles the Loop/KOB sounder state.

        If Closer is open and the type is Loop, energize (power) the sounder loop so it can follow the key.
        If the Closer is closed and the type is Loop, de-energize the sounder so it can be driven to 'click'/'clack'.
        '''
        if self.noKeyCloserExists:
            return
        self.keyCloserIsOpen = open
        if self.interfaceType == config.interface_type.loop:
            if self.keyCloserIsOpen:
                self.energizePhysicalSounder(True)
            else:
                self.energizePhysicalSounder(False)

    def energizePhysicalSounder(self, energize):
        '''
        Energize the physical sounder (click) or De-energize (clack) if enabled.
        '''
        try:
            if energize != self.physicalSdrEnergized:
                self.physicalSdrEnergized = energize
                if self.port:
                    if energize:
                        log.debug("click-p")
                        self.port.rts = True
                    else:
                        log.debug(" clack-p")
                        self.port.rts = False
        except(OSError):
            log.err("Port not available.")
            self.port = None

    def energizeSynthSounder(self, energize):
        '''
        Energize the synthetic (computer audio) sounder (click) or De-energize (clack) if enabled.
        '''
        if energize != self.synthSdrEnergized:
            self.synthSdrEnergized = energize
            if energize:
                if self.audio:
                    log.debug("click-s")
                    audio.play(1)  # click
            else:
                if self.audio:
                    log.debug(" clack-s")
                    audio.play(0)  # clack

    def energizeSounder(self, energize):
        '''
        Energize the sounder (click) or De-energize (clack)
        '''
        if self.interfaceType != config.InterfaceType.loop or not self.keyCloserIsOpen:
            # Drive the physical sounder if the interface type isn't loop 
            # or it is loop and the key-closer is closed or doesn't exist
            self.energizePhysicalSounder(energize)
        self.energizeSynthSounder(energize)

##if sys.platform == 'win32':  ### ZZZ This should be executed when the program is closed.
##    windll.winmm.timeEndPeriod(1)  # Restore default clock resolution. (Windows only)
