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

from pykob import config2, kob, log, preferencesWindow, recorder, VERSION
from pykob.config2 import Config
import mkobevents

print("PyKOB " + VERSION)

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
        print("Open a file for sending...")
        pf = fd.askopenfilename(title='Text File for Sending', filetypes=[('Text','*.txt'),('Markdown','*.md'),('Any','*.*')])
        if pf:
            print(" Open: ", pf)
            self._kkb.load_file(pf)

    def doFilePlay(self):
        print("Play a file...")
        pf = fd.askopenfilename(title='Select KOB Recording', filetypes=[('KOB Recording','*.json')])
        if pf:
            print(" Play: ", pf)
            self._km.disconnect()
            self._km.StationList.handle_clear_station_list(None) # okay to call directly as we are in a handler
            self._km.Recorder.source_file_path = pf
            self._krdr.handle_clear(None)
            self._km.sender_ID = None
            dirpath, filename = os.path.split(pf)
            self._krdr.handle_append_text('[{}]\n'.format(filename))
            self._km.Recorder.playback_start(list_data=False, max_silence=5)
        self._kw.give_keyboard_focus()

    def _preferencesDialogDismissed(self, prefsDialog):
        """
        Called when the Preferences Dialog is dismissed via 'Cancel'/'Apply'/'Save'
        """
        self._preferencesDialog = None
        self._km.preferences_closed()
        # Put the ESC key binding back.
        self._kw._root.bind_all("<Key-Escape>", self.handle_toggle_closer)

    def doFilePreferences(self):
        if not self._preferencesDialog:
            self._preferencesDialog = preferencesWindow.PreferencesWindow(
                self._cfg,
                callback=self._preferencesDialogDismissed,
                quitWhenDismissed=False,
                allowApply=True)
        # Unbind the ESC key so the dialog can use it
        self._kw._root.unbind_all("<Key-Escape>")
        #
        self._preferencesDialog.root.deiconify()
        self._preferencesDialog.root.lift()

    def doFilePrefsLoad(self):
        dir = self._cfg.get_directory()
        dir = dir if dir else ""
        name = self._cfg.get_name(True)
        name = name if name else ""
        pf = fd.askopenfilename(
            title="Load Configuration",
            initialdir=dir,
            initialfile=name,
            filetypes=[("PyKOB Configuration", config2.PYKOB_CFG_EXT)]
        )
        if pf:
            print(" Load Config: ", pf)
            self._cfg.load_config(pf)
            self._cfg.clear_dirty()

    def doFilePrefsSave(self):
        if not self._cfg.get_filepath() and not self._cfg.load_from_global:
            # The config doesn't have a file path and it isn't global
            # call the SaveAs
            self.doFilePrefsSaveAs()
        else:
            self._cfg.save_config()

    def doFilePrefsSaveAs(self):
        dir = self._cfg.get_directory()
        dir = dir if dir else ""
        name = self._cfg.get_name(True)
        name = name if name else ""
        pf = fd.asksaveasfile(
            title="Save As",
            initialdir=dir,
            initialfile=name,
            defaultextension=config2.PYKOB_CFG_EXT,
            filetypes=[("PyKOB Configuration", config2.PYKOB_CFG_EXT)]
        )
        if pf:
            self._cfg.save_config(pf.name)

    def doFileExit(self):
        self._kw.exit()

    # Tools menu
    def doShowPacketsChanged(self):
        sp = self._kw.show_packets
        self._km.show_packets = sp

    def doKeyGraphShow(self):
        self._km.show_key_graph()

    # Help menu

    def doHelpAbout(self):
        mb.showinfo(title="About", message=self._kw.app_name_version)

    ####
    #### Action handlers for control events
    ####

    def doOfficeID(self, event=None, *args):
        new_officeID = self._kw.office_id
        self._cfg.station = new_officeID
        self._km.Internet.set_officeID(new_officeID)

    def doCircuitCloser(self, event=None, *args):
        self._km.virtualCloserClosed(self._kw.circuit_closer == 1)

    def doWPM(self, event=None, *args):
        new_cwpm = self._kw.cwpm
        new_twpm = self._kw.twpm
        if new_cwpm > -1 and new_twpm > -1:
            with self._cfg.notification_pauser() as npcfg:
                npcfg.text_speed = new_twpm
                npcfg.min_char_speed = new_cwpm
            self._km.setwpm(new_cwpm, new_twpm)

    def doWireNo(self, event=None, *args):
        wire = self._kw.wire_number
        if wire > -1:
            self._cfg.wire = wire
            if self._km.connected:
                self._km.change_wire(wire)

    def doConnect(self, event=None, *args):
        """
        Handle the 'Connect' button being pressed, by toggling the connected state.
        """
        if not self._km.connected:
            # If the recorder is playing a recording do not allow connection
            if self._km.Recorder and not self._km.Recorder.playback_state == recorder.PlaybackState.idle:
                return
        self._km.toggle_connect()
        self._kw.connected(self._km.connected)

    ####
    #### Trigger event messages ###
    ####

    def trigger_circuit_close(self):
        """
        Generate an event to indicate that the circuit has closed.
        'LATCH' (key/circuit closed)
        """
        self._kw.event_generate(mkobevents.EVENT_CIRCUIT_CLOSE, when='tail')

    def trigger_circuit_open(self):
        """
        Generate an event to indicate that the circuit has opened.
        'UNLATCH' (key/circuit open)
        """
        self._kw.event_generate(mkobevents.EVENT_CIRCUIT_OPEN, when='tail')

    def trigger_emit_kb_code(self, code: list):
        """
        Generate an event to emit the code sequence originating from the keyboard.
        """
        self._kw.event_generate(mkobevents.EVENT_EMIT_KB_CODE, when='tail', data=code)

    def trigger_emit_key_code(self, code: list):
        """
        Generate an event to emit the code sequence originating from the key.
        """
        self._kw.event_generate(mkobevents.EVENT_EMIT_KEY_CODE, when='tail', data=code)

    def trigger_keyboard_send(self):
        """
        Generate an event to indicate that text should be sent from the keyboard window.
        """
        log.debug("mka.trigger_keyboard_send", 3)
        self._kw.event_generate(mkobevents.EVENT_KB_PROCESS_SEND, when='tail')

    def trigger_player_wire_change(self, id: int):
        """
        Generate an event to indicate that the wire number
        from the player has changed.
        """
        self._kw.event_generate(mkobevents.EVENT_PLAYER_WIRE_CHANGE, when='tail', data=str(id))

    def trigger_reader_append_text(self, text: str):
        """
        Generate an event to add text to the reader window.
        """
        self._kw.event_generate(mkobevents.EVENT_READER_APPEND_TEXT, when='tail', data=text)

    def trigger_reader_clear(self):
        """
        Generate an event to clear the Reader window
        """
        self._kw.event_generate(mkobevents.EVENT_READER_CLEAR, when='tail')

    def trigger_speed_change(self):
        """
        Generate an event to indicate that the user changed the character or text speed.
        """
        self._kw.event_generate(mkobevents.EVENT_SPEED_CHANGE, when='tail')

    def trigger_station_list_clear(self):
        """
        Generate an event to clear the station list and the window.
        """
        self._kw.event_generate(mkobevents.EVENT_STATIONS_CLEAR, when='tail')

    def trigger_update_current_sender(self, id: str):
        """
        Generate an event to record the current sender.
        """
        self._kw.event_generate(mkobevents.EVENT_CURRENT_SENDER, when='tail', data=id)

    def trigger_update_station_active(self, id: str):
        """
        Generate an event to update the active status (timestamp) of a station.
        """
        self._kw.event_generate(mkobevents.EVENT_STATION_ACTIVE, when='tail', data=id)

    ####
    #### Event (message) handlers
    ####

    def handle_circuit_close(self, event):
        """
        Close the circuit and trigger associated local functions (checkbox, etc.)
        """
        self._km.virtualCloserClosed(True)

    def handle_circuit_open(self, event):
        """
        Open the circuit and trigger associated local functions (checkbox, sender, etc.)
        """
        self._km.virtualCloserClosed(False)

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
            self._km.emit_code(code, code_source)

    def handle_toggle_closer(self, event):
        """
        toggle Circuit Closer and regain control of the wire
        """
        self._kw.circuit_closer = not self._kw.circuit_closer
        self.doCircuitCloser()
        self._km.reset_wire_state()  # regain control of the wire
        return "break"

    def handle_decrease_wpm(self, event):
        """
        Decrease code speed
        """
        cwpm = self._kw.cwpm
        if cwpm > -1:
            cwpm = (cwpm - 1 if cwpm > 5 else 5)
            self._kw.cwpm = cwpm
        return "break"

    def handle_increase_wpm(self, event):
        """
        Increase code speed
        """
        cwpm = self._kw.cwpm
        if cwpm > -1:
            cwpm = (cwpm + 1 if cwpm < 40 else cwpm)
            self._kw.cwpm = cwpm
        return "break"

    def handle_clear_reader_window(self, event):
        """
        Clear Code Reader window
        """
        self._krdr.handle_clear()
        return "break"

    def handle_clear_sender_window(self, event):
        """
        Clear Code Sender window
        """
        self._kw.keyboard_sender.handle_clear()
        return "break"

    def handle_toggle_code_sender(self, event):
        """
        Toggle Code Sender ON|OFF
        """
        self._kw.code_sender_enabled = not self._kw.code_sender_enabled
        return "break"

    def handle_playback_move_back15(self, event):
        """
        Move the playback position back 15 seconds.
        """
        print("Playback - move back 15 seconds...")
        if self._km.Reader:
            self._km.Reader.flush()  # Flush the Reader content before moving.
        self._km.Recorder.playback_move_seconds(-15)

    def handle_playback_move_forward15(self, event):
        """
        Move the playback position forward 15 seconds.
        """
        print("Playback - move forward 15 seconds...")
        if self._km.Reader:
            self._km.Reader.flush()  # Flush the Reader content before moving.
        self._km.Recorder.playback_move_seconds(15)

    def handle_playback_move_sender_start(self, event):
        """
        Move the playback position to the start of the current sender.
        """
        print("Playback - move to sender start...")
        if self._km.Reader:
            self._km.Reader.flush()  # Flush the Reader content before moving.
        self._km.Recorder.playback_move_to_sender_begin()

    def handle_playback_move_sender_end(self, event):
        """
        Move the playback position to the end of the current sender.
        """
        print("Playback - move to next sender...")
        if self._km.Reader:
            self._km.Reader.flush()  # Flush the Reader content before moving.
        self._km.Recorder.playback_move_to_sender_end()

    def handle_playback_pauseresume(self, event):
        """
        Pause/Resume a recording if currently playing/paused.

        This does not play 'from scratch'. A playback must have been started
        for this to have any effect.
        """
        self._km.Recorder.playback_pause_resume()

    def handle_playback_stop(self, event):
        """
        Stop playback of a recording if playing.
        """
        self._km.Recorder.playback_stop()

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
        self._km.Recorder.station_id = event_data

    def handle_clear_stations(self, event=None):
        """
        Handle a <<Clear_Stations>> message by:
        1. Telling the station list to clear

        event has no meaningful information
        """
        self._ksl.handle_clear_station_list(event)

    def handle_reader_clear(self, event=None):
        """
        Handle a <<Clear_Reader>> message by:
        1. Telling the reader window to clear

        event has no meaningful information
        """
        self._krdr.handle_clear()

    def handle_reader_append_text(self, event_data):
        """
        Handle a <<Reader_Append_Text>> message by:
        1. Telling the reader window to append the text in the event_data

        event_data is the text to append
        """
        self._krdr.handle_append_text(event_data)

    def handle_player_wire_change(self, event_data):
        """
        Handle a <<Player_Wire_Change>> message by:
        1. Appending <<wire>> to the reader window

        event_data contains a string version of the wire number
        """
        self._krdr.handle_append_text("\n\n<<{}>>\n".format(event_data))
