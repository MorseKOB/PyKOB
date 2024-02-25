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
from pykob import audio, config, config2, log
from pykob.config2 import Config
from threading import Event, Thread
from typing import Any, Callable, Optional

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

class __ks_interface:
    """
    Key & Sounder Interface

    This is the base-class and also handles the synth-sounder (computer audio)
    """
    def __init__(self, use_audio: bool, use_sounder: bool, sounder_power_save_secs: float, invert_key_input: bool, interface_type: config.InterfaceType=config.InterfaceType.loop):
        self._invert_key_input: bool = invert_key_input
        self._use_audio: bool = use_audio
        self._use_sounder: bool = use_sounder
        self._interface_type: config.InterfaceType = interface_type
        self._key_closer_is_open: bool = False
        self._power_saving: bool = False  # Indicates if Power-Save is active
        self._sounder_energized: bool = False
        self._t_sounder_energized: float = -1.0
        self._sounder_power_save_secs: float = sounder_power_save_secs
        self._synthsounder_energized: bool = False  # True: last played 'click', False: played 'clack' (or hasn't played)
        self._threadsStop: Event = Event()
        self._virtual_closer_is_open: bool = False
        #
        self._powersave_thread = None

    def _callbackPowerSave(self):
        """
        Called by the PowerSave thread 'run' to control the power save (sounder energize)
        """
        while not self._threadsStop.is_set():
            now = time.time()
            if self._sounder_power_save_secs > 0 and not self._power_saving:
                if self._t_sounder_energized > 0 and (now - self._t_sounder_energized) > self._sounder_power_save_secs:
                    self.power_save(True)
            time.sleep(1.0)

    def _energize_hw_sounder(self, energize: bool):
        """
        Hardware subclasses should implement this.
        """
        return

    def _key_is_closed(self) -> bool:
        """
        Hardware subclasses should implement this.
        """
        return True

    def _loop_power_off(self):
        """
        Hardwar subclasses should implement this.
        """
        return

    def _loop_power_on(self):
        """
        Hardwar subclasses should implement this.
        """
        return

    @property
    def virtual_closer_is_open(self) -> bool:
        return self._virtual_closer_is_open

    def energize_sounder(self, energize: bool, from_key: bool):
        '''
        Set the state of the sounder.
        True: Energized/Click
        False: De-Energized/Clack
        '''
        if energize:
            self._t_sounder_energized = time.time()
        if self._use_sounder and not (self._interface_type == config.InterfaceType.loop and from_key):
            # If using a loop interface and the source is the key,
            # don't do anything, as the closing of the key will energize the sounder,
            # since the loop is energized.
            self._sounder_energized = energize
            self._energize_hw_sounder(energize)
        if self._use_audio:
            if energize != self._synthsounder_energized:
                self._synthsounder_energized = energize
                try:
                    if energize:
                        audio.play(1) # click
                    else:
                        audio.play(0) # clack
                except:
                    log.err("System audio error playing sounder state")

    def exit(self):
        """
        Stop the threads and exit.
        """
        self._threadsStop.set()

    def key_is_available(self) -> bool:
        return False

    def key_is_closed(self) -> bool:
        """
        Since there is no hardware, always indicate that the key is closed.
        """
        kc = self._key_is_closed()
        # Invert key state if configured to do so (ex: input is from a modem)
        if self._invert_key_input:
            kc = not kc
        return kc

    def loop_power_off(self):
        '''
        Force the loop power off (de-energize sounder).

        This is used to silence the sounder on a loop interface (KOB).
        '''
        self._sounder_energized = False
        self._loop_power_off()

    def loop_power_on(self):
        '''
        Force the loop power on (energize sounder).

        This is used to enable the sounder on a loop interface (KOB).
        '''
        self._sounder_energized = True
        self._t_sounder_energized = time.time()
        self._loop_power_on()

    def power_save(self, enable: bool):
        '''
        True to turn off the sounder power to save power (reduce risk of fire, etc.)
        '''
        # Don't enable Power Save if the key is open.
        if enable and (self._virtual_closer_is_open or self._key_closer_is_open):
            return
        if not enable and not self._power_saving:
            return  # Already disabled
        if enable and self._power_saving:
            return  # Already enabled

        now = time.time()
        if enable:
            self._energize_hw_sounder(False)
            self._power_saving = True
            log.debug("Sounder power-save on", 2)
        else: # disable power-save. restore the state of the sounder
            self._power_saving = False
            log.debug("Sounder power-save off", 2)
            if self._sounder_energized:
                self._energize_hw_sounder(True)
                self.tSndrEnergized = now

    def set_key_closer_open(self, open: bool):
        '''
        Track the physical key closer. This controlles the Loop/KOB sounder state.
        '''
        self._key_closer_is_open = open
        #
        # If this is a loop interface and the closer is now open (meaning that they are
        # intending to send code), make sure the loop is powered if the sounder is enabled
        # (in the configuration) so the sounder will follow the key.
        #
        if self._interface_type == config.InterfaceType.loop and self._use_sounder:
            self._energize_hw_sounder(open)
        if open:
            self.power_save(False)

    def set_virtual_closer_open(self, open: bool):
        '''
        Track the virtual closer. This controlles the Loop/KOB sounder state.
        '''
        self._virtual_closer_is_open = open
        if open:
            self.power_save(False)

    def start(self):
        pass

