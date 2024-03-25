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
from pykob.recorder import Recorder
import pkappargs

import argparse
from pathlib import Path
import platform
import queue
from queue import Empty, Queue
import re  # RegEx
import sys
from threading import Event, Thread
from time import sleep
from typing import Any, Callable, Optional

__version__ = '1.3.1'
MRT_VERSION_TEXT = "MRT " + __version__

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
    def __init__(self):
        self.impl = None
        operating_system = platform.system()
        if operating_system == "Windows":
            try:
                self.impl = _GetchWindows()
            except Exception as ex:
                log.error("Unable to get direct keyboard access (Win:{})".format(ex))
        elif operating_system == "Darwin": # MacOSX
            try:
                self.impl = _GetchUnix()
            except Exception as ex:
                log.error("unable to get direct keyboard access (Mac:{})".format(ex))
        elif operating_system == "Linux":
            try:
                self.impl = _GetchUnix()
            except Exception as ex:
                log.error("unable to get direct keyboard access (Linux:{})".format(ex))
        return

    def getch(self) -> str:
        return self.impl._getch()

    def exit(self) -> None:
        self.impl._exit()
        return

class _GetchUnix:
    """
    Get a single character from the standard input on *nix

    Used by `RawTerm`
    """
    def __init__(self):
        import tty, sys, termios
        self.fd = sys.stdin.fileno()
        self.original_settings = termios.tcgetattr(self.fd)
        try:
            tty.setraw(sys.stdin.fileno())
            attrs = termios.tcgetattr(self.fd)
            attrs[1] |= termios.OPOST
            termios.tcsetattr(self.fd, termios.TCSANOW, attrs)
        except Exception as ex:
            log.warn("GetchUnix - Error setting terminal attributes: {}".format(ex))
            # try to put the original back
            termios.tcsetattr(self.fd, termios.TCSANOW, self.original_settings)
        return

    def _getch(self) -> str:
        ch = sys.stdin.read(1)
        return ch

    def _exit(self):
        import termios
        termios.tcsetattr(self.fd, termios.TCSADRAIN, self.original_settings)
        return

class _GetchWindows:
    """
    Get a single character from the standard input on Windows

    Used by `RawTerm`
    """
    def __init__(self):
        import msvcrt
        pass
        return

    def _getch(self) -> str:
        import msvcrt
        return msvcrt.getch().decode("utf-8")

    def _exit(self):
        return

