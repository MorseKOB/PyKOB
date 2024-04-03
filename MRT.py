#!/usr/bin/env python3
"""
MIT License

Copyright (c) 2020-2024 PyKOB - MorseKOB in Python

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
MRT.py

Morse Receive & Transmit (Marty).
Connects to a wire and receives code from it, which is sounded and displayed
on the console. Follows the local key and opens the circuit if the key
closer is opened, then sends the local code to the wire.

This reads the current configuration and supports the common option flags.
To maintain backward compatibility it also allows a positional command
line parameter:
    1. KOB Server wire no.

Example:
    python MRT.py 11
"""

from pykob import VERSION, config, config2, log, kob, internet, morse, recorder
from pykob.config2 import Config
from pykob.internet import Internet
from pykob.kob import KOB
from pykob.morse import Reader, Sender
from pykob.recorder import Recorder
from pykob.selector import Selector, SelectorMode, SelectorChange
import pkappargs

import argparse
from enum import Enum
import json
from json import JSONDecodeError
from pathlib import Path
import platform
import queue
from queue import Empty, Queue
import select
import sys
from sys import platform
from threading import Event, Thread
import time
from time import sleep
from typing import Optional, Sequence

__version__ = '1.3.3'
MRT_VERSION_TEXT = "MRT " + __version__

MRT_SEL_EXT = ".mrtsel"

class SelectorType(Enum):

    def __new__(cls, *args, **kwds):
        obj = object.__new__(cls)
        obj._value_ = args[0]
        obj._key = args[0]
        obj._elements = args[1]
        obj._mode = args[2]
        obj._index_adj = args[3]
        obj._change = args[4]
        return obj

    def __repr__(self):
        return f'<{type(self).__name__}.{self.name}:({self._key},{self._elements!r},{self._mode!r},{self._index_adj},{self._change!r})>'

    def __str__(self) -> str:
        return self.name

    @property
    def key(self) -> str:
        return self._key
    @property
    def elements(self) -> int:
        return self._elements
    @property
    def mode(self) -> SelectorMode:
        return self._mode
    @property
    def index_adj(self) -> int:
        return self._index_adj
    @property
    def change(self) -> SelectorChange:
        return self._change

    ONE_OF_FOUR = "1OF4", 4, SelectorMode.OneOfFour, -1, SelectorChange.OneOfFour
    BINARY = "BINARY", 16, SelectorMode.Binary, 0, SelectorChange.Binary


SELECTOR_SELECTIONS_KEY = "selections"
SELECTOR_TYPE_KEY = "type"
SELECTION_ARGS_KEY = "args"
SELECTION_DESCRIPTION_KEY = "desc"

LATCH_CODE = (-0x7fff, +1)  # code sequence to force latching (close)
UNLATCH_CODE = (-0x7fff, +2)  # code sequence to unlatch (open)

class RawTerm:
    """
    Sets the terminal to Raw Mode (but still w/CRNL on output) and provides a method to
    gets a single character.  Does not echo to the screen.

    This uses native calls on Windows and *nix (Linux and MacOS), and relies on
    the Subclasses for each platform.

    Call `exit` when done using, to restore settings.
    """
    def __init__(self, shutdown_event:Optional[Event]=None):
        self._shutdown_event = shutdown_event if not shutdown_event is None else Event()
        self._impl = None
        if platform.startswith(("darwin", "linux", "freebsd", "openbsd")):  # MacOSX and Linux/UNIX
            try:
                self._impl = _GetchUnix(self._shutdown_event)
            except Exception as ex:
                log.warn("Unable to set up direct keyboard access for {} ({})".format(platform, ex))
        elif platform in ("win32", "cygwin"):
            try:
                self._impl = _GetchWindows(self._shutdown_event)
            except Exception as ex:
                log.warn("Unable to set up direct keyboard access for {} ({})".format(platform, ex))
        else:
            log.warn("The platform {} is not currently supported for direct keyboard access.".format(platform))
        return

    def getch(self) -> str:
        return self._impl._getch()

    def exit(self) -> None:
        self._shutdown_event.set()
        self._impl._exit()
        return