class __ks_interface_gpio(__ks_interface):
    def __init__(self, gpio_button, gpio_led, use_audio: bool, use_sounder: bool, sounder_power_save_secs: float, invert_key_input: bool, interface_type: config.InterfaceType=config.InterfaceType.loop):
        super().__init__(use_audio, use_sounder, sounder_power_save_secs, invert_key_input, interface_type)
        pass
        self._gpi = gpio_button(21, pull_up=True)  # GPIO21 is key input.
        self._gpo = gpio_led(26)  # GPIO26 used to drive sounder.
        print("The GPIO interface is available/active and will be used.")

    def _energize_hw_sounder(self, energize: bool):
        try:
            if energize:
                self._gpo.on() # Pin goes high and energizes sounder
            else:
                self._gpo.off() # Pin goes low and deenergizes sounder
        except(OSError):
            log.err("GPIO output error setting sounder state")

    def _key_is_closed(self) -> bool:
        """
        Check the state of the key and return True if it is closed.
        """
        kc = False
        try:
            kc = not (self._gpi.is_pressed)
        except(OSError):
            log.err("GPIO key interface not available.")
        return kc

    def _loop_power_off(self):
        try:
            self.gpo.off() # Pin goes low and deenergizes sounder
        except(OSError):
            log.err("GPIO output error when de-energizing loop")

    def _loop_power_on(self):
        try:
            self.gpo.on() # Pin goes high and energizes sounder
        except(OSError):
            log.err("GPIO output error when energizing loop")

    def key_is_available(self) -> bool:
        kia = False
        try:
            kc = not (self._gpi.is_pressed)
            kia = True  # if we get here, we can at least read the pin
        except(OSError):
            pass
        return kia

    def start(self):
        self._powersave_thread = Thread(
            name="Sounder-PowerSave", daemon=True, target=self._callbackPowerSave
        )
        self._powersave_thread.start()


class __ks_interface_serial(__ks_interface):
    def __init__(self, port, use_audio: bool, use_sounder: bool, sounder_power_save_secs: float, invert_key_input: bool, interface_type: config.InterfaceType=config.InterfaceType.loop):
        super().__init__(use_audio, use_sounder, sounder_power_save_secs, invert_key_input, interface_type)
        self._port = port
        self._port.dtr = True # Provide power for the Les/Chip Loop Interface
        # Check for loopback - The PyKOB interface loops-back data to identify itself. It uses CTS for the key.
        self._key_read = self.__read_dsr
        print("The serial interface is available/active and will be used.")
        port.write(b"PyKOB\n")
        time.sleep(0.5)
        indata = port.readline()
        if indata == b"PyKOB\n":
            self._key_read = self.__read_cts
            log.info("KOB Serial Interface is 'PyKOB' type.")
        else:
            log.info("KOB Serial Interface is 'L/C' type.")

    def __read_cts(self) -> bool:
        return self._port.cts

    def __read_dsr(self) -> bool:
        return self._port.dsr

    def _energize_hw_sounder(self, energize: bool):
        try:
            if energize:
                self._port.rts = True
            else:
                self._port.rts = False
        except(OSError):
            log.err("Serial RTS error setting sounder state")

    def _key_is_closed(self) -> bool:
        """
        Read the key an return True if it is closed.
        """
        return self._key_read()

    def _loop_power_off(self):
        try:
            self._port.rts = False
        except(OSError):
            log.err("Serial RTS error when de-energizing loop")

    def _loop_power_on(self):
        try:
            self._port.rts = True
        except(OSError):
            log.err("Serial RTS error when energizing loop")

    def key_is_available(self) -> bool:
        kia = False
        try:
            kc = self._key_read()
            kia = True  # if we get here, we can at least read the signal
        except(OSError):
            pass
        return kia

    def start(self):
        self._powersave_thread = Thread(
            name="Sounder-PowerSave", daemon=True, target=self._callbackPowerSave
        )
        self._powersave_thread.start()


