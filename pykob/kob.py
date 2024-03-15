"""
MIT License

Copyright (c) 2020-24 PyKOB - MorseKOB in Python

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
See the table in the documents section for the different modes/states the physical
and synth sounders are in based on the states of the closers (key and virtual).

Also used to appropriately spend time based on the code being sounded,
even if no hardware or synth is being used.

"""
import sys
import time
from enum import Enum, IntEnum, unique
from pykob import config, log
from pykob.config import AudioType, InterfaceType
import threading
from threading import Event, RLock, Thread
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
    mode_change = 6


@unique
class HWInterface(IntEnum):
    NONE = 0
    GPIO = 1
    SERIAL = 2

@unique
class SounderMode(IntEnum):
    DISABLED    = 0  # Not energized (OFF) and do not energize.
    ENERGIZE_FK = 1  # Energized (ON) and do not change (sounder follows key in loop).
    FOLLOW_KEY  = 2  # Energized when key closed. Off when key open.
    SLC         = 3  # ON/OFF to sound local code. When ON accept power-save. OFF cancels power-save
    SRC         = 4  # ON/OFF to sound remote code. When ON accept power-save. OFF cancels power-save.

@unique
class SynthMode(IntEnum):
    DISABLED    = 0  # Play CLACK/SILENCE if needed, then do not play.
    FOLLOW_KEY  = 2  # CLICK/TONE when key closed. CLACK/SILENCE when key open.
    SLC         = 3  # CLICK/TONE / CLACK/SILENCE to sound local code starting with silence.
    SRC         = 4  # CLICK/TONE / CLACK/SILENCE to sound remote code starting with silence.

# ####################################################################