class _GetchUnix:
    """
    Get a single character from the standard input on *nix

    Used by `RawTerm`
    """
    def __init__(self, shutdown_event:Event):
        import tty, sys, termios
        self.shutdown_event = shutdown_event
        self.fd = sys.stdin.fileno()
        self.original_settings = None
        try:
            self.original_settings = termios.tcgetattr(self.fd)
        except Exception as ex:
            log.warn("RawTerm cannot read the current terminal settings. "
                    + "The terminal will not be able to be restored when MRT terminates. "
                    + "Error: {}".format(ex))
        try:
            tty.setraw(sys.stdin.fileno())
            attrs = termios.tcgetattr(self.fd)
            attrs[1] |= termios.OPOST
            termios.tcsetattr(self.fd, termios.TCSANOW, attrs)
        except Exception as ex:
            log.warn("RawTerm cannot set the terminal settings needed to read keys directly. "
                    + "MRT will not be able to support keyboard sending. "
                    + "Error: {}".format(ex))
            # try to put the original back
            if self.original_settings:
                try:
                    termios.tcsetattr(self.fd, termios.TCSADRAIN, self.original_settings)
                except Exception as ex:
                    log.warn("Terminal settings were not able to be restored. " +
                        "It is suggested that you close the terminal when done with MRT.")
                    pass
                pass
            pass
        return

    def _getch(self) -> str:
        while not self.shutdown_event.is_set():
            char_ready = select.select([self.fd], [], [], 0)  # Check readability and never block
            if len(char_ready[0]) > 0:  # Simple check since we only have stdin registered
                return sys.stdin.read(1)
            self.shutdown_event.wait(0.01)
        return ''

    def _exit(self):
        import termios
        self.shutdown_event.set()
        if self.original_settings:
            try:
                termios.tcsetattr(self.fd, termios.TCSADRAIN, self.original_settings)
            except Exception as ex:
                log.warn("Terminal settings were not able to be restored. " +
                    "It is suggested that you close the terminal when done with MRT.")
                pass
            pass
        return

class _GetchWindows:
    """
    Get a single character from the standard input on Windows

    Used by `RawTerm`
    """
    def __init__(self, shutdown_event:Event):
        import msvcrt
        self.shutdown_event = shutdown_event
        return

    def _getch(self) -> str:
        import msvcrt

        while not self.shutdown_event.is_set():
            if msvcrt.kbhit():
                return msvcrt.getch().decode("utf-8")
            self.shutdown_event.wait(0.01)
        return ''

    def _exit(self):
        self.shutdown_event.set()
        return

