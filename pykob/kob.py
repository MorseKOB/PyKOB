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
import sys
import time
from enum import Enum, IntEnum, unique
from pykob import config, log, morse
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
        (SounderMode.REC, SounderMode.DIS, SounderMode.REC, SounderMode.DIS),
        (SounderMode.REC, SounderMode.SLC, SounderMode.REC, SounderMode.EFK),
        (SounderMode.SRC, SounderMode.DIS, SounderMode.SRC, SounderMode.DIS),
        (SounderMode.SRC, SounderMode.SLC, SounderMode.SRC, SounderMode.EFK)
    )

    __KS_MODES = (
        (SounderMode.REC, SounderMode.DIS, SounderMode.REC, SounderMode.DIS),
        (SounderMode.REC, SounderMode.SLC, SounderMode.REC, SounderMode.FK),
        (SounderMode.SRC, SounderMode.DIS, SounderMode.SRC, SounderMode.DIS),
        (SounderMode.SRC, SounderMode.SLC, SounderMode.SRC, SounderMode.FK)
    )

    __SYNTH_MODES = (
        (SynthMode.REC, SynthMode.DIS, SynthMode.REC, SynthMode.DIS),
        (SynthMode.REC, SynthMode.SLC, SynthMode.REC, SynthMode.FK),
        (SynthMode.SRC, SynthMode.DIS, SynthMode.SRC, SynthMode.DIS),
        (SynthMode.SRC, SynthMode.SLC, SynthMode.SRC, SynthMode.FK)
    )

    __COL_SEL = (
        (0, 1),     # KC & VC | KC & VO
        (2, 3)      # KO & VC | KO & VO
    )

    __ROW_SEL = (
        (0, 1),     # WNC & NLC | WNC & LC
        (2, 3)      # WC  & NLC | WC  & LC
    )

    
    def __init__(
            self, interfaceType:InterfaceType=InterfaceType.loop, portToUse:Optional[str]=None,
            useGpio:bool=False, useAudio:bool=False, audioType:AudioType=AudioType.SOUNDER, useSounder:bool=False, invertKeyInput:bool=False, soundLocal:bool=True, sounderPowerSaveSecs:int=0,
                    virtual_closer_in_use: bool = False, err_msg_hndlr=None, keyCallback=None):
        """
        When PyKOB code is not running, the physical sounder (if connected) is not powered by
        a connected interface, so set the initial state flags accordingly.

        Initialize the hardware and update the flags and mode.
        """
        self._interface_type:InterfaceType = interfaceType # Loop, K&S, Keyer/Paddle (K&S and Keyer are mostly the same)
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
        self._shutdown: Event = Event()
        self._hw_interface:HWInterface = HWInterface.NONE
        self._gpio_key_read = None
        self._gpio_pdl_dah = None
        self._gpio_sndr_drive = None
        self._port = None
        self._serial_key_read = self.__read_nul  # Read a NUL key. Changed in HW Init if interface is configured.
        self._serial_pdl_dah = self.__read_nul   # Read a NUL paddle dah (dash).
        self._audio = None
        self._paddle_is_supported = False        # Set in HW Init if possible.
        self._audio_guard: RLock = RLock()
        self._keyer_mode_guard: RLock = RLock()
        self._sounder_guard: RLock = RLock()
        #
        now = time.time()
        self._keyer_mode: tuple[KeyerMode,CodeSource] = (KeyerMode.IDLE, CodeSource.key)
        self._keyer_dit_len: int = morse.Sender.DOT_LEN_20WPM
        self._t_keyer_mode_change: float = now  # time of last keyer mode change during processing
        self._keyer_dits_down: bool = False
        #
        self._key_closer_is_open: bool = True
        self._virtual_closer_is_open: bool = True
        self._circuit_is_closed: bool = False
        self._internet_circuit_closed = False
        self._wire_connected: bool = False
        self._power_saving: bool = False  # Indicates if Power-Save is active
        self._ps_energize_sounder: bool = False
        self._sounder_energized: bool = False
        self._synth_energized: bool = False  # True: last played 'click/tone', False: played 'clack' (or hasn't played)
        self._sounder_mode: SounderMode = SounderMode.DIS
        self._synth_mode: SynthMode = SynthMode.DIS
        self._t_sounder_energized: float = -1.0
        self._t_soundcode_last_change: float = 0.0  # time of last code sounding transition
        self._t_key_last_change: float = -1.0  # time of last key transition
        #
        self._key_callback = None # Set to the passed in value once we establish an interface
        #
        self._thread_keyer: Optional[Thread] = None
        self._thread_keyread: Optional[Thread] = None
        self._thread_powersave: Optional[Thread] = None
        self._threadsStop: Event = Event()
        #
        self._key_state_last_closed = False
        #
        self.__init_audio()  # Do this first so it doesn't get an error when HW energizes the sounder.
        self.__init_hw_interface()
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
                    self._gpio_pdl_dah = gpio_button(20, pull_up=True)   # GPIO20 is paddle-dah (dash).
                    self._gpio_sndr_drive = gpio_led(26)  # GPIO26 used to drive sounder.
                    self._hw_interface = HWInterface.GPIO
                    self._paddle_is_supported = True
                    log.info("The GPIO interface is available/active and will be used.")
                except:
                    self._hw_interface = HWInterface.NONE
                    self._paddle_is_supported = False
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
                    self._serial_pdl_dah = self.__read_cts   # Assume that we will use CTS to read the paddle-dah (dash)
                    self._hw_interface = HWInterface.SERIAL
                    log.info("The serial interface is available/active and will be used.")
                    self._port.write(b"PyKOB\n")
                    self._threadsStop.wait(0.5)
                    indata = self._port.readline()
                    if indata == b"PyKOB\n":
                        self._serial_key_read = self.__read_cts  # Use CTS to read the key
                        self._serial_pdl_dah = self.__read_nul   # Paddle Dah/Dash cannot be supported
                        self._paddle_is_supported = False
                        log.info("KOB Serial Interface is 'minimal' type (key on CTS).")
                    else:
                        self._paddle_is_supported = True
                        log.info("KOB Serial Interface is 'full' type (key/pdl-dit on DSR, pdl-dah on CTS).")
                except Exception as ex:
                    self._hw_interface = HWInterface.NONE
                    self._serial_key_read = self.__read_nul
                    self._serial_pdl_dah = self.__read_nul
                    self._err_msg_hndlr(
                        "Serial port '{}' is not available. Key/sounder will not function.".format(self._port_to_use)
                    )
                    log.debug(ex)
            # Update closers states based on state of key
            key_closed = False
            if not self._hw_interface == HWInterface.NONE:
                # Read the key
                key_closed = self._key_is_closed()
            self._circuit_is_closed = key_closed
            self._t_key_last_change = time.time()  # time of last key transition
            self._set_key_closer_open(not key_closed)
            self._set_virtual_closer_open(not key_closed)
            self._update_modes()
        return

    def __read_cts(self) -> bool:
        v = False
        if self._port:
            v = self._port.cts
        return v

    def __read_dsr(self) -> bool:
        v = False
        if self._port:
            v = self._port.dsr
        return v

    def __read_nul(self) -> bool:
        """ Always returns False """
        return False

    def __restart_hw_processing(self) -> None:
        """
        Restart processing due to hardware changes.
        """
        if not self._shutdown.is_set() and self._hw_is_available():
            self.__start_hw_processing()
        elif self._threadsStop.is_set() or not self._hw_is_available():
            self.__stop_hw_processing()
        return

    def __start_hw_processing(self) -> None:
        """
        Start our processing threads if needed.
        """
        if not self._shutdown.is_set() and self._hw_is_available():
            self._threadsStop.clear()
            self.power_save(False)
            if not self._thread_keyer:
                self._thread_keyer = Thread(name="KOB-Keyer", target=self._thread_keyer_body)
                self._thread_keyer.start()
            if self._key_callback:
                if not self._thread_keyread:
                    self._thread_keyread = Thread(name="KOB-KeyRead", target=self._thread_keyread_body)
                    self._thread_keyread.start()
            if not self._thread_powersave:
                self._thread_powersave = Thread(name="KOB-PowerSave", target=self._thread_powersave_body)
                self._thread_powersave.start()
        return

    def __stop_hw_processing(self) -> None:
        self._threadsStop.set()
        if self._thread_keyread and self._thread_keyread.is_alive():
            self._thread_keyread.join(timeout=2.0)
        if self._thread_powersave and self._thread_powersave.is_alive():
            self._thread_powersave.join(timeout=2.0)
        self._thread_keyread = None
        self._thread_powersave = None
        return

    def _thread_keyer_body(self):
        """
        Called by the Keyer thread `run` to send automated dits/dah based on the mode.
        """
        while not self._threadsStop.is_set() and not self._shutdown.is_set():
            code = self.keyer()
            if len(code) > 0:
                if code[-1] == 1: # special code for closer/circuit closed
                    self._set_key_closer_open(False)
                elif code[-1] == 2: # special code for closer/circuit open
                    self._set_key_closer_open(True)
                if self._key_callback and not self._threadsStop.is_set():
                    self._key_callback(code)
        log.debug("{} thread done.".format(threading.current_thread().name))
        return

    def _thread_keyread_body(self):
        """
        Called by the KeyRead thread `run` to read code from the key.
        """
        while not self._threadsStop.is_set() and self._hw_is_available() and not self._shutdown.is_set():
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

    def _thread_powersave_body(self):
        """
        Called by the PowerSave thread 'run' to control the power save (sounder energize)
        """
        while not self._threadsStop.is_set() and not self._shutdown.is_set():
            now = time.time()
            if self._sounder_power_save_secs > 0 and not self._power_saving:
                if self._t_sounder_energized > 0 and (now - self._t_sounder_energized) > self._sounder_power_save_secs:
                    self.power_save(True)
            self._threadsStop.wait(0.5)
        log.debug("{} thread done.".format(threading.current_thread().name))
        return

    def _energize_hw_sounder(self, energize: bool):
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
                    pass
                pass
            pass
        return

    def _energize_synth(self, energize: bool, no_tone: bool):
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
        if self._shutdown.is_set():
            return
        log.debug("kob._play_clack_silence - requested", 5)
        if self._use_audio and self._synth_energized:
            log.debug("kob._play_clack_silence", 3)
            self._audio.play(0)  # clack/silence
            self._synth_energized = False
        return

    def _play_click(self):
        if self._shutdown.is_set():
            return
        log.debug("kob._play_click - requested", 5)
        if (self._use_audio and self._audio_type == AudioType.SOUNDER and not self._synth_energized):
            log.debug("kob._play_click", 3)
            self._audio.play(1)  # click
            self._synth_energized = True
        return

    def _play_click_tone(self):
        if self._shutdown.is_set():
            return
        log.debug("kob._play_click_tone - requested", 5)
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
        if not open == self._key_closer_is_open:
            if not self._virtual_closer_in_use:
                # Have virtual track physical and update modes
                self._virtual_closer_is_open = open
                self._update_modes()
            elif open:
                if self._virtual_closer_is_open:
                    self._update_modes()
                self.power_save(False)
        return

    def _set_virtual_closer_open(self, open: bool):
        """
        Track the virtual closer. This controlles the Loop/KOB sounder state.
        """
        log.debug("kob._set_virtual_closer_open: {}->{}".format(self._virtual_closer_is_open, open), 3)
        if not open == self._virtual_closer_is_open:
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
        if self._shutdown.is_set():
            return
        sounder_mode_was = self._sounder_mode
        synth_mode_was = self._synth_mode
        log.debug("kob._update_modes: was {}:{}".format(sounder_mode_was.name, synth_mode_was.name), 2)
        #
        mode_col = KOB.__COL_SEL[self._key_closer_is_open][self._virtual_closer_is_open]
        mode_row = KOB.__ROW_SEL[self._wire_connected][self._sound_local]
        sounder_tbl = KOB.__LOOP_MODES if self._interface_type == InterfaceType.loop else KOB.__KS_MODES
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

        energize_sounder = ((
                not self._virtual_closer_is_open and
                not self._wire_connected
            ) or (
                self._wire_connected and
                self._internet_circuit_closed and
                not self._virtual_closer_is_open
            )
        )
        self._energize_hw_sounder(energize_sounder or sounder_mode == SounderMode.EFK)
        self._energize_synth(energize_sounder, no_tone=True)
        log.debug("kob._update_modes: now {}:{}".format(self._sounder_mode.name, self._synth_mode.name), 2)
        return

    # #############################################################################################
    # Public Interface
    # #############################################################################################

    @property
    def internet_circuit_closed(self) -> bool:
        return self._internet_circuit_closed
    @internet_circuit_closed.setter
    def internet_circuit_closed(self, closed:bool) -> None:
        if not closed == self._internet_circuit_closed:
            self._internet_circuit_closed = closed
        return

    @property
    def keyer_dit_len(self) -> int:
        return self._keyer_dit_len
    @keyer_dit_len.setter
    def keyer_dit_len(self, dit_len:int):
        self._keyer_dit_len = dit_len
        return

    @property
    def keyer_mode(self) -> tuple[KeyerMode,CodeSource]:
        with self._keyer_mode_guard:
            return self._keyer_mode
        pass

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
    def sounder_is_power_saving(self) -> bool:
        return self._power_saving

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

    @property
    def wire_connected(self) -> bool:
        return self._wire_connected
    @wire_connected.setter
    def wire_connected(self, connected:bool) -> None:
        if not connected == self._wire_connected:
            self._wire_connected = connected
            self._update_modes()
        return

    def change_audio(self, use_audio:bool, audio_type:AudioType) -> None:
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

    def change_hardware(self, interface_type: InterfaceType, port_to_use: Optional[str], use_gpio: bool, use_sounder: bool) -> None:
        """
        Change the hardware from what it was at initialization
        """
        if self._shutdown.is_set():
            return
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

    def exit(self):
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

    def key(self) -> tuple[int,...]:
        '''
        Process input from the key and return a code sequence.
        '''
        code = ()  # Start with empty sequence
        if self._shutdown.is_set():
            return code
        # The following 3 are used to slowing increase the sleep
        # time if the key is idle. This is to reduce CPU usage.
        no_change = 0
        sleep_time = 0.001
        sleep_bump = 0.005
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
                if self._sounder_mode == SounderMode.FK or self._synth_mode == SynthMode.FK:
                    self.energize_sounder(kc, CodeSource.key)
                elif self._sounder_mode == SounderMode.EFK and self._use_sounder and kc:
                    # For LOOP interface, update the key energized time so the sounder power
                    # save won't kick in as soon as the key is closed.
                    self._t_sounder_energized = t
                self._threadsStop.wait(DEBOUNCE)
                if kc:
                    code += (-dt,)
                elif self._circuit_is_closed:
                    code += (-dt, +2)  # unlatch closed circuit
                    self._circuit_is_closed = False
                    return code
                else:
                    code += (dt,)
                no_change = 0
                sleep_time = 0.001
                sleep_bump = 0.005
            else:
                if sleep_time < 0.025:
                    no_change += 1
                    if (no_change % 1000) == 0:
                        sleep_time += sleep_bump  # if no changes for a while, slightly increase sleep
                        sleep_bump += sleep_bump
            if not kc and code and t > self._t_key_last_change + CODESPACE:
                return code
            if kc and not self._circuit_is_closed and t > self._t_key_last_change + CKTCLOSE:
                code += (+1,)  # latch circuit closed
                self._circuit_is_closed = True
                return code
            if len(code) >= 50:  # code sequences can't have more than 50 elements
                return code
            self._threadsStop.wait(sleep_time)
        return code

    def keyer(self) -> tuple[int,...]:
        '''
        generate and return a code sequence based on the current and changes to
        the keyer_mode.
        '''
        code = ()  # Start with empty sequence
        if self._shutdown.is_set():
            return code
        km1 = self.keyer_mode  # Use the property to employ the guard
        # The following 3 are used to slowing increase the sleep
        # time if the key is idle. This is to reduce CPU usage.
        no_change = 0
        sleep_time = 0.001
        sleep_bump = 0.005
        while not self._threadsStop.is_set():
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
                self._threadsStop.wait(self.keyer_dit_len / 1000)
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
                else:  # DAH or IDLE
                    self._keyer_dits_down = False
                    if drive_sounder:
                        energize = km[0] == KeyerMode.DAH
                        self.energize_sounder(energize, CodeSource.key)
                if km[0] == KeyerMode.IDLE:
                    if self._circuit_is_closed:
                        code += (-dt, +2)  # unlatch closed circuit
                        self._circuit_is_closed = False
                        return code
                    elif km2[0] == KeyerMode.DITS:
                        return code
                    else:
                        code += (dt,)
                else:  # DITS or DAH
                    code += (-dt,)
                no_change = 0
                sleep_time = 0.001
                sleep_bump = 0.005
            else:
                if sleep_time < 0.030:
                    no_change += 1
                    if (no_change % 1000) == 0:
                        sleep_time += sleep_bump  # if no changes for a while, slightly increase sleep
                        sleep_bump += sleep_bump
            if km[0] == KeyerMode.IDLE and code and t > self._t_keyer_mode_change + CODESPACE:
                return code
            if km[0] == KeyerMode.DAH and not self._circuit_is_closed and t > self._t_keyer_mode_change + CKTCLOSE:
                code += (+1,)  # latch circuit closed
                self._circuit_is_closed = True
                return code
            if len(code) >= 50:  # code sequences can't have more than 50 elements
                return code
            if km[0] == KeyerMode.IDLE:
                self._threadsStop.wait(sleep_time)
        return code

    def keyer_mode_set(self, mode: KeyerMode, source: CodeSource):
        """
        Set the keyer mode. 
        """
        km:tuple[KeyerMode,CodeSource] = (mode, source)
        log.debug("kob.keyer_mode_set {}->{}".format(self._keyer_mode, km), 3)
        with self._keyer_mode_guard:
            self._keyer_mode = km
        return

    def power_save(self, enable: bool):
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

    def shutdown(self):
        """
        Initiate shutdown of our operations (and don't start anything new),
        but DO NOT BLOCK.
        """
        self._shutdown.set()
        self._threadsStop.set()
        self.__stop_hw_processing()
        self._key_callback = None
        return

    def soundCode(self, code, code_source: CodeSource = CodeSource.local, sound: bool = True):
        '''
        Process the code and sound it.
        '''
        if self._shutdown.is_set():
            return
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