def _get_ks_interface(use_audio: bool, use_sounder: bool, use_gpio: bool, port_to_use: str, invert_key_input: bool, sounder_power_save_secs: float, interface_type: config.InterfaceType) -> __ks_interface:
    """
    Given the arguments, do some tests and return a kob_hw object to use.

        Conditionally load GPIO or Serial library if requested.
        GPIO takes priority if both are requested.
    """
    gpio_module_available = False
    gpio_led = None
    gpio_button = None
    serial_module_available = False
    if use_gpio:
        try:
            from gpiozero import LED, Button
            gpio_module_available = True
            gpio_led = LED
            gpio_button = Button
        except:
            log.err("Module 'gpiozero' is not available. GPIO interface cannot be used.")
    if port_to_use and not gpio_module_available:
        try:
            import serial
            serial_module_available = True
        except:
            log.err("Module pySerial is not available. Serial interface cannot be used.")
    #
    # Set up the external interface to the key and sounder.
    #  GPIO takes priority if it is requested and available.
    #  Then, serial is used if Port is set and PySerial is available.
    #
    # The reason for some repeated code in these two sections is to perform the Key read
    # and Sounder set within the section so the error can be reported with an appropriate
    # message and the interface availability can be set knowing that both operations
    # have been performed.
    #
    ks_interface = None
    if use_gpio and gpio_module_available:
        try:
            ks_interface = __ks_interface_gpio(gpio_button, gpio_led, use_audio, use_sounder, sounder_power_save_secs, invert_key_input, interface_type)
        except:
            log.info("Interface for key and/or sounder on GPIO not available. GPIO key and sounder will not function.")
    elif port_to_use and serial_module_available:
        try:
            port = serial.Serial(port_to_use, timeout=0.5)
            ks_interface = __ks_interface_serial(port, use_audio, use_sounder, sounder_power_save_secs, invert_key_input, interface_type)
        except:
            log.info("Interface for key and/or sounder on serial port '{}' not available. Key and sounder will not function.".format(port_to_use))
    if not ks_interface:
        ks_interface = __ks_interface(use_audio, use_sounder, sounder_power_save_secs, invert_key_input, interface_type)
    return ks_interface


# ####################################################################

