"""
MIT License

Copyright (c) 2020-24 PyKOB - MorseKOB in Python

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
import tkinter as tk
import tkinter.filedialog as fd
import traceback

from pykob import config2, kob, log, preferencesWindow, recorder, VERSION
from pykob.config2 import Config
import mkobevents

class MKOBActions():
    def __init__(self, mkwindow, mksl, mkrdr, cfg:Config) -> None:
        self._cfg = cfg
        self._preferencesDialog = None
        self._km = None # Set in start
        self._kw = mkwindow
        self._ksl = mksl
        self._krdr = mkrdr
        self._kkb = None # Set in start

    def start(self, mkmain, mkkb):
        self._km = mkmain
        self._kkb = mkkb

    ####
    #### Menu item handlers
    ####

    # File menu
    def doFileNew(self):
        self._kw.keyboard_win.delete('1.0', tk.END)

    def doFileOpen(self):
        log.debug("Open a file for sending...")
        pf = fd.askopenfilename(title='Text File for Sending', filetypes=[('Text','*.txt'),('Markdown','*.md'),('Any','*.*')])
        if pf:
            log.debug(" Open: {}".format(pf))
            self._kkb.load_file(pf)

    def doFilePlay(self):
        log.debug("Play a file...")
        pf = fd.askopenfilename(title='Select KOB Recording', filetypes=[('KOB Recording','*.json')])
        if pf:
            self._km.recording_play(pf)
        self._kw.give_keyboard_focus()
        return

    def doFileRecord(self):
        log.debug("Record session...")
        self._km.record_session()
        return

    def doFileRecordEnd(self):
        log.debug("End recording...")
        self._km.recording_end()
        return

    def _preferencesDialogDismissed(self, prefsDialog):
        """
        Called when the Preferences Dialog is dismissed via 'Cancel'/'Apply'/'Save'
        """
        # Put the ESC key binding back.
        self._kw._root.bind_all("<Key-Escape>", self.handle_toggle_closer)
        self._preferencesDialog = None
        self._km.preferences_closed(prefsDialog)
        return

    def doFilePreferences(self):
        if not self._preferencesDialog:
            # Unbind the ESC key so the dialog can use it
            self._kw._root.unbind_all("<Key-Escape>")
            cfg = self._km.preferences_opening()
            self._preferencesDialog = preferencesWindow.PreferencesWindow(
                cfg,
                callback=self._preferencesDialogDismissed,
                quitWhenDismissed=False,
                allowApply=True,
                saveIfRequested=False
            )
        #
        self._preferencesDialog.root.deiconify()
        self._preferencesDialog.root.lift()
        return

    def doFilePrefsLoad(self):
        self._km.preferences_load()
        return

    def doFilePrefsSave(self):
        self._km.preferences_save()
        return

    def doFilePrefsSaveAs(self):
        self._km.preferences_save_as()
        return

    def doFileExit(self):
        self._kw.exit()
        return

    # Tools menu
    def doShowPacketsChanged(self):
        sp = self._kw.show_packets
        self._km.show_packets = sp
        return

    def doKeyGraphShow(self):
        self._km.show_key_graph()
        return

    # Help menu

    def doHelpAbout(self):
        self._kw.show_help_about()
        return

    def doHelpShortcuts(self):
        self._kw.show_shortcuts()
        return

    ####
    #### Action handlers for control events
    ####

    def doOfficeID(self, event=None, *args):
        new_officeID = self._kw.office_id
        self._cfg.station = new_officeID
        self._km.Internet.set_officeID(new_officeID)
        return

    def doCircuitCloser(self, event=None, *args):
        self._km.set_virtual_closer_closed(self._kw.circuit_closer == 1)
        return

    def doMorseChange(self, event=None, *args):
        self._km.do_morse_change()
        return

    def doWireNo(self, event=None, *args):
        wire = self._kw.wire_number
        if wire > -1:
            self._cfg.wire = wire
            self._km.change_wire(wire)
        return

    def doConnect(self, event=None, *args):
        """
        Handle the 'Connect' button being pressed, by toggling the connected state.
        """
        if not self._km.connected:
            # If the recorder is playing a recording do not allow connection
            if self._km.Player and not self._km.Player.playback_state == recorder.PlaybackState.idle:
                return
        self._km.toggle_connect()
        self._kw.connected(self._km.connected)
        return

    ####
    #### Trigger event messages ###
    ####

    def trigger_circuit_close(self):
        """
        Generate an event to indicate that the circuit has closed.
        'LATCH' (key/circuit closed)
        """
        self._kw.event_generate(mkobevents.EVENT_CIRCUIT_CLOSE, when='tail')
        return

    def trigger_circuit_open(self):
        """
        Generate an event to indicate that the circuit has opened.
        'UNLATCH' (key/circuit open)
        """
        self._kw.event_generate(mkobevents.EVENT_CIRCUIT_OPEN, when='tail')
        return

    def trigger_emit_kb_code(self, code: list):
        """
        Generate an event to emit the code sequence originating from the keyboard.
        """
        self._kw.event_generate(mkobevents.EVENT_EMIT_KB_CODE, when='tail', data=code)
        return

    def trigger_emit_key_code(self, code: list):
        """
        Generate an event to emit the code sequence originating from the key.
        """
        self._kw.event_generate(mkobevents.EVENT_EMIT_KEY_CODE, when='tail', data=code)
        return

    def trigger_keyboard_send(self):
        """
        Generate an event to indicate that text should be sent from the keyboard window.
        """
        log.debug("mka.trigger_keyboard_send", 3)
        self._kw.event_generate(mkobevents.EVENT_KB_PROCESS_SEND, when='tail')
        return

    def trigger_player_wire_change(self, id: int):
        """
        Generate an event to indicate that the wire number
        from the player has changed.
        """
        self._kw.event_generate(mkobevents.EVENT_PLAYER_WIRE_CHANGE, when='tail', data=str(id))
        return

    def trigger_reader_append_text(self, text: str):
        """
        Generate an event to add text to the reader window.
        """
        self._kw.event_generate(mkobevents.EVENT_READER_APPEND_TEXT, when='tail', data=text)
        return

    def trigger_reader_clear(self):
        """
        Generate an event to clear the Reader window
        """
        self._kw.event_generate(mkobevents.EVENT_READER_CLEAR, when='tail')
        return

    def trigger_station_list_clear(self):
        """
        Generate an event to clear the station list and the window.
        """
        self._kw.event_generate(mkobevents.EVENT_STATIONS_CLEAR, when='tail')
        return

    def trigger_update_current_sender(self, id: str):
        """
        Generate an event to record the current sender.
        """
        self._kw.event_generate(mkobevents.EVENT_CURRENT_SENDER, when='tail', data=id)
        return

    def trigger_update_station_active(self, id: str):
        """
        Generate an event to update the active status (timestamp) of a station.
        """
        self._kw.event_generate(mkobevents.EVENT_STATION_ACTIVE, when='tail', data=id)
        return

    ####
    #### Event (message) handlers
    ####

    def handle_circuit_close(self, event=None):
        """
        Close the circuit and trigger associated local functions (checkbox, etc.)
        """
        self._km.set_virtual_closer_closed(True)
        return

    def handle_circuit_open(self, event=None):
        """
        Open the circuit and trigger associated local functions (checkbox, sender, etc.)
        """
        self._km.set_virtual_closer_closed(False)
        return

    def handle_emit_key_code(self, event_data):
        """
        Emit code originating from the key
        """
        self.handle_emit_code(event_data, kob.CodeSource.key)
        return

    def handle_emit_kb_code(self, event_data):
        """
        Emit code originating from the keyboard
        """
        self.handle_emit_code(event_data, kob.CodeSource.keyboard)
        return

    def handle_emit_code(self, event_data, code_source):
        """
        Emit a code sequence.

        event_data is the code sequence list as a string (ex: '(-17290 89)')
        It is converted to a list of integer values to emit.
        """
        data = event_data.strip(')(')
        if (data and (not data.isspace())):
            code = tuple(map(int, data.split(', ')))
            self._km.emit_code(code, code_source)
        return

    def handle_toggle_closer(self, event=None):
        """
        toggle Circuit Closer and regain control of the wire
        """
        self._kw.circuit_closer = not self._kw.circuit_closer
        self.doCircuitCloser()
        self._km.reset_wire_state()  # regain control of the wire
        return "break"

    def handle_decrease_wpm(self, event=None):
        """
        Decrease code speed
        """
        cwpm = self._kw.cwpm
        if cwpm > -1:
            cwpm = (cwpm - 1 if cwpm > 5 else 5)
            self._kw.cwpm = cwpm
        return "break"

    def handle_increase_wpm(self, event=None):
        """
        Increase code speed
        """
        cwpm = self._kw.cwpm
        if cwpm > -1:
            cwpm = (cwpm + 1 if cwpm < 40 else cwpm)
            self._kw.cwpm = cwpm
        return "break"

    def handle_clear_reader_window(self, event=None):
        """
        Clear Code Reader window
        """
        self._krdr.handle_clear()
        return "break"

    def handle_clear_sender_window(self, event=None):
        """
        Clear Code Sender window
        """
        self._kw.keyboard_sender.handle_clear()
        return "break"

    def handle_toggle_code_sender(self, event=None):
        """
        Toggle Code Sender ON|OFF
        """
        self._kw.code_sender_enabled = not self._kw.code_sender_enabled
        return "break"

    def handle_playback_move_back15(self, event=None):
        """
        Move the playback position back 15 seconds.
        """
        log.debug("Playback - move back 15 seconds...")
        if self._km.Reader:
            self._km.Reader.flush()  # Flush the Reader content before moving.
        if self._km.Player:
            self._km.Player.playback_move_seconds(-15)
        return

    def handle_playback_move_forward15(self, event=None):
        """
        Move the playback position forward 15 seconds.
        """
        log.debug("Playback - move forward 15 seconds...")
        if self._km.Reader:
            self._km.Reader.flush()  # Flush the Reader content before moving.
        if self._km.Player:
            self._km.Player.playback_move_seconds(15)
        return

    def handle_playback_move_sender_start(self, event=None):
        """
        Move the playback position to the start of the current sender.
        """
        log.debug("Playback - move to sender start...")
        if self._km.Reader:
            self._km.Reader.flush()  # Flush the Reader content before moving.
        if self._km.Player:
            self._km.Player.playback_move_to_sender_begin()
        return

    def handle_playback_move_sender_end(self, event=None):
        """
        Move the playback position to the end of the current sender.
        """
        log.debug("Playback - move to next sender...")
        if self._km.Reader:
            self._km.Reader.flush()  # Flush the Reader content before moving.
        if self._km.Player:
            self._km.Player.playback_move_to_sender_end()
        return

    def handle_playback_pauseresume(self, event=None):
        """
        Pause/Resume a recording if currently playing/paused.

        This does not play 'from scratch'. A playback must have been started
        for this to have any effect.
        """
        if self._km.Player:
            self._km.Player.playback_pause_resume()
        return

    def handle_playback_stop(self, event=None):
        """
        Stop playback of a recording if playing.
        """
        if self._km.Player:
            self._km.Player.playback_stop()
        return

    def handle_sender_update(self, event_data):
        """
        Handle a <<Current_Sender>> message by:
        1. Informing kobmain of a (possibly new) sender
        2. Informing the station list of a (possibly new) sender
        3. Informing the recorder of a (possibly new) sender

        event_data is the station ID
        """
        self._km.update_sender(event_data)
        self._ksl.handle_update_current_sender(event_data)
        if self._km.Recorder:
            self._km.Recorder.station_id = event_data
        return

    def handle_clear_stations(self, event=None):
        """
        Handle a <<Clear_Stations>> message by:
        1. Telling the station list to clear

        event has no meaningful information
        """
        self._ksl.handle_clear_station_list(None)
        return

    def handle_reader_clear(self, event=None):
        """
        Handle a <<Clear_Reader>> message by:
        1. Telling the reader window to clear

        event has no meaningful information
        """
        self._krdr.handle_clear()
        return

    def handle_reader_append_text(self, event_data):
        """
        Handle a <<Reader_Append_Text>> message by:
        1. Telling the reader window to append the text in the event_data

        event_data is the text to append
        """
        self._krdr.handle_append_text(event_data)
        return

    def handle_player_wire_change(self, event_data):
        """
        Handle a <<Player_Wire_Change>> message by:
        1. Appending <<wire>> to the reader window

        event_data contains a string version of the wire number
        """
        self._krdr.handle_append_text("\n\n<<{}>>\n".format(event_data))
        return
