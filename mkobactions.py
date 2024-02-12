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
import traceback

from pykob import config, kob, internet, morse, preferencesWindow, recorder, VERSION
import mkobevents

print("PyKOB " + VERSION)

class MKOBActions():
    def __init__(self, mkwindow, mksl, mkrdr) -> None:
        self._preferencesDialog = None
        self.km = None # Set in start
        self.kw = mkwindow
        self.ksl = mksl
        self.krdr = mkrdr
        self.kkb = None # Set in start

    def start(self, mkmain, mkkb):
        self.km = mkmain
        self.kkb = mkkb

    ####
    #### Menu item handlers
    ####

    # File menu
    def doFileNew(self):
        self.kw.keyboard_win.delete('1.0', tk.END)

    def doFileOpen(self):
        print("Open a file for sending...")
        pf = fd.askopenfilename(title='Text File for Sending', filetypes=[('Text','*.txt'),('Markdown','*.md'),('Any','*.*')])
        if pf:
            print(" Open: ", pf)
            self.kkb.load_file(pf)

    def doFilePlay(self):
        print("Play a file...")
        pf = fd.askopenfilename(title='Select KOB Recording', filetypes=[('KOB Recording','*.json')])
        if pf:
            print(" Play: ", pf)
            self.km.disconnect()
            self.km.StationList.handle_clear_station_list(None) # okay to call directly as we are in a handler
            self.km.Recorder.source_file_path = pf
            self.krdr.handle_clear(None)
            self.km.sender_ID = None
            dirpath, filename = os.path.split(pf)
            self.krdr.handle_append_text('[{}]\n'.format(filename))
            self.km.Recorder.playback_start(list_data=False, max_silence=5)
        self.kw.give_keyboard_focus()

    def _markPreferencesDestroyed(self, prefsDialog):
        self._preferencesDialog = None

    def doFilePreferences(self):
        if not self._preferencesDialog:
            self._preferencesDialog = \
                preferencesWindow.PreferencesWindow(callback=self._markPreferencesDestroyed,
                                                    quitWhenDismissed=False)
        self._preferencesDialog.root.deiconify()
        self._preferencesDialog.root.lift()

    def doFileExit(self):
        self.kw.exit()

    # Tools menu
    def doShowPacketsChanged(self):
        sp = self.kw.show_packets
        self.km.show_packets = sp

    def doKeyGraphShow(self):
        self.km.show_key_graph()

    # Help menu

    def doHelpAbout(self):
        mb.showinfo(title="About", message=self.kw.MKOB_VERSION_TEXT)

    ####
    #### Action handlers for control events
    ####

    def doOfficeID(self, event=None, *args):
        new_officeID = self.kw.office_id
        config.set_station(new_officeID)
        config.save_config()
        self.km.Internet.set_officeID(new_officeID)

    def doCircuitCloser(self, event=None, *args):
        self.km.virtualCloserClosed(self.kw.circuit_closer == 1)

    def doWPM(self, event=None, *args):
        new_cwpm = self.kw.cwpm
        new_twpm = self.kw.twpm
        if new_cwpm > -1 and new_twpm > -1:
            config.set_text_speed_int(new_twpm)
            config.set_min_char_speed_int(new_cwpm)
            config.save_config()
            self.km.setwpm(new_cwpm, new_twpm)

    def doWireNo(self, event=None, *args):
        wire = self.kw.wire_number
        if wire > -1:
            config.set_wire_int(wire)
            config.save_config()
            if self.km.connected:
                self.km.change_wire(wire)

    def doConnect(self, event=None, *args):
        """
        Handle the 'Connect' button being pressed, by toggling the connected state.
        """
        if not self.km.connected:
            # If the recorder is playing a recording do not allow connection
            if self.km.Recorder and not self.km.Recorder.playback_state == recorder.PlaybackState.idle:
                return
        self.km.toggle_connect()
        self.kw.connected(self.km.connected)

    ####
    #### Trigger event messages ###
    ####

    def trigger_circuit_close(self):
        """
        Generate an event to indicate that the circuit has closed.
        'LATCH' (key/circuit closed)
        """
        self.kw.event_generate(mkobevents.EVENT_CIRCUIT_CLOSE, when='tail')

    def trigger_circuit_open(self):
        """
        Generate an event to indicate that the circuit has opened.
        'UNLATCH' (key/circuit open)
        """
        self.kw.event_generate(mkobevents.EVENT_CIRCUIT_OPEN, when='tail')

    def trigger_emit_kb_code(self, code: list):
        """
        Generate an event to emit the code sequence originating from the keyboard.
        """
        self.kw.event_generate(mkobevents.EVENT_EMIT_KB_CODE, when='tail', data=code)

    def trigger_emit_key_code(self, code: list):
        """
        Generate an event to emit the code sequence originating from the key.
        """
        self.kw.event_generate(mkobevents.EVENT_EMIT_KEY_CODE, when='tail', data=code)

    def trigger_keyboard_send(self):
        """
        Generate an event to indicate that text should be sent from the keyboard window.
        """
        self.kw.event_generate(mkobevents.EVENT_KB_PROCESS_SEND, when='tail')

    def trigger_player_wire_change(self, id: int):
        """
        Generate an event to indicate that the wire number
        from the player has changed.
        """
        self.kw.event_generate(mkobevents.EVENT_PLAYER_WIRE_CHANGE, when='tail', data=str(id))

    def trigger_reader_append_text(self, text: str):
        """
        Generate an event to add text to the reader window.
        """
        self.kw.event_generate(mkobevents.EVENT_READER_APPEND_TEXT, when='tail', data=text)

    def trigger_reader_clear(self):
        """
        Generate an event to clear the Reader window
        """
        self.kw.event_generate(mkobevents.EVENT_READER_CLEAR, when='tail')

    def trigger_set_code_sender_on(self, on: bool):
        """
        Generate an event to set the Code Sender state ON|OFF.
        """
        self.kw.event_generate(mkobevents.EVENT_SET_CODE_SENDER_ON, when='tail', data=on)

    def trigger_speed_change(self):
        """
        Generate an event to indicate that the user changed the character or text speed.
        """
        self.kw.event_generate(mkobevents.EVENT_SPEED_CHANGE, when='tail')

    def trigger_station_list_clear(self):
        """
        Generate an event to clear the station list and the window.
        """
        self.kw.event_generate(mkobevents.EVENT_STATIONS_CLEAR, when='tail')

    def trigger_update_current_sender(self, id: str):
        """
        Generate an event to record the current sender.
        """
        self.kw.event_generate(mkobevents.EVENT_CURRENT_SENDER, when='tail', data=id)

    def trigger_update_station_active(self, id: str):
        """
        Generate an event to update the active status (timestamp) of a station.
        """
        self.kw.event_generate(mkobevents.EVENT_STATION_ACTIVE, when='tail', data=id)


    ####
    #### Event (message) handlers
    ####

    def handle_circuit_close(self, event):
        """
        Close the circuit and trigger associated local functions (checkbox, etc.)
        """
        self.km.virtualCloserClosed(True)

    def handle_circuit_open(self, event):
        """
        Open the circuit and trigger associated local functions (checkbox, sender, etc.)
        """
        self.km.virtualCloserClosed(False)

    def handle_emit_key_code(self, event_data):
        """
        Emit code originating from the key
        """
        self.handle_emit_code(event_data, kob.CodeSource.key)

    def handle_emit_kb_code(self, event_data):
        """
        Emit code originating from the keyboard
        """
        self.handle_emit_code(event_data, kob.CodeSource.keyboard)

    def handle_emit_code(self, event_data, code_source):
        """
        Emit a code sequence.

        event_data is the code sequence list as a string (ex: '(-17290 89)')
        It is converted to a list of integer values to emit.
        """
        data = event_data.strip(')(')
        if (data and (not data.isspace())):
            code = tuple(map(int, data.split(', ')))
            self.km.emit_code(code, code_source)

    def handle_toggle_closer(self, event):
        """
        toggle Circuit Closer and regain control of the wire
        """
        self.kw.circuit_closer = not self.kw.circuit_closer
        self.doCircuitCloser()
        self.km.reset_wire_state()  # regain control of the wire
        return "break"

    def handle_decrease_wpm(self, event):
        """
        Decrease code speed
        """
        cwpm = self.kw.cwpm
        if cwpm > -1:
            cwpm = (cwpm - 1 if cwpm > 5 else 5)
            self.kw.cwpm = cwpm
        return "break"

    def handle_increase_wpm(self, event):
        """
        Increase code speed
        """
        cwpm = self.kw.cwpm
        if cwpm > -1:
            cwpm = (cwpm + 1 if cwpm < 40 else cwpm)
            self.kw.cwpm = cwpm
        return "break"

    def handle_clear_reader_window(self, event):
        """
        Clear Code Reader window
        """
        self.krdr.handle_clear()
        return "break"

    def handle_clear_sender_window(self, event):
        """
        Clear Code Sender window
        """
        self.kw.keyboard_sender.handle_clear()
        return "break"

    def handle_toggle_code_sender(self, event):
        """
        Toggle Code Sender ON|OFF
        """
        self.kw.code_sender_enabled = not self.kw.code_sender_enabled
        return "break"

    def handle_playback_move_back15(self, event):
        """
        Move the playback position back 15 seconds.
        """
        print("Playback - move back 15 seconds...")
        if self.km.Reader:
            self.km.Reader.flush()  # Flush the Reader content before moving.
        self.km.Recorder.playback_move_seconds(-15)

    def handle_playback_move_forward15(self, event):
        """
        Move the playback position forward 15 seconds.
        """
        print("Playback - move forward 15 seconds...")
        if self.km.Reader:
            self.km.Reader.flush()  # Flush the Reader content before moving.
        self.km.Recorder.playback_move_seconds(15)

    def handle_playback_move_sender_start(self, event):
        """
        Move the playback position to the start of the current sender.
        """
        print("Playback - move to sender start...")
        if self.km.Reader:
            self.km.Reader.flush()  # Flush the Reader content before moving.
        self.km.Recorder.playback_move_to_sender_begin()

    def handle_playback_move_sender_end(self, event):
        """
        Move the playback position to the end of the current sender.
        """
        print("Playback - move to next sender...")
        if self.km.Reader:
            self.km.Reader.flush()  # Flush the Reader content before moving.
        self.km.Recorder.playback_move_to_sender_end()

    def handle_playback_pauseresume(self, event):
        """
        Pause/Resume a recording if currently playing/paused.

        This does not play 'from scratch'. A playback must have been started
        for this to have any effect.
        """
        self.km.Recorder.playback_pause_resume()

    def handle_playback_stop(self, event):
        """
        Stop playback of a recording if playing.
        """
        self.km.Recorder.playback_stop()

    def handle_sender_update(self, event_data):
        """
        Handle a <<Current_Sender>> message by:
        1. Informing kobmain of a (possibly new) sender
        2. Informing the station list of a (possibly new) sender
        3. Informing the recorder of a (possibly new) sender

        event_data is the station ID
        """
        self.km.update_sender(event_data)
        self.ksl.handle_update_current_sender(event_data)
        self.km.Recorder.station_id = event_data

    def handle_set_code_sender_on(self, event_data):
        """
        Handle a <<Set_Code_Sender_On>> message by:
        1. Setting the Code Sender On checkbox to Checked|Unchecked

        event_data is a string representation of True|False
        """
        on = eval(event_data)
        self.kw.code_sender_enabled = on

    def handle_clear_stations(self, event=None):
        """
        Handle a <<Clear_Stations>> message by:
        1. Telling the station list to clear

        event has no meaningful information
        """
        self.ksl.handle_clear_station_list(event)

    def handle_reader_clear(self, event=None):
        """
        Handle a <<Clear_Reader>> message by:
        1. Telling the reader window to clear

        event has no meaningful information
        """
        self.krdr.handle_clear()

    def handle_reader_append_text(self, event_data):
        """
        Handle a <<Reader_Append_Text>> message by:
        1. Telling the reader window to append the text in the event_data

        event_data is the text to append
        """
        self.krdr.handle_append_text(event_data)

    def handle_player_wire_change(self, event_data):
        """
        Handle a <<Player_Wire_Change>> message by:
        1. Appending <<wire>> to the reader window

        event_data contains a string version of the wire number
        """
        self.krdr.handle_append_text("\n\n<<{}>>\n".format(event_data))