class Mrt:
    """
    Morse Receive & Transmit 'Marty'.

    Process the keyboard and a key to send code sequences. Receive from a wire
    and sound and decode/display.

    Options allow sending a file or playing a recording, and repeating that operation.
    """
    def __init__(
        self,
        app_name_version: str, wire: int,
        cfg: Config,
        sender_dt: bool,
        repeat_delay: int = -1,
        record_filepath: Optional[str] = None,
        file_to_play: Optional[str] = None,
        file_to_send: Optional[str] = None
    ) -> None:
        self._app_name_version = app_name_version
        self._wire: int = wire
        self._cfg: Config = cfg
        self._sender_dt: bool = sender_dt
        self._repeat_delay: int = repeat_delay
        self._shutdown: Event = Event()
        self._fst_stop: Event = Event()
        self._kbt_stop: Event = Event()
        self._prt_stop: Event = Event()
        self._control_c_pressed: Event = Event()
        self._kb_queue: Queue = Queue(128)
        self._closed: Event = Event()

        self._record_filepath = None if record_filepath is None else recorder.add_ext_if_needed(record_filepath.strip())
        self._player: Optional[Recorder] = None
        self._playback_complete: Event = Event()
        self._play_file_path = None
        if file_to_play:
            self._play_file_path = recorder.add_ext_if_needed(file_to_play.strip())
            p = Path(self._play_file_path)
            p.resolve()
            if not p.is_file():
                print("Recording not found. '{}'".format(self._play_file_path), flush=True)
                self._play_file_path = None
                self._playback_complete.set()
                raise FileNotFoundError(p)
            pass
        else:
            self._playback_complete.set()

        self._filesend_running: Event = Event()
        self._send_file_path = None
        if file_to_send:
            self._send_file_path = file_to_send.strip()
            p = Path(self._send_file_path)
            p.resolve()
            if not p.is_file():
                print("File to send not found. '{}'".format(self._send_file_path), flush=True)
                self._send_file_path = None
                raise FileNotFoundError(p)
            pass


        self._internet: Optional[Internet] = None
        self._kob: Optional[KOB] = None
        self._reader: Optional[Reader] = None
        self._recorder: Optional[Recorder] = None
        self._sender: Optional[Sender] = None
        self._thread_kbreader: Optional[Thread] = None
        self._thread_kbsender: Optional[Thread] = None

        self._connected = False
        self._internet_station_active = False  # True if a remote station is sending
        self._last_received_para = False # The last character received was a Paragraph ('=')
        self._local_loop_active = False  # True if sending on key or keyboard
        self._our_office_id = cfg.station if not cfg.station is None else ""
        self._sender_current = ""

        self._do_automated_stuff: bool = (not self._play_file_path is None or not self._send_file_path is None)
        self._automation_started: bool = False

        self._exit_status = 1

        return

    def exit(self):
        if not self._closed.is_set():
            self._closed.set()
            print("\nClosing...")
            self._shutdown.set()
            sleep(0.3)
            log.debug("MRT.exit - 1", 3)
            self.shutdown()
            log.debug("MRT.exit - 2", 3)
            kob_ = self._kob
            if kob_:
                log.debug("MRT.exit - 3a", 3)
                kob_.exit()
                log.debug("MRT.exit - 3b", 3)
            inet = self._internet
            if inet:
                log.debug("MRT.exit - 4a", 3)
                inet.exit()
                log.debug("MRT.exit - 4b", 3)
            plr = self._player
            if plr:
                log.debug("MRT.exit - 5a", 3)
                plr.exit()
                log.debug("MRT.exit - 5b", 3)
            rdr = self._reader
            if rdr:
                log.debug("MRT.exit - 6a", 3)
                rdr.exit()
                log.debug("MRT.exit - 6b", 3)
            rec = self._recorder
            if rec:
                log.debug("MRT.exit - 7a", 3)
                rec.exit()
                log.debug("MRT.exit - 7b", 3)
            sndr = self._sender
            if sndr:
                log.debug("MRT.exit - 8a", 3)
                sndr.exit()
                log.debug("MRT.exit - 8b", 3)
        return

    def main_loop(self):
        self._print_start_info()
        if not self._wire == 0:
            self._internet.connect(self._wire)
            self._connected = True
            kob_ = self._kob
            if kob_:
                kob_.internet_circuit_closed = not self._internet_station_active
                kob_.wire_connected = self._connected
        self._shutdown.wait(0.5)
        try:
            #
            # If we have been asked to play a recording, play it.
            # If we have been asked to send a file, send it.
            # If we have a non-negative repeat value, repeat (with a pause if specified)
            #
            while not self._shutdown.is_set() and not self._control_c_pressed.is_set():
                self._process_automation()
                self._shutdown.wait(0.05)  # Loop while background threads take care of 'stuff'
                if self._control_c_pressed.is_set():
                    raise KeyboardInterrupt
        except KeyboardInterrupt:
            raise KeyboardInterrupt
        finally:
            self.exit()
        return

    def shutdown(self):
        log.debug("MRT.shutdown - 1", 3)
        self._shutdown.set()
        log.debug("MRT.shutdown - 2", 3)
        kob_ = self._kob
        if kob_:
            log.debug("MRT.shutdown - 3a", 3)
            kob_.shutdown()
            log.debug("MRT.shutdown - 3b", 3)
        inet = self._internet
        if inet:
            log.debug("MRT.shutdown - 4a", 3)
            inet.shutdown()
            log.debug("MRT.shutdown - 4b", 3)
        plr = self._player
        if plr:
            log.debug("MRT.shutdown - 5a", 3)
            plr.shutdown()
            log.debug("MRT.shutdown - 5b", 3)
        rdr = self._reader
        if rdr:
            log.debug("MRT.shutdown - 6a", 3)
            rdr.shutdown()
            log.debug("MRT.shutdown - 6b", 3)
        rec = self._recorder
        if rec:
            log.debug("MRT.shutdown - 7a", 3)
            rec.shutdown()
            log.debug("MRT.shutdown - 7b", 3)
        sndr = self._sender
        if sndr:
            log.debug("MRT.shutdown - 8a", 3)
            sndr.shutdown()
            log.debug("MRT.shutdown - 8b", 3)
        return

    def start(self):
        if self._play_file_path:
            self._player = Recorder(
                None,
                self._play_file_path,
                station_id=self._cfg.station,
                wire=self._wire,
                play_code_callback=self._from_player,
                play_sender_id_callback=self._handle_sender_update,
                play_station_list_callback=None,
                play_wire_callback=None,
                play_finished_callback=self._from_player_finished
            )
        if self._record_filepath:
            log.log("Recording to '{}'\n".format(self._record_filepath), dt="")
            self._recorder = Recorder(
                self._record_filepath,
                None,
                station_id=self._our_office_id,
                wire=self._wire,
                play_code_callback=None,
                play_sender_id_callback=None,
                play_station_list_callback=None,
                play_wire_callback=None,
            )

        self._kob = kob.KOB(
            interfaceType=self._cfg.interface_type,
            portToUse=self._cfg.serial_port,
            useGpio=self._cfg.gpio,
            useAudio=self._cfg.sound,
            audioType=self._cfg.audio_type,
            useSounder=self._cfg.sounder,
            invertKeyInput=self._cfg.invert_key_input,
            soundLocal=self._cfg.local,
            sounderPowerSaveSecs=self._cfg.sounder_power_save,
            virtual_closer_in_use=True,
            keyCallback=self._from_key
            )
        self._internet = internet.Internet(
            officeID=self._our_office_id,
            code_callback=self._from_internet,
            appver=self._app_name_version,
            server_url=self._cfg.server_url,
            err_msg_hndlr=log.warn
        )
        self._internet.monitor_sender(self._handle_sender_update) # Set callback for monitoring current sender
        self._sender = morse.Sender(
            wpm=self._cfg.text_speed,
            cwpm=self._cfg.min_char_speed,
            codeType=self._cfg.code_type,
            spacing=self._cfg.spacing
            )
        self._reader = morse.Reader(
            wpm=self._cfg.text_speed,
            cwpm=self._cfg.min_char_speed,
            codeType=self._cfg.code_type,
            callback=self._reader_callback
            )
        if sys.stdin.isatty():
            # Threads to read characters from the keyboard to allow sending without (instead of) a physical key.
            self._thread_kbreader = Thread(name="Keyboard-read-thread", daemon=False, target=self._thread_kbreader_body)
            self._thread_kbsender = Thread(name="Keyboard-send-thread", daemon=False, target=self._thread_kbsender_body)
        self._thread_fsender = None
        if self._send_file_path:
            self.__create_file_thread()
        if not self._thread_kbreader is None and not self._thread_kbsender is None:
            self._thread_kbreader.start()
            self._thread_kbsender.start()
        return

    def __create_file_thread(self):
        if self._thread_fsender:
            self._fst_stop.set()
            if self._thread_fsender.is_alive():
                self._thread_fsender.join()
        self._thread_fsender = Thread(name="File-send-thread", daemon=False, target=self._thread_fsender_body)
        self._fst_stop.clear()
        self._filesend_running.clear()
        return

    def _emit_local_code(self, code, code_source, char:Optional[str]=None):
        """
        Emit local code. That involves:
        1. Record code if recording is enabled
        2. Send code to the wire if connected
        3. Decode the code and display it if from the key (no need to display code from the keyboard)

        This is used indirectly from the key or the keyboard threads to emit code once they
        determine it should be emitted.
        """
        kob_ = self._kob
        if kob_:
            kob_.internet_circuit_closed = not self._internet_station_active
        self._handle_sender_update(self._our_office_id)
        if self._recorder and not code_source == kob.CodeSource.player:
            self._recorder.record(code, code_source, char)
        if not code_source == kob.CodeSource.key:
            kob_.soundCode(code, code_source)
        if self._reader and not code_source == kob.CodeSource.keyboard:
            self._reader.decode(code)
        if self._connected and self._cfg.remote:
            self._internet.write(code)
        return

    def _from_file(self, code, char:Optional[str]=None):
        """
        Handle inputs received from reading a file.
        Only send if the circuit is open.

        Called from the 'File Sender' thread.
        """
        if len(code) > 0:
            if code[-1] == 1:  # special code for closer/circuit closed
                self._set_virtual_closer_closed(True)
                return
            elif code[-1] == 2:  # special code for closer/circuit open
                self._set_virtual_closer_closed(False)
                return
        if not self._internet_station_active and self._local_loop_active:
            self._emit_local_code(code, kob.CodeSource.player, char) # Say that it's from the player
        return

    def _from_key(self, code):
        """
        Handle inputs received from the external key.
        Only send if the circuit is open.

        Called from the 'KOB-KeyRead' thread.
        """
        if len(code) > 0:
            if code[-1] == 1: # special code for closer/circuit closed
                self._set_virtual_closer_closed(True)
                return
            elif code[-1] == 2: # special code for closer/circuit open
                self._set_virtual_closer_closed(False)
                return
        if not self._internet_station_active and self._local_loop_active:
            self._emit_local_code(code, kob.CodeSource.key)
        return

    def _from_keyboard(self, code, char:Optional[str]=None):
        """
        Handle inputs received from the keyboard sender.
        Only send if the circuit is open.

        Called from the 'Keyboard-Send' thread.
        """
        if len(code) > 0:
            if code[-1] == 1: # special code for closer/circuit closed
                self._set_virtual_closer_closed(True)
                return
            elif code[-1] == 2: # special code for closer/circuit open
                self._set_virtual_closer_closed(False)
                print('[+ to close key (Ctrl-Z=Help)]', flush=True)
                sys.stdout.flush()
                return
        if not self._internet_station_active and self._local_loop_active:
            self._emit_local_code(code, kob.CodeSource.keyboard, char)
        return

    def _from_internet(self, code):
        """handle inputs received from the internet"""
        if self._connected:
            if not self._sender_current == self._our_office_id:
                if self._reader:
                    self._reader.decode(code)
                self._kob.soundCode(code, kob.CodeSource.wire)
            if self._recorder:
                self._recorder.record(code, kob.CodeSource.wire)
            if len(code) > 0 and code[-1] == +1:
                self._internet_station_active = False
            else:
                self._internet_station_active = True
            self._kob.internet_circuit_closed = not self._internet_station_active
        return

    def _from_player(self, code, char:Optional[str]=None):
        """
        Handle inputs received from the recording player.
        Only send if the circuit is open.

        Called from the player.
        """
        if not self._internet_station_active and self._local_loop_active:
            self._emit_local_code(tuple(code), kob.CodeSource.player, char)
        return

    def _from_player_finished(self):
        if self._reader:
            # If we have a Reader, assume we printed some text, so print a NL
            print("", flush=True)
        log.debug("Recording playback finished.")
        self._playback_complete.set()
        return

    def _handle_sender_update(self, sender):
        """
        Handle a <<Current_Sender>> message by:
        1. Displaying the sender if new
        """
        if not self._sender_current == sender:
            self._sender_current = sender
            ts = ""
            if self._sender_dt:
                ts = time.strftime("%Y-%m-%d %I:%M:%S %p ")
            print()
            print(f"{ts}<<{self._sender_current}>>", flush=True)
        return

    def _print_start_info(self):
        cfgname = "Global" if not self._cfg.get_filepath() else self._cfg.get_filepath()
        print("Using configuration: {}".format(cfgname))
        if self._wire == 0:
            print("Not connecting to a wire.")
        else:
            print("Connecting to wire: " + str(self._wire))
        print("Connecting as Station/Office: " + self._our_office_id)
        # Let the user know if 'invert key input' is enabled (typically only used for MODEM input)
        if self._cfg.invert_key_input:
            print("IMPORTANT! Key input signal invert is enabled (typically only used with a MODEM). " + \
                "To enable/disable this setting use `Configure --iki`.")
        if self._play_file_path:
            print("Play recording: {}".format(self._play_file_path))
        if self._send_file_path:
            print("Process text from file: {}".format(self._send_file_path))
        print("[Use CTRL+Z for keyboard help.]", flush=True)
        return

    def _process_automation(self):
        """
        Start and monitor playing a recording and/or sending a file.
        """
        if not self._do_automated_stuff:
            return
        if self._play_file_path and self._player and not self._playback_complete.is_set():
            # We have a recording to play. See if we are playing it.
            if self._player.playback_state == recorder.PlaybackState.idle:
                # Not playing it, are we sending a file?
                if self._send_file_path and self._filesend_running.is_set():
                    # Yes.
                    return
                # Start it playing
                log.debug("Mrt._process_automation - Play recording...", 2)
                self._sender_current = ""
                self._set_virtual_closer_closed(False)
                self._playback_complete.clear()
                self._player.playback_start(max_silence=8)
                return
            else:
                # We are currently playing.
                return
        if self._send_file_path and self._thread_fsender and not self._filesend_running.is_set():
            # We have a file to send.
            # Start it sending
            log.debug("Mrt._process_automation - Key a file...", 2)
            self._handle_sender_update(self._our_office_id)
            self._thread_fsender.start()
            self._shutdown.wait(0.010)
            self._filesend_running.set()
            return
        #
        # See if things are running...
        if not self._playback_complete.is_set() or (self._thread_fsender and self._thread_fsender.is_alive()):
            return
        #
        # Done with one pass of a recording or a file. See if we should loop.
        #
        if self._repeat_delay < 0:
            # No repeat. We are done.
            self._do_automated_stuff = False
            log.debug("Mrt._process_automation - No repeat, finished processing.", 2)
            return
        if self._repeat_delay > 0:
            print("Automation - Delaying {} seconds before repeat...".format(self._repeat_delay), flush=True)
            self._shutdown.wait(self._repeat_delay)
        if self._play_file_path:
            self._playback_complete.clear()
        if self._send_file_path:
            self._filesend_running.clear()
            self.__create_file_thread()
        return

    def _reader_callback(self, char, spacing):
        rec = self._recorder
        player = self._player
        if rec:
            if not player or (player and player.playback_state == recorder.PlaybackState.idle):
                rec.record([], "", text=char)
        if not char == '=':
            if self._last_received_para:
                print(flush=True)
            self._last_received_para = False
        else:
            self._last_received_para = True
        halfSpaces = min(max(int(2 * spacing + 0.5), 0), 10)
        fullSpace = False
        if halfSpaces > 0:
            halfSpaces -=1
        if halfSpaces >= 2:
            fullSpace = True
            halfSpaces = (halfSpaces - 1) // 2
        for i in range(halfSpaces):
            print(' ', end='')
        if fullSpace:
            print(' ', end='')
        print(char, end='', flush=True)
        if char == '_':
            print(flush=True)
        return

    def _set_local_loop_active(self, active):
        """
        Set local_loop_active state

        True: Key or Keyboard active (Ciruit Closer OPEN)
        False: Circuit Closer (physical and virtual) CLOSED
        """
        self._local_loop_active = active
        self._kob.energize_sounder((not active), kob.CodeSource.local)
        return

    def _set_virtual_closer_closed(self, closed):
        """
        Handle change of Circuit Closer state.

        A state of:
        True: 'latch'
        False: 'unlatch'
        """
        self._kob.virtual_closer_is_open = not closed
        code = LATCH_CODE if closed else UNLATCH_CODE
        if not self._internet_station_active:
            if self._cfg.local:
                if not closed:
                    self._handle_sender_update(self._our_office_id)
                if self._reader:
                    self._reader.decode(code)
            if self._recorder:
                self._recorder.record(code, kob.CodeSource.local)
        if self._connected and self._cfg.remote:
            self._internet.write(code)
        if len(code) > 0:
            if code[-1] == 1:
                # Unlatch (Key closed)
                self._set_local_loop_active(False)
                if self._reader:
                    self._reader.flush()
            elif code[-1] == 2:
                # Latch (Key open)
                self._set_local_loop_active(True)
        return

    def _thread_fsender_body(self):
        while not self._fst_stop.is_set() and not self._shutdown.is_set():
            try:
                self._set_virtual_closer_closed(False)
                while not self._fst_stop.is_set() and not self._shutdown.is_set():
                    with open(self._send_file_path, "r") as fp:
                        while not self._fst_stop.is_set() and not self._shutdown.is_set():
                            ch = fp.read(1)
                            if not ch:
                                break
                            if ch < ' ':
                                # don't send control characters
                                continue
                            code = self._sender.encode(ch)
                            self._from_file(code, ch)
                    self._fst_stop.set()
            except Exception as ex:
                print(
                    "<<< File sender encountered an error and will stop sending. Exception: {}"
                ).format(ex)
                self._fst_stop.set()
            finally:
                self._set_virtual_closer_closed(True)
        log.debug("MRT-File Sender thread done.")
        return

    def _thread_kbreader_body(self):
        rawterm = RawTerm(self._shutdown)
        try:
            while not self._kbt_stop.is_set() and not self._shutdown.is_set():
                try:
                    ch = rawterm.getch()
                    if ch == '\x03': # They pressed ^C
                        self._shutdown.set()
                        self._control_c_pressed.set()
                        return # We are done
                    if ch == '\x1a': # CTRL-Z, help...
                        print("\n['~' to open the key]\n['+' to close the key]\n[^C to exit]", flush=True)
                        continue
                    if not self._local_loop_active and not ch == '~':
                        # The local loop needs to be active
                        print('\x07[~ to open key (Ctrl-Z=Help)]', flush=True) # Ring the bell to let them know we are full
                        continue
                    if ch >= ' ' or ch == '\x0A' or ch == '\x0D':
                        # See if there is room in the keyboard queue
                        if self._kb_queue.not_full:
                            # Since this is from the keyboard, print it so it can be seen.
                            nl = '\r\n' if ch == '=' or ch == '\x0A' or ch == '\x0D' else ''
                            print(ch, end=nl, flush=True)
                            # Put it in our queue
                            self._kb_queue.put(ch)
                        else:
                            print('\x07', end='', flush=True) # Ring the bell to let them know we are full
                    self._shutdown.wait(0.008)
                except Exception as ex:
                    print("<<< Keyboard reader encountered an error and will stop reading. Error: {}".format(ex))
                    self._kbt_stop.set()
        finally:
            rawterm.exit()
            log.debug("MRT-KB Reader thread done.")
        return

    def _thread_kbsender_body(self):
        while not self._kbt_stop.is_set() and not self._shutdown.is_set():
            try:
                ch = self._kb_queue.get(block=False)
                code = self._sender.encode(ch)
                self._from_keyboard(code, ch)
            except Empty:
                # The queue was empty. Wait a bit, then try again.
                self._shutdown.wait(0.001)
            except Exception as ex:
                print("<<< Keyboard sender encountered an error and will stop running. Exception: {}".format(ex))
                self._kbt_stop.set()
        log.debug("MRT-KB Sender thread done.")
        return

