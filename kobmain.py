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
kobmain.py

Handle the flow of Morse code throughout the program.
"""

import time
from datetime import datetime

from pykob import kob, morse, internet, config, recorder, log
import kobconfig as kc
import kobactions as ka
import kobstationlist
import kobkeyboard

NNBSP = "\u202f"  # narrow no-break space

KOB = None
Sender = None
Reader = None
Recorder = None
Internet = None
connected = False

local_loop_active = False  # True if sending on key or keyboard
internet_active = False  # True if a remote station is sending

latch_code = (-0x7fff, +1)  # code sequence to force latching
unlatch_code = (-0x7fff, +2)  # code sequence to unlatch

sender_ID = ""

def set_local_loop_active(state):
    """set local_loop_active state and update Circuit Closer checkbox"""
    global local_loop_active
    local_loop_active = state
    ka.kw.varCircuitCloser.set(1 if not local_loop_active else 0)

def from_key(code):
    """handle inputs received from the external key"""
    global internet_active
    if not internet_active:
        if kc.config.interface_type == config.interface_type.loop:
            KOB.setSounder(True)
        update_sender(kc.config.station)
        Reader.decode(code)
        if Recorder:
            Recorder.record(code, kob.CodeSource.local)
    if connected and kc.Remote:
        Internet.write(code)
    if len(code) > 0 and code[-1] == +1:
        set_local_loop_active(False)
        Reader.flush()  # ZZZ is this necessary/desirable?
    else:
        set_local_loop_active(True)

def from_keyboard(code):
    """handle inputs received from the keyboard sender"""
    # ZZZ combine common code with `from_key()`
    global internet_active
    if not internet_active:
        if kc.Local:
            KOB.sounder(code)
        update_sender(kc.config.station)
        Reader.decode(code)
        if Recorder:
            Recorder.record(code, kob.CodeSource.local)
    if connected and kc.Remote:
        Internet.write(code)
    if len(code) > 0 and code[-1] == +1:
        set_local_loop_active(False)
        Reader.flush()  # ZZZ is this necessary/desirable?
    else:
        set_local_loop_active(True)

def from_internet(code):
    """handle inputs received from the internet"""
    global local_loop_active, internet_active
    if connected:
        KOB.sounder(code)
        Reader.decode(code)
        if Recorder:
            Recorder.record(code, kob.CodeSource.wire)
        if len(code) > 0 and code[-1] == +1:
            internet_active = False
            Reader.flush()  # ZZZ is this necessary/desirable?
        else:
            internet_active = True

def from_recorder(code, source=None):
    """
    Handle inputs received from the recorder during playback.
    """
    if connected:
        disconnect()
    KOB.sounder(code)
    Reader.decode(code)

def recorder_wire_callback(wire):
    """
    Called from the recorder playback when a wire changes for a sender.
    """
    Reader.flush()
    ka.codereader_append("\n\n<<{}>>".format(wire))


def from_circuit_closer(state):
    """handle change of Circuit Closer state"""
    global local_loop_active, internet_active
    code = latch_code if state == 1 else unlatch_code
    if not internet_active:
        if kc.Local:
            update_sender(kc.config.station)
            KOB.sounder(code)
            Reader.decode(code)
        if Recorder:
            Recorder.record(code, kob.CodeSource.local)
    if connected and kc.Remote:
        Internet.write(code)
    if len(code) > 0 and code[-1] == +1:
        set_local_loop_active(False)
        Reader.flush()  # ZZZ is this necessary/desirable?
    else:
        set_local_loop_active(True)

def disconnect():
    """
    Disconnect if connected.
    """
    if connected:
        toggle_connect()

def toggle_connect():
    """connect or disconnect when user clicks on the Connect button"""
    global local_loop_active, internet_active
    global connected
    connected = not connected
    if connected:
        kobstationlist.clear_station_list()
        Internet.connect(kc.WireNo)
    else:
        Internet.disconnect()
        Reader.flush()
        time.sleep(1.0)  # wait for any buffered code to complete
        connected = False  # just to make sure
        if not local_loop_active:
            KOB.sounder(latch_code)
            Reader.decode(latch_code)
            Reader.flush()
        kobstationlist.clear_station_list()
    internet_active = False

def change_wire():
    global local_loop_active, internet_active
    global connected
    if connected:
        connected = False
        Reader.flush()
        time.sleep(1.0)  # wait for any buffered code to complete
        if internet_active:
            internet_active = False
            if not local_loop_active:
                KOB.sounder(latch_code)
                Reader.decode(latch_code)
                Reader.flush()
        Internet.connect(kc.WireNo)
        connected = True
    if Recorder:
        Recorder.wire = kc.WireNo
    internet_active = False
    
# callback functions

def update_sender(id):
    """display station ID in reader window when there's a new sender"""
    global sender_ID, Reader
    if id != sender_ID:  # new sender
        sender_ID = id
        Reader.flush()
        ka.codereader_append("\n\n<{}>".format(sender_ID))
        kobstationlist.update_current_sender(sender_ID)
        Reader = morse.Reader(
                wpm=kc.WPM, codeType=kc.CodeType,
                callback=readerCallback)  # reset to nominal code speed
        if Recorder:
            Recorder.station_id = sender_ID