class KOB:
    def __init__(
            self, interfaceType=config.InterfaceType.loop, portToUse=None,
            useGpio=False, useAudio=False, useSounder=False, invertKeyInput=False, soundLocal=True,sounderPowerSaveSecs=0, keyCallback=None):
        self._interface_type = interfaceType
        self._invert_key_input = invertKeyInput
        self._port_to_use = portToUse
        self._sound_local = soundLocal
        self._sounder_power_save_secs = sounderPowerSaveSecs
        self._use_gpio = useGpio
        self._use_audio = useAudio
        self._use_sounder = useSounder
        #
        self._threadsStop = Event()
        self._tCodeSounded = -1.0  # Keep track of when the code was first sounded
        self._key_callback = None # Set to the passed in value once we establish an interface
        #
        self._recorder = None
        self._keyreadThread = None
        #
        self._ks_interface:__ks_interface = _get_ks_interface(self._use_audio, self._use_sounder, self._use_gpio, self._port_to_use, self._invert_key_input, self._sounder_power_save_secs, self._interface_type)
        self._ks_interface.start()
        self._ks_interface.set_key_closer_open(False)
        self._ks_interface.set_virtual_closer_open(False)  # Manage virtual closer that might be different from physical
        self._last_key_state = self._ks_interface.key_is_closed # False is key open
        self._tLastSdr = time.time()  # time of last sounder transition
        time.sleep(0.5)
        if self._use_sounder:
            self._ks_interface.loop_power_on()
        else:
            # if no sounder output wanted, de-energize the loop
            self._ks_interface.loop_power_off()
        self._tLastKey = time.time()  # time of last key transition
        self._circuit_is_closed = self._ks_interface.key_is_closed()  # True: circuit latched closed
        self._key_callback = keyCallback
        if self._key_callback:
            self._keyreadThread = Thread(
                name="KOB-KeyRead", daemon=True, target=self._callbackKeyRead
            )
            self._keyreadThread.start()

    def _callbackKeyRead(self):
        """
        Called by the KeyRead thread `run` to read code from the key.
        """
        while not self._threadsStop.is_set():
            code = self.key()
            if len(code) > 0:
                if code[-1] == 1: # special code for closer/circuit closed
                    self._ks_interface.set_key_closer_open(False)
                elif code[-1] == 2: # special code for closer/circuit open
                    self._ks_interface.set_key_closer_open(True)
            self._key_callback(code)

    @property
    def recorder(self):
        """ Recorder instance or None """
        return self._recorder

    @recorder.setter
    def recorder(self, recorder):
        """ Recorder instance or None """
        self._recorder = recorder

    @property
    def keyCloserIsOpen(self):
        return self._keyCloserIsOpen

    @property
    def virtualCloserIsOpen(self):
        return self._ks_interface.virtual_closer_is_open

    @virtualCloserIsOpen.setter
    def virtualCloserIsOpen(self, open):
        log.debug("virtualCloserIsOpen:{}".format(open))
        self._ks_interface.set_virtual_closer_open(open)

    def energizeSounder(self, energize: bool):
        """
        Force the sounder to be energized or not.
        """
        self._ks_interface.energize_sounder(energize, False)

    def exit(self):
        """
        Stop the threads and exit.
        """
        self._ks_interface.exit()
        self._threadsStop.set()

    def key(self):
        '''
        Process input from the key.
        '''
        code = ()
        while self._ks_interface.key_is_available():
            try:
                kc = self._ks_interface.key_is_closed()
            except(OSError):
                return "" # Stop trying to process the key
            t = time.time()
            if kc != self._last_key_state:
                self._last_key_state = kc
                dt = int((t - self._tLastKey) * 1000)
                self._tLastKey = t
                #
                # For 'Seperate Key & Sounder' and the Audio/Synth Sounder,
                # drive it here to avoid as much delay from the key
                # transitions as possible.
                #
                if self._sound_local and self._ks_interface.virtual_closer_is_open:
                    self._ks_interface.energize_sounder(kc, True)
                time.sleep(DEBOUNCE)
                if kc:
                    code += (-dt,)
                elif self._circuit_is_closed:
                    code += (-dt, +2)  # unlatch closed circuit
                    self._circuit_is_closed = False
                    return code
                else:
                    code += (dt,)
            if not kc and code and \
                    t > self._tLastKey + CODESPACE:
                return code
            if kc and not self._circuit_is_closed and \
                    t > self._tLastKey + CKTCLOSE:
                code += (+1,)  # latch circuit closed
                self._circuit_is_closed = True
                return code
            if len(code) >= 50:  # code sequences can't have more than 50 elements
                return code
            time.sleep(0.005)
        return ""

    def soundCode(self, code, code_source=CodeSource.local, sound=True):
        '''
        Process the code and sound it.
        '''
        if sound:
            self._ks_interface.power_save(False)
        if self._tCodeSounded < 0:  # capture start time
            self._tCodeSounded = time.time()
        if self._recorder and not code_source == CodeSource.player:
            self._recorder.record(code_source, code)
        for c in code:
            if self._threadsStop.is_set():
                self._ks_interface.energize_sounder(True, True)
                return
            t = time.time()
            if c < -3000:  # long pause, change of senders, or missing packet
                c = -1
            if c == 1 or c > 2:  # start of mark
                if sound:
                    self._ks_interface.energize_sounder(True, code_source == CodeSource.key)
            tNext = self._tLastSdr + abs(c) / 1000.
            dt = tNext - t
            if dt <= 0:
                self._tLastSdr = t
            else:
                self._tLastSdr = tNext
                time.sleep(dt)
            if c > 1:  # end of (nonlatching) mark
                if sound:
                    self._ks_interface.energize_sounder(False, code_source == CodeSource.key)
