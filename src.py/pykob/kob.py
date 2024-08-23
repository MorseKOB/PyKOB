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

Handles external key, kob, sounder, keyer/paddle and the virtual sounder
(computer audio).

The interface type controls certain aspects of how the physical sounder is driven.
See the table in the documents section for the different modes/states the physical
and synth sounders are in based on the states of the closers (key and virtual).

A keyer/paddle acts as a bug (key) with a separate sounder (not a KOB).
The keyer/paddle has 3 states:
    1. Idle
    2. Send dits
    3. Send dah (until state changes to Idle or Send dits)
A method is also provided to change the state from other sources, for example the
keyboard. Note that a keyer/paddle will not have closer, and therefore, the
virtual closer will need to be used.

The `sound_code` method can also be used to appropriately spend time based on the
code being sounded without causing any sound to be produced.

"""
import re  # RegEx
import sys
import time
from enum import Enum, IntEnum, unique
from pykob import config, log, morse, util
from pykob.config import AudioType, InterfaceType
import threading
from threading import Event, RLock, Thread
import traceback
from typing import Any, Callable

DEBOUNCE  = 0.018  # time to ignore transitions due to contact bounce (sec)
CODESPACE = 0.120  # amount of space to signal end of code sequence (sec)
CKTCLOSE  = 0.800  # length of mark to signal circuit closure (sec)

PORT_FIND_SDIF_KEY = "SDIF"
SDIF_SN_END = "_AES"

log.debug("Platform: {}".format(sys.platform))
if sys.platform == "win32" or sys.platform == "cygwin":
    # We are on a Windows system
    from ctypes import windll
    windll.winmm.timeBeginPeriod(1)  # set clock resolution to 1 ms (Windows only)

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
class KeyerMode(IntEnum):
    IDLE = 0
    DITS = 1
    DAH  = 2


SLC_BITS = 0x10  # Bits in ...Mode that signify that local code (not from key) should be sounded.
@unique
class SounderMode(IntEnum):
    DIS         = 0x00  # Not energized (OFF) and do not energize.
    EFK         = 0x11  # Energized (ON) and do not change (sounder follows key in loop).
    FK          = 0x12  # Energized when key closed. Off when key open.
    SLC         = 0x10  # ON/OFF to sound local code. When ON accept power-save. OFF cancels power-save
    REC         = 0x20  # ON/OFF to sound recordings, but nothing else.
    SRC         = 0x40  # ON/OFF to sound remote code. When ON accept power-save. OFF cancels power-save.

@unique
class SynthMode(IntEnum):
    DIS         = 0x00  # Play CLACK/SILENCE if needed, then do not play.
    FK          = 0x12  # CLICK/TONE when key closed. CLACK/SILENCE when key open.
    SLC         = 0x10  # CLICK/TONE / CLACK/SILENCE to sound local code starting with silence.
    REC         = 0x20  # ON/OFF to sound recordings, but nothing else.
    SRC         = 0x40  # CLICK/TONE / CLACK/SILENCE to sound remote code starting with silence.

# ####################################################################

class KOB:

    #
    # The tables below are the modes the sounder/synth can be in given the control inputs.
    #
    # Columns: KC & VC | KC & VO | KO & VC | KO & VO
    #  KC = Key Closed
    #  KO = Key Open
    #  VC = Virtual Key CLosed
    #  VO = Virtual Key Open
    #
    # Rows are:
    #           0: WireNotConnected & LocalCopy
    #           1: WireNotConnected & NoLocalCopy
    #           2: WireConnected & LocalCopy
    #           3: WireConnected & NoLocalCopy
    #
    __LOOP_MODES = (
        ("Loop Modes"),  # For debugging
        (SounderMode.REC, SounderMode.DIS, SounderMode.REC, SounderMode.DIS),
        (SounderMode.REC, SounderMode.SLC, SounderMode.REC, SounderMode.EFK),
        (SounderMode.SRC, SounderMode.DIS, SounderMode.SRC, SounderMode.DIS),
        (SounderMode.SRC, SounderMode.SLC, SounderMode.SRC, SounderMode.EFK),
    )

    __KS_MODES = (
        ("Key&Sounder Modes"),  # For debugging
        (SounderMode.REC, SounderMode.DIS, SounderMode.REC, SounderMode.DIS),
        (SounderMode.REC, SounderMode.SLC, SounderMode.REC, SounderMode.FK),
        (SounderMode.SRC, SounderMode.DIS, SounderMode.SRC, SounderMode.DIS),
        (SounderMode.SRC, SounderMode.SLC, SounderMode.SRC, SounderMode.FK)
    )

    __SYNTH_MODES = (
        ("Synth Modes"),  # For debugging
        (SynthMode.REC, SynthMode.DIS, SynthMode.REC, SynthMode.DIS),
        (SynthMode.REC, SynthMode.SLC, SynthMode.REC, SynthMode.FK),
        (SynthMode.SRC, SynthMode.DIS, SynthMode.SRC, SynthMode.DIS),
        (SynthMode.SRC, SynthMode.SLC, SynthMode.SRC, SynthMode.FK)
    )

    __COL_SEL = (
        (0, 1),     # KC & VC | KC & VO
        (2, 3)      # KO & VC | KO & VO
    )

    __ROW_SEL = (  # Row 0 is the table name
        (1, 2),     # WNC & NLC | WNC & LC
        (3, 4)      # WC  & NLC | WC  & LC
    )


    def __init__(
            self, interfaceType=InterfaceType.loop, useSerial=False, portToUse=None,
            useGpio=False, useAudio=False, audioType=AudioType.SOUNDER, useSounder=False, invertKeyInput=False,
            noKeyCloser=False, soundLocal=True, sounderPowerSaveSecs=0,
            virtual_closer_in_use=False, err_msg_hndlr=None, keyCallback=None):
        # type: (InterfaceType, bool, str|None, bool, bool, AudioType, bool, bool, bool, bool, int, bool, Callable, Callable) -> None
        """
        When PyKOB code is not running, the physical sounder (if connected) is not powered by
        a connected interface, so set the initial state flags accordingly.

        Initialize the hardware and update the flags and mode.
        """
        self._interface_type = interfaceType        # type: InterfaceType
        self._invert_key_input = invertKeyInput     # type: bool
        self._no_key_closer = noKeyCloser           # type: bool
        self._err_msg_hndlr = err_msg_hndlr if err_msg_hndlr else log.warn  # type: Callable  # Function that can take a string
        self._use_serial = useSerial                # type: bool
        self._port_to_use = portToUse               # type: str
        self._sound_local = soundLocal              # type: bool
        self._sounder_power_save_secs = sounderPowerSaveSecs    # type: float
        self._use_gpio = useGpio                    # type: bool
        self._use_audio = useAudio                  # type: bool
        self._audio_type = audioType                # type: AudioType
        self._use_sounder = useSounder              # type: bool
        self._virtual_closer_in_use = virtual_closer_in_use  # type: bool  # The owning code will drive the VC
        #
        self._shutdown = Event()                    # type: Event
        self._hw_interface = HWInterface.NONE       # type: HWInterface
        self._gpio_key_read = self.__read_nul       # type: Callable
        self._gpio_pdl_dah = self.__read_nul        # type: Callable
        self._gpio_sndr_drive = None                # type: Callable|None
        self._port = None                           # type: 'serial.Serial'|None
        self._serial_key_read = self.__read_nul     # type: Callable  # Read a NUL key. Changed in HW Init if interface is configured.
        self._serial_pdl_dah = self.__read_nul      # type: Callable  # Read a NUL paddle dah (dash).
        self._audio = None                          # type: audio.Audio|None
        self._paddle_is_supported = False           # type: bool  # Set in HW Init if possible.
        self._audio_guard = RLock()                 # type: RLock
        self._keyer_mode_guard = RLock()            # type: RLock
        self._sounder_guard = RLock()               # type: RLock
        #
        now = time.time()
        self._keyer_mode = (KeyerMode.IDLE, CodeSource.key) # type: tuple[KeyerMode,CodeSource]
        self._keyer_dit_len = morse.Sender.DOT_LEN_20WPM    # type: int
        self._t_keyer_mode_change = now             # type: float  # time of last keyer mode change during processing
        self._keyer_dits_down = False               # type: bool
        #
        self._key_closer_is_open = False            # type: bool  # Will be set from the key in HW Init
        self._virtual_closer_is_open = False        # type: bool
        self._circuit_is_closed = True              # type: bool
        self._internet_circuit_closed = False       # type: bool
        self._wire_connected = False                # type: bool
        self._power_saving = False                  # type: bool  # Indicates if Power-Save is active
        self._ps_energize_sounder = False           # type: bool
        self._sounder_energized = False             # type: bool
        self._synth_energized = False  # type: bool  # True: last played 'click/tone', False: played 'clack' (or hasn't played)
        self._sounder_mode = SounderMode.DIS        # type: SounderMode
        self._synth_mode = SynthMode.DIS            # type: SynthMode
        self._t_sounder_energized = -1.0            # type: float
        self._t_soundcode_last_change = 0.0         # type: float  # time of last code sounding transition
        self._t_key_last_change = -1.0              # type: float  # time of last key transition
        #
        self._key_callback = None  # type: Callable|None  # Set to the passed in value once we establish an interface
        #
        self._thread_keyer = None                   # type: Thread|None
        self._thread_keyread = None                 # type: Thread|None
        self._thread_powersave = None               # type: Thread|None
        self._threadsStop_KS = Event()              # type: Event
        self._threadsStop_keyer = Event()           # type: Event
        #
        self._key_state_last_closed = True          # type: bool
        #
        self.__init_audio()  # Do this first so it doesn't get an error when HW energizes the sounder.
        self._set_key_closer_open(False)  # Use the method to set to False (for no key or key w/o closer)
        self.__init_hw_interface()  # This will make the closer state correct if there is one
        #
        self._key_callback = keyCallback  # Now that things are initialized, set the key callback
        #
        # Kick everything off
        #
        self.__start_keyer_processing()
        self.__start_hw_processing()
        return

    def __init_audio(self): # type: () -> None
        """
        Load the audio module if they want the synth sounder
        """
        if self._shutdown.is_set():
            return
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
                    self._err_msg_hndlr("Audio module is not available. The synth sounder and tone cannot be used.")
                    log.debug(traceback.format_exc(), 3)
                    self._use_audio = False
        return

    def __init_hw_interface(self): # type: () -> None
        """
        Conditionally load GPIO or Serial library if requested.
        GPIO takes priority if both are requested.
        """
        if self._shutdown.is_set():
            return
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
                    self._err_msg_hndlr("Module 'gpiozero' is not available. GPIO interface cannot be used for a key/sounder.")
                    log.debug(traceback.format_exc(), 3)
            elif self._use_serial and not self._port_to_use is None:
                try:
                    import serial
                    import serial.tools.list_ports

                    serial_module_available = True
                except:
                    self._err_msg_hndlr("Module 'pySerial' is not available. Serial interface cannot be used for a key/sounder.")
                    log.debug(traceback.format_exc(), 3)
                pass
            pass
            #
            # At this point, we have either the GPIO or the Serial module available, or none.
            #
            if gpio_module_available:
                try:
                    self._gpio_key_read = gpio_button(21, pull_up=True)  # GPIO21 is key input.
                    self._gpio_pdl_dah = gpio_button(20, pull_up=True)   # GPIO20 is paddle-dah (dash).
                    self._gpio_sndr_drive = gpio_led(26)  # GPIO26 used to drive sounder.
                    self._hw_interface = HWInterface.GPIO
                    self._paddle_is_supported = True
                    log.debug("The GPIO interface is available/active and will be used.")
                except:
                    self._hw_interface = HWInterface.NONE
                    self._paddle_is_supported = False
                    self._err_msg_hndlr("Interface for key and/or sounder on GPIO not available. GPIO key/sounder will not function.")
                    log.debug(traceback.format_exc(), 3)
            elif serial_module_available:
                try:
                    if self._port_to_use == PORT_FIND_SDIF_KEY:
                        """
                        Look for a Silky-DESIGN Interface, by searching for a serial port with a serial
                        number that ends in '_AESnnn' (nnn is the unit number '_AESnnnA' on Windows).
                        Note: Early SD interfaces didn't have a unit number (nnn), and SilkyDESIGN-Selector
                            switches have a serial number like '_AESSEL'. So it is important to find
                            interfaces and not selector switches.
                        If found, set the port ID.
                        Else, indicate a warning
                        """
                        log.debug("Try to find SD-Interface on serial.")
                        re1 = re.compile(r"_AES([0-9]*)")
                        re2 = re.compile(r"_AESSEL")
                        sdif_port_id = None
                        systemSerialPorts = serial.tools.list_ports.comports()
                        for sp in systemSerialPorts:
                            sn = sp.serial_number if sp.serial_number else ""
                            m = re1.search(sn)
                            if m:
                                # Found an SD device, make sure it's not a Selector
                                if not re2.search(sn):
                                    sdif_port_id = sp.device
                                    unit = m.group(1)
                                    us = "" if not unit or len(unit) < 1 else " {}".format(unit)
                                    log.info("SD-Interface{} found on: {}".format(us, sp.device), dt="")
                                    break
                        self._port_to_use = sdif_port_id
                        if self._port_to_use is None:
                            self._err_msg_hndlr("An SD-Interface was not found. Key/sounder will not function.")
                    if not self._port_to_use is None:
                        self._port = serial.Serial(self._port_to_use, timeout=0.5)
                        self._port.write_timeout = 1
                        self._port.dtr = True  # Provide power for the Les/Chip Loop Interface
                        # Read the inputs to initialize them
                        self.__read_cts()
                        self.__read_dsr()
                        # Check for loopback - The minimal PyKOB interface loops-back data to identify itself. It uses CTS for the key.
                        self._serial_key_read = self.__read_dsr  # Assume that we will use DSR to read the key
                        self._serial_pdl_dah = self.__read_cts   # Assume that we will use CTS to read the paddle-dah (dash)
                        self._hw_interface = HWInterface.SERIAL
                        self._port.write(b"PyKOB\n")
                        self._threadsStop_KS.wait(0.5)
                        indata = self._port.readline()
                        if indata == b"PyKOB\n":
                            self._serial_key_read = self.__read_cts  # Use CTS to read the key
                            self._serial_pdl_dah = self.__read_nul   # Paddle Dah/Dash cannot be supported
                            self._paddle_is_supported = False
                            log.debug("KOB Serial Interface is 'minimal' type (key on CTS).")
                        else:
                            self._paddle_is_supported = True
                            log.debug("KOB Serial Interface is 'full' type (key/pdl-dit on DSR, pdl-dah on CTS).")
                    pass
                except Exception as ex:
                    self._hw_interface = HWInterface.NONE
                    self._serial_key_read = self.__read_nul
                    self._serial_pdl_dah = self.__read_nul
                    self._err_msg_hndlr("Serial port '{}' is not available. Key/sounder will not function.".format(self._port_to_use))
                    log.debug(ex)
                    log.debug(traceback.format_exc(), 3)
                pass
            else:
                # For one reason or another, we are not using GPIO or Serial.
                self._hw_interface = HWInterface.NONE
            if self._hw_interface == HWInterface.NONE:
                # Clear out and set things to a specific set of values for
                # consistency.
                self._interface_type = InterfaceType.key_sounder
                self._no_key_closer = True
                self._paddle_is_supported = False
                self._port = None
                self._port_to_use = None
            # Update closers states based on state of key
            key_closed = True
            if not (self._hw_interface == HWInterface.NONE or self._no_key_closer):
                # Read the key
                key_closed = self._key_is_closed()
            self._t_key_last_change = time.time()  # time of last key transition
            self._key_state_last_closed = key_closed
            self._circuit_is_closed = key_closed
            key_open = not key_closed
            self._set_key_closer_open(not key_closed)
            self._set_virtual_closer_open(not key_closed)
            self._update_modes(key_open, key_open, key_open, key_open)
        return

    def __read_cts(self): # type: () -> bool
        v = False
        if self._port:
            v = self._port.cts
        return v

    def __read_dsr(self): # type: () -> bool
        v = False
        if self._port:
            v = self._port.dsr
        return v

    def __read_nul(self): # type: () -> bool
        """ Always returns False """
        return False

    def __restart_hw_processing(self): # type: () -> None
        """
        Restart processing due to hardware changes.
        """
        if not self._shutdown.is_set() and self._hw_is_available():
            self.__start_hw_processing()
        elif self._threadsStop_KS.is_set() or not self._hw_is_available():
            self.__stop_hw_processing()
        return

    def __start_hw_processing(self): # type: () -> None
        """
        Start our processing threads if needed.
        """
        if not self._shutdown.is_set() and self._hw_is_available():
            self._threadsStop_KS.clear()
            self.power_save(False)
            if self._key_callback:
                if not self._thread_keyread:
                    self._thread_keyread = Thread(name="KOB-KeyRead", target=self._thread_keyread_body)
                    self._thread_keyread.start()
            if not self._thread_powersave:
                self._thread_powersave = Thread(name="KOB-PowerSave", target=self._thread_powersave_body)
                self._thread_powersave.start()
        return

    def __start_keyer_processing(self): # type: () -> None
        if not self._shutdown.is_set() and not self._thread_keyer:
            self._threadsStop_keyer.clear()
            self._thread_keyer = Thread(name="KOB-Keyer", target=self._thread_keyer_body)
            self._thread_keyer.start()
        return

    def __stop_hw_processing(self): # type: () -> None
        self._threadsStop_KS.set()
        if self._thread_keyread and self._thread_keyread.is_alive():
            self._thread_keyread.join(timeout=2.0)
        if self._thread_powersave and self._thread_powersave.is_alive():
            self._thread_powersave.join(timeout=2.0)
        self._thread_keyread = None
        self._thread_powersave = None
        return

    def _thread_keyer_body(self): # type: () -> None
        """
        Called by the Keyer thread `run` to send automated dits/dah based on the mode.
        """
        while not self._threadsStop_keyer.is_set() and not self._shutdown.is_set():
            code = self.keyer()
            if len(code) > 0:
                if code[-1] == 1: # special code for closer/circuit closed
                    # self._set_key_closer_open(False)
                    pass
                elif code[-1] == 2: # special code for closer/circuit open
                    # self._set_key_closer_open(True)
                    pass
                if self._key_callback and not self._threadsStop_keyer.is_set():
                    self._key_callback(code)
        log.debug("{} thread done.".format(threading.current_thread().name))
        return

    def _thread_keyread_body(self): # type: () -> None
        """
        Called by the KeyRead thread `run` to read code from the key.
        """
        while not self._threadsStop_KS.is_set() and self._hw_is_available() and not self._shutdown.is_set():
            code = self.key()
            if len(code) > 0:
                if code[-1] == 1: # special code for closer/circuit closed
                    self._set_key_closer_open(False)
                elif code[-1] == 2: # special code for closer/circuit open
                    self._set_key_closer_open(True)
                if self._key_callback and not self._threadsStop_KS.is_set():
                    self._key_callback(code)
        log.debug("{} thread done.".format(threading.current_thread().name))
        return

    def _thread_powersave_body(self): # type: () -> None
        """
        Called by the PowerSave thread 'run' to control the power save (sounder energize)
        """
        while not self._threadsStop_KS.is_set() and not self._shutdown.is_set():
            now = time.time()
            if self._sounder_power_save_secs > 0 and not self._power_saving:
                if self._t_sounder_energized > 0 and (now - self._t_sounder_energized) > self._sounder_power_save_secs:
                    self.power_save(True)
            self._threadsStop_KS.wait(0.5)
        log.debug("{} thread done.".format(threading.current_thread().name))
        return

    def _energize_hw_sounder(self, energize): # type: (bool) -> None
        """
        Energize or de-energize the hardware sounder.
        """
        if self._shutdown.is_set():
            return
        with self._sounder_guard:
            hw_energize = (energize and self._use_sounder)
            log.debug("kob._energize_hw_sounder: {}:{}".format(energize, hw_energize), 3)
            if not self._sounder_energized == hw_energize:
                if hw_energize:
                    self._t_sounder_energized = time.time()
                else:
                    self._t_sounder_energized = -1.0
                self._sounder_energized = hw_energize
                if self._hw_interface == HWInterface.GPIO:
                    try:
                        if hw_energize:
                            self._gpio_sndr_drive.on()  # Pin goes high and energizes sounder
                        else:
                            self._gpio_sndr_drive.off()  # Pin goes low and deenergizes sounder
                    except OSError:
                        self._hw_interface = HWInterface.NONE
                        self._err_msg_hndlr("GPIO output error setting sounder state. Disabling interface.")
                        log.debug(traceback.format_exc(), 3)
                elif self._hw_interface == HWInterface.SERIAL:
                    try:
                        if self._port:
                            if hw_energize:
                                self._port.rts = True
                            else:
                                self._port.rts = False
                    except OSError:
                        self._hw_interface = HWInterface.NONE
                        self._err_msg_hndlr("Serial RTS error setting sounder state. Disabling interface.")
                        log.debug(traceback.format_exc(), 3)
                    pass
                pass
            pass
        return

    def _energize_synth(self, energize, no_tone): # type: (bool, bool) -> None
        """
        Energize or de-energize the synth-sounder.

        Energize will play 'click' or 'tone' unless no_tone is True
        De-energize will play 'clack' or silence the tone
        """
        if self._shutdown.is_set():
            return
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
                self._err_msg_hndlr("System audio error playing sounder state. Disabling synth sounder.")
                log.debug(traceback.format_exc(), 3)
        return

    def _hw_is_available(self): # type: () -> bool
        """
        Returns True if hardware is available.
        """
        return (not self._hw_interface == HWInterface.NONE)

    def _key_is_closed(self): # type: () -> bool
        """
        Check the state of the key and return True if it is closed.
        """
        if self._shutdown.is_set():
            return True
        kc = True
        if self._hw_interface == HWInterface.GPIO:
            try:
                kc = not (self._gpio_key_read.is_pressed)
                pass
            except:
                self._hw_interface = HWInterface.NONE
                self._err_msg_hndlr("GPIO interface read error. Disabling interface.")
                log.debug(traceback.format_exc(), 3)
        elif self._hw_interface == HWInterface.SERIAL:
            try:
                kc = self._serial_key_read()
                pass
            except:
                self._hw_interface = HWInterface.NONE
                self._err_msg_hndlr("Serial interface read error. Disabling interface.")
                log.debug(traceback.format_exc(), 3)
        # Invert key state if configured to do so (ex: input is from a modem)
        if self._invert_key_input:
            kc = not kc
        return kc

    def _play_clack_silence(self): # type: () -> None
        if self._shutdown.is_set():
            return
        log.debug("kob._play_clack_silence - requested", 5)
        if self._use_audio and self._synth_energized:
            log.debug("kob._play_clack_silence", 3)
            self._audio.play(0)  # clack/silence
            self._synth_energized = False
        return

    def _play_click(self): # type: () -> None
        if self._shutdown.is_set():
            return
        log.debug("kob._play_click - requested", 5)
        if (self._use_audio and self._audio_type == AudioType.SOUNDER and not self._synth_energized):
            log.debug("kob._play_click", 3)
            self._audio.play(1)  # click
            self._synth_energized = True
        return

    def _play_click_tone(self): # type: () -> None
        if self._shutdown.is_set():
            return
        log.debug("kob._play_click_tone - requested", 5)
        if self._use_audio and not self._synth_energized:
            log.debug("kob._play_click_tone", 3)
            self._audio.play(1)  # click/tone
            self._synth_energized = True
        return

    def _set_key_closer_open(self, open): # type: (bool) -> None
        """
        Track the physical key closer. This controls the Loop/KOB sounder state.
        """
        log.debug("kob._set_key_closer_open: {}->{}".format(self._key_closer_is_open, open), 3)
        if not open == self._key_closer_is_open:
            was_open = self._key_closer_is_open
            self._key_closer_is_open = open
            if not open and self._sounder_mode == SounderMode.EFK:
                # If the sounder was enabled to follow the key (loop)
                # and the key is now closed, update the sounder enabled
                # time so the power save won't kick in right away (due to
                # the time spent using the key)
                self._t_sounder_energized = time.time()
            if not self._virtual_closer_in_use:
                # Have virtual track physical
                self._virtual_closer_is_open = open
            elif open:
                if self._virtual_closer_is_open:
                    self.power_save(False)
            vco = self._virtual_closer_is_open
            self._update_modes(was_open, open, vco, vco, from_key_closer=True)
        return

    def _set_virtual_closer_open(self, open: bool): # type: (bool) -> None
        """
        Track the virtual closer. This controls the Loop/KOB sounder state.
        """
        log.debug("kob._set_virtual_closer_open: {}->{}".format(self._virtual_closer_is_open, open), 3)
        if not open == self._virtual_closer_is_open:
            vcow = self._virtual_closer_is_open
            self._virtual_closer_is_open = open
            if open:
                self.power_save(False)
            kco = self._key_closer_is_open
            self._update_modes(kco, kco, vcow, open)
        return

    def _update_modes(self, kcow=True, kcon=True, vcow=True, vcon=True, from_key_closer=False):
        # type: (bool, bool, bool, bool, bool) -> None
        """
        Based on the type of interface, the closers states, and the local-copy flag,
        set the current sounder and synth mode.

        @SEE: Table in docs for states/modes
        """
        if self._shutdown.is_set():
            return
        sounder_mode_was = self._sounder_mode
        synth_mode_was = self._synth_mode
        log.debug("kob._update_modes: was {}:{} - [{}:{}]|[{}:{}]({})".format(
            sounder_mode_was.name, synth_mode_was.name, kcow, kcon, vcow, vcon, from_key_closer), 2)
        #
        mode_col = KOB.__COL_SEL[self._key_closer_is_open][self._virtual_closer_is_open]
        mode_row = KOB.__ROW_SEL[self._wire_connected][self._sound_local]
        sounder_tbl = KOB.__LOOP_MODES if self._interface_type == InterfaceType.loop else KOB.__KS_MODES
        log.debug("kob._update_modes: Table: '{}'  Row: {}  Col: {}  KO: {}  VO: {}".format(
            sounder_tbl[0],
            mode_row,
            mode_col + 1,
            self._key_closer_is_open,
            self._virtual_closer_is_open), 4)  # Print COL 1-based

        sounder_mode = SounderMode.DIS if (self._hw_interface == HWInterface.NONE) else (
            (sounder_tbl[mode_row])[mode_col]
        )
        synth_mode = (KOB.__SYNTH_MODES[mode_row])[mode_col]
        #
        self._sounder_mode = sounder_mode
        self._synth_mode = synth_mode
        #
        if not sounder_mode == sounder_mode_was:
            log.debug("kob._update_modes: sounder_mode changed", 4)

        if not synth_mode == synth_mode_was:
            log.debug("kob._update_modes: synth_mode changed", 4)

        log.debug("kob._update_modes: now {}:{}".format(
            self._sounder_mode.name, self._synth_mode.name), 2)
        energize_sounder = (not sounder_mode == SounderMode.DIS) and ((sounder_mode == SounderMode.EFK) or (not sounder_mode == SounderMode.SLC and not sounder_mode == SounderMode.FK))
        self._energize_hw_sounder(energize_sounder)
        if not (from_key_closer and self._virtual_closer_in_use):
            energize_synth = (not synth_mode == SynthMode.DIS) and ((not synth_mode == SynthMode.SLC and not synth_mode == SynthMode.FK))
            self._energize_synth(energize_synth, no_tone=True)
        return

    # #############################################################################################
    # Public Interface
    # #############################################################################################

    @property
    def internet_circuit_closed(self): # type: () -> bool
        return self._internet_circuit_closed
    @internet_circuit_closed.setter
    def internet_circuit_closed(self, closed): # type: (bool) -> None
        if not closed == self._internet_circuit_closed:
            self._internet_circuit_closed = closed
        return

    @property
    def keyer_dit_len(self): # type: () -> int
        return self._keyer_dit_len
    @keyer_dit_len.setter
    def keyer_dit_len(self, dit_len): # type: (int) -> None
        self._keyer_dit_len = dit_len
        return

    @property
    def keyer_mode(self): # type: () -> tuple[KeyerMode,CodeSource]
        with self._keyer_mode_guard:
            return self._keyer_mode
        pass

    @property
    def message_receiver(self): # type: () -> Callable
        return self._err_msg_hndlr
    @message_receiver.setter
    def message_receiver(self, f): # type: (Callable) -> None
        self._err_msg_hndlr = f if not f is None else log.warn

    @property
    def no_key_closer(self): # type: () -> bool
        return self._no_key_closer
    @no_key_closer.setter
    def no_key_closer(self, on:bool): # type: (bool) -> None
        was = self._no_key_closer
        if not on == was:
            self._no_key_closer = on
            self._update_modes()
        return

    @property
    def sound_local(self): # type: () -> bool
        return self._sound_local
    @sound_local.setter
    def sound_local(self, on): # type: (bool) -> None
        was = self._sound_local
        if not on == was:
            self._sound_local = on
            self._update_modes()
        return

    @property
    def sounder_is_power_saving(self): # type: () -> bool
        return self._power_saving

    @property
    def sounder_power_save_secs(self): # type: () -> int
        return self._sounder_power_save_secs
    @sounder_power_save_secs.setter
    def sounder_power_save_secs(self, s): # type: (int) -> None
        self._sounder_power_save_secs = 0 if s < 0 else s
        return

    @property
    def use_sounder(self): # type: () -> bool
        return self._use_sounder
    @use_sounder.setter
    def use_sounder(self, use): # type: (bool) -> None
        if not use == self._use_sounder:
            self._use_sounder = use
            self._update_modes()
        return

    @property
    def virtual_closer_is_open(self): # type: () -> bool
        return self._virtual_closer_is_open
    @virtual_closer_is_open.setter
    def virtual_closer_is_open(self, open): # type: (bool) -> None
        self._set_virtual_closer_open(open)
        return

    @property
    def wire_connected(self): # type: () -> bool
        return self._wire_connected
    @wire_connected.setter
    def wire_connected(self, connected): # type (bool) -> None
        if not connected == self._wire_connected:
            self._wire_connected = connected
            self._update_modes()
        return

    def change_audio(self, use_audio, audio_type): # type: (bool, AudioType) -> None
        """
        Change the audio settings from what they were at initialization.
        """
        if self._shutdown.is_set():
            return
        if not (self._use_audio == use_audio and self._audio_type == audio_type):
            self._use_audio = use_audio
            self._audio_type = audio_type
            self.__init_audio()
            self._update_modes()
        return

    def change_hardware(self, interface_type, use_serial, port_to_use, use_gpio, use_sounder, invert_key_input, no_key_closer):
        # type: (InterfaceType, bool, str|None, bool, bool, bool, bool) -> None
        """
        Change the hardware from what it was at initialization
        Note: Hardware may not be different, but re-init with these values.
        """
        if self._shutdown.is_set():
            return
        port_to_use = util.str_none_or_value(port_to_use)
        self._interface_type = interface_type
        self._invert_key_input = invert_key_input
        self._no_key_closer = no_key_closer
        self._use_serial = use_serial
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

    def energize_sounder(self, energize, code_source, from_disconnect = False):
        # type: (bool, CodeSource, bool) -> None
        """
        Set the state of the sounder, both physical and synth/tone, for sounding code.
        True: Energized/Click/Tone
        False: De-Energized/Clack/Silence
        """
        # On Mode-Change, set the correct states
        if self._shutdown.is_set():
            return
        if not code_source == CodeSource.mode_change:
            local_source = not code_source == CodeSource.wire
            if not (self._sounder_mode == SounderMode.DIS or self._sounder_mode == SounderMode.EFK):
                with self._sounder_guard:
                    if local_source and ((not self._sounder_mode == SounderMode.SRC) or from_disconnect):
                        self._energize_hw_sounder(energize)
                    elif not local_source and self._sounder_mode == SounderMode.SRC:
                        self._energize_hw_sounder(energize)
            if not (self._synth_mode == SynthMode.DIS):
                with self._audio_guard:
                    if local_source and ((not self._synth_mode == SynthMode.SRC) or from_disconnect):
                        self._energize_synth(energize, from_disconnect)
                    elif not local_source and self._synth_mode == SynthMode.SRC:
                        self._energize_synth(energize, from_disconnect)
        return

    def exit(self): # type: () -> None
        """
        Stop the threads and exit.
        """
        self.shutdown()
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

    def key(self): # type: () -> tuple[int,...]
        """
        Process input from the key and return a code sequence.
        """
        code = ()  # Start with empty sequence
        if self._shutdown.is_set():
            return code
        sleep_time = 0.001
        while not self._threadsStop_KS.is_set() and self._hw_is_available():
            kc = self._key_state_last_closed
            try:
                kc = self._key_is_closed()
            except(OSError):
                log.debug(traceback.format_exc(), 3)
                return code # Stop trying to process the key
            t = time.time()
            if kc != self._key_state_last_closed:
                self._key_state_last_closed = kc
                dt = int((t - self._t_key_last_change) * 1000)
                self._t_key_last_change = t
                #
                # For 'Separate Key & Sounder' and the Audio/Synth Sounder,
                # drive it here to avoid as much delay from the key
                # transitions as possible. With Loop interface, the physical
                # sounder follows the key (but this is still needed for the synth).
                #
                if self._sounder_mode == SounderMode.FK or self._synth_mode == SynthMode.FK:
                    self.energize_sounder(kc, CodeSource.key)
                self._threadsStop_KS.wait(DEBOUNCE)
                if kc:
                    code += (-dt,)
                elif self._circuit_is_closed and not self._no_key_closer:
                    code += (-dt, +2)  # unlatch closed circuit
                    self._circuit_is_closed = False
                    return code
                else:
                    code += (dt,)
            if not kc and code and t > self._t_key_last_change + CODESPACE:
                return code
            if kc and not self._circuit_is_closed and not self._no_key_closer and t > self._t_key_last_change + CKTCLOSE:
                code += (+1,)  # latch circuit closed
                self._circuit_is_closed = True
                return code
            if len(code) >= 50:  # code sequences can't have more than 50 elements
                return code
            self._threadsStop_KS.wait(sleep_time)
        return code

    def keyer(self): # type: () -> tuple[int,...]
        """
        generate and return a code sequence based on the current and changes to
        the keyer_mode.
        """
        code = ()  # Start with empty sequence
        if self._shutdown.is_set():
            return code
        km1 = self.keyer_mode  # Use the property to employ the guard
        sleep_time = 0.001
        while not self._threadsStop_keyer.is_set():
            drive_sounder = ((self._sounder_mode == SounderMode.FK) or
                            (self._sounder_mode == SounderMode.SLC) or
                            (self._synth_mode == SynthMode.FK) or
                            (self._synth_mode == SynthMode.SLC))
            km = self.keyer_mode
            t = time.time()
            if km[0] == km1[0] and km[0] == KeyerMode.DITS:
                # Still generating dits
                if drive_sounder:
                    self.energize_sounder(self._keyer_dits_down, km[1])
                self._threadsStop_keyer.wait(self.keyer_dit_len / 1000)
                klen = self.keyer_dit_len if self._keyer_dits_down else -self.keyer_dit_len
                code += (klen,)
                self._keyer_dits_down = not self._keyer_dits_down
                t = time.time()
            elif km[0] != km1[0]:  # Mode changed
                km2 = km1  # We'll need to know if it was DITS
                km1 = km
                dt = self.keyer_dit_len if km2[0] == KeyerMode.DITS else (int((t - self._t_keyer_mode_change) * 1000) - 8)
                self._t_keyer_mode_change = t
                #
                # Drive the sounder based on the mode.
                #
                if km[0] == KeyerMode.DITS:
                    # Start generating dits...
                    self._keyer_dits_down = True
                    self._threadsStop_keyer.wait(self.keyer_dit_len / 2000)  # Delay 1/2 a dit len to allow for keyboard reaction
                else:  # DAH or IDLE
                    self._keyer_dits_down = False
                    if drive_sounder:
                        energize = km[0] == KeyerMode.DAH
                        self.energize_sounder(energize, CodeSource.key)
                if km[0] == KeyerMode.IDLE:
                    if km2[0] == KeyerMode.DITS:
                        if code[-1] < 0:
                            code += (dt,)
                        return code
                    else:
                        code += (dt,)
                else:  # DITS or DAH
                    code += (-dt,)
            if km[0] == KeyerMode.IDLE and code and t > self._t_keyer_mode_change + CODESPACE:
                return code
            if len(code) >= 50:  # code sequences can't have more than 50 elements
                return code
            if km[0] == KeyerMode.IDLE:
                self._threadsStop_keyer.wait(sleep_time)
        return code

    def keyer_mode_set(self, mode: KeyerMode, source: CodeSource): # type: (KeyerMode, CodeSource) -> None
        """
        Set the keyer mode.
        """
        km:tuple[KeyerMode,CodeSource] = (mode, source)
        log.debug("kob.keyer_mode_set {}->{}".format(self._keyer_mode, km), 3)
        with self._keyer_mode_guard:
            self._keyer_mode = km
        return

    def power_save(self, enable): # type: (bool) -> None
        """
        True to turn off the sounder power to save power (reduce risk of fire, etc.)
        """
        # Only enable power save if mode is sounding remote code or a recording.
        if self._shutdown.is_set():
            return
        if enable and (
            self._sounder_mode == SounderMode.DIS or
            self._sounder_mode == SounderMode.EFK or
            self._sounder_mode == SounderMode.FK):
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

    def shutdown(self): # type: () -> None
        """
        Initiate shutdown of our operations (and don't start anything new),
        but DO NOT BLOCK.
        """
        self._shutdown.set()
        self._threadsStop_keyer.set()
        self._threadsStop_KS.set()
        self.__stop_hw_processing()
        self._key_callback = None
        return

    def soundCode(self, code, code_source = CodeSource.local, sound = True):
        # type: (tuple[int,...], CodeSource, bool) -> None
        """
        Process the code and sound it.
        """
        if self._shutdown.is_set():
            return
        if sound:
            self.power_save(False)
        for c in code:
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
                self._shutdown.wait(dt)
            if c > 1:  # end of (nonlatching) mark
                if sound:
                    self.energize_sounder(False, code_source)
        return