class SelectorLoadError(Exception):
    pass

class SelectorLoadSpecError(SelectorLoadError):
    pass

class SelectorLoadFileNotFound(SelectorLoadError):
    pass

class SelectorMrtLoadError(SelectorLoadError):
    pass

class SelectorMrtArgumentsError(SelectorMrtLoadError):
    pass
class SelectorMrtFileNotFound(SelectorMrtLoadError):
    pass

class MrtSelector:
    """
    Uses a pykob.Selector to run Mrt in different ways (as specified in a Selector structure).
    """

    def add_ext_if_needed(s: str) -> str:
        """
        Add the MRT selector file extension if needed.

        Adds '.mrtsel' to the string argument if it doesn't already end with it.
        """
        if s and not s.endswith(MRT_SEL_EXT):
            return (s + MRT_SEL_EXT)
        return s


    def __init__(self, selector_port, selector_file_path, cfg:Optional[Config]=None) -> None:
        self._selector_file_path = MrtSelector.add_ext_if_needed(selector_file_path)
        self._selector_port: str = selector_port
        self._cfg: Optional[Config] = cfg

        self._selector_type: Optional[SelectorType] = None
        self._selector_specs: Optional[list[Optional[dict[str,Optional[list[str]]]]]] = None
        self._selector: Optional[Selector] = None
        self._accept_select: Event = Event()
        self._selection_changed: Event = Event()
        self._run_complete: Event = Event()

        self._mrt: Optional[Mrt] = None
        self._new_mrt: Optional[Mrt] = None
        self._spec_args: Optional[list[str]] = None
        self._spec_desc: Optional[str] = None

        self._load_selector(self._selector_file_path)
        return

    def _load_mrt_for_spec(self, spec:dict[str,Optional[list[str]]]) -> Optional[Mrt]:
        """
        Create an Mrt based on the specification.

        Can raise:
            * SelectorMrtLoadError: General Mrt creation error.
            * SelectorMrtFileNotFound: A file needed to create the Mrt wasn't found.
        """
        spec_args = spec[SELECTION_ARGS_KEY]
        spec_desc = spec[SELECTION_DESCRIPTION_KEY]
        log.debug("MrtSelector._load_mrt_for_spec: '{}'  MRT {}".format(spec_desc, spec_args))
        mrt = None
        try:
            mrt, sel_spec = mrt_from_args(spec_args, cfg=self._cfg, allow_selector=False)  # Don't allow a Selector to be specified in a selection spec.
        except FileNotFoundError as fnf:
            raise SelectorMrtFileNotFound("File not found: '{}', trying to load specification: '{}'".format(fnf, spec_desc))
        except Exception as ex:
            raise SelectorMrtLoadError(ex)
        except SystemExit as args_err:
            raise SelectorMrtArgumentsError(args_err)
        finally:
            if not mrt is None:
                self._spec_desc = spec_desc
                self._spec_args = spec_args
        return mrt

    def _load_selector(self, filepath:str) -> bool:
        """
        Load a MRT selector file (json).
        Create a pykob selector for the port.

        filepath: File path to use for a Selector Spec.

        Selector Spec is:
        0. Selector Type
        1. Mrt specs
            a. Description
            b. Spec

        Raises: FileNotFoundError if the selector file isn't found.
                SelectorLoadError if the selector file isn't valid.
                System may throw other file related exceptions.
        """
        try:
            selector_spec = None
            with open(filepath, 'r', encoding="utf-8") as fp:
                selector_spec = json.load(fp)
            if selector_spec:
                    selector_type_name = selector_spec[SELECTOR_TYPE_KEY]
                    self._selector_type = SelectorType(selector_type_name)
                    selections: list[Optional[dict[str,list[Optional[str]]]]] = selector_spec[SELECTOR_SELECTIONS_KEY]
                    # Make sure the list has the correct number of elements
                    ne = self._selector_type.elements
                    for n in range(len(selections), ne):
                        selection_no = n - self._selector_type.index_adj
                        log.log("Adding a generated selector entry for selection {}.\n".format(selection_no), dt="")
                        entry = {SELECTION_DESCRIPTION_KEY : "Selection {}".format(selection_no), SELECTION_ARGS_KEY : []}
                        selections.append(entry)
                    self._selector_specs = selections
                    log.debug("MrtSelector.load_selector - Port: {}".format(self._selector_port))
                    log.debug("MrtSelector.load_selector - Type: {}".format(selector_type_name))
                    log.debug("MrtSelector.load_selector - Mrt Specs: {}".format(selections))
                    #
                    # Create the selector
                    self._selector = Selector(self._selector_port, self._selector_type.mode, on_change=self._on_selection_changed)
                    #
                    # Try to load an Mrt for each spec
                    for n in range(0, len(self._selector_specs)):
                        selection_no = n - self._selector_type.index_adj
                        spec = self._selector_specs[n]
                        log.log("Checking selector spec for selection {}\n".format(selection_no), dt="")
                        test_mrt = self._load_mrt_for_spec(spec)
                        log.debug("MrtSelector._load_selector - Test Mrt created for spec [{}] with args {}".format(spec[SELECTION_DESCRIPTION_KEY], spec[SELECTION_ARGS_KEY]), 4)
                    self._selector.start()
                    return True
        except SelectorMrtLoadError as smle:
            # Just raise it, as it is already set with a message.
            raise smle
        except FileNotFoundError as fnf:
            log.debug("Selector file not found: {}".format(filepath))
            raise SelectorLoadFileNotFound(fnf)
        except JSONDecodeError as jde:
            log.debug("Selector spec error: {}".format(jde))
            raise SelectorLoadSpecError(jde)
        except Exception as ex:
            log.debug(ex)
            raise SelectorLoadError("Load selector error: {}".format(ex))
        return False

    def _on_selection_changed(self, change:SelectorChange, value):
        """
        The Selector changed. Get the selection number and start an Mrt with the configuration.
        """
        if self._accept_select.is_set() and self._selector_type.change == change:
            selected = value
            index = selected + self._selector_type.index_adj
            spec = self._selector_specs[index]
            if spec is None:
                # There wasn't a specification for this selection. ZZZ: Raise an exception?
                return
            new_mrt = self._load_mrt_for_spec(spec)
            if new_mrt is None:
                # Should we raise an exception in this case?
                pass
            else:
                self._new_mrt = new_mrt
                if self._mrt:
                    self._mrt.exit()
                self._selection_changed.set()
        return

    def exit(self) -> None:
        self._new_mrt = None
        self._selection_changed.set()  # Wake up `run
        self._run_complete.wait()
        if self._mrt:
            self._mrt.exit()
        if self._selector:
            self._selector.exit()
        return

    def run(self) -> None:
        """
        Main loop of the Selector.

        Wait for a selection change.
        On selection change, switch to the new Mrt.
        """
        try:
            self._accept_select.set()
            while self._selection_changed.wait():
                self._selection_changed.clear()
                self._accept_select.clear()
                if self._mrt:
                    self._mrt.exit()
                    self._mrt = None
                if self._new_mrt:
                    log.log("\nSwitching to MRT selection {}: {}\n\n".format(self._selector.one_of_four, self._spec_desc), dt="")
                    self._mrt = self._new_mrt
                    self._new_mrt = None
                    self._mrt.start()
                    self._accept_select.set()
                    self._mrt.main_loop()
                    log.debug("MrtSelector.run - Mrt returned from main_loop.")
                else:
                    break
        finally:
            log.debug("MrtSelector.run - ending", 3)
            self._run_complete.set()
            self.exit()
            log.debug("MrtSelector.run - done")
        return