class KOB:
    def __init__(
            self, interfaceType:InterfaceType=InterfaceType.loop, portToUse:Optional[str]=None,
            useGpio:bool=False, useAudio:bool=False, audioType:AudioType=AudioType.SOUNDER, useSounder:bool=False, invertKeyInput:bool=False, soundLocal:bool=True, sounderPowerSaveSecs:int=0,
                    virtual_closer_in_use: bool = False, err_msg_hndlr=None, keyCallback=None):
        """
        When code is not running, the physical sounder (if connected) is not enabled, so
        set the initial state flags accordingly.

        Initialize the hardware and update the flags and mode.
        """
        self._interface_type:InterfaceType = interfaceType
        self._invert_key_input:bool = invertKeyInput
        self._err_msg_hndlr = err_msg_hndlr if err_msg_hndlr else log.warn  # Function that can take a string
        self._port_to_use:str = portToUse
        self._sound_local:bool = soundLocal
        self._sounder_power_save_secs: float = sounderPowerSaveSecs
        self._use_gpio: bool = useGpio
        self._use_audio: bool = useAudio
        self._audio_type: AudioType = audioType
        self._use_sounder:bool = useSounder
        self._virtual_closer_in_use: bool = virtual_closer_in_use  # The owning code will drive the VC
        #
        self._hw_interface:HWInterface = HWInterface.NONE
        self._gpio_key_read = None
        self._gpio_sndr_drive = None
        self._port = None
        self._serial_key_read = self.__read_dsr  # Assume key is on DSR. Changed in HW Init if needed.
        self._audio = None
        self._audio_guard: RLock = RLock()
        self._sounder_guard: RLock = RLock()
        #
        self._key_closer_is_open: bool = True
        self._virtual_closer_is_open: bool = True
        self._circuit_is_closed = False
        self._power_saving: bool = False  # Indicates if Power-Save is active
        self._ps_energize_sounder: bool = False
        self._sounder_energized: bool = False
        self._synth_energized: bool = False  # True: last played 'click/tone', False: played 'clack' (or hasn't played)
        self._sounder_mode: SounderMode = SounderMode.DISABLED
        self._synth_mode: SynthMode = SynthMode.DISABLED
        self._t_sounder_energized: float = -1.0
        self._t_soundcode_last_change: float = 0.0  # time of last code sounding transition
        self._t_key_last_change: float = -1.0  # time of last key transition
        #
        self._key_callback = None # Set to the passed in value once we establish an interface
        #
        self._keyread_thread = None
        self._powersave_thread = None
        self._threadsStop: Event = Event()
        #
        self._key_state_last_closed = False
        #
        self.__init_hw_interface()
        self.__init_audio()
        self._update_modes()
        #
        self._key_callback = keyCallback
        #
        # Kick everything off
        #
        self.__start_hw_processing()
        return

    def __init_audio(self):
        #
        # Load the audio module if they want the synth sounder
        #
        with self._audio_guard:
            if self._audio:
                self._audio.exit()
                self._audio = None
            if self._use_audio:
                # Try to import the audio module.
                try:
                    from pykob import audio
                    self._audio = audio.Audio(self._audio_type)
                except ModuleNotFoundError:
                    self._err_msg_hndlr(
                        "Audio module is not available. The synth sounder and tone cannot be used."
                    )
                    self._use_audio = False
        return

    def __init_hw_interface(self):
        """
        Conditionally load GPIO or Serial library if requested.
        GPIO takes priority if both are requested.
        """
        with self._sounder_guard:
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
                    self._err_msg_hndlr(
                        "Module 'gpiozero' is not available. GPIO interface cannot be used for a key/sounder."
                    )
            if self._port_to_use and not gpio_module_available:
                try:
                    import serial

                    serial_module_available = True
                except:
                    self._err_msg_hndlr(
                        "Module pySerial is not available. Serial interface cannot be used for a key/sounder."
                    )
            #
            # At this point, we have either the GPIO or the Serial module available, or none.
            #
            if gpio_module_available:
                try:
                    self._gpio_key_read = gpio_button(21, pull_up=True)  # GPIO21 is key input.
                    self._gpio_sndr_drive = gpio_led(26)  # GPIO26 used to drive sounder.
                    self._hw_interface = HWInterface.GPIO
                    log.info("The GPIO interface is available/active and will be used.")
                except:
                    self._hw_interface = HWInterface.NONE
                    self._err_msg_hndlr(
                        "Interface for key and/or sounder on GPIO not available. GPIO key/sounder will not function."
                    )
            elif serial_module_available:
                try:
                    self._port = serial.Serial(self._port_to_use, timeout=0.5)
                    self._port.dtr = True  # Provide power for the Les/Chip Loop Interface
                    # Read the inputs to initialize them
                    self.__read_cts()
                    self.__read_dsr()
                    # Check for loopback - The PyKOB interface loops-back data to identify itself. It uses CTS for the key.
                    self._serial_key_read = self.__read_dsr  # Assume that we will use DSR to read the key
                    self._hw_interface = HWInterface.SERIAL
                    log.info("The serial interface is available/active and will be used.")
                    self._port.write(b"PyKOB\n")
                    self._threadsStop.wait(0.5)
                    indata = self._port.readline()
                    if indata == b"PyKOB\n":
                        self._serial_key_read = self.__read_cts  # Use CTS to read the key
                        log.info("KOB Serial Interface is 'minimal' type (key on CTS).")
                    else:
                        log.info("KOB Serial Interface is 'full' type (key on DSR).")
                except Exception as ex:
                    self._hw_interface = HWInterface.NONE
                    self._err_msg_hndlr(
                        "Serial port '{}' is not available. Key/sounder will not function.".format(self._port_to_use)
                    )
                    log.debug(ex)
            # Update closers states based on state of key
            key_closed = False
            if not self._hw_interface == HWInterface.NONE:
                # Read the key
                key_closed = self._key_is_closed()
            self._t_key_last_change = time.time()  # time of last key transition
            self._set_key_closer_open(not key_closed)
            self._set_virtual_closer_open(not key_closed)
            self._circuit_is_closed = key_closed
        return

    def __read_cts(self) -> bool:
        v = True
        if self._port:
            v = self._port.cts
        return v

    def __read_dsr(self) -> bool:
        v = True
        if self._port:
            v = self._port.dsr
        return v

    def __restart_hw_processing(self) -> None:
        """
        Restart processing due to hardware changes.
        """
        if self._hw_is_available():
            self.__start_hw_processing()
        elif self._threadsStop.is_set() or not self._hw_is_available():
            self.__stop_hw_processing()
        return

    def __start_hw_processing(self) -> None:
        """
        Start our processing threads if needed.
        """
        if self._hw_is_available():
            self._threadsStop.clear()
            self.power_save(False)
            if self._key_callback:
                if not self._keyread_thread:
                    self._keyread_thread = Thread(name="KOB-KeyRead", target=self.__thread_keyread_run)
                    self._keyread_thread.start()
            if not self._powersave_thread:
                self._powersave_thread = Thread(name="KOB-PowerSave", target=self.__thread_powersave_run)
                self._powersave_thread.start()
        return

    def __stop_hw_processing(self) -> None:
        self._threadsStop.set()
        if self._keyread_thread and self._keyread_thread.is_alive():
            self._keyread_thread.join(timeout=2.0)
        if self._powersave_thread and self._powersave_thread.is_alive():
            self._powersave_thread.join(timeout=2.0)
        self._keyread_thread = None
        self._powersave_thread = None
        return

    def __thread_keyread_run(self):
        """
        Called by the KeyRead thread `run` to read code from the key.
        """
        while not self._threadsStop.is_set() and self._hw_is_available():
            code = self.key()
            if len(code) > 0:
                if code[-1] == 1: # special code for closer/circuit closed
                    self._set_key_closer_open(False)
                elif code[-1] == 2: # special code for closer/circuit open
                    self._set_key_closer_open(True)
                if self._key_callback and not self._threadsStop.is_set():
                    self._key_callback(code)
        log.debug("{} thread done.".format(threading.current_thread().name))
        return

    def __thread_powersave_run(self):
        """
        Called by the PowerSave thread 'run' to control the power save (sounder energize)
        """
        while not self._threadsStop.is_set():
            now = time.time()
            if self._sounder_power_save_secs > 0 and not self._power_saving:
                if self._t_sounder_energized > 0 and (now - self._t_sounder_energized) > self._sounder_power_save_secs:
                    self.power_save(True)
            self._threadsStop.wait(0.5)
        log.debug("{} thread done.".format(threading.current_thread().name))
        return

    def _energize_hw_sounder(self, energize: bool):
        with self._sounder_guard:
            log.debug("kob._energize_hw_sounder: {}".format(energize), 3)
            if not self._sounder_energized == energize:
                self._sounder_energized = energize
                if energize:
                    self._t_sounder_energized = time.time()
                else:
                    self._t_sounder_energized = -1.0
            if self._hw_interface == HWInterface.GPIO:
                try:
                    if energize:
                        self._gpio_sndr_drive.on()  # Pin goes high and energizes sounder
                    else:
                        self._gpio_sndr_drive.off()  # Pin goes low and deenergizes sounder
                except OSError:
                    self._hw_interface = HWInterface.NONE
                    self._err_msg_hndlr("GPIO output error setting sounder state. Disabling interface.")
            elif self._hw_interface == HWInterface.SERIAL:
                try:
                    if self._port:
                        if energize:
                            self._port.rts = True
                        else:
                            self._port.rts = False
                except OSError:
                    self._hw_interface = HWInterface.NONE
                    self._err_msg_hndlr("Serial RTS error setting sounder state. Disabling interface.")
        return

    def _energize_synth(self, energize: bool, no_tone: bool):
        with self._audio_guard:
            try:
                if energize:
                    if no_tone:
                        self._play_click()
                    else:
                        self._play_click_tone()
                else:
                    self._play_clack_silence()
            except:
                self._use_audio = False
                self._err_msg_hndlr(
                    "System audio error playing sounder state. Disabling synth sounder."
                )
        return

    def _hw_is_available(self) -> bool:
        return (not self._hw_interface == HWInterface.NONE)

    def _key_is_closed(self) -> bool:
        """
        Check the state of the key and return True if it is closed.
        """
        kc = True
        if self._hw_interface == HWInterface.GPIO:
            try:
                kc = not (self._gpio_key_read.is_pressed)
                pass
            except:
                self._hw_interface = HWInterface.NONE
                self._err_msg_hndlr("GPIO interface read error. Disabling interface.")
        elif self._hw_interface == HWInterface.SERIAL:
            try:
                kc = self._serial_key_read()
                pass
            except:
                self._hw_interface = HWInterface.NONE
                self._err_msg_hndlr("Serial interface read error. Disabling interface.")
        # Invert key state if configured to do so (ex: input is from a modem)
        if self._invert_key_input:
            kc = not kc
        return kc

    def _play_clack_silence(self):
        if self._use_audio and self._synth_energized:
            log.debug("kob._play_clack_silence", 3)
            self._audio.play(0)  # clack/silence
            self._synth_energized = False
        return

    def _play_click(self):
        if (self._use_audio and self._audio_type == AudioType.SOUNDER and not self._synth_energized):
            log.debug("kob._play_click", 3)
            self._audio.play(1)  # click
            self._synth_energized = True
        return

    def _play_click_tone(self):
        if self._use_audio and not self._synth_energized:
            log.debug("kob._play_click_tone", 3)
            self._audio.play(1)  # click/tone
            self._synth_energized = True
        return

    def _set_key_closer_open(self, open: bool):
        """
        Track the physical key closer. This controlles the Loop/KOB sounder state.
        """
        log.debug("kob._set_key_closer_open: {}".format(open), 3)
        self._key_closer_is_open = open
        if open:
            self.power_save(False)
        if not self._virtual_closer_in_use:
            # Have virtual track physical and update modes
            self._virtual_closer_is_open = open
            self._update_modes()
        return

    def _set_virtual_closer_open(self, open: bool):
        """
        Track the virtual closer. This controlles the Loop/KOB sounder state.
        """
        log.debug("kob._set_virtual_closer_open: {}->{}".format(self._virtual_closer_is_open, open), 3)
        self._virtual_closer_is_open = open
        if open:
            self.power_save(False)
        self._update_modes()
        return

    def _update_modes(self):
        """
        Based on the type of interface, the closers states, and the local-copy flag,
        set the current sounder and synth mode.

        @SEE: Table in docs for states/modes
        """
        m1s = False  # True once Sounder Mode has been set
        m2s = False  # True once Synth Mode has been set
        sounder_mode_was = self._sounder_mode
        synth_mode_was = self._synth_mode
        log.debug("kob._update_modes: is {}:{}".format(sounder_mode_was.name, synth_mode_was.name), 2)
        with self._audio_guard:
            with self._sounder_guard:
                if not self._use_sounder or self._hw_interface == HWInterface.NONE:
                    self._sounder_mode = SounderMode.DISABLED
                    self._energize_hw_sounder(False)
                    m1s = True
                if not self._use_audio:
                    self._synth_mode = SynthMode.DISABLED
                    self._energize_synth(False, no_tone=True)
                    m2s = True
                if not (m1s and m2s):
                    if (not self._key_closer_is_open) and (not self._virtual_closer_is_open):
                        if not m1s:
                            self._sounder_mode = SounderMode.SRC
                            self._energize_hw_sounder(self._circuit_is_closed)
                        if not m2s:
                            self._synth_mode = SounderMode.SRC
                            self._energize_synth(self._circuit_is_closed, no_tone=True)
                    elif (not self._key_closer_is_open) and (self._virtual_closer_is_open):
                        if self._sound_local:
                            if not m1s:
                                self._sounder_mode = SounderMode.SLC
                                self._energize_hw_sounder(False)
                            if not m2s:
                                self._synth_mode = SynthMode.SLC
                                self._energize_synth(False, no_tone=True)
                        else:  # Not sounding local
                            if not m1s:
                                self._sounder_mode = SounderMode.DISABLED
                                self._energize_hw_sounder(False)
                            if not m2s:
                                self._synth_mode = SynthMode.DISABLED
                                self._energize_synth(False, no_tone=True)
                    elif (self._key_closer_is_open) and (not self._virtual_closer_is_open):
                        if not m1s:
                            self._sounder_mode = SounderMode.SRC
                            self._energize_hw_sounder(self._circuit_is_closed)
                        if not m2s:
                            self._synth_mode = SynthMode.SRC
                            self._energize_synth(self._circuit_is_closed, no_tone=True)
                    else:  # Both open
                        if self._sound_local:
                            if not m1s:
                                if self._interface_type == InterfaceType.loop:
                                    self._sounder_mode = SounderMode.ENERGIZE_FK
                                    self._energize_hw_sounder(True)
                                else:
                                    self._sounder_mode = SounderMode.FOLLOW_KEY
                                    self._energize_hw_sounder(False)
                            if not m2s:
                                self._synth_mode = SynthMode.FOLLOW_KEY
                                self._energize_synth(False, no_tone=True)
                        else:
                            self._sounder_mode = SounderMode.DISABLED
                            self._synth_mode = SynthMode.DISABLED
                            self._energize_hw_sounder(False)
                            self._energize_synth(False, no_tone=True)
        log.debug("kob._update_modes: now {}:{}".format(self._sounder_mode.name, self._synth_mode.name), 2)
        return

    # #############################################################################################
    # Public Interface
    # #############################################################################################

    @property
    def message_receiver(self):
        return self._err_msg_hndlr

    @message_receiver.setter
    def message_receiver(self, f):
        self._err_msg_hndlr = f if not f is None else log.warn

    @property
    def sound_local(self) -> bool:
        return self._sound_local
    @sound_local.setter
    def sound_local(self, on:bool):
        was = self._sound_local
        if not on == was:
            self._sound_local = on
            self._update_modes()
        return

    @property
    def sounder_power_save_secs(self) -> int:
        return self._sounder_power_save_secs
    @sounder_power_save_secs.setter
    def sounder_power_save_secs(self, s:int) -> None:
        self._sounder_power_save_secs = 0 if s < 0 else s
        return

    @property
    def use_sounder(self) -> bool:
        return self._use_sounder
    @use_sounder.setter
    def use_sounder(self, use:bool) -> None:
        if not use == self._use_sounder:
            self._use_sounder = use
            self._update_modes()
        return

    @property
    def virtual_closer_is_open(self) -> bool:
        return self._virtual_closer_is_open
    @virtual_closer_is_open.setter
    def virtual_closer_is_open(self, open:bool) -> None:
        self._set_virtual_closer_open(open)
        return

    def change_audio(self, use_audio:bool, audio_type:AudioType) -> None:
        """
        Change the audio settings from what they were at initialization.
        """
        if not (self._use_audio == use_audio and self._audio_type == audio_type):
            self._use_audio = use_audio
            self._audio_type = audio_type
            self.__init_audio()
            self._update_modes()
        return

    def change_hardware(self, interface_type: InterfaceType, port_to_use: Optional[str], use_gpio: bool, use_sounder: bool) -> None:
        """
        Change the hardware from what it was at initialization
        """
        if not (
                self._interface_type == interface_type and
                self._port_to_use == port_to_use and
                self._use_gpio == use_gpio and
                self._use_sounder == use_sounder):
            self._interface_type = interface_type
            self._port_to_use = port_to_use
            self._use_gpio = use_gpio
            self._use_sounder = use_sounder
            self.__stop_hw_processing()
            if self._port and not self._port.closed:
                self._port.close()
                self._port = None
            self.__init_hw_interface()
            self._update_modes()
            self.__restart_hw_processing()
        return

    def energize_sounder(self, energize: bool, code_source: CodeSource, from_disconnect: bool = False):
        """
        Set the state of the sounder, both physical and synth/tone, for sounding code.
        True: Energized/Click/Tone
        False: De-Energized/Clack/Silence
        """
        # On Mode-Change, set the correct states
        if not code_source == CodeSource.mode_change:
            local_source = not code_source == CodeSource.wire
            if not (self._sounder_mode == SounderMode.DISABLED or self._sounder_mode == SounderMode.ENERGIZE_FK):
                with self._sounder_guard:
                    if local_source and ((not self._sounder_mode == SounderMode.SRC) or from_disconnect):
                        self._energize_hw_sounder(energize)
                    elif not local_source and self._sounder_mode == SounderMode.SRC:
                        self._energize_hw_sounder(energize)
            if not (self._synth_mode == SynthMode.DISABLED):
                with self._audio_guard:
                    if local_source and ((not self._synth_mode == SynthMode.SRC) or from_disconnect):
                        self._energize_synth(energize, from_disconnect)
                    elif not local_source and self._synth_mode == SynthMode.SRC:
                        self._energize_synth(energize, from_disconnect)
        return

    def exit(self):
        """
        Stop the threads and exit.
        """
        self.__stop_hw_processing()
        if self._audio:
            self._audio.exit()
        if self._port and not self._port.closed:
            self._port.close()
            self._port = None
        if self._gpio_key_read:
            self._gpio_key_read = None
        if self._gpio_sndr_drive:
            self._gpio_sndr_drive = None
        return

    def key(self):
        '''
        Process input from the key and return a code sequence.
        '''
        code = ()  # Start with empty sequence
        while not self._threadsStop.is_set() and self._hw_is_available():
            kc = self._key_state_last_closed
            try:
                kc = self._key_is_closed()
            except(OSError):
                return code # Stop trying to process the key
            t = time.time()
            if kc != self._key_state_last_closed:
                self._key_state_last_closed = kc
                dt = int((t - self._t_key_last_change) * 1000)
                self._t_key_last_change = t
                #
                # For 'Seperate Key & Sounder' and the Audio/Synth Sounder,
                # drive it here to avoid as much delay from the key
                # transitions as possible. With Loop interface, the physical
                # sounder follows the key (but this is still needed for the synth).
                #
                if self._sounder_mode == SounderMode.FOLLOW_KEY or self._synth_mode == SynthMode.FOLLOW_KEY:
                    self.energize_sounder(kc, CodeSource.key)
                self._threadsStop.wait(DEBOUNCE)
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
            self._threadsStop.wait(0.005)
        return code

    def power_save(self, enable: bool):
        """
        True to turn off the sounder power to save power (reduce risk of fire, etc.)
        """
        # Only enable power save if mode is sounding remote code.
        if enable and not self._sounder_mode == SounderMode.SRC:
            return
        if enable == self._power_saving:
            return  # Already correct

        if enable:
            log.debug("KOB: Sounder power-save on", 2)
            self._ps_energize_sounder = self._sounder_energized
            self._energize_hw_sounder(False)
            self._power_saving = True
        else:  # disable power-save. restore the state of the sounder
            log.debug("KOB: Sounder power-save off", 2)
            self._power_saving = False
            if self._ps_energize_sounder:
                self._energize_hw_sounder(True)
            self._ps_energize_sounder = False
        return

    def soundCode(self, code, code_source: CodeSource = CodeSource.local, sound: bool = True):
        '''
        Process the code and sound it.
        '''
        if sound:
            self.power_save(False)
        for c in code:
            if self._threadsStop.is_set():
                self.energize_sounder(False, code_source, from_disconnect=True)
                return
            t = time.time()
            if c < -3000:  # long pause, change of senders, or missing packet
                c = -1
            if c == 1 or c > 2:  # start of mark
                if sound:
                    self.energize_sounder(True, code_source)
            tNext = self._t_soundcode_last_change + abs(c) / 1000.
            dt = tNext - t
            if dt <= 0:
                self._t_soundcode_last_change = t
            else:
                self._t_soundcode_last_change = tNext
                self._threadsStop.wait(dt)
            if c > 1:  # end of (nonlatching) mark
                if sound:
                    self.energize_sounder(False, code_source)
        return