class Mrt:

    def __init__(
        self,
        app_name_version: str, wire: int,
        cfg: Config,
        record_filepath: Optional[str] = None,
        file_to_send: Optional[str] = None,
    ) -> None:
        self._app_name_version = app_name_version
        self._wire = wire
        self._cfg = cfg
        self._shutdown = Event()
        self._control_c_pressed = Event()
        self._kb_queue = Queue(128)

        self._send_file_path = None
        self._send_repeat_count = -1  # -1 is flag to indicate that a repeat hasn't been set
        if file_to_send:
            self._send_file_path = file_to_send.strip()
            p = Path(self._send_file_path)
            p.resolve()
            if not p.is_file():
                print("File to send not found. '{}'".format(self._send_file_path))
                self._send_file_path = None

        self._internet = None
        self._kob = None
        self._reader = None
        self._recorder = None
        self._sender = None

        self._connected = False
        self._internet_station_active = False  # True if a remote station is sending
        self._last_received_para = False # The last character received was a Paragraph ('=')
        self._local_loop_active = False  # True if sending on key or keyboard
        self._our_office_id = cfg.station if not cfg.station is None else ""
        self._sender_current = ""

        self._exit_status = 1

        if record_filepath:
            log.info("Recording to '{}'".format(record_filepath))
            self._recorder = Recorder(
                record_filepath,
                None,
                station_id=self._our_office_id,
                wire=self._wire,
                play_code_callback=None,
                play_sender_id_callback=None,
                play_station_list_callback=None,
                play_wire_callback=None,
            )

        self._kob = kob.KOB(
            interfaceType=cfg.interface_type,
            portToUse=cfg.serial_port,
            useGpio=cfg.gpio,
            useAudio=cfg.sound,
            audioType=cfg.audio_type,
            useSounder=cfg.sounder,
            invertKeyInput=cfg.invert_key_input,
            soundLocal=cfg.local,
            sounderPowerSaveSecs=cfg.sounder_power_save,
            virtual_closer_in_use=True,
            keyCallback=self._from_key
            )
        self._internet = internet.Internet(
            officeID=self._our_office_id,
            code_callback=self._from_internet,
            appver=self._app_name_version,
            server_url=cfg.server_url,
            err_msg_hndlr=log.warn
        )
        self._internet.monitor_sender(self._handle_sender_update) # Set callback for monitoring current sender
        self._reader = morse.Reader(
            wpm=cfg.text_speed,
            cwpm=cfg.min_char_speed,
            codeType=cfg.code_type,
            callback=self._reader_callback
            )
        self._sender = morse.Sender(
            wpm=cfg.text_speed,
            cwpm=cfg.min_char_speed,
            codeType=cfg.code_type,
            spacing=cfg.spacing
            )

        # Thread to read characters from the keyboard to allow sending without (instead of) a physical key.
        self._thread_kbreader = Thread(name="Keyboard-read-thread", daemon=False, target=self._thread_kbreader_body)
        self._thread_kbsender = Thread(name="Keyboard-send-thread", daemon=False, target=self._thread_kbsender_body)
        self._thread_fsender = None
        if self._send_file_path:
            self._thread_fsender = Thread(name="File-send-thread", daemon=False, target=self._thread_fsender_body)
        return

    def exit(self):
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
        rdr = self._reader
        if rdr:
            log.debug("MRT.exit - 5a", 3)
            rdr.exit()
            log.debug("MRT.exit - 5b", 3)
        rec = self._recorder
        if rec:
            log.debug("MRT.exit - 6a", 3)
            rec.exit()
            log.debug("MRT.exit - 6b", 3)
        sndr = self._sender
        if sndr:
            log.debug("MRT.exit - 7a", 3)
            sndr.exit()
            log.debug("MRT.exit - 7b", 3)
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
            if self._thread_fsender:
                self._thread_fsender.start()
            while not self._shutdown.is_set() and not self._control_c_pressed.is_set():
                self._shutdown.wait(0.02)  # Loop while background threads take care of 'stuff'
                if self._control_c_pressed.is_set():
                    raise KeyboardInterrupt
        except KeyboardInterrupt:
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
        rdr = self._reader
        if rdr:
            log.debug("MRT.shutdown - 5a", 3)
            rdr.shutdown()
            log.debug("MRT.shutdown - 5b", 3)
        rec = self._recorder
        if rec:
            log.debug("MRT.shutdown - 6a", 3)
            rec.shutdown()
            log.debug("MRT.shutdown - 6b", 3)
        sndr = self._sender
        if sndr:
            log.debug("MRT.shutdown - 7a", 3)
            sndr.shutdown()
            log.debug("MRT.shutdown - 7b", 3)
        return

    def start(self):
        self._thread_kbreader.start()
        self._thread_kbsender.start()
        return

    def _handle_sender_update(self, sender):
        """
        Handle a <<Current_Sender>> message by:
        1. Displaying the sender if new
        """
        if not self._sender_current == sender:
            self._sender_current = sender
            print()
            print(f'<<{self._sender_current}>>')
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
        if self._send_file_path:
            print("Sending text from file: {}".format(self._send_file_path))
        print("[Use CTRL+Z for keyboard help.]", flush=True)
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
                self._reader.decode(code)
            if self._recorder:
                self._recorder.record(code, kob.CodeSource.local)
        if self._connected and self._cfg.remote:
            self._internet.write(code)
        if len(code) > 0:
            if code[-1] == 1:
                # Unlatch (Key closed)
                self._set_local_loop_active(False)
                self._reader.flush()
            elif code[-1] == 2:
                # Latch (Key open)
                self._set_local_loop_active(True)
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
        self._handle_sender_update(self._our_office_id)
        if self._recorder:
            self._recorder.record(code, code_source, char)
        if self._connected and self._cfg.remote:
            self._internet.write(code)
        if code_source == kob.CodeSource.keyboard:
            self._kob.soundCode(code, code_source)
        if code_source == kob.CodeSource.key:
            self._reader.decode(code)
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
            self._emit_local_code(code, kob.CodeSource.keyboard, char) # Say that it' from the keyboard
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
            self._reader.decode(code)
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
                print('[+ to close key (Ctrl-Z=Help)]')
                sys.stdout.flush()
                return
        if not self._internet_station_active and self._local_loop_active:
            self._emit_local_code(code, kob.CodeSource.keyboard, char)
        return

    def _from_internet(self, code):
        """handle inputs received from the internet"""
        if self._connected:
            if not self._sender_current == self._our_office_id:
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

    def _reader_callback(self, char, spacing):
        rec = self._recorder
        if rec:
            rec.record([], "", text=char)
        if not char == '=':
            if self._last_received_para:
                print()
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
            print()
        return

    def _thread_fsender_body(self):
        done_sending = False
        while not done_sending and not self._shutdown.is_set():
            try:
                self._set_virtual_closer_closed(False)
                while (
                    not self._send_repeat_count == 0
                    and not self._shutdown.is_set()
                    ):
                    with open(self._send_file_path, "r") as fp:
                        while not self._shutdown.is_set():
                            ch = fp.read(1)
                            if not ch:
                                # at the end, adjust repeat count
                                self._send_repeat_count = 0
                                break
                            elif ch == '`':
                                if not self._send_repeat_count == -1:
                                    # We already set a repeat count, so repeat now.
                                    if not self._send_repeat_count == -2:
                                        self._send_repeat_count -= 1
                                    break
                                # Collect the repeat count
                                l = fp.readline()
                                if l == "" or l[0] == '*':
                                    self._send_repeat_count = -2  # Repeat indefinately
                                else:
                                    # Try to collect a number
                                    rc = 1
                                    p = re.compile("[0-9]+")
                                    m = p.match(l)
                                    n = m.group()
                                    if n:
                                        rc = int(n)
                                    if rc > 0:
                                        self._send_repeat_count = rc
                                    else:
                                        self._send_repeat_count = 1
                                break
                            if ch < ' ':
                                # don't send control characters
                                continue
                            code = self._sender.encode(ch)
                            self._from_file(code, ch)
                done_sending = True
            except Exception as ex:
                print(
                    "<<< File sender encountered an error and will stop running. Exception: {}"
                ).format(ex)
                self._shutdown.set()
            finally:
                self._set_virtual_closer_closed(True)
        log.debug("MRT-File Sender thread done.")
        return

    def _thread_kbreader_body(self):
        rawterm = RawTerm()
        try:
            while not self._shutdown.is_set():
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
                    print("<<< Keyboard reader encountered an error and will stop reading. Exception: {}").format(ex)
                    self._shutdown.set()
        finally:
            rawterm.exit()
            log.debug("MRT-KB Reader thread done.")
        return

    def _thread_kbsender_body(self):
        while not self._shutdown.is_set():
            try:
                ch = self._kb_queue.get(block=False)
                code = self._sender.encode(ch)
                self._from_keyboard(code, ch)
            except Empty:
                # The queue was empty. Wait a bit, then try again.
                self._shutdown.wait(0.001)
            except Exception as ex:
                print("<<< Keyboard sender encountered an error and will stop running. Exception: {}").format(ex)
                self._shutdown.set()
        log.debug("MRT-KB Sender thread done.")
        return

