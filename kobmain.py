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
internet_station_active = False  # True if a remote station is sending
physical_closer_closed = True  # True if we detect that the pysical key closer is closed

latch_code = (-0x7fff, +1)  # code sequence to force latching (close)
unlatch_code = (-0x7fff, +2)  # code sequence to unlatch (open)

sender_ID = ""

def __set_local_loop_active(state):
    """
    Set local_loop_active state
    
    True: Key or Keyboard active (Ciruit Closer OPEN)
    False: Circuit Closer (physical and virtual) CLOSED
    """
    global local_loop_active
    local_loop_active = state
    log.debug("local_loop_active:{}".format(state))

def __emit_code(code):
    """
    Emit local code. That involves:
    1. Record code if recording is enabled
    2. Send code to the wire if connected

    This is used from the key or the keyboard threads to emit code once they 
    determine it should be emitted.
    """
    global connected
    update_sender(config.station)
    Reader.decode(code)
    Recorder.record(code, kob.CodeSource.local) # ZZZ ToDo: option to enable/disable recording
    if config.local:
        KOB.soundCode(code)
    if connected and config.remote:
        Internet.write(code)

def from_key(code):
    """
    Handle inputs received from the external key.
    Only send if the circuit is open.
    Note: typically this will be the case, but it is possible to 
     close the circuit from the GUI while the key's physical closer 
     is still open.

    Called from the 'KOB-KeyRead' thread.
    """
    global internet_station_active, local_loop_active
    if len(code) > 0:
        if code[-1] == 1: # special code for closer/circuit closed
            ka.trigger_circuit_close()
            return
        elif code[-1] == 2: # special code for closer/circuit open
            ka.trigger_circuit_open()
            return
    if not internet_station_active and local_loop_active:
        __emit_code(code)

def from_keyboard(code):
    """
    Handle inputs received from the keyboard sender.
    Only send if the circuit is open.

    Called from the 'Keyboard-Send' thread.
    """
    global internet_station_active, local_loop_active
    if not internet_station_active and local_loop_active:
        __emit_code(code)

def from_internet(code):
    """handle inputs received from the internet"""
    global local_loop_active, internet_station_active
    if connected:
        KOB.soundCode(code)
        Reader.decode(code)
        Recorder.record(code, kob.CodeSource.wire)
        if len(code) > 0 and code[-1] == +1:
            internet_station_active = False
        else:
            internet_station_active = True

def from_recorder(code, source=None):
    """
    Handle inputs received from the recorder during playback.
    """
    if connected:
        disconnect()
    KOB.soundCode(code)
    Reader.decode(code)

def from_circuit_closer(state):
    """
    Handle change of Circuit Closer state.
    This must be called from the GUI thread handling the Circuit-Closer checkbox, 
    the ESC keyboard shortcut, or by posting a message.

    A state of:
     True: 'latch'
     False: 'unlatch'

    """
    global local_loop_active, internet_station_active
    code = latch_code if state == 1 else unlatch_code
    if not internet_station_active:
        if config.local:
            ka.handle_sender_update(config.station) # Okay to call 'handle_' as this is run on the main thread
            KOB.soundCode(code)
            Reader.decode(code)
        Recorder.record(code, kob.CodeSource.local)
    if connected and config.remote:
        Internet.write(code)
    if len(code) > 0:
        if code[-1] == 1:
            # Unlatch
            __set_local_loop_active(False)
            Reader.flush()
        elif code[-1] == 2:
            # Latch
            __set_local_loop_active(True)
    ka.kw.varCircuitCloser.set(1 if not local_loop_active else 0)

def disconnect():
    """
    Disconnect if connected.
    """
    if connected:
        toggle_connect()

def toggle_connect():
    """connect or disconnect when user clicks on the Connect button"""
    global local_loop_active, internet_station_active
    global connected
    global sender_ID
    if not connected:
        sender_ID = ""
        ka.trigger_station_list_clear()
        Internet.monitor_IDs(ka.trigger_update_station_active) # Set callback for monitoring stations
        Internet.monitor_sender(ka.trigger_update_current_sender) # Set callback for monitoring current sender
        Internet.connect(config.wire)
        connected = True
    else:
        connected = False
        Internet.monitor_IDs(None) # don't monitor stations
        Internet.monitor_sender(None) # don't monitor current sender
        Internet.disconnect()
        Reader.flush()
        if not local_loop_active:
            KOB.soundCode(latch_code)
            Reader.decode(latch_code)
        sender_ID = ""
        ka.trigger_station_list_clear()
    internet_station_active = False

def change_wire():
    """
    Change the current wire. If connected, drop the current connection and 
    connect to the new wire.
    """
    global connected
    # Disconnect, change wire, reconnect.
    was_connected = connected
    disconnect()
    Recorder.wire = config.wire
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
### ZZZ not necessary if code speed recognition is disabled in pykob/morse.py
##        Reader = morse.Reader(
##                wpm=config.text_speed, codeType=config.code_type,
##                callback=readerCallback)  # reset to nominal code speed

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
    global internet_station_active
    internet_station_active = False

# initialization

def init():
    """
    Initialize the main class. This must be called by the main window class once all windows, 
    menus, etc. are created, configured and ready.
    """
    global KOB, Internet, Recorder
    KOB = kob.KOB(
            portToUse=config.serial_port, useGpio=config.gpio, interfaceType=config.interface_type,
            useAudio=config.sound, callback=from_key)
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
    Recorder = recorder.Recorder(targetFileName, None, station_id=sender_ID, wire=config.wire, \
        play_code_callback=from_recorder, \
        play_sender_id_callback=ka.trigger_update_current_sender, \
        play_station_list_callback=ka.trigger_update_station_active, \
        play_wire_callback=ka.trigger_player_wire_change)
    kobkeyboard.init()
    # If the configuration indicates that an application should automatically connect - 
    # connect to the currently configured wire.
    if config.auto_connect:
        ka.doConnect() # Suggest a connect.

