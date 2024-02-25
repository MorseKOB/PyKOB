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

from pykob import VERSION, config, log, kob, internet, morse

import argparse
import os
import platform
import queue
import sys
from threading import Event, Thread
from time import sleep

__version__ = '1.1.0'

LATCH_CODE = (-0x7fff, +1)  # code sequence to force latching (close)
UNLATCH_CODE = (-0x7fff, +2)  # code sequence to unlatch (open)

Control_C_Pressed = False
KB_Queue = None
ThreadsStop = Event()

KOB = None
Sender = None
Reader = None
Recorder = None
Internet = None

connected = False
internet_station_active = False  # True if a remote station is sending
last_received_para = False # The last character received was a Paragraph ('=')
local_loop_active = False  # True if sending on key or keyboard
our_office_id = ""
sender_current = ""

exit_status = 1

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


def handle_sender_update(sender):
    """
    Handle a <<Current_Sender>> message by:
    1. Displaying the sender if new
    """
    global sender_current
    if not sender_current == sender:
        sender_current = sender
        print()
        print(f'<<{sender_current}>>')

def set_local_loop_active(state):
    """
    Set local_loop_active state

    True: Key or Keyboard active (Ciruit Closer OPEN)
    False: Circuit Closer (physical and virtual) CLOSED
    """
    global local_loop_active
    local_loop_active = state
    # log.debug("local_loop_active:{}".format(state))

def circuit_closer_closed(state):
    """
    Handle change of Circuit Closer state.

    A state of:
     True: 'latch'
     False: 'unlatch'
    """
    global local_loop_active, internet_station_active
    code = LATCH_CODE if state == 1 else UNLATCH_CODE
    if not internet_station_active:
        if config.local:
            handle_sender_update(config.station)
            Reader.decode(code)
        if Recorder:
            Recorder.record(code, kob.CodeSource.local)
    if connected and config.remote:
        Internet.write(code)
    if len(code) > 0:
        if code[-1] == 1:
            # Unlatch
            set_local_loop_active(False)
            Reader.flush()
        elif code[-1] == 2:
            # Latch
            set_local_loop_active(True)

def emit_local_code(code, code_source):
    """
    Emit local code. That involves:
    1. Record code if recording is enabled
    2. Send code to the wire if connected

    This is used indirectly from the key or the keyboard threads to emit code once they
    determine it should be emitted.
    """
    global connected
    handle_sender_update(config.station)
    #Reader.decode(code)
    if Recorder:
        Recorder.record(code, code_source) # ZZZ ToDo: option to enable/disable recording
    if connected and config.remote:
        Internet.write(code)
    if code_source == kob.CodeSource.keyboard and config.local:
        KOB.soundCode(code, code_source)

def from_key(code):
    """
    Handle inputs received from the external key.
    Only send if the circuit is open.

    Called from the 'KOB-KeyRead' thread.
    """
    global internet_station_active, local_loop_active
    if len(code) > 0:
        if code[-1] == 1: # special code for closer/circuit closed
            circuit_closer_closed(True)
            return
        elif code[-1] == 2: # special code for closer/circuit open
            circuit_closer_closed(False)
            return
    if not internet_station_active and local_loop_active:
        emit_local_code(code, kob.CodeSource.key)

def from_keyboard(code):
    """
    Handle inputs received from the keyboard sender.
    Only send if the circuit is open.

    Called from the 'Keyboard-Send' thread.
    """
    global internet_station_active, local_loop_active
    if len(code) > 0:
        if code[-1] == 1: # special code for closer/circuit closed
            circuit_closer_closed(True)
            return
        elif code[-1] == 2: # special code for closer/circuit open
            circuit_closer_closed(False)
            print('[+ to close key]')
            sys.stdout.flush()
            return
    if not internet_station_active and local_loop_active:
        emit_local_code(code, kob.CodeSource.keyboard)

def from_internet(code):
    """handle inputs received from the internet"""
    global local_loop_active, internet_station_active, sender_current, our_office_id
    if connected:
        if not sender_current == our_office_id:
            Reader.decode(code)
            KOB.soundCode(code, kob.CodeSource.wire)
        if Recorder:
            Recorder.record(code, kob.CodeSource.wire)
        if len(code) > 0 and code[-1] == +1:
            internet_station_active = False
        else:
            internet_station_active = True


def reader_callback(char, spacing):
    global last_received_para
    if not char == '=':
        if last_received_para:
            print()
        last_received_para = False
    else:
        last_received_para = True
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

