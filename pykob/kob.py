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
If the interface type is LOOP then the sounder (loop) is energized when the key-closer is
open. This is required to allow the key and closer to be read. In that case
calls to drive (energize/de-energize) the (general) sounder do not change the state of the
physical sounder (loop), only the virtual/synthesized sounder.
"""

import sys
import time
from enum import Enum, IntEnum, unique
from pykob import audio, config, log
from threading import Event, Thread

DEBOUNCE  = 0.018  # time to ignore transitions due to contact bounce (sec)
CODESPACE = 0.120  # amount of space to signal end of code sequence (sec)
CKTCLOSE  = 0.800  # length of mark to signal circuit closure (sec)

if sys.platform == 'win32':
    from ctypes import windll
    windll.winmm.timeBeginPeriod(1)  # set clock resoluton to 1 ms (Windows only)

@unique
class CodeSource(IntEnum):
    local = 1
    wire = 2
    player = 3
    key = 4
    keyboard = 5

class KOB:
    def __init__(
            self, interfaceType=config.interface_type.loop, portToUse=None,
            useGpio=False, useAudio=False, keyCallback=None):
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
        self.threadsStop = Event()
        self.tCodeSounded = -1.0  # Keep track of when the code was first sounded
        self.tSndrEnergized = time.time() # Time the sounder was last energized
        self.useGpioIn = False # Set to True if we establish GPIO input (Key state read)
        self.useGpioOut = False # Set to True if we establish GPIO output (Sounder drive)
        self.useSerialIn = False # Set to True if we establish Serial input (Key state read)
        self.useSerialOut = False # Set to True if we establish Serial output (Sounder drive)
        self.keyCallback = None # Set to the passed in value once we establish an interface
        self.audio = useAudio
        self.interfaceType = interfaceType
        self.lastKeyState = False # False is key open
        self.keyHasCloser = False # We will determine once the interface is configured
        self.__keyCloserIsOpen = False
        self.loopIsEnergized = False
        self.synthSounderEnergized = False # True: last played 'click', False: played 'clack' (or hasn't played)
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
                self.keyCallback = keyCallback
                self.useGpioOut = True
                self.useGpioIn = True
                self.keyHasCloser = self.keyIsClosed # If True (circuit closed) when we start, assume key has a closer
                print("The GPIO interface is available/active and will be used.")
            except:
                self.useGpioIn = False
                self.useGpioOut = False
                log.info("Interface for key and/or sounder on GPIO not available. Key and sounder will not function.")
        elif portToUse and serialModuleAvailable:
            try:
                self.port = serial.Serial(portToUse)
                self.port.dtr = True
                self.keyCallback = keyCallback
                self.useSerialOut = True
                self.useSerialIn = True
                self.keyHasCloser = self.keyIsClosed # If True (circuit closed) when we start, assume key has a closer
                self.useSerial = True
                print("The serial interface is available/active and will be used.")
            except:
                self.useSerialIn = False
                self.useSerialOut = False
                log.info("Interface for key and/or sounder on serial port '{}' not available. Key and sounder will not function.".format(portToUse))
        self.tLastSdr = time.time()  # time of last sounder transition
        time.sleep(0.5)
        self.tLastKey = time.time()  # time of last key transition
        self.circuitClosed = self.keyIsClosed  # True: circuit latched closed
        self.energizeLoop(self.circuitClosed, False)
        #
        # If configured for a loop interface and no sounder output, de-energize the loop
        if config.interface_type == config.InterfaceType.loop and not config.sounder:
            self.energizeLoop(False, False)
        self.__recorder = None
        self.keyreadThread = None
        self.powersaveThread = None
        if self.keyCallback:
            self.keyreadThread = Thread(name='KOB-KeyRead', daemon=True, target=self.callbackKeyRead)
            self.keyreadThread.start()
        powersaveThread = Thread(name='KOB-PowerSave', daemon=True, target=self.callbackPowerSave)
        powersaveThread.start()

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

    def exit(self):
        """
        Stop the threads and exit.
        """
        self.threadsStop.set()

    def callbackKeyRead(self):
        """
        Called by the KeyRead thread `run` to read code from the key.
        """
        while not self.threadsStop.is_set():
            code = self.key()
            if len(code) > 0:
                if code[-1] == 1: # special code for closer/circuit closed
                    self.keyCloserOpen(False)
                elif code[-1] == 2: # special code for closer/circuit open
                    self.keyCloserOpen(True)
            self.keyCallback(code)

    def callbackPowerSave(self):
        """
        Called by the PowerSave thread 'run' to control the power save (sounder energize)
        """
        while not self.threadsStop.is_set():
            now = time.time()
            power_save_seconds = config.sounder_power_save
            if power_save_seconds > 0:
                if (now - self.tSndrEnergized) > power_save_seconds:
                    self.powerSave(True)
            time.sleep(1.0)

    @property
    def keyIsClosed(self) -> bool:
        """
        Return the current key state.
        True = Closed (Down)
        False = Open (Up)

        Return
        ------
        kc : bool
            current key state
        """
        kc = False
        if self.useGpioIn:
            try:
                kc = not (self.gpi.is_pressed)
            except(OSError):
                log.err("GPIO key interface not available.")
                raise
        elif self.useSerialIn:
            try:
                kc = self.port.dsr
            except(OSError):
                log.err("Serial key interface not available.")
                raise
        # Invert key state if configured to do so (ex: input is from a modem)
        if config.invert_key_input:
            kc = not kc
        return kc


    def energizeLoop(self, energize: bool, fromKey: bool):
        '''
        Set the state of the sounder.
        True: Energized/Click
        False: De-Energized/Clack
        '''
        self.loopIsEnergized = energize
        if energize:
            self.tSndrEnergized = time.time()
        if config.sounder and not (config.interface_type == config.InterfaceType.loop and fromKey):
            # If using a loop interface and the source is the key,
            # don't do anything, as the closing of the key will sound the energized sounder.
            if self.useGpioOut:
                try:
                    if energize:
                        self.gpo.on() # Pin goes high and energizes sounder
                    else:
                        self.gpo.off() # Pin goes low and deenergizes sounder
                except(OSError):
                    log.err("GPIO output error setting sounder state")
            if self.useSerialOut:
                try:
                    if energize:
                        self.port.rts = True
                    else:
                        self.port.rts = False
                except(OSError):
                    log.err("Serial RTS error setting sounder state")
        if config.sound and self.audio:
            if energize != self.synthSounderEnergized:
                try:
                    if energize:
                        self.synthSounderEnergized = True
                        audio.play(1) # click
                    else:
                        self.synthSounderEnergized = False
                        audio.play(0) # clack
                except:
                    log.err("System audio error playing sounder state")

    def key(self):
        '''
        Process input from the key.
        '''
        code = ()
        while self.useGpioIn or self.useSerialIn:
            try:
                kc = self.keyIsClosed
            except(OSError):
                return "" # Stop trying to process the key
            t = time.time()
            if kc != self.lastKeyState:
                self.lastKeyState = kc
                dt = int((t - self.tLastKey) * 1000)
                self.tLastKey = t
                #
                # For 'Seperate Key & Sounder' and the Audio Sounder,
                # drive it here to avoid as much delay from the key
                # transitions as possible.
                #
                if config.local:
                    self.energizeLoop(kc, True)
                time.sleep(DEBOUNCE)
                if kc:
                    code += (-dt,)
                elif self.circuitClosed:
                    code += (-dt, +2)  # unlatch closed circuit
                    self.circuitClosed = False
                    return code
                else:
                    code += (dt,)
            if not kc and code and \
                    t > self.tLastKey + CODESPACE:
                return code
            if kc and not self.circuitClosed and \
                    t > self.tLastKey + CKTCLOSE:
                code += (+1,)  # latch circuit closed
                self.circuitClosed = True
                return code
            if len(code) >= 50:  # code sequences can't have more than 50 elements
                return code
            time.sleep(0.001)
        return ""

    def soundCode(self, code, code_source=CodeSource.local):
        '''
        Process the code and sound it.
        '''
        self.powerSave(False)
        if self.tCodeSounded < 0:  # capture start time
            self.tCodeSounded = time.time()
        if self.__recorder and not code_source == CodeSource.player:
            self.__recorder.record(code_source, code)
        for c in code:
            if self.threadsStop.is_set():
                self.energizeLoop(True, True)
                return
            t = time.time()
            if c < -3000:  # long pause, change of senders, or missing packet
                c = -1
            if c == 1 or c > 2:  # start of mark
                self.energizeLoop(True, code_source == CodeSource.key)
            tNext = self.tLastSdr + abs(c) / 1000.
            dt = tNext - t
            if dt <= 0:
                self.tLastSdr = t
            else:
                self.tLastSdr = tNext
                time.sleep(dt)
            if c > 1:  # end of (nonlatching) mark
                self.energizeLoop(False, code_source == CodeSource.key)

    def keyCloserOpen(self, open):
        '''
        Track the physical key closer. This controlles the Loop/KOB sounder state.
        '''
        self.__keyCloserIsOpen = open
        #
        # If this is a loop interface and the closer is now open (meaning that they are
        # intending to send code), and if the sounder is enabled (in the configuration),
        # energize the loop so the sounder will follow the key. Likewise, if it's closed,
        # de-energize the loop.
        #
        if config.interface_type == config.InterfaceType.loop and config.sounder:
            self.energizeLoop(open, True)
        if open:
            self.powerSave(False)

    def powerSave(self, enable: bool):
        '''
        Turn off the loop power to save power (reduce risk of fire, etc.)
        '''
        # Don't enable Power Save if the key is open.
        if enable and not self.keyIsClosed:
            return
        
        now = time.time()
        if self.useGpioOut:
            try:
                if enable:
                    self.gpo.off() # Pin goes low and deenergizes sounder
                else:
                    if self.loopIsEnergized:
                        self.gpo.on() # Pin goes high and energizes sounder
                        self.tSndrEnergized = now

            except(OSError):
                log.err("GPIO output error setting sounder state")
        if self.useSerialOut:
            try:
                if enable:
                    self.port.rts = False
                else:
                    if self.loopIsEnergized:
                        self.port.rts = True
                        self.tSndrEnergized = now
            except(OSError):
                log.err("Serial RTS error setting sounder state")

##if sys.platform == 'win32':  ### ZZZ This should be executed when the program is closed.
##    windll.winmm.timeEndPeriod(1)  # Restore default clock resolution. (Windows only)