"""
Main code
"""
if __name__ == "__main__":
    mrt = None
    exit_status = 1
    try:
        # Main code
        arg_parser = argparse.ArgumentParser(description="Morse Receive & Transmit (Marty). "
            + "Receive from wire and send from key.\nThe Global configuration is used except as overridden by options.",
            parents= [
                config2.station_override,
                config2.min_char_speed_override,
                config2.text_speed_override,
                config2.config_file_override,
                config2.logging_level_override,
                pkappargs.record_session_override
            ]
        )
        arg_parser.add_argument(
            "--send",
            metavar="text-file",
            dest="sendtext_filepath",
            help="Text file to send when started. If the text ends with a back-tick and a number '`2', "
            + "it will be repeated that many times. Ending with '`*' will repeat indefinately.",
        )
        arg_parser.add_argument("wire", nargs='?', type=int,
            help="Wire to connect to. If specified, this is used rather than the configured wire. "
            + "Use 0 to not connect.")
        args = arg_parser.parse_args()
        cfg = config2.process_config_args(args)
        wire = args.wire if args.wire else cfg.wire
        record_filepath = pkappargs.record_filepath_from_args(args)

        log.set_logging_level(cfg.logging_level)

        print(MRT_VERSION_TEXT)
        print("Python: " + sys.version + " on " + sys.platform)
        print("pykob: " + VERSION)
        print("PySerial: " + config.pyserial_version)

        mrt = Mrt(MRT_VERSION_TEXT, wire, cfg, record_filepath, args.sendtext_filepath)
        mrt.start()
        mrt.main_loop()
        mrt = None
        exit_status = 0
    except FileNotFoundError as fnf:
        print("File not found: {}".format(fnf.args[0]))
    except Exception as ex:
        print("Error encountered: {}".format(ex))
    finally:
        if mrt:
            mrt.exit()
        print()
        print("~73")
        sleep(0.5)
        sys.exit(exit_status)