def add_to_sender_list(sender):
    """
    Add a sender to the sender list.
    """


def readerCallback(char, spacing):
    """display characters returned from the decoder"""
    if kc.CodeType == config.CodeType.american:
        sp = (spacing - 0.25) / 1.25  # adjust for American Morse spacing
    else:
        sp = spacing
    if sp > 100:
        txt = "" if char == "~" or char == "+" else " * "
    elif sp > 10:
        txt = "  —  "
    elif sp < -0.2:
        txt = ""
    elif sp < 0.2:
        txt = NNBSP
    elif sp < 0.5:
        txt = 2 * NNBSP
    elif sp < 0.8:
        txt = NNBSP + " "
    else:
        n = int(sp - 0.8) + 2
        txt = n * " "
    txt += char
    ka.codereader_append(txt)
    if char == "=":
        ka.codereader_append("\n")

def reset_wire_state():
    """log the current internet state and regain control of the wire"""
    global internet_active
    print(
            "Circuit Closer {}, internet_active was {}".format(
            local_loop_active, internet_active))
    internet_active = False

# initialization

def init():
    """
    Initialize the main class. This must be called by the main window class once all windows, 
    menus, etc. are created, configured and ready.
    """
    global KOB, Internet, Recorder
    KOB = kob.KOB(
            port=kc.config.serial_port, interfaceType=kc.config.interface_type, audio=kc.config.sound, callback=from_key)
    Internet = internet.Internet(kc.config.station, callback=from_internet)
    Internet.monitor_IDs(kobstationlist.update_station_active)
    Internet.monitor_sender(kobstationlist.update_current_sender)
    # Let the user know if 'invert key input' is enabled (typically only used for MODEM input)
    if config.invert_key_input:
        log.info("IMPORTANT! Key input signal invert is enabled (typically only used with a MODEM). " + \
            "To enable/disable this setting use `Configure --iki`.")
    # ZZZ temp always enable recorder - goal is to provide menu option
    ts = recorder.get_timestamp()
    dt = datetime.fromtimestamp(ts / 1000.0)
    dateTimeStr = str("{:04}{:02}{:02}-{:02}{:02}").format(dt.year, dt.month, dt.day, dt.hour, dt.minute)
    targetFileName = "Session-" + dateTimeStr + ".json"
    log.info("Record to '{}'".format(targetFileName))
    Recorder = recorder.Recorder(targetFileName, None, station_id=sender_ID, wire=kc.WireNo, \
        play_code_callback=from_recorder, \
        play_station_id_callback=update_sender, \
        play_station_list_callback=kobstationlist.update_station_active, \
        play_wire_callback=recorder_wire_callback)
    kobkeyboard.init()
