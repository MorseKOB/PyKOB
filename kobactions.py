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
kobactions.py

Handle actions for controls on main MKOB window
"""
import os
import tkinter as tk
import tkinter.messagebox as mb
import tkinter.filedialog as fd
import time
from pykob import config, kob, internet, morse, recorder
import kobconfig as kc
import kobevents
import kobmain as km
import kobreader as krdr
import kobstationlist as ksl

import pykob  # for version number
print("PyKOB " + pykob.VERSION)

kw = None  # initialized by KOBWindow

####
#### Menu item handlers
####

# File menu

def doFileNew():
    kw.txtKeyboard.delete('1.0', tk.END)

def doFileOpen():
## TODO: newFile()
    kw.txtKeyboard.insert(tk.END, "~  Now is the time for all good men to come to the aid of their country.  +")
    kw.txtKeyboard.mark_set('mark', '0.0')
    kw.txtKeyboard.mark_gravity('mark', tk.LEFT)
    kw.txtKeyboard.tag_config('highlight', underline=1)
    kw.txtKeyboard.tag_add('highlight', 'mark')

def doFilePlay():
    print("Play a file...")
    pf = fd.askopenfilename(title='Select KOB Recording', filetypes=[('KOB Recording','*.json')])
    if pf:
        print(" Play: ", pf)
        km.disconnect()
        km.kobstationlist.handle_clear_station_list(None) # okay to call directly as we are in a handler
        km.Recorder.source_file_path = pf
        krdr.handle_clear(None)
        km.sender_ID = None
        dirpath, filename = os.path.split(pf)
        krdr.handle_append_text('[{}]\n'.format(filename))
        km.Recorder.playback_start(list_data=False, max_silence=5)
    kw.make_keyboard_focus()
    
def doFileExit():
    kw.root.destroy()
    kw.root.quit()

# Help menu

def doHelpAbout():
    mb.showinfo(title="About", message=kw.MKOB_VERSION_TEXT)

####
#### Action handlers for control events
####

def doOfficeID(event):
    kc.OfficeID = kw.varOfficeID.get()
    config.set_station(kc.OfficeID)
    config.save_config()
    km.Internet.set_officeID(kc.OfficeID)

def doCircuitCloser():
    km.from_circuit_closer(kw.varCircuitCloser.get() == 1)

def doWPM(event=None):
    kc.WPM = int(kw.spnWPM.get())
    config.set_text_speed(kw.spnWPM.get())
    config.save_config()
    km.Sender = morse.Sender(wpm=kc.WPM, cwpm=kc.CWPM,
            codeType=kc.CodeType, spacing=kc.Spacing)
    km.Reader = morse.Reader(wpm=kc.WPM, codeType=kc.CodeType,
            callback=km.readerCallback)

def doWireNo(event=None):
    kc.WireNo = int(kw.spnWireNo.get())
    config.set_wire(kw.spnWireNo.get())
    config.save_config()
    if km.connected:
        km.change_wire()
        km.Recorder.wire = kc.WireNo

def doConnect():
    if km.Recorder and not km.Recorder.playback_state == recorder.PlaybackState.idle:
        return # If the recorder is playing a recording do not allow connection
    km.toggle_connect()
    color = 'red' if km.connected else 'white'
    kw.cvsConnect.create_rectangle(0, 0, 20, 20, fill=color)

####
#### Trigger event messages ###
####

def trigger_player_wire_change(id: int):
    """
    Generate an event to indicate that the wire number 
    from the player has changed.
    """
    kw.root.event_generate(kobevents.EVENT_PLAYER_WIRE_CHANGE, when='tail', data=str(id))

def trigger_reader_append_text(text: str):
    """
    Generate an event to add text to the reader window.
    """
    kw.root.event_generate(kobevents.EVENT_READER_APPEND_TEXT, when='tail', data=text)

def trigger_reader_clear():
    """
    Generate an event to clear the Reader window
    """
    kw.root.event_generate(kobevents.EVENT_READER_CLEAR, when='tail')

def trigger_station_list_clear():
    """
    Generate an event to clear the station list and the window.
    """
    kw.root.event_generate(kobevents.EVENT_STATIONS_CLEAR, when='tail')

def trigger_update_current_sender(id: str):
    """
    Generate an event to record the current sender.
    """
    kw.root.event_generate(kobevents.EVENT_CURRENT_SENDER, when='tail', data=id)

def trigger_update_station_active(id: str):
    """
    Generate an event to update the active status (timestamp) of a station.
    """
    kw.root.event_generate(kobevents.EVENT_STATION_ACTIVE, when='tail', data=id)


####
#### Event (message) handlers
####

def handle_escape(event):
    """
    toggle Circuit Closer and regain control of the wire
    """
    kw.varCircuitCloser.set(not kw.varCircuitCloser.get())
    doCircuitCloser()
    km.reset_wire_state()  # regain control of the wire

def handle_playback_move_back15(event):
    """
    Move the playback position back 15 seconds.
    """
    print("Playback - move back 15 seconds...")
    if km.Reader:
        km.Reader.flush()  # Flush the Reader content before moving.
    km.Recorder.playback_move_seconds(-15)

def handle_playback_move_forward15(event):
    """
    Move the playback position forward 15 seconds.
    """
    print("Playback - move forward 15 seconds...")
    if km.Reader:
        km.Reader.flush()  # Flush the Reader content before moving.
    km.Recorder.playback_move_seconds(15)
        
def handle_playback_move_sender_start(event):
    """
    Move the playback position to the start of the current sender.
    """
    print("Playback - move to sender start...")
    if km.Reader:
        km.Reader.flush()  # Flush the Reader content before moving.
    km.Recorder.playback_move_to_sender_begin()
        
def handle_playback_move_sender_end(event):
    """
    Move the playback position to the end of the current sender.
    """
    print("Playback - move to next sender...")
    if km.Reader:
        km.Reader.flush()  # Flush the Reader content before moving.
    km.Recorder.playback_move_to_sender_end()
        
def handle_playback_pauseresume(event):
    """
    Pause/Resume a recording if currently playing/paused.

    This does not play 'from scratch'. A playback must have been started 
    for this to have any effect.
    """
    km.Recorder.playback_pause_resume()

def handle_playback_stop(event):
    """
    Stop playback of a recording if playing.
    """
    km.Recorder.playback_stop()

def handle_sender_update(event_data):
    """
    Handle a <<Current_Sender>> message by:
    1. Informing kobmain of a (possibly new) sender
    2. Informing the station list of a (possibly new) sender
    3. Informing the recorder of a (possibly new) sender

    event_data is the station ID
    """
    km.update_sender(event_data)
    ksl.handle_update_current_sender(event_data)
    km.Recorder.station_id = event_data

def handle_clear_stations(event):
    """
    Handle a <<Clear_Stations>> message by:
    1. Telling the station list to clear

    event has no meaningful information
    """
    ksl.handle_clear_station_list(event)

def handle_reader_clear(event):
    """
    Handle a <<Clear_Reader>> message by:
    1. Telling the reader window to clear

    event has no meaningful information
    """
    krdr.handle_clear()

def handle_reader_append_text(event_data):
    """
    Handle a <<Reader_Append_Text>> message by:
    1. Telling the reader window to append the text in the event_data

    event_data is the text to append
    """
    krdr.handle_append_text(event_data)

def handle_player_wire_change(event_data):
    """
    Handle a <<Player_Wire_Change>> message by:
    1. Appending <<wire>> to the reader window

    event_data contains a string version of the wire number
    """
    krdr.handle_append_text("\n\n<<{}>>\n".format(event_data))