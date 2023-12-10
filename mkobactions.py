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

from pykob import config, kob, internet, morse, preferencesWindow, recorder, VERSION
import mkobevents

print("PyKOB " + VERSION)

class MKOBActions():
    def __init__(self, mkwindow, mksl, mkrdr) -> None:
        self.__preferencesDialog = None
        self.km = None
        self.kw = mkwindow
        self.ksl = mksl
        self.krdr = mkrdr

    ####
    #### Menu item handlers
    ####

    # File menu

    def setMKobMain(self, mkmain):
        self.km = mkmain

    def doFileNew(self):
        self.kw.keyboard_win.delete('1.0', tk.END)

    def doFileOpen(self):
        self.kw.keyboard_win.insert(tk.END, "~  Now is the time for all good men to come to the aid of their party.  +")
        self.kw.keyboard_win.mark_set('mark', '0.0')
        self.kw.keyboard_win.mark_gravity('mark', tk.LEFT)
        self.kw.keyboard_win.tag_config('highlight', underline=1)
        self.kw.keyboard_win.tag_add('highlight', 'mark')

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
        self.__preferencesDialog = None

    def doFilePreferences(self):
        if not self.__preferencesDialog:
            self.__preferencesDialog = \
                preferencesWindow.PreferencesWindow(callback=self._markPreferencesDestroyed,
                                                    quitWhenDismissed=False)
        self.__preferencesDialog.root.deiconify()
        self.__preferencesDialog.root.lift()

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

    def doOfficeID(self, event):
        new_officeID = self.kw.office_id
        config.set_station(new_officeID)
        config.save_config()
        self.km.Internet.set_officeID(new_officeID)

    def doCircuitCloser(self):
        self.km.circuit_closer_closed(self.kw.circuit_closer == 1)

    def doWPM(self, event=None):
        new_wpm = self.kw.wpm
        config.set_text_speed(new_wpm)
        config.save_config()
        self.km.wpm = new_wpm
        self.km.Sender = morse.Sender(wpm=int(new_wpm), cwpm=int(config.min_char_speed), codeType=config.code_type, spacing=config.spacing)
        self.km.Reader = morse.Reader(wpm=int(new_wpm), cwpm=int(config.min_char_speed), codeType=config.code_type, callback=self.km.readerCallback)

    def doWireNo(self, event=None):
        wire = self.kw.wire_number
        config.set_wire(wire)
        config.save_config()
        if self.km.connected:
            self.km.change_wire()
            self.km.Recorder.wire = wire

    def doConnect(self):
        if self.km.Recorder and not self.km.Recorder.playback_state == recorder.PlaybackState.idle:
            return # If the recorder is playing a recording do not allow connection
        self.km.toggle_connect()
        self.kw.connected(self.km.connected)

    ####
    #### Trigger event messages ###
    ####

    def trigger_circuit_close(self):
        """
        Generate an event to indicate that the circuit has closed.
        """
        self.kw.event_generate(mkobevents.EVENT_CIRCUIT_CLOSE, when='tail')

    def trigger_circuit_open(self):
        """
        Generate an event to indicate that the circuit has opened.
        """
        self.kw.event_generate(mkobevents.EVENT_CIRCUIT_OPEN, when='tail')

    def trigger_emit_key_code(self, code: list):
        """
        Generate an event to emit the code sequence originating from the key.
        """
        self.kw.event_generate(mkobevents.EVENT_EMIT_KEY_CODE, when='tail', data=code)

    def trigger_emit_kb_code(self, code: list):
        """
        Generate an event to emit the code sequence originating from the keyboard.
        """
        self.kw.event_generate(mkobevents.EVENT_EMIT_KB_CODE, when='tail', data=code)

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
        self.km.circuit_closer_closed(True)

    def handle_circuit_open(self, event):
        """
        Open the circuit and trigger associated local functions (checkbox, sender, etc.)
        """
        self.km.circuit_closer_closed(False)

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

    def handle_escape(self, event):
        """
        toggle Circuit Closer and regain control of the wire
        """
        self.kw.circuit_closer = not self.kw.circuit_closer
        self.doCircuitCloser()
        self.km.reset_wire_state()  # regain control of the wire

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

    def handle_clear_stations(self, event):
        """
        Handle a <<Clear_Stations>> message by:
        1. Telling the station list to clear

        event has no meaningful information
        """
        self.ksl.handle_clear_station_list(event)

    def handle_reader_clear(self, event):
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
