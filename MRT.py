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

from pykob import VERSION, config, config2, log, kob, internet, morse
from pykob.config2 import Config

import argparse
from pathlib import Path
import platform
import queue
import re
import sys
from threading import Event, Thread
from time import sleep
from typing import Any, Callable, Optional

__version__ = '1.2.0'

LATCH_CODE = (-0x7fff, +1)  # code sequence to force latching (close)
UNLATCH_CODE = (-0x7fff, +2)  # code sequence to unlatch (open)

class _Getch:
    """
    Gets a single character from standard input.  Does not echo to the screen.

    This uses native calls on Windows and *nix (Linux and MacOS), and relies on
    the Subclasses for each platform.
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

    def __call__(self): return self.impl()

class _GetchUnix:
    """
    Get a single character from the standard input on *nix

    Used by `_Getch`
    """
    def __init__(self):
        import tty, sys

    def __call__(self):
        import sys, tty, termios
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch

class _GetchWindows:
    """
    Get a single character from the standard input on Windows

    Used by `_Getch`
    """
    def __init__(self):
        import msvcrt

    def __call__(self):
        import msvcrt
        return msvcrt.getch().decode("utf-8")

class Mrt:

    def __init__(self, wire: int, cfg: Config, file_to_send: Optional[str]=None) -> None:
        self._wire = wire
        self._cfg = cfg
        self._kb_queue = None
        self._threadsStop = Event()
        self._control_c_pressed = Event()

        self._send_file_path = None
        self._send_repeat_count = -1  # -1 is flag to indicate that a repeat hasn't been set
        if file_to_send:
            self._send_file_path = file_to_send.strip()
            p = Path(self._send_file_path)
            p.resolve()
            if not p.is_file():
                print("File to send not found. '{}'".format(self._send_file_path))
                self._send_file_path = None
        self._kob = None
        self._sender = None
        self._reader = None
        self._recorder = None
        self._internet = None

        self._connected = False
        self._internet_station_active = False  # True if a remote station is sending
        self._last_received_para = False # The last character received was a Paragraph ('=')
        self._local_loop_active = False  # True if sending on key or keyboard
        self._our_office_id = cfg.station
        self._sender_current = ""

        self._exit_status = 1

        self._kob = kob.KOB(
            interfaceType=cfg.interface_type,
            portToUse=cfg.serial_port,
            useGpio=cfg.gpio,
            useAudio=cfg.sound,
            useSounder=cfg.sounder,
            invertKeyInput=cfg.invert_key_input,
            soundLocal=cfg.local,
            sounderPowerSaveSecs=cfg.sounder_power_save,
            keyCallback=self._from_key
            )
        self._internet = internet.Internet(
            officeID=self._our_office_id,
            code_callback=self._from_internet,
            server_url=cfg.server_url,
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
        self._kb_queue = queue.Queue(128)
        self._kbrthread = Thread(name="Keyboard-read-thread", daemon=True, target=self._thread_kbreader_run)
        self._kbsthread = Thread(name="Keyboard-send-thread", daemon=True, target=self._thread_kbsender_run)
        self._fsndthread = None
        if self._send_file_path:
            self._fsndthread = Thread(name="File-send-thread", daemon=True, target=self._thread_fsender_run)

    def exit(self):
        self._threadsStop.set()
        sleep(0.3)
        if self._internet:
            if self._connected:
                self._internet.disconnect()
                sleep(0.8)
            self._internet.exit()
        if self._reader:
            self._reader.exit()
        if self._kob:
            self._kob.exit()

    def main_loop(self):
        self._print_start_info()
        if not self._wire == 0:
            self._internet.connect(self._wire)
            self._connected = True
        sleep(0.5)
        try:
            if self._fsndthread:
                self._fsndthread.start()
            while not self._threadsStop.is_set() and not self._control_c_pressed.is_set():
                sleep(0.1)  # Loop while background threads take care of 'stuff'
                if self._control_c_pressed.is_set():
                    raise KeyboardInterrupt
        except KeyboardInterrupt:
            self.exit()

    def start(self):
        self._kbrthread.start()
        self._kbsthread.start()

    def _handle_sender_update(self, sender):
        """
        Handle a <<Current_Sender>> message by:
        1. Displaying the sender if new
        """
        if not self._sender_current == sender:
            self._sender_current = sender
            print()
            print(f'<<{self._sender_current}>>')

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

    def _set_local_loop_active(self, active):
        """
        Set local_loop_active state

        True: Key or Keyboard active (Ciruit Closer OPEN)
        False: Circuit Closer (physical and virtual) CLOSED
        """
        self._local_loop_active = active
        self._kob.energize_sounder((not active))

    def _set_virtual_closer_closed(self, closed):
        """
        Handle change of Circuit Closer state.

        A state of:
        True: 'latch'
        False: 'unlatch'
        """
        self._kob.virtualCloserIsOpen = not closed
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

    def _emit_local_code(self, code, code_source):
        """
        Emit local code. That involves:
        1. Record code if recording is enabled
        2. Send code to the wire if connected

        This is used indirectly from the key or the keyboard threads to emit code once they
        determine it should be emitted.
        """
        self._handle_sender_update(self._our_office_id)
        # Reader.decode(code)
        if self._recorder:
            self._recorder.record(code, code_source)
        if self._connected and self._cfg.remote:
            self._internet.write(code)
        if code_source == kob.CodeSource.keyboard:
            self._kob.soundCode(code, code_source)

    def _from_file(self, code):
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
            self._emit_local_code(code, kob.CodeSource.keyboard) # Say that it' from the keyboard

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

    def _from_keyboard(self, code):
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
            self._emit_local_code(code, kob.CodeSource.keyboard)

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

    def _reader_callback(self, char, spacing):
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

    def _thread_fsender_run(self):
        done_sending = False
        while not done_sending and not self._threadsStop.is_set():
            try:
                self._set_virtual_closer_closed(False)
                while (
                    not self._send_repeat_count == 0
                    and not self._threadsStop.is_set()
                    ):
                    with open(self._send_file_path, "r") as fp:
                        while not self._threadsStop.is_set():
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
                                if l == "":
                                    # Just repeat once
                                    self._send_repeat_count = 1
                                else:
                                    if l[0] == '*':
                                        self._send_repeat_count = -2  # Repeat indefinately
                                    else:
                                        # Try to collect a number
                                        p = re.compile("[0-9]+")
                                        m = p.match(l)
                                        n = m.group()
                                        if n:
                                            rc = int(n)
                                            if rc > 0:
                                                self._send_repeat_count = rc
                                break
                            if ch < ' ':
                                # don't send control characters
                                continue
                            code = self._sender.encode(ch)
                            self._from_file(code)
                done_sending = True
            except Exception as ex:
                print(
                    "<<< File sender encountered an error and will stop running. Exception: {}"
                ).format(ex)
                self._threadsStop.set()
            finally:
                self._set_virtual_closer_closed(True)

    def _thread_kbreader_run(self):
        kbrd_char = _Getch()
        while not self._threadsStop.is_set():
            try:
                ch = kbrd_char()
                if ch == '\x03': # They pressed ^C
                    self._threadsStop.set()
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
                sleep(0.01)
            except Exception as ex:
                print("<<< Keyboard reader encountered an error and will stop reading. Exception: {}").format(ex)
                self._threadsStop.set()

    def _thread_kbsender_run(self):
        while not self._threadsStop.is_set():
            try:
                ch = self._kb_queue.get()
                code = self._sender.encode(ch)
                self._from_keyboard(code)
            except Exception as ex:
                print("<<< Keyboard sender encountered an error and will stop running. Exception: {}").format(ex)
                self._threadsStop.set()

"""
Main code
"""
if __name__ == "__main__":
    mrt = None
    exit_status = 1
    try:
        # Main code
        arg_parser = argparse.ArgumentParser(description="Morse Receive & Transmit (Marty). Receive from wire and send from key.\nThe configuration is used except as overridden by optional arguments.",
            parents= [
                config2.station_override,
                config2.min_char_speed_override,
                config2.text_speed_override,
                config2.config_file_override,
                config2.debug_level_override
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
        log.set_debug_level(cfg.debug_level)

        print("Python " + sys.version + " on " + sys.platform)
        print("PyKOB " + VERSION)
        try:
            import serial
            print("PySerial " + serial.VERSION)
        except:
            print("PySerial is not installed or the version information is not available (check installation)")

        mrt = Mrt(wire, cfg, args.sendtext_filepath)
        mrt.start()
        mrt.main_loop()
        exit_status = 0
    except FileNotFoundError as fnf:
        print("File not found: {}".format(fnf.args[0]))
    except Exception as ex:
        print("Error encountered: {}".format(ex))
    finally:
        print()
        print("~73")
        if mrt:
            mrt.exit()
        sleep(0.5)
        sys.exit(exit_status)
