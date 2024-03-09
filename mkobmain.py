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
kobmain.py

Handle the flow of Morse code throughout the program.
"""
import os
import time
from datetime import datetime
from queue import Queue
from threading import Event, Thread
import tkinter.filedialog as fd
import tkinter.messagebox as mb
from typing import Optional

from pykob import config, config2, kob, morse, internet, recorder, log
from pykob.config2 import Config, ConfigLoadError
from mkobkeytimewin import MKOBKeyTimeWin

NNBSP = "\u202f"  # narrow no-break space
LATCH_CODE = (-0x7FFF, +1)  # code sequence to force latching (close)
UNLATCH_CODE = (-0x7FFF, +2)  # code sequence to unlatch (open)


class MKOBMain:
    def __init__(self, tkroot, app_ver, mkactions, mkwindow, cfg: Config) -> None:
        self.app_ver = app_ver
        self._tkroot = tkroot
        self._ka = mkactions
        self._kw = mkwindow
        self._player: Optional[recorder.Recorder] = None
        self._recorder: Optional[recorder.Recorder] = None
        self._cfg = cfg
        self._set_on_cfg:bool = False # Flag to control setting values on our config
        self._mreader = None  # Set by do_morse_change
        self._msender = None  # Set by do_morse_change
        self._code_type = None  # Set by do_morse_change
        self._cwpm = 0  # Set by do_morse_change
        self._twpm = 0  # Set by do_morse_change
        self._spacing = None  # Set by do_morse_change

        self._key_graph_win = None

        self._wire = self._cfg.wire
        self._connected = Event()
        self._odc_fu = None
        self._show_packets = False
        self._lastCharWasParagraph = False

        self._internet_station_active = False  # True if a remote station is sending

        self._sender_ID = ""

        # For emitting code
        self._emit_code_queue = Queue()
        self._threadStop: Event = Event()
        self._emit_code_thread = Thread(
            name="MKMain-EmitCode", target=self._emit_code_thread_run
        )

        self._internet = None
        self._kob = None
        self._create_internet(self._cfg)
        self._create_kob(self._cfg)
        self.do_morse_change()

        # Let the user know if 'invert key input' is enabled (typically only used for MODEM input)
        if self._cfg.invert_key_input:
            log.warn(
                "IMPORTANT! Key input signal invert is enabled (typically only used with a MODEM). "
                + "To enable/disable this setting use `Configure --iki`."
            )

    def _create_internet(self, cfg:Config):
        was_connected = self._connected.is_set()
        if self._internet:
            if was_connected:
                self.disconnect()
            self._internet.exit()
        self._internet = internet.Internet(
            officeID=cfg.station,
            code_callback=self.from_internet,
            pckt_callback=self._packet_callback,
            appver=self.app_ver,
            server_url=cfg.server_url,
            msg_receiver=self._critical_msg_handler
        )
        if was_connected:
            self.toggle_connect()

    def _create_kob(self, cfg:Config):
        was_connected = self._connected.is_set()
        vcloser = False
        if self._internet and was_connected:
            self.disconnect()
        if self._kob:
            vcloser = self._kob.virtual_closer_is_open
            self._kob.exit()
        self._kob = kob.KOB(
            interfaceType=cfg.interface_type,
            portToUse=cfg.serial_port,
            useGpio=cfg.gpio,
            useAudio=cfg.sound,
            audioType=cfg.audio_type,
            useSounder=cfg.sounder,
            invertKeyInput=cfg.invert_key_input,
            soundLocal=cfg.local,
            sounderPowerSaveSecs=cfg.sounder_power_save,
            keyCallback=self.from_key
        )
        self._kob.virtual_closer_is_open = vcloser
        if was_connected:
            self.toggle_connect()

    def _create_player(self):
        self._player = recorder.Recorder(
            None,
            None,
            station_id=self._sender_ID,
            wire=self._wire,
            play_code_callback=self.from_recorder,
            play_sender_id_callback=self._ka.trigger_update_current_sender,
            play_station_list_callback=self._ka.trigger_update_station_active,
            play_wire_callback=self._ka.trigger_player_wire_change,
        )

    def _create_recorder(self):
        ts = recorder.get_timestamp()
        dt = datetime.fromtimestamp(ts / 1000.0)
        dateTimeStr = str("{:04}{:02}{:02}-{:02}{:02}").format(
            dt.year, dt.month, dt.day, dt.hour, dt.minute
        )
        targetFileName = "Session-" + dateTimeStr + ".json"
        log.info("Recording to '{}'".format(targetFileName))
        self._recorder = recorder.Recorder(
            targetFileName,
            None,
            station_id=self._sender_ID,
            wire=self._wire,
            play_code_callback=None,
            play_sender_id_callback=None,
            play_station_list_callback=None,
            play_wire_callback=None,
        )
        return

    def _critical_msg_handler(self, msg:str) -> None:
        log.warn(msg)
        self._ka.trigger_reader_append_text(msg)

    def _emit_code_thread_run(self):
        while not self._threadStop.is_set():
            # Read from the emit code queue
            emit_code_packet = (
                self._emit_code_queue.get()
            )  # Blocks until a packet is available
            #
            code = emit_code_packet[0]
            code_source = emit_code_packet[1]
            closer_open = emit_code_packet[2]
            done_callback = emit_code_packet[3]

            callback_delay = 30
            if not self._internet_station_active:
                callback_delay = 1
                if closer_open:
                    self.update_sender(self._cfg.station)
                    self._mreader.decode(code)
                    if self._recorder:
                        self._recorder.record(code, code_source)
                    if self._connected.is_set() and self._cfg.remote:
                        self._internet.write(code)
                    if self.key_graph_is_active():
                        self._key_graph_win.key_code(code)
                if self._cfg.local and not code_source == kob.CodeSource.key:
                    # Don't call if from key. Local sounder handled in key processing.
                    # Call even if closer closed in order to take the appropriate amount of time.
                    self._kob.soundCode(code, code_source, closer_open)
            if done_callback:
                self._tkroot.after(callback_delay, done_callback)
            pass
        log.debug("Internet-Data-Read thread done.")
        return

    def start(self):
        """
        Start the main processing.
        """
        self._emit_code_thread.start()
        # If the configuration indicates that an application should automatically connect -
        # connect to the currently configured wire.
        if self._cfg.auto_connect:
            self._ka.doConnect()  # Suggest a connect.
        #
        # If operational values change, set them on our config
        self._set_on_cfg = True
        return

    def exit(self):
        self._threadStop.set()
        if self._kob:
            self._kob.exit()
        if self._internet:
            self._internet.exit()
        if self._emit_code_thread and self._emit_code_thread.is_alive():
            self._emit_code_thread.join()
        return

    @property
    def connected(self):
        """
        True if connected to a wire.
        """
        return self._connected.is_set()

    @property
    def internet_station_active(self) -> bool:
        return self._internet_station_active

    @property
    def show_packets(self):
        """
        True if the user requested the received and sent packets be displayed.
        """
        return self._show_packets

    @show_packets.setter
    def show_packets(self, b: bool):
        """
        Set whether to display the received and sent packets.
        """
        self._show_packets = b

    @property
    def Internet(self):
        return self._internet

    @property
    def Player(self) -> Optional[recorder.Recorder]:
        return self._player

    @property
    def Reader(self):
        return self._mreader

    @property
    def Recorder(self) -> Optional[recorder.Recorder]:
        return self._recorder

    @property
    def Sender(self):
        return self._msender

    @property
    def tkroot(self):
        return self._tkroot

    @property
    def wpm(self):
        return self._cwpm

    def change_wire(self, wire: int):
        """
        Change the current wire. If connected, drop the current connection and
        connect to the new wire.
        """
        if not wire == self._wire:
            # Disconnect, change wire, reconnect.
            log.debug("mkm - change_wire: {}->{}".format(self._wire, wire))
            was_connected = self._connected.is_set()
            self.disconnect()
            self._wire = wire
            if self._recorder:
                self._recorder.wire = wire
            if was_connected:
                time.sleep(0.50)  # Needed to allow UTP packets to clear
                self.toggle_connect()
        return

    def do_morse_change(self):
        """
        Read Morse values from the UI and Config and update our operations.
        """
        code_type = self._cfg.code_type
        cwpm = self._kw.cwpm
        twpm = self._kw.twpm
        spacing = self._kw.spacing
        self.set_morse(code_type, cwpm, twpm, spacing)

    def emit_code(self, code, code_source, closer_open=True, done_callback=None):
        """
        Emit local code. That involves:
        1. Record code if recording is enabled
        2. Send code to the wire if connected

        This is used from the keyboard or indirectly from the key thread to emit code once they
        determine it should be emitted.

        It should be called by an event handler in response to a 'EVENT_EMIT_KEY_CODE' message,
        or from the keyboard sender.
        """
        emit_code_packet = [code, code_source, closer_open, done_callback]
        self._emit_code_queue.put(emit_code_packet)
        return

    def from_key(self, code):
        """
        Handle inputs received from the external key.
        Only send if the circuit is open.
        Note: typically this will be the case, but it is possible to
        close the circuit from the GUI while the key's physical closer
        is still open.

        Called from the 'KOB-KeyRead' thread.
        """
        log.debug("MKOBMain.from_key: {}".format(code), 3)
        if len(code) > 0:
            if code[-1] == 1:  # special code for 'LATCH' (key/circuit closed)
                self._ka.trigger_circuit_close()
                return
            elif code[-1] == 2:  # special code for 'UNLATCH' (key/circuit open)
                self._ka.trigger_circuit_open()
                return
        if not self._internet_station_active and self._kob.virtual_closer_is_open:
            self._ka.trigger_emit_key_code(code)
        return

    def from_keyboard(self, code, finished_callback=None):
        """
        Handle inputs received from the keyboard sender.

        Called from the Keyboard-Sender.
        """
        self.emit_code(
            code,
            kob.CodeSource.keyboard,
            self._kob.virtual_closer_is_open,
            finished_callback
        )
        return

    def from_internet(self, code):
        """handle inputs received from the internet"""
        if self._connected.is_set():
            self._kob.soundCode(code, kob.CodeSource.wire)
            self._mreader.decode(code)
            if self._recorder:
                self._recorder.record(code, kob.CodeSource.wire)
            if len(code) > 0 and code[-1] == +1:
                self._internet_station_active = False
            else:
                self._internet_station_active = True
            if self.key_graph_is_active():
                self._key_graph_win.wire_code(code)
        else:
            self._internet_station_active = False

    def from_recorder(self, code, source=None):
        """
        Handle inputs received from the recorder during playback.
        """
        if self._connected.is_set():
            self.disconnect()
        self._kob.soundCode(code, kob.CodeSource.player)
        self._mreader.decode(code)
        if self.key_graph_is_active():
            self._key_graph_win.key_code(code)

    def set_virtual_closer_closed(self, closed):
        """
        Handle change of Circuit Closer state.
        This must be called from the GUI thread handling the Circuit-Closer checkbox,
        the ESC keyboard shortcut, or by posting a message (from the Key handler).

        A state of:
        True: 'LATCH' the circuit closed
        False: 'UNLATCH' the circuit (now open)

        """
        code = LATCH_CODE if closed else UNLATCH_CODE
        # Set the Circuit Closer checkbox appropriately
        self._kw.circuit_closer = 1 if closed else 0
        self._kob.virtual_closer_is_open = not closed
        if not self._internet_station_active:
            if self._cfg.local:
                if not closed:
                    self._ka.handle_sender_update(
                        self._cfg.station
                    )  # Can call 'handle_' as this is run on the UI thread
                self._kob.energize_sounder(closed)
                self._mreader.decode(code)
            if self._recorder:
                self._recorder.record(code, kob.CodeSource.local)
        if self._connected.is_set() and self._cfg.remote:
            self._internet.write(code)
        if closed:
            # Latch
            self._mreader.flush()
        else:
            # Unlatch
            pass
        if self.key_graph_is_active():
            if closed:
                self._key_graph_win.key_closed()
            else:
                self._key_graph_win.key_opened()

    def set_morse(self, code_type:config.CodeType, cwpm:int, twpm:int, spacing:config.Spacing):
        if cwpm < 5:
            cwpm = 5
        if cwpm > 45:
            cwpm = 45
        if twpm < 5:
            twpm = 5
        if twpm > 45:
            twpm = 45
        if cwpm < twpm:
            cwpm = twpm  # Character (dot) speed needs to be at least the text speed
        if (not cwpm == self._cwpm)\
        or (not twpm == self._twpm)\
        or (not code_type == self._code_type)\
        or (not spacing == self._spacing):
            self._code_type = code_type
            self._cwpm = cwpm
            self._twpm = twpm
            self._spacing = spacing
            if self._set_on_cfg:
                self._cfg.code_type = code_type
                self._cfg.min_char_speed = cwpm
                self._cfg.text_speed = twpm
                self._cfg.spacing = spacing
            self._msender = morse.Sender(
                wpm=twpm, cwpm=cwpm, codeType=code_type, spacing=spacing
            )
            self._mreader = morse.Reader(
                wpm=twpm,
                cwpm=cwpm,
                codeType=code_type,
                callback=self._reader_callback,
            )
            if self.key_graph_is_active():
                self._key_graph_win.wpm = cwpm
            self._kw.cwpm = cwpm
            self._kw.twpm = twpm
            self._kw.spacing = self._cfg.spacing

    def disconnect(self):
        """
        Disconnect if connected.
        """
        if self._connected.is_set():
            self.toggle_connect()

    def toggle_connect(self):
        """
        Connect or disconnect when user clicks on the Connect button.

        # Okay to call 'handle...' in here, as this is run on main thread.
        """
        if not self._connected.is_set():
            # Connect
            self._sender_ID = ""
            self._ka.handle_clear_stations()
            self._internet.monitor_IDs(
                self._ka.trigger_update_station_active
            )  # Set callback for monitoring stations
            self._internet.monitor_sender(
                self._ka.trigger_update_current_sender
            )  # Set callback for monitoring current sender
            self._internet.connect(self._wire)
            self._connected.set()
        else:
            # Disconnect
            self._connected.clear()
            self._internet.monitor_IDs(None)  # don't monitor stations
            self._internet.monitor_sender(None)  # don't monitor current sender
            self._internet.disconnect(self._on_disconnect)

    def _on_disconnect_followup(self, *args):
        self._odc_fu = None
        self._mreader.decode(LATCH_CODE, use_flusher=False)
        self._mreader.flush()
        self._ka.trigger_station_list_clear()
        self._ka.trigger_reader_append_text("\n#####\n")
        if not self._kob.virtual_closer_is_open:
            # Sounder should be energized when disconnected.
            self._kob.energize_sounder(False)
            self._kob.energize_sounder(True, from_disconnect=True)

    def _on_disconnect(self):
        # These should be false and blank from the 'disconnect', but make sure.
        self._internet_station_active = False
        self._sender_ID = ""
        self._mreader.flush()
        if not self._odc_fu:
            self._odc_fu = self._tkroot.after(800, self._on_disconnect_followup)

    # callback functions

    def _packet_callback(self, pckt_text):
        """
        Set as a callback for the Internet package to print packets
        """
        if self.show_packets:
            self._ka.trigger_reader_append_text(pckt_text)

    def _reader_callback(self, char, spacing):
        """display characters returned from the decoder"""
        if self._recorder:
            self._recorder.record([], "", text=char)
        if self._cfg.code_type == config.CodeType.american:
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
        if char == "=":
            self._lastCharWasParagraph = True
        else:
            if self._lastCharWasParagraph:
                txt += "\n"
            self._lastCharWasParagraph = False
        txt += char
        self._ka.trigger_reader_append_text(txt)

    def key_graph_is_active(self):
        """
        True if the key graph is currently active.
        """
        return self._key_graph_win and MKOBKeyTimeWin.active

    def _update_from_config(self, cfg:Config, ct:config2.ChangeType):
        try:
            self._set_on_cfg = False
            new_kob_created = False
            log.set_debug_level(cfg.debug_level)
            if ct & config2.ChangeType.HARDWARE:
                # If the hardware changed, we need a new KOB instance.
                self._create_kob(cfg)
                new_kob_created = True
            if ct & config2.ChangeType.MORSE:
                self._kw.spacing = cfg.spacing
                self._kw.twpm = cfg.text_speed
                self._kw.cwpm = cfg.min_char_speed
                # Update the Reader and Sender instances
                self.set_morse(
                    cfg.code_type,
                    cfg.min_char_speed,
                    cfg.text_speed,
                    cfg.spacing,
                )
            if ct & config2.ChangeType.OPERATIONS:
                self._kw.office_id = cfg.station
                self._kw.wire_number = cfg.wire
                if cfg.local_changed and not new_kob_created:
                    self._create_kob(cfg)
                if cfg.server_url_changed:
                    self._create_internet(cfg)
            self._kw.set_app_title()
        finally:
            self._set_on_cfg = True

    def preferences_closed(self, prefsDialog):
        """
        The preferences (config) window returned.
        """
        if not prefsDialog.cancelled:
            cfg_from_prefs:Config = prefsDialog.cfg
            ct = cfg_from_prefs.get_changes_types()
            log.debug("mkm - Preferences Dialog closed. Change types: {}".format(ct))
            if not ct == 0:
                self._cfg.copy_from(cfg_from_prefs)
                self._update_from_config(cfg_from_prefs, ct)
                if prefsDialog.save_pressed:
                    self.preferences_save()
                self._set_on_cfg = True

    def preferences_load(self):
        """
        Load a new configuration.
        """
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
            try:
                log.debug(" Load Config: {}".format(pf))
                self._cfg.load_config(pf)
                self._update_from_config(self._cfg, config2.ChangeType.ANY)
                self._cfg.clear_dirty()
            except ConfigLoadError as err:
                log.warn("Unable to load configuration: {}  Error: {}".format(pf, err))

    def preferences_opening(self) -> Config:
        """
        The Preferences (config) Dialog is being opened.

        Return a config for it to use.
        """
        cfg_for_prefs = self._cfg.copy()
        if self._cfg.using_global():
            cfg_for_prefs.set_using_global(True)
        else:
            cfg_for_prefs.set_filepath(self._cfg.get_filepath())
        cfg_for_prefs.clear_dirty()
        return cfg_for_prefs

    def preferences_save(self):
        if not self._cfg.get_filepath() and not self._cfg.load_from_global:
            # The config doesn't have a file path and it isn't global
            # call the SaveAs
            self.preferences_save_as()
        else:
            self._cfg.save_config()

    def preferences_save_as(self):
        dir = self._cfg.get_directory()
        dir = dir if dir else ""
        name = self._cfg.get_name(True)
        name = name if name else ""
        pf = fd.asksaveasfilename(
            title="Save As",
            initialdir=dir,
            initialfile=name,
            defaultextension=config2.PYKOB_CFG_EXT,
            filetypes=[("PyKOB Configuration", config2.PYKOB_CFG_EXT)],
        )
        if pf:
            self._cfg.set_using_global(False)
            self._cfg.save_config(pf)

    def record_end(self):
        return

    def record_session(self):
        """
        Start recording if not already started.
        """
        if not self._recorder:
            self._create_recorder()
        msg = "Recording session to: {}".format(self._recorder.target_file_path)
        mb.showinfo(title=self.app_ver, message=msg)
        return

    def recording_end(self):
        msg = "Session was not being recorded."
        if self._recorder:
            r = self._recorder
            self._recorder = None
            msg = "Session recorded to: {}".format(r.target_file_path)
            r.playback_stop()
        mb.showinfo(title=self.app_ver, message=msg)
        return

    def recording_play(self, file_path:str):
        log.debug(" Play: {}".format(file_path))
        if not self._player:
            self._create_player()
        self.disconnect()
        self._ka.handle_clear_stations() # okay to call directly as we are in a handler
        self._ka.handle_clear_reader_window()
        self._sender_ID = None
        dirpath, filename = os.path.split(file_path)
        self._ka.handle_reader_append_text("[{}]\n".format(filename))
        self._player.source_file_path = file_path
        self._player.playback_start(list_data=False, max_silence=5)
        return

    def reset_wire_state(self):
        """regain control of the wire"""
        self._internet_station_active = False

    def show_key_graph(self):
        """
        Show the Key Timing graph.
        """
        if not (self._key_graph_win and MKOBKeyTimeWin.active):
            self._key_graph_win = MKOBKeyTimeWin(self._cwpm)
        self._key_graph_win.focus()

    def update_sender(self, id):
        """display station ID in reader window when there's a new sender"""
        if id != self._sender_ID:  # new sender
            self._sender_ID = id
            self._ka.trigger_reader_append_text("\n<{}>".format(self._sender_ID))
        ### ZZZ not necessary if code speed recognition is disabled in pykob/morse.py
        ##        Reader = morse.Reader(
        ##                wpm=self._cfg.text_speed, codeType=self._cfg.code_type,
        ##                callback=readerCallback)  # reset to nominal code speed