def mrt_from_args(options: Optional[Sequence[str]] = None, cfg: Optional[Config] = None, allow_selector:bool=True) -> tuple[Mrt, Optional[MrtSelector]]:
    arg_parser = argparse.ArgumentParser(description="Morse Receive & Transmit (Marty). "
        + "Receive from wire and send from key.\nThe Global configuration is used except as overridden by options.",
        parents= [
            config2.sound_override,
            config2.sounder_override,
            config2.gpio_override,
            config2.serial_port_override,
            config2.station_override,
            config2.min_char_speed_override,
            config2.text_speed_override,
            config2.config_file_override,
            config2.logging_level_override,
            pkappargs.record_session_override,
            pkappargs.sender_datetime_override
        ],
        exit_on_error=False
    )
    arg_parser.add_argument(
        "--file",
        metavar="text-file-path",
        dest="textfile_filepath",
        help="Key a text file when started. Code will be sent if connected to a wire.",
    )
    arg_parser.add_argument(
        "--play",
        metavar="recording-path",
        dest="play_filepath",
        help="Play a recording when started. Code will be sent if connected to a wire.",
    )
    arg_parser.add_argument(
        "--repeat",
        metavar="delay",
        dest="repeat_delay",
        default=-1,
        type=int,
        help="Used in conjunction with '--play' or '--file', " +
            "this will cause the playback or file processing to be repeated. " +
            "The value is the delay, in seconds, to pause before repeating."
    )
    if allow_selector:
        arg_parser.add_argument(
            "--selector",
            nargs=2,
            metavar="port specfile",
            dest="selector_args",
            help="Use a PyKOB Selector to run MRT with different options based on " +
                "the MRT Selector Specification file 'specfile' and the current selector " +
                "setting of a selector connected to port 'port'."
        )
    arg_parser.add_argument("wire", nargs='?', type=int,
        help="Wire to connect to. If specified, this is used rather than the configured wire. " +
            "Use 0 to not connect.")

    args = arg_parser.parse_args(options)

    cfg = config2.process_config_args(args, cfg)
    log.set_logging_level(cfg.logging_level)

    wire = args.wire if args.wire else cfg.wire
    record_filepath = pkappargs.record_filepath_from_args(args)
    play_filepath = None if not (hasattr(args, "play_filepath") and args.play_filepath) else args.play_filepath
    sendtext_filepath = None if not (hasattr(args, "textfile_filepath") and args.textfile_filepath) else args.textfile_filepath
    repeat_delay = args.repeat_delay
    selector_specpath = None
    selector_port = None
    if hasattr(args, "selector_args"):
        if args.selector_args:
            selector_port = args.selector_args[0]
            selector_specpath = args.selector_args[1]
        pass
    sender_dt = args.sender_dt
    #
    # Check to see that recordings/files aren't specified if there is a selector
    if selector_specpath and (play_filepath or sendtext_filepath):
        raise Exception("Cannot specify a recording or a file to process when using a Selector. ")

    #
    # If we have a selector spec path, create a selector to return
    selector = None if not selector_specpath else MrtSelector(selector_port, selector_specpath, cfg)

    mrt = None if not selector is None else Mrt(
        MRT_VERSION_TEXT,
            wire,
            cfg,
            sender_dt,
            record_filepath=record_filepath,
            repeat_delay=repeat_delay,
            file_to_play=play_filepath,
            file_to_send=sendtext_filepath,
        )
    return (mrt, selector)

