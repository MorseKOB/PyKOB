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
from pykob import config, config2, log
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


@unique
class HWInterface(IntEnum):
    none = 0
    gpio = 1
    serial = 2


# ####################################################################

class KOB:
    def __init__(
            self, interfaceType=config.InterfaceType.loop, portToUse=None,
            useGpio=False, useAudio=False, useSounder=False, invertKeyInput=False, soundLocal=True,sounderPowerSaveSecs=0, keyCallback=None):
        self._interface_type:config.InterfaceType = interfaceType
        self._invert_key_input:bool = invertKeyInput
        self._port_to_use:str = portToUse
        self._sound_local:bool = soundLocal
        self._sounder_power_save_secs: float = sounderPowerSaveSecs
        self._use_gpio: bool = useGpio
        self._use_audio:bool = useAudio
        self._use_sounder:bool = useSounder
        self._hw_interface:HWInterface = HWInterface.none
        #
        self._key_closer_is_open: bool = False
        self._power_saving: bool = False  # Indicates if Power-Save is active
        self._sounder_energized: bool = False
        self._t_sounder_energized: float = -1.0
        self._synthsounder_energized: bool = (
            False  # True: last played 'click', False: played 'clack' (or hasn't played)
        )
        self._virtual_closer_is_open: bool = False
        self._t_code_sounded = -1.0  # Keep track of when the code was first sounded
        #
        self._key_callback = None # Set to the passed in value once we establish an interface
        #
        self._audio = None
        self._recorder = None
        self._keyread_thread = None
        self._powersave_thread = None
        self._threadsStop: Event = Event()
        #
        # The following requires that the key interface is running
        #
        self.__init_hw_interface()
        #
        self._set_key_closer_open(self._key_closer_is_open)
        self._set_virtual_closer_open(False)  # Manage virtual closer that might be different from physical
        self._key_last_state = self._key_is_closed # False is key open
        self._t_key_last_change = time.time()  # time of last key transition
        time.sleep(0.5)
        self._t_sounder_last_change = time.time()  # time of last sounder transition
        if self._use_sounder:
            self._loop_power_on()
        else:
            # if no sounder output wanted, de-energize the loop
            self._loop_power_off()
        self._circuit_is_closed = self._key_is_closed()  # True: circuit latched closed
        self._key_callback = keyCallback
        #
        # Kick everything off
        #
        self.__start()

    def __init_hw_interface(self):
        """
        Conditionally load GPIO or Serial library if requested.
        GPIO takes priority if both are requested.
        """
        gpio_module_available = False
        gpio_led = None
        gpio_button = None
        serial_module_available = False
        if self._use_gpio:
            try:
                from gpiozero import LED, Button

                gpio_module_available = True
                gpio_led = LED
                gpio_button = Button
            except:
                log.err(
                    "Module 'gpiozero' is not available. GPIO interface cannot be used."
                )
        if self._port_to_use and not gpio_module_available:
            try:
                import serial

                serial_module_available = True
            except:
                log.err(
                    "Module pySerial is not available. Serial interface cannot be used."
                )
        #
        # At this point, we have either the GPIO or the Serial module available, or none.
        #
        if gpio_module_available:
            try:
                self._gpi = gpio_button(21, pull_up=True)  # GPIO21 is key input.
                self._gpo = gpio_led(26)  # GPIO26 used to drive sounder.
                self._hw_interface = HWInterface.gpio
                print("The GPIO interface is available/active and will be used.")
            except:
                log.info(
                    "Interface for key and/or sounder on GPIO not available. GPIO key and sounder will not function."
                )
        elif serial_module_available:
            try:
                self._port = serial.Serial(self._port_to_use, timeout=0.5)
                self._port.dtr = True  # Provide power for the Les/Chip Loop Interface
                # Check for loopback - The PyKOB interface loops-back data to identify itself. It uses CTS for the key.
                self._key_read = self.__read_dsr  # Assume that we will use DSR to read the key
                print("The serial interface is available/active and will be used.")
                self._port.write(b"PyKOB\n")
                time.sleep(0.5)
                indata = self._port.readline()
                if indata == b"PyKOB\n":
                    self._key_read = self.__read_cts  # Use CTS to read the key
                    log.info("KOB Serial Interface is 'PyKOB' type.")
                else:
                    log.info("KOB Serial Interface is 'L/C' type.")
                self._hw_interface = HWInterface.serial
            except:
                log.info(
                    "Interface for key and/or sounder on serial port '{}' not available. Key and sounder will not function.".format(
                        self._port_to_use
                    )
                )
        #
        # Load the audio module if they want the synth sounder
        #
        if self._use_audio:
            # Try to import the audio module.
            try:
                from pykob import audio

                self._audio = audio.Audio()
            except ModuleNotFoundError:
                log.err(
                    "Audio module is not available. The synth sounder cannot be used."
                )
                self._use_audio = False

    def __start(self):
        """
        Get things set up and tart our processing threads.
        """
        if self._key_callback:
            self._keyread_thread = Thread(
                name="KOB-KeyRead", daemon=True, target=self._keyReadThread_run
            )
            self._keyread_thread.start()
        self._powersave_thread = Thread(
            name="Sounder-PowerSave", daemon=True, target=self._powerSaveThread_run
        )
        self._powersave_thread.start()

    def __read_cts(self) -> bool:
        return self._port.cts

    def __read_dsr(self) -> bool:
        return self._port.dsr

    def _keyReadThread_run(self):
        """
        Called by the KeyRead thread `run` to read code from the key.
        """
        while not self._threadsStop.is_set():
            code = self.key()
            if len(code) > 0:
                if code[-1] == 1: # special code for closer/circuit closed
                    self._set_key_closer_open(False)
                elif code[-1] == 2: # special code for closer/circuit open
                    self._set_key_closer_open(True)
                if self._key_callback:
                    self._key_callback(code)

    def _powerSaveThread_run(self):
        """
        Called by the PowerSave thread 'run' to control the power save (sounder energize)
        """
        while not self._threadsStop.is_set():
            now = time.time()
            if self._sounder_power_save_secs > 0 and not self._power_saving:
                if (
                    self._t_sounder_energized > 0
                    and (now - self._t_sounder_energized)
                    > self._sounder_power_save_secs
                ):
                    self.power_save(True)
            time.sleep(1.0)

    def _energize_hw_sounder(self, energize: bool):
        if self._hw_interface == HWInterface.gpio:
            try:
                if energize:
                    self._gpo.on()  # Pin goes high and energizes sounder
                else:
                    self._gpo.off()  # Pin goes low and deenergizes sounder
            except OSError:
                self._hw_interface = HWInterface.none
                log.err("GPIO output error setting sounder state. Disabling GPIO.")
        if self._hw_interface == HWInterface.serial:
            try:
                if energize:
                    self._port.rts = True
                else:
                    self._port.rts = False
            except OSError:
                self._hw_interface = HWInterface.none
                log.err("Serial RTS error setting sounder state. Disabling Serial.")

    def energize_sounder(self, energize:bool, from_key:bool=False):
        """
        Set the state of the sounder.
        True: Energized/Click
        False: De-Energized/Clack
        """
        if energize:
            self._t_sounder_energized = time.time()
        # If using a loop interface and the source is the key,
        # don't do anything, as the closing of the key will energize the sounder,
        # since the loop is energized.
        if self._use_sounder and not (self._interface_type == config.InterfaceType.loop and from_key):
            self._sounder_energized = energize
            self._energize_hw_sounder(energize)
        if self._use_audio:
            if energize != self._synthsounder_energized:
                self._synthsounder_energized = energize
                try:
                    if energize:
                        self._audio.play(1)  # click
                    else:
                        self._audio.play(0)  # clack
                except:
                    self._use_audio = False
                    log.err(
                        "System audio error playing sounder state. Disabling synth sounder."
                    )

    def _key_is_available(self) -> bool:
        return (not self._hw_interface == HWInterface.none)

    def _key_is_closed(self) -> bool:
        """
        Check the state of the key and return True if it is closed.
        """
        kc = True
        if self._hw_interface == HWInterface.gpio:
            try:
                kc = not (self._gpi.is_pressed)
            except:
                self._hw_interface = HWInterface.none
                log.err("GPIO key interface read error. Disabling GPIO.")
        elif self._hw_interface == HWInterface.serial:
            try:
                kc = self._key_read()
            except:
                self._hw_interface = HWInterface.none
                log.err("Serial key interface read error. Disabling Serial.")
        # Invert key state if configured to do so (ex: input is from a modem)
        if self._invert_key_input:
            kc = not kc
        return kc

    def _loop_power_off(self):
        self._sounder_energized = False
        if self._hw_interface == HWInterface.gpio:
            try:
                self.gpo.off() # Pin goes low and deenergizes sounder
            except(OSError):
                self._hw_interface = HWInterface.none
                log.err("GPIO output error when de-energizing loop. Disabling GPIO.")
        elif self._hw_interface == HWInterface.serial:
            try:
                self._port.rts = False
            except OSError:
                self._hw_interface = HWInterface.none
                log.err("Serial RTS error when de-energizing loop. Disabling Serial.")

    def _loop_power_on(self):
        self._sounder_energized = True
        self._t_sounder_energized = time.time()
        if self._hw_interface == HWInterface.gpio:
            try:
                self.gpo.on() # Pin goes high and energizes sounder
            except(OSError):
                self._hw_interface = HWInterface.none
                log.err("GPIO output error when energizing loop. Disabling GPIO")
        elif self._hw_interface == HWInterface.serial:
            try:
                self._port.rts = True
            except OSError:
                self._hw_interface = HWInterface.none
                log.err("Serial RTS error when energizing loop. Disabling Serial.")

    def _set_key_closer_open(self, open: bool):
        """
        Track the physical key closer. This controlles the Loop/KOB sounder state.
        """
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

    def _set_virtual_closer_open(self, open: bool):
        """
        Track the virtual closer. This controlles the Loop/KOB sounder state.
        """
        self._virtual_closer_is_open = open
        if open:
            self.power_save(False)

    @property
    def recorder(self):
        """ Recorder instance or None """
        return self._recorder

    @recorder.setter
    def recorder(self, recorder):
        """ Recorder instance or None """
        self._recorder = recorder

    @property
    def virtual_closer_is_open(self) -> bool:
        return self._virtual_closer_is_open
    @virtual_closer_is_open.setter
    def virtual_closer_is_open(self, open):
        log.debug("virtual_closer_is_open:{}".format(open))
        self._set_virtual_closer_open(open)

    def exit(self):
        """
        Stop the threads and exit.
        """
        if self._audio:
            self._audio.exit()
        self._threadsStop.set()

    def key(self):
        '''
        Process input from the key.
        '''
        code = ()
        while self._key_is_available():
            try:
                kc = self._key_is_closed()
            except(OSError):
                return "" # Stop trying to process the key
            t = time.time()
            if kc != self._key_last_state:
                self._key_last_state = kc
                dt = int((t - self._t_key_last_change) * 1000)
                self._t_key_last_change = t
                #
                # For 'Seperate Key & Sounder' and the Audio/Synth Sounder,
                # drive it here to avoid as much delay from the key
                # transitions as possible.
                #
                if self._sound_local and self._virtual_closer_is_open:
                    self.energize_sounder(kc, True)
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
                    t > self._t_key_last_change + CODESPACE:
                return code
            if kc and not self._circuit_is_closed and \
                    t > self._t_key_last_change + CKTCLOSE:
                code += (+1,)  # latch circuit closed
                self._circuit_is_closed = True
                return code
            if len(code) >= 50:  # code sequences can't have more than 50 elements
                return code
            time.sleep(0.005)
        return ""

    def power_save(self, enable: bool):
        """
        True to turn off the sounder power to save power (reduce risk of fire, etc.)
        """
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
        else:  # disable power-save. restore the state of the sounder
            self._power_saving = False
            log.debug("Sounder power-save off", 2)
            if self._sounder_energized:
                self._energize_hw_sounder(True)
                self.tSndrEnergized = now

    def soundCode(self, code, code_source=CodeSource.local, sound=True):
        '''
        Process the code and sound it.
        '''
        if sound:
            self.power_save(False)
        if self._t_code_sounded < 0:  # capture start time
            self._t_code_sounded = time.time()
        if self._recorder and not code_source == CodeSource.player:
            self._recorder.record(code_source, code)
        for c in code:
            if self._threadsStop.is_set():
                self.energize_sounder(True, True)
                return
            t = time.time()
            if c < -3000:  # long pause, change of senders, or missing packet
                c = -1
            if c == 1 or c > 2:  # start of mark
                if sound:
                    self.energize_sounder(True, code_source == CodeSource.key)
            tNext = self._t_sounder_last_change + abs(c) / 1000.
            dt = tNext - t
            if dt <= 0:
                self._t_sounder_last_change = t
            else:
                self._t_sounder_last_change = tNext
                time.sleep(dt)
            if c > 1:  # end of (nonlatching) mark
                if sound:
                    self.energize_sounder(False, code_source == CodeSource.key)
