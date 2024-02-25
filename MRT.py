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
    1. KOB wire no.

Example:
    python MRT.py 11
"""

from pykob import VERSION, config, config2, log, kob, internet, morse
from pykob.config2 import Config

import argparse
import platform
import queue
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
    def __init__(self, cfg: Config) -> None:
        self._cfg = cfg
        self._kb_queue = None
        self._threadsStop = Event()
        self._control_c_pressed = Event()

        self._kob = None
        self._sender = None
        self._reader = None
        self._recorder = None
        self._internet = None

        self._connected = False
        self._internet_station_active = False  # True if a remote station is sending
        self._last_received_para = False # The last character received was a Paragraph ('=')
        self._local_loop_active = False  # True if sending on key or keyboard
        self._our_office_id = ""
        self._sender_current = ""

        self._exit_status = 1

        self._kob = kob.KOB(cfg=self._cfg, keyCallback=self._from_key)
        self._internet = internet.Internet(cfg.station, code_callback=self._from_internet)
        self._internet.monitor_sender(self._handle_sender_update) # Set callback for monitoring current sender
        self._reader = morse.Reader(wpm=cfg.text_speed, cwpm=cfg.min_char_speed, codeType=cfg.code_type,
                callback=self._reader_callback)
        self._sender = morse.Sender(wpm=cfg.text_speed, cwpm=cfg.min_char_speed, codeType=cfg.code_type)

        # Thread to read characters from the keyboard to allow sending without (instead of) a physical key.
        self._kb_queue = queue.Queue(128)
        self._kbrthread = Thread(name="Keyboard-read-thread", daemon=True, target=self._thread_kbreader_run)
        self._kbsthread = Thread(name="Keyboard-send-thread", daemon=True, target=self._thread_kbsender_run)


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
        self._internet.connect(self._cfg.wire)
        self._connected = True
        sleep(0.5)
        while not self._threadsStop.is_set() and not self._control_c_pressed.is_set():
            sleep(0.1)  # Loop while background threads take care of 'stuff'
            if self._control_c_pressed.is_set():
                raise KeyboardInterrupt

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
        print("Connecting to wire: " + str(self._cfg.wire))
        print("Connecting as Station/Office: " + self._cfg.station)
        # Let the user know if 'invert key input' is enabled (typically only used for MODEM input)
        if self._cfg.invert_key_input:
            print("IMPORTANT! Key input signal invert is enabled (typically only used with a MODEM). " + \
                "To enable/disable this setting use `Configure --iki`.")
        print('[Use CTRL+Z for keyboard help.]', flush=True)

    def _set_local_loop_active(self, active):
        """
        Set local_loop_active state

        True: Key or Keyboard active (Ciruit Closer OPEN)
        False: Circuit Closer (physical and virtual) CLOSED
        """
        self._local_loop_active = active
        self._kob.energizeSounder((not active))

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
                    self._handle_sender_update(self._cfg.station)
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
        self._handle_sender_update(self._cfg.station)
        #Reader.decode(code)
        if self._recorder:
            self._recorder.record(code, code_source) # ZZZ ToDo: option to enable/disable recording
        if self._connected and self._cfg.remote:
            self._internet.write(code)
        if code_source == kob.CodeSource.keyboard and self._cfg.local:
            self._kob.soundCode(code, code_source)

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
        arg_parser.add_argument("wire", nargs='?', type=int,
            help="Wire to connect to. If specified, this is used rather than the configured wire.")
        args = arg_parser.parse_args()
        cfg = config2.process_config_args(args)

        log.set_debug_level(cfg.debug_level)

        cfg.load_to_global()  # ZZZ Push our config values to the global store temporarily

        print("Python " + sys.version + " on " + sys.platform)
        print("PyKOB " + VERSION)
        try:
            import serial
            print("PySerial " + serial.VERSION)
        except:
            print("PySerial is not installed or the version information is not available (check installation)")


        mrt = Mrt(cfg)
        mrt.start()
        mrt.main_loop()
    except FileNotFoundError as fnf:
        print(fnf.args[0])
    except KeyboardInterrupt:
        exit_status = 0 # Since the main program is an infinite loop, ^C is a normal way to exit.
    finally:
        print()
        print()
        if mrt:
            mrt.exit()
        sleep(0.5)
        sys.exit(exit_status)