"""
Main code
"""
if __name__ == "__main__":
    mrt = None
    mrt_selector = None
    exit_status = 1
    try:
        # Main code
        print(MRT_VERSION_TEXT)
        print("Python: " + sys.version + " on " + sys.platform)
        print("pykob: " + VERSION)
        print("PySerial: " + config.pyserial_version, flush=True)


        mrt, mrt_selector = mrt_from_args(allow_selector=True)

        if mrt_selector:
            log.log("Running with a selector.\n", dt="")
            mrt_selector.run()
            mrt_selector = None
        elif mrt:
            mrt.start()
            mrt.main_loop()
            mrt = None
            exit_status = 0
        else:
            raise Exception("Could not initialize MRT or Selector.")
    except KeyboardInterrupt:
        exit_status = 0
    except FileNotFoundError as fnf:
        print("File not found: {}".format(fnf.args[0]))
    except SelectorLoadError as sle:
        print("Error loading selector - {}".format(sle))
    except Exception as ex:
        print("Error encountered: {}".format(ex))
    except SystemExit as arg_err:
        print(arg_err)
    finally:
        if mrt:
            mrt.exit()
        if mrt_selector:
            mrt_selector.exit()
        print()
        print("~73", flush=True)
        sleep(0.5)
        sys.exit(exit_status)
