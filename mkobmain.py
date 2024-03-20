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
from queue import Empty, Queue
import threading
from threading import Event, Thread
import tkinter.filedialog as filedlg
import tkinter.messagebox as msgbox
from typing import Optional

from pykob import config, config2, kob, morse, internet, recorder, log
from pykob.recorder import PlaybackState, Recorder
from pykob.config2 import Config, ConfigLoadError
from mkobkeytimewin import MKOBKeyTimeWin

NNBSP = "\u202f"  # narrow no-break space
LATCH_CODE = (-0x7FFF, +1)  # code sequence to force latching (close)
UNLATCH_CODE = (-0x7FFF, +2)  # code sequence to unlatch (open)


class MKOBMain:
    def __init__(self, tkroot, app_ver, mkactions, mkwindow, cfg: Config) -> None:
        self.app_ver = app_ver
        self._app_started: bool = False  # Set true by call from MKWindow when everything is started
        self._tkroot = tkroot
        self._ka = mkactions
        self._kw = mkwindow
        self._player: Optional[Recorder] = None
        self._player_file_to_play: Optional[str] = None  # Used to hold the file name if we have to wait
        self._player_fu = None
        self._player_vco: bool = False
        self._recorder: Optional[Recorder] = None
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
        self._show_packets: bool = False
        self._last_char_was_para: bool = False
        self._wire_data_received: bool = False

        self._internet_station_active = False  # True if a remote station is sending

        self._sender_ID = ""

        # For emitting code
        self._emit_code_queue = Queue()
        self._threadsStop: Event = Event()
        self._emit_code_thread = Thread(name="MKMain-EmitCode", target=self._emit_code_thread_run)

        self._internet: Optional[internet.Internet] = None
        self._after_iac = None  # Internet available check - after ID
        self._inet_was_availabe: bool = False
        self._kob: Optional[kob.KOB] = None
        self._create_internet(self._cfg)
        self._create_kob(self._cfg)
        self.do_morse_change()

        return

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
            err_msg_hndlr=self._net_err_msg_hndlr
        )
        # See if we have internet - that will update the status bar
        self._check_internet_available()
        if was_connected:
            self.toggle_connect()
        return

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
            virtual_closer_in_use=True,
            err_msg_hndlr=self._kob_err_msg_hndlr,
            keyCallback=self.from_key
        )
        self._kob.virtual_closer_is_open = vcloser
        if was_connected:
            self.toggle_connect()
        return

    def _create_player(self):
        self._player = Recorder(
            None,
            None,
            station_id=self._sender_ID,
            wire=self._wire,
            play_code_callback=self.from_recorder,
            play_sender_id_callback=self._ka.trigger_update_current_sender,
            play_station_list_callback=self._ka.trigger_update_station_active,
            play_wire_callback=self._ka.trigger_player_wire_change,
            play_finished_callback=self._on_playback_finished
        )
        return

    def _create_recorder(self):
        ts = recorder.get_timestamp()
        dt = datetime.fromtimestamp(ts / 1000.0)
        dateTimeStr = str("{:04}{:02}{:02}-{:02}{:02}").format(
            dt.year, dt.month, dt.day, dt.hour, dt.minute
        )
        targetFileName = "Session-" + dateTimeStr + ".json"
        log.info("Recording to '{}'".format(targetFileName))
        self._recorder = Recorder(
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

    def _emit_code_thread_run(self):
        while not self._threadsStop.is_set():
            # Read from the emit code queue
            try:
                emit_code_packet = self._emit_code_queue.get(True, 0.1)  # Blocks until packet available or 100ms (to check stop)
            except Empty as ex:
                continue  # Allow check of threadStop
            #
            code = emit_code_packet[0]
            code_source = emit_code_packet[1]
            sound_it = emit_code_packet[2]
            closer_open = emit_code_packet[3]
            done_callback = emit_code_packet[4]

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
                    sound = sound_it and closer_open
                    self._kob.soundCode(code, code_source, sound)
            if done_callback:
                self._tkroot.after(callback_delay, done_callback)
            pass
        log.debug("{} thread done.".format(threading.current_thread().name))
        return

    def _check_internet_available(self, realtime:bool=False) -> bool:
        """
        Use the internet object to check if internet is available.
        Update the status bar message and return the availability.

        realtime: True will get realtime status from Internet, else use cached value.
        """
        hi:bool
        if self._after_iac:
            self._kw.tkroot.after_cancel(self._after_iac)
            self._after_iac = None
        if realtime:
            hi = self._internet.check_internet_available()
            if not hi:
                self._kw.status_msg = "Internet not available"
            else:
                self._kw.clear_status_msg()
        else:
            hi = self._internet.internet_available
            if not hi and self._inet_was_availabe:
                self._kw.status_msg = "Internet not available"
            if hi and not self._inet_was_availabe:
                self._kw.clear_status_msg()

        if not hi:
            self._after_iac = self._kw.tkroot.after(2000, self._check_internet_available)
        else:
            self._after_iac = self._kw.tkroot.after(5000, self._check_internet_available)
        self._inet_was_availabe = hi
        return hi

    def _kob_err_msg_hndlr(self, msg:str) -> None:
        log.warn(msg)
        msgbox.showwarning(title=self.app_ver, message=msg)
        return

    def _net_err_msg_hndlr(self, msg:str) -> None:
        log.warn(msg)
        self._ka.trigger_reader_append_text("\n{}\n".format(msg))
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
        """
        Exit all of the modules.
        """
        try:
            self._threadsStop.set()
            if self._kob:
                self._kob.exit()
                self._kob = None
            if self._player:
                self._player.exit()
                self._player = None
            if self._recorder:
                self._recorder.exit()
                self._recorder = None
            if self._mreader:
                self._mreader.exit()
                self._mreader = None
            if self._msender:
                self._msender.exit()
                self._msender = None
            if self._internet:
                self._internet.exit()
                self._internet = None
            if self._emit_code_thread and self._emit_code_thread.is_alive():
                self._emit_code_thread.join(timeout=2.0)
                self._emit_code_thread = None
        finally:
            log.debug("MKOBMain - Done")
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
        return

    @property
    def Internet(self):
        return self._internet

    @property
    def Kob(self) -> Optional[kob.KOB]:
        return self._kob

    @property
    def Player(self) -> Optional[Recorder]:
        return self._player

    @property
    def Reader(self):
        return self._mreader

    @property
    def Recorder(self) -> Optional[Recorder]:
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
                self._threadsStop.wait(0.50)  # Needed to allow UTP packets to clear
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
        return

    def emit_code(self, code, code_source, sound_it=True, closer_open=True, done_callback=None):
        """
        Emit local code. That involves:
        1. Record code if recording is enabled
        2. Send code to the wire if connected

        This is used from the keyboard or indirectly from the key thread to emit code once they
        determine it should be emitted.

        It should be called by an event handler in response to a 'EVENT_EMIT_KEY_CODE' message,
        or from the keyboard sender.
        """
        emit_code_packet = [code, code_source, sound_it, closer_open, done_callback]
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
            True,  # Sound the code
            self._kob.virtual_closer_is_open,
            finished_callback
        )
        return

    def from_keyboard_vkey(self, code, sound_it, finished_callback=None):
        self.emit_code(
            code,
            kob.CodeSource.keyboard,
            sound_it,
            self._kob.virtual_closer_is_open,
            finished_callback
        )
        return

    def from_internet(self, code):
        """handle inputs received from the internet"""
        if self._connected.is_set():
            self._wire_data_received = True
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
        return

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
        return

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
        self._kw.vkey_closed = 1 if closed else 0
        self._kob.virtual_closer_is_open = not closed
        if not self._internet_station_active:
            if self._cfg.local:
                if not closed:
                    self._ka.handle_sender_update(self._cfg.station)  # Can call 'handle_' as this is run on the UI thread
                self._kob.virtual_closer_is_open = not closed
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
        return

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
        return

    def disconnect(self):
        """
        Disconnect if connected.
        """
        if self._connected.is_set():
            self.toggle_connect()
        return

    def toggle_connect(self):
        """
        Connect or disconnect when user clicks on the Connect button.

        # Okay to call 'handle...' in here, as this is run on main thread.
        """
        if not self._connected.is_set():
            # Connect
            self._sender_ID = ""
            self._wire_data_received = False
            self._ka.handle_clear_stations()
            inet_available = self._check_internet_available(True)  # Use method, rather than property, to get realtime status.
            if inet_available:
                # Close the key when connecting to avoid breaking into an active sender (if any).
                self.set_virtual_closer_closed(True)
                self._internet.monitor_IDs(
                    self._ka.trigger_update_station_active
                )  # Set callback for monitoring stations
                self._internet.monitor_sender(
                    self._ka.trigger_update_current_sender
                )  # Set callback for monitoring current sender
                self._kob.power_save(False)
                self._internet.connect(self._wire)
                self._connected.set()
            else:
                msg = "Internet not available. Unable to connect at this time."
                log.info("{}".format(msg))
                msgbox.showinfo(title=self.app_ver, message=msg)
        else:
            # Disconnect
            self._connected.clear()
            self._internet.monitor_IDs(None)  # don't monitor stations
            self._internet.monitor_sender(None)  # don't monitor current sender
            self._internet.disconnect(self._on_disconnect)
        return

    def _on_disconnect_followup(self, *args):
        log.debug("mkmain._on_disconnect_followup", 3)
        self._odc_fu = None
        if self._wire_data_received:
            self._mreader.decode(LATCH_CODE, use_flusher=False)
            self._mreader.flush()
            self._ka.trigger_reader_append_text("\n#####\n")
        # Sounder should be energized when disconnected.
        self._kob.energize_sounder(True, kob.CodeSource.local, from_disconnect=True)
        self._ka.trigger_station_list_clear()
        if self._kob.virtual_closer_is_open:
            # If the closer is open, Sounder should not be energized.
            self._kob.energize_sounder(False, kob.CodeSource.local, from_disconnect=True)
        self._wire_data_received = False
        self._internet_station_active = False
        return

    def _on_disconnect(self):
        # These should be false and blank from the 'disconnect', but make sure.
        self._internet_station_active = False
        self._sender_ID = ""
        if self._wire_data_received:
            self._mreader.flush()
        self._kob.power_save(False)
        if not self._odc_fu:
            self._odc_fu = self._tkroot.after(950, self._on_disconnect_followup)
        return

    def _op_playback_finished_fu(self):
        if self._player:  # Should be True, but just in case...
            file_path = self._player.source_file_path
            dirpath, filename = os.path.split(file_path)
            self._ka.handle_reader_append_text("\n\n[Done playing: {}]\n".format(filename))
            self._kw.clear_status_msg()
            self._kob.virtual_closer_is_open = self._player_vco

    def _on_playback_finished(self):
        # Called from the Player when playback is finished.
        self._player_fu = self._tkroot.after(950, self._op_playback_finished_fu)
        return

    # callback functions

    def _packet_callback(self, pckt_text):
        """
        Set as a callback for the Internet package to print packets
        """
        if self.show_packets:
            self._ka.trigger_reader_append_text(pckt_text)
        return

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
            self._last_char_was_para = True
        else:
            if self._last_char_was_para:
                txt += "\n"
            self._last_char_was_para = False
        txt += char
        self._ka.trigger_reader_append_text(txt)
        return

    def key_graph_is_active(self):
        """
        True if the key graph is currently active.
        """
        return self._key_graph_win and MKOBKeyTimeWin.active

    def _update_from_config(self, cfg:Config, ct:config2.ChangeType):
        log.debug("MKMain._update_from_config. CT:{}".format(ct), 2)
        try:
            self._set_on_cfg = False
            log.set_logging_level(cfg.logging_level)
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
                if cfg.server_url_changed:
                    self._create_internet(cfg)
                elif cfg.station_changed:
                    self._internet.set_officeID(cfg.station)
            # Update KOB
            self._kob.sound_local = cfg.local
            self._kob.sounder_power_save_secs = cfg.sounder_power_save
            if cfg.sound_changed or cfg.audio_type_changed:
                self._kob.change_audio(cfg.sound, cfg.audio_type)
            if cfg.interface_type_changed or cfg.serial_port_changed or cfg.gpio_changed:
                self._kob.change_hardware(cfg.interface_type, cfg.serial_port, cfg.gpio, cfg.sounder)
            elif cfg.sounder_changed:
                self._kob.use_sounder = cfg.sounder
        finally:
            self._set_on_cfg = True
        return

    def preferences_closed(self, prefsDialog):
        """
        The preferences (config) window returned.
        """
        log.debug("MKMain.preferences_closed.")
        if not prefsDialog.cancelled:
            cfg_from_prefs:Config = prefsDialog.cfg
            ct = cfg_from_prefs.get_changes_types()
            log.debug("mkm - Preferences Dialog closed. Change types: {}".format(ct), 1)
            if not ct == 0:
                self._cfg.copy_from(cfg_from_prefs)
                self._update_from_config(cfg_from_prefs, ct)
                if prefsDialog.save_pressed:
                    self.preferences_save()
            self._kw.set_app_title()
        return

    def preferences_load(self):
        """
        Load a new configuration.
        """
        log.debug("MKMain.preferences_load.")
        dir = self._cfg.get_directory()
        dir = dir if dir else ""
        name = self._cfg.get_name(True)
        name = name if name else ""
        pf = filedlg.askopenfilename(
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
                self._kw.set_app_title()
            except ConfigLoadError as err:
                msg = "Unable to load configuration: {}".format(pf)
                log.error("{}  Error: {}".format(msg, err))
                msgbox.showerror(title=self.app_ver, message=msg)
        return

    def preferences_load_global(self):
        """
        Load the global configuration.
        """
        log.debug("MKMain.preferences_load_global.")
        try:
            self._cfg.clear_dirty()
            self._cfg.set_using_global(True)
            self._cfg.load_from_global()
            self._update_from_config(self._cfg, config2.ChangeType.ANY)
            self._cfg.clear_dirty()
            self._kw.set_app_title()
        except ConfigLoadError as err:
                msg = "Unable to load Global configuration."
                log.error("{}  Error: {}".format(msg, err))
                msgbox.showerror(title=self.app_ver, message=msg)
        return

    def preferences_opening(self) -> Config:
        """
        The Preferences (config) Dialog is being opened.

        Return a config for it to use.
        """
        log.debug("MKMain.preferences_opening.")
        cfg_for_prefs = self._cfg.copy()
        if self._cfg.using_global():
            cfg_for_prefs.set_using_global(True)
        else:
            cfg_for_prefs.set_filepath(self._cfg.get_filepath())
        cfg_for_prefs.clear_dirty()
        return cfg_for_prefs

    def preferences_save(self):
        log.debug("MKMain.preferences_save.")
        if not self._cfg.get_filepath() and not self._cfg.using_global():
            # The config doesn't have a file path and it isn't global
            # call the SaveAs
            self.preferences_save_as()
        else:
            try:
                self._cfg.save_config()
            except Exception as err:
                msg = "Unable to save "
                if self._cfg.using_global():
                    msg += "Global configuration"
                else:
                    msg += "configuration: {}".format(self._cfg.get_filepath())
                log.error("{}  Error: {}".format(msg, err))
                msgbox.showerror(title=self.app_ver, message=msg)
        return

    def preferences_save_as(self):
        log.debug("MKMain.preferences_save_as.")
        dir = self._cfg.get_directory()
        dir = dir if dir else ""
        name = self._cfg.get_name(True)
        name = name if name else ""
        pf = filedlg.asksaveasfilename(
            title="Save As",
            initialdir=dir,
            initialfile=name,
            defaultextension=config2.PYKOB_CFG_EXT,
            filetypes=[("PyKOB Configuration", config2.PYKOB_CFG_EXT)],
        )
        if pf:
            try:
                self._cfg.set_using_global(False)
                self._cfg.save_config(pf)
                self._cfg.clear_dirty()
                self._kw.set_app_title()
            except Exception as err:
                msg = "Unable to save configuration: {}".format(pf)
                log.error("{}  Error: {}".format(msg, err))
                msgbox.showerror(title=self.app_ver, message=msg)
        return

    def preferences_save_global(self):
        log.debug("MKMain.preferences_save_global.")
        try:
            self._cfg.save_global()
            if self._cfg.using_global():
                self._cfg.clear_dirty()
                self._kw.set_app_title()
        except Exception as err:
            msg = "Unable to save Global configuration."
            log.error("{}  Error: {}".format(msg, err))
            msgbox.showerror(title=self.app_ver, message=msg)
        return

    def record_session(self):
        """
        Start recording if not already started.
        """
        if not self._recorder:
            self._create_recorder()
        msg = "Recording session to: {}".format(self._recorder.target_file_path)
        msgbox.showinfo(title=self.app_ver, message=msg)
        return

    def recording_end(self):
        msg = "Session was not being recorded."
        if self._recorder:
            r = self._recorder
            self._recorder = None
            msg = "Session recorded to: {}".format(r.target_file_path)
            r.playback_stop()
        msgbox.showinfo(title=self.app_ver, message=msg)
        return

    def _recording_play_followup(self):
        # Open the virtual closer to sound code
        self._player_vco = self._kob.virtual_closer_is_open
        self._kob.virtual_closer_is_open = True
        self._player.playback_start(list_data=False, max_silence=5)  # Limit the silence to 5 seconds
        return

    def _recording_play_wait_stop(self):
        if self._player and not self._player.playback_state == PlaybackState.idle:
            self._player_fu = self._tkroot.after(500, self._recording_play_wait_stop)
            return
        else:
            self._player = None
        self._create_player()
        self.disconnect()
        self._ka.handle_clear_stations() # okay to call directly as we are in a handler
        self._ka.handle_clear_reader_window()
        self._sender_ID = None
        dirpath, filename = os.path.split(self._player_file_to_play)
        msg = "Playing: {}".format(filename)
        self._ka.handle_reader_append_text("[{}\n".format(msg))
        self._kw.status_msg = msg
        self._player.source_file_path = self._player_file_to_play
        self._player_fu = self._tkroot.after(1500, self._recording_play_followup)
        return

    def recording_play(self, file_path:str):
        log.debug(" Play: {}".format(file_path))
        self._player_file_to_play = file_path
        if self._player and not self._player.playback_state == PlaybackState.idle:
            self._player.playback_stop()
            self._player_fu = self._tkroot.after(1500, self._recording_play_wait_stop)
        else:
            self._recording_play_wait_stop()
        return

    def reset_wire_state(self):
        """regain control of the wire"""
        self._internet_station_active = False
        return

    def show_key_graph(self):
        """
        Show the Key Timing graph.
        """
        if not (self._key_graph_win and MKOBKeyTimeWin.active):
            self._key_graph_win = MKOBKeyTimeWin(self._cwpm)
        self._key_graph_win.focus()
        return

    def update_sender(self, id):
        """display station ID in reader window when there's a new sender"""
        if id != self._sender_ID:  # new sender
            self._sender_ID = id
            self._ka.trigger_reader_append_text("\n<{}>".format(self._sender_ID))
        ### ZZZ not necessary if code speed recognition is disabled in pykob/morse.py
        ##        Reader = morse.Reader(
        ##                wpm=self._cfg.text_speed, codeType=self._cfg.code_type,
        ##                callback=readerCallback)  # reset to nominal code speed
        return
