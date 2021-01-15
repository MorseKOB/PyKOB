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
    ka.kw.varCircuitCloser.set(1 if not local_loop_active else 0)  # ZZZ is this GUI-safe? probably not

def from_key(code):
    """handle inputs received from the external key"""
    global internet_active
    if not internet_active:
        if config.interface_type == config.interface_type.loop:
            KOB.setSounder(True)
        update_sender(config.station)
        Reader.decode(code)
        Recorder.record(code, kob.CodeSource.local) # ZZZ ToDo: option to start/stop recording
<<<<<<< HEAD
    if connected and remote:
=======
    if connected and config.remote:
>>>>>>> master
        Internet.write(code)
    if len(code) > 0 and code[-1] == +1:
        set_local_loop_active(False)
    else:
        set_local_loop_active(True)

def from_keyboard(code):
    """handle inputs received from the keyboard sender"""
    # ZZZ combine common code with `from_key()`
    global internet_active
    if not internet_active:
        if config.local:
            KOB.sounder(code)
        update_sender(config.station)
        Reader.decode(code)
        Recorder.record(code, kob.CodeSource.local)
    if connected and config.remote:
        Internet.write(code)
    if len(code) > 0 and code[-1] == +1:
        set_local_loop_active(False)
    else:
        set_local_loop_active(True)

def from_internet(code):
    """handle inputs received from the internet"""
    global local_loop_active, internet_active
    if connected:
        KOB.sounder(code)
        Reader.decode(code)
        Recorder.record(code, kob.CodeSource.wire)
        if len(code) > 0 and code[-1] == +1:
            internet_active = False
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

def from_circuit_closer(state):
    """handle change of Circuit Closer state"""
    global local_loop_active, internet_active
    code = latch_code if state == 1 else unlatch_code
    if not internet_active:
        if config.local:
            ka.handle_sender_update(config.station) # Okay to call 'handle_' as this is run on the main thread
            KOB.sounder(code)
            Reader.decode(code)
        Recorder.record(code, kob.CodeSource.local)
    if connected and config.remote:
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
    global sender_ID
    if not connected:
        sender_ID = ""
        ka.trigger_station_list_clear()
        Internet.monitor_IDs(ka.trigger_update_station_active) # Set callback for monitoring stations
        Internet.monitor_sender(ka.trigger_update_current_sender) # Set callback for monitoring current sender
<<<<<<< HEAD
        Internet.connect(config.wire)
=======
        Internet.connect(int(config.wire))
>>>>>>> master
        connected = True
    else:
        connected = False
        Internet.monitor_IDs(None) # don't monitor stations
        Internet.monitor_sender(None) # don't monitor current sender
        Internet.disconnect()
        Reader.flush()
        if not local_loop_active:
            KOB.sounder(latch_code)
            Reader.decode(latch_code)
        sender_ID = ""
        ka.trigger_station_list_clear()
    internet_active = False

def change_wire():
    """
    Change the current wire. If connected, drop the current connection and 
    connect to the new wire.
    """
    global connected
    # Disconnect, change wire, reconnect.
    was_connected = connected
    disconnect()
<<<<<<< HEAD
    Recorder.wire = config.wireNo
=======
    Recorder.wire = int(config.wire)
>>>>>>> master
    if was_connected:
        time.sleep(0.350) # Needed to allow UTP packets to clear
        toggle_connect()

    
# callback functions

def update_sender(id):
    """display station ID in reader window when there's a new sender"""
    global sender_ID, Reader
    if id != sender_ID:  # new sender
        sender_ID = id
        Reader.flush()
        ka.trigger_reader_append_text("\n\n<{}>".format(sender_ID))
<<<<<<< HEAD
        Reader = morse.Reader(
                wpm=config.text_speed, codeType=config.code_type,
                callback=readerCallback)  # reset to nominal code speed
=======
### ZZZ not necessary if code speed recognition is disabled in pykob/morse.py
##        Reader = morse.Reader(
##                wpm=config.text_speed, codeType=config.code_type,
##                callback=readerCallback)  # reset to nominal code speed
>>>>>>> master

def readerCallback(char, spacing):
    """display characters returned from the decoder"""
    Recorder.record([], '', text=char)
    if config.code_type == config.CodeType.american:
        sp = (spacing - 0.25) / 1.25  # adjust for American Morse spacing
    else:
        sp = spacing
    if sp > 100:
        txt = "" if char == "__" else " * "
## ZZZ Temporarily disable 'intelligent' spacing
##    elif sp > 10:
##        txt = "     "
##    elif sp < -0.2:
##        txt = ""
##    elif sp < 0.2:
##        txt = NNBSP
##    elif sp < 0.5:
##        txt = 2 * NNBSP
##    elif sp < 0.8:
##        txt = NNBSP + " "
##    else:
##        n = int(sp - 0.8) + 2
##        txt = n * " "
    elif sp > 5:
        txt = "     "
    else:
        n = int(sp + 0.5)
        txt = n * " "
    txt += char
    ka.trigger_reader_append_text(txt)
    if char == "=":
        ka.trigger_reader_append_text("\n")

def reset_wire_state():
    """regain control of the wire"""
    global internet_active
    internet_active = False

# initialization

def init():
    """
    Initialize the main class. This must be called by the main window class once all windows, 
    menus, etc. are created, configured and ready.
    """
    global KOB, Internet, Recorder
    KOB = kob.KOB(
            port=config.serial_port, interfaceType=config.interface_type, audio=config.sound, callback=from_key)
    Internet = internet.Internet(config.station, callback=from_internet)
    # Let the user know if 'invert key input' is enabled (typically only used for MODEM input)
    if config.invert_key_input:
        log.warn("IMPORTANT! Key input signal invert is enabled (typically only used with a MODEM). " + \
            "To enable/disable this setting use `Configure --iki`.")
    ts = recorder.get_timestamp()
    dt = datetime.fromtimestamp(ts / 1000.0)
    dateTimeStr = str("{:04}{:02}{:02}-{:02}{:02}").format(dt.year, dt.month, dt.day, dt.hour, dt.minute)
    targetFileName = "Session-" + dateTimeStr + ".json"
    log.info("Record to '{}'".format(targetFileName))
<<<<<<< HEAD
    Recorder = recorder.Recorder(targetFileName, None, station_id=sender_ID, wire=config.wire, \
=======
    Recorder = recorder.Recorder(targetFileName, None, station_id=sender_ID, wire=int(config.wire), \
>>>>>>> master
        play_code_callback=from_recorder, \
        play_sender_id_callback=ka.trigger_update_current_sender, \
        play_station_list_callback=ka.trigger_update_station_active, \
        play_wire_callback=ka.trigger_player_wire_change)
    kobkeyboard.init()
    # If the configuration indicates that an application should automatically connect - 
    # connect to the currently configured wire.
    if config.auto_connect:
        ka.doConnect() # Suggest a connect.