def thread_kbreader_run():
    global Control_C_Pressed, KB_Queue, local_loop_active, ThreadsStop
    kbrd_char = _Getch()
    while not ThreadsStop.is_set():
        try:
            ch = kbrd_char()
            if ch == '\x03': # They pressed ^C
                ThreadsStop.set()
                Control_C_Pressed = True
                return # We are done
            if ch == '\x00': # CTRL-SP on some terminals will send NULL, use it for help...
                print("\n['~' to open the key]\n['+' to close the key]\n[^C to exit]")
                sys.stdout.flush()
                continue
            if not local_loop_active and not ch == '~':
                # The local loop needs to be active
                print('\x07[~ to open key]') # Ring the bell to let them know we are full
                sys.stdout.flush()
                continue
            if ch >= ' ' or ch == '\x0A' or ch == '\x0D':
                # See if there is room in the keyboard queue
                if KB_Queue.not_full:
                    # Since this is from the keyboard, print it so it can be seen.
                    nl = '\r\n' if ch == '=' or ch == '\x0A' or ch == '\x0D' else ''
                    print(ch, end=nl)
                    sys.stdout.flush()
                    # Put it in our queue
                    KB_Queue.put(ch)
                else:
                    print('\x07', end='') # Ring the bell to let them know we are full
                    sys.stdout.flush()
            sleep(0.01)
        except Exception as ex:
            print("<<< Keyboard reader encountered an error and will stop reading. Exception: {}").format(ex)

def thread_kbsender_run():
    global KB_Queue
    while not ThreadsStop.is_set():
        try:
            ch = KB_Queue.get()
            code = Sender.encode(ch)
            from_keyboard(code)
        except Exception as ex:
            print("<<< Keyboard sender encountered an error and will stop running. Exception: {}").format(ex)

try:
    # Main code
    arg_parser = argparse.ArgumentParser(description="Morse Receive & Transmit (Marty). Receive from wire and send from key.\nThe current configuration is used except as overridden by optional arguments.", \
        parents=\
        [\
        config.station_override, \
        config.text_speed_override])
    arg_parser.add_argument('wire', nargs='?', default=config.wire, type=int,\
        help='Wire to connect to. If specified, this is used rather than the configured wire.')
    args = arg_parser.parse_args()

    our_office_id = args.station # the Station/Office ID string to attach with
    text_speed = args.text_speed  # text speed (words per minute)
    if (text_speed < 1) or (text_speed > 50):
        print("text speed specified must be between 1 and 50 [-t|--textspeed]")
        sys.exit(1)
    wire = args.wire # wire to connect to

    print('Python ' + sys.version + ' on ' + sys.platform)
    print('PyKOB ' + VERSION)
    try:
        import serial
        print('PySerial ' + serial.VERSION)
    except:
        print('PySerial is not installed or the version information is not available (check installation)')

    print('Connecting to wire: ' + str(wire))
    print('Connecting as Station/Office: ' + our_office_id)
    # Let the user know if 'invert key input' is enabled (typically only used for MODEM input)
    if config.invert_key_input:
        print("IMPORTANT! Key input signal invert is enabled (typically only used with a MODEM). " + \
            "To enable/disable this setting use `Configure --iki`.")
    print('[Use CTRL+SPACE for keyboard help.]')
    sys.stdout.flush()

    KOB = kob.KOB(
            portToUse=config.serial_port, useGpio=config.gpio, interfaceType=config.interface_type,
            useAudio=config.sound, keyCallback=from_key)
    Internet = internet.Internet(our_office_id, code_callback=from_internet)
    Internet.monitor_sender(handle_sender_update) # Set callback for monitoring current sender
    Reader = morse.Reader(wpm=text_speed, cwpm=int(config.min_char_speed), codeType=config.code_type, callback=reader_callback)
    Sender = morse.Sender(wpm=text_speed, cwpm=int(config.min_char_speed), codeType=config.code_type)

    # Thread to read characters from the keyboard to allow sending without (instead of) a physical key.
    KB_Queue = queue.Queue(128)
    kbrthread = Thread(name="Keyboard-read-thread", daemon=True, target=thread_kbreader_run)
    kbsthread = Thread(name="Keyboard-send-thread", daemon=True, target=thread_kbsender_run)
    kbrthread.start()
    kbsthread.start()

    Internet.connect(wire)
    connected = True
    sleep(0.5)
    while not ThreadsStop.is_set():
        sleep(0.1)  # Loop while background threads take care of 'stuff'
        if Control_C_Pressed:
            raise KeyboardInterrupt
    exit_status = 0
except KeyboardInterrupt:
    exit_status = 0 # Since the main program is an infinite loop, ^C is a normal way to exit.
finally:
    print()
    print()
    if Internet:
        if connected:
            Internet.disconnect()
            sleep(0.8)
        Internet.exit()
    if Reader:
        Reader.exit()
    if KOB:
        KOB.exit()
    sleep(0.5)
    sys.exit(exit_status)
