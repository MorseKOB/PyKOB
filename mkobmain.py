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
from threading import Event, RLock, Thread
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
    def __init__(self, tkroot, app_ver, mkactions, mkwindow, cfg: Config, record_filepath: Optional[str]=None) -> None:
        self.app_ver = app_ver
        self._app_started: bool = False  # Set true by call from MKWindow when everything is started
        self._tkroot = tkroot
        self._ka = mkactions
        self._kw = mkwindow
        self._cfg = cfg
        self._set_on_cfg:bool = False # Flag to control setting values on our config
        self._code_type = None  # Set by do_morse_change
        self._cwpm = 0  # Set by do_morse_change
        self._twpm = 0  # Set by do_morse_change
        self._spacing = None  # Set by do_morse_change
        self._record_file_initial = record_filepath

        self._key_graph_win = None

        self._wire = self._cfg.wire
        self._connected = Event()
        self._odc_fu = None
        self._show_packets: bool = False
        self._last_char_was_para: bool = False
        self._wire_data_received: bool = False

        self._internet_station_active = False  # True if connected and a remote station is sending

        self._sender_ID = ""

        # For emitting code
        self._emit_code_queue = Queue()
        self._shutdown: Event = Event()
        self._thread_emit_code = Thread(name="MKMain-EmitCode", target=self._thread_emit_code_body)

        # The Class Instances (Objects) we rely on...
        self._internet: Optional[internet.Internet] = None
        self._internet_guard: RLock = RLock()
        self._after_iac = None  # Internet available check - after ID
        self._inet_was_availabe: bool = False
        self._kob: Optional[kob.KOB] = None
        self._kob_guard: RLock = RLock()
        self._mreader = None  # Set by do_morse_change
        self._mreader_guard: RLock = RLock()
        self._msender = None  # Set by do_morse_change
        self._msender_guard: RLock = RLock()
        self._player: Optional[Recorder] = None
        self._player_guard: RLock = RLock()
        self._player_file_to_play: Optional[str] = None  # Used to hold the file name if we have to wait
        self._player_fu = None
        self._player_vco: bool = False
        self._recorder: Optional[Recorder] = None
        self._recorder_guard: RLock = RLock()

        return

    def _create_internet(self, cfg:Config):
        was_connected = self._connected.is_set()
        with self._internet_guard:
            if self._internet:
                if was_connected:
                    self.disconnect()
                self._internet.shutdown()
            self._internet = internet.Internet(
                officeID=cfg.station,
                code_callback=self._from_internet,
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
        inet = self.Internet
        if inet and was_connected:
            self.disconnect()
        with self._kob_guard:
            if self._kob:
                vcloser = self._kob.virtual_closer_is_open
                self._kob.shutdown()
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
                keyCallback=self._from_key
            )
            self._kob.virtual_closer_is_open = vcloser
        kob_ = self.Kob
        if was_connected:
            self.toggle_connect()
        else:
            kob_.internet_circuit_closed = not self._internet_station_active
            kob_.wire_connected = False
        return

    def _create_player(self):
        with self._player_guard:
            if not self._player is None:
                self._player.shutdown()
                self._player.exit()
            self._player = Recorder(
                None,
                None,
                station_id=self._sender_ID,
                wire=self._wire,
                play_code_callback=self._from_recorder,
                play_sender_id_callback=self._ka.trigger_current_sender_update,
                play_station_list_callback=self._ka.trigger_station_active_update,
                play_wire_callback=self._ka.trigger_player_wire_change,
                play_finished_callback=self._on_playback_finished
            )
        return

    def _create_recorder(self, filename=None):
        targetFileName = recorder.add_ext_if_needed(filename) if not filename is None else recorder.generate_session_recording_name()
        log.info("Recording to '{}'".format(targetFileName))
        with self._recorder_guard:
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

    def _thread_emit_code_body(self):
        while not self._shutdown.is_set():
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
                    self.Reader.decode(code)
                    rec = self.Recorder
                    if rec:
                        rec.record(code, code_source)
                    if self._connected.is_set() and self._cfg.remote:
                        inet = self.Internet
                        if inet:
                            inet.write(code)
                    if self.key_graph_is_active():
                        self._key_graph_win.key_code(code)
                if self._cfg.local and not code_source == kob.CodeSource.key:
                    # Don't call if from key. Local sounder handled in key processing.
                    # Call even if closer closed in order to take the appropriate amount of time.
                    sound = sound_it and closer_open
                    kob_ = self.Kob
                    if kob_:
                        kob_.soundCode(code, code_source, sound)
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
        inet = self.Internet
        if realtime:
            if inet:
                hi = inet.check_internet_available()
            if not hi:
                self._ka.trigger_status_msg_set("Internet not available")
            else:
                self._ka.trigger_status_msg_clear()
        else:
            if inet:
                hi = inet.internet_available
            if not hi and self._inet_was_availabe:
                self._ka.trigger_status_msg_set("Internet not available")
            if hi and not self._inet_was_availabe:
                self._ka.trigger_status_msg_clear()

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

    def _set_internet_station_active(self, active:bool) -> None:
        self._internet_station_active = active
        kob_ = self.Kob
        if kob_:
            kob_.internet_circuit_closed = not active
        return


    def exit(self):
        """
        Exit all of the modules.
        """
        try:
            log.debug("mkmain.exit - 1", 3)
            self.shutdown()
            log.debug("mkmain.exit - 2", 3)
            # Order is important
            with self._internet_guard:
                log.debug("mkmain.exit - 3", 3)
                if self._internet:
                    log.debug("mkmain.exit - 3b", 3)
                    self._internet.exit()
            with self._player_guard:
                log.debug("mkmain.exit - 4", 3)
                if self._player:
                    log.debug("mkmain.exit - 4b", 3)
                    self._player.exit()
            with self._recorder_guard:
                log.debug("mkmain.exit - 5", 3)
                if self._recorder:
                    log.debug("mkmain.exit - 5b", 3)
                    self._recorder.exit()
            with self._mreader_guard:
                log.debug("mkmain.exit - 6", 3)
                if self._mreader:
                    log.debug("mkmain.exit - 6b", 3)
                    self._mreader.exit()
            with self._msender_guard:
                log.debug("mkmain.exit - 7", 3)
                if self._msender:
                    log.debug("mkmain.exit - 7b", 3)
                    self._msender.exit()
            if self._thread_emit_code and self._thread_emit_code.is_alive():
                self._thread_emit_code.join(timeout=2.0)
                self._thread_emit_code = None
            with self._kob_guard:
                log.debug("mkmain.exit - 8", 3)
                if self._kob:
                    log.debug("mkmain.exit - 8b", 3)
                    self._kob.exit()
        finally:
            log.debug("MKOBMain - Done")
        return

    def shutdown(self):
        """
        Initiate shutdown of our operations (and don't start anything new),
        but DO NOT BLOCK.
        """
        log.debug("mkmain.shutdown - 1", 3)
        self._shutdown.set()
        log.debug("mkmain.shutdown - 2", 3)
        with self._internet_guard:
            log.debug("mkmain.shutdown - 3", 3)
            if self._internet:
                log.debug("mkmain.shutdown - 3b", 3)
                self._internet.shutdown()
        with self._player_guard:
            log.debug("mkmain.shutdown - 4", 3)
            if self._player:
                log.debug("mkmain.shutdown - 4b", 3)
                self._player.shutdown()
        with self._msender_guard:
            log.debug("mkmain.shutdown - 5", 3)
            if self._msender:
                log.debug("mkmain.shutdown - 5b", 3)
                self._msender.shutdown()
        with self._recorder_guard:
            log.debug("mkmain.shutdown - 6", 3)
            if self._recorder:
                log.debug("mkmain.shutdown - 6b", 3)
                self._recorder.shutdown()
        with self._mreader_guard:
            log.debug("mkmain.shutdown - 7", 3)
            if self._mreader:
                log.debug("mkmain.shutdown - 7b", 3)
                self._mreader.shutdown()
        with self._kob_guard:
            log.debug("mkmain.shutdown - 8", 3)
            if self._kob:
                log.debug("mkmain.shutdown - 8b", 3)
                self._kob.message_receiver = None
                self._kob.shutdown()
        return

    def start(self):
        """
        Start the main processing.
        """
        self._create_internet(self._cfg)
        self._create_kob(self._cfg)
        self.do_morse_change()
        self._thread_emit_code.start()
        #
        # If operational values change, set them on our config
        self._set_on_cfg = True
        #
        # MKOB app is now considered to be started.
        self._app_started = True
        log.debug("MKOBMain: App started.")
        self.set_virtual_closer_closed(True)
        #
        # If the configuration indicates that an application should automatically connect -
        # connect to the currently configured wire.
        if self._cfg.auto_connect:
            log.debug("MKOBMain: Auto-connect.")
            self._ka.doConnect()  # Suggest a connect.
        #
        # If requested to initially record the session, start it.
        if self._record_file_initial:
            self.record_session(self._record_file_initial, show_msgbox=False)
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
        inet = None
        with self._internet_guard:
            inet = self._internet
        return inet

    @property
    def Kob(self) -> Optional[kob.KOB]:
        kob_ = None
        with self._kob_guard:
            kob_ = self._kob
        return kob_

    @property
    def Player(self) -> Optional[Recorder]:
        with self._player_guard:
            return self._player

    @property
    def Reader(self):
        with self._mreader_guard:
            return self._mreader

    @property
    def Recorder(self) -> Optional[Recorder]:
        recorder = None
        with self._recorder_guard:
            recorder = self._recorder
        return recorder

    @property
    def Sender(self):
        with self._msender_guard:
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
        if wire < 0:  # protect against invalid values.
            wire = 0
        if not wire == self._wire:
            # Disconnect, change wire, reconnect.
            log.debug("mkm - change_wire: {}->{}".format(self._wire, wire))
            was_connected = self._connected.is_set()
            self._wire = wire
            self.disconnect()
            rec = self.Recorder
            if rec:
                rec.wire = wire
            if not self._wire == 0:
                self._kw.connect_enable(True)
                if was_connected:
                        self._shutdown.wait(0.50)  # Needed to allow UTP packets to clear
                        self.toggle_connect()
            else:
                self._kw.connect_enable(False)
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
        if self._shutdown.is_set():
            return
        emit_code_packet = [code, code_source, sound_it, closer_open, done_callback]
        self._emit_code_queue.put(emit_code_packet)
        return

    def _from_key(self, code):
        """
        Handle inputs received from the external key.
        Only send if the circuit is open.
        Note: typically this will be the case, but it is possible to
        close the circuit from the GUI while the key's physical closer
        is still open.

        Called from the 'KOB-KeyRead' thread.
        """
        if self._shutdown.is_set():
            return
        log.debug("MKOBMain.from_key: {}".format(code), 3)
        if len(code) > 0:
            if code[-1] == 1:  # special code for 'LATCH' (key/circuit closed)
                self._ka.trigger_circuit_close()
                return
            elif code[-1] == 2:  # special code for 'UNLATCH' (key/circuit open)
                self._ka.trigger_circuit_open()
                return
            kob_ = self.Kob
            if kob_ and not self._internet_station_active and kob_.virtual_closer_is_open:
                self._ka.trigger_emit_key_code(code)
        return

    def from_keyboard(self, code, finished_callback=None):
        """
        Handle inputs received from the keyboard sender.

        Called from the Keyboard-Sender.
        """
        if self._shutdown.is_set():
            return
        kob_ = self.Kob
        if kob_:
            self.emit_code(
                code,
                kob.CodeSource.keyboard,
                True,  # Sound the code
                kob_.virtual_closer_is_open,
                finished_callback
            )
        return

    def from_keyboard_vkey(self, code, sound_it, finished_callback=None):
        if self._shutdown.is_set():
            return
        kob_ = self.Kob
        if kob_:
            self.emit_code(
                code,
                kob.CodeSource.keyboard,
                sound_it,
                kob_.virtual_closer_is_open,
                finished_callback
            )
        return

    def _from_internet(self, code):
        """handle inputs received from the internet"""
        if self._shutdown.is_set():
            return
        kob_ = self.Kob
        rec = self.Recorder
        if self._connected.is_set() and not self._shutdown.is_set():
            self._wire_data_received = True
            if kob_:
                kob_.soundCode(code, kob.CodeSource.wire)
            self.Reader.decode(code)
            if rec:
                rec.record(code, kob.CodeSource.wire)
            if len(code) > 0 and code[-1] == +1:
                self._set_internet_station_active(False)
            else:
                self._set_internet_station_active(True)
            if self.key_graph_is_active():
                self._key_graph_win.wire_code(code)
        else:
            self._set_internet_station_active(False)
        return

    def _from_recorder(self, code, source=None):
        """
        Handle inputs received from the recorder during playback.
        """
        if self._shutdown.is_set():
            return
        kob_ = self.Kob
        if self._connected.is_set():
            self.disconnect()
        if kob_:
            kob_.soundCode(code, kob.CodeSource.player)
        self.Reader.decode(code)
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
        if self._shutdown.is_set():
            return
        kob_ = self.Kob
        rec = self.Recorder
        if kob_:
            kob_.virtual_closer_is_open = not closed
        if not self._internet_station_active:
            if self._cfg.local:
                if not closed and self._connected.is_set():
                    self._ka.trigger_current_sender_update(self._cfg.station)
                self.Reader.decode(code)
            if rec:
                rec.record(code, kob.CodeSource.local)
        if self._connected.is_set() and self._cfg.remote:
            inet = self.Internet
            if inet:
                inet.write(code)
        if closed:
            # Latch
            self.Reader.flush()
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
            with self._msender_guard:
                self._msender = morse.Sender(
                    wpm=twpm,
                    cwpm=cwpm,
                    codeType=code_type,
                    spacing=spacing
                )
            with self._mreader_guard:
                self._mreader = morse.Reader(
                    wpm=twpm,
                    cwpm=cwpm,
                    codeType=code_type,
                    callback=self._reader_callback,
                )
            kob_ = self._kob
            if kob_:
                kob_.keyer_dit_len = self._msender.dot_len
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
        if self._shutdown.is_set():
            return
        log.debug("mkmain.disconnect", 3)
        if self._connected.is_set():
            self.toggle_connect()
        return

    def toggle_connect(self):
        """
        Connect or disconnect when user clicks on the Connect button.

        # Okay to call 'handle...' in here, as this is run on main thread.
        """
        if self._shutdown.is_set():
            return
        log.debug("mkmain.toggle_connect", 3)
        kob_ = self.Kob
        inet = self.Internet
        if not self._connected.is_set():
            # Connect
            log.debug("mkmain.toggle_connect - connect", 3)
            if self._wire == 0:
                log.debug("mkmain.toggle_connect - connect NOT ALLOWED on Wire-0")
                self._kw.connect_enable(False)
                return
            self._sender_ID = ""
            self._wire_data_received = False
            self._ka.handle_stations_clear()
            inet_available = self._check_internet_available(True)  # Use method, rather than property, to get realtime status.
            if inet_available:
                # Close the key when connecting to avoid breaking into an active sender (if any).
                self.set_virtual_closer_closed(True)
                if inet:
                    inet.monitor_IDs(
                        self._ka.trigger_station_active_update
                    )  # Set callback for monitoring stations
                    inet.monitor_sender(
                        self._ka.trigger_current_sender_update
                    )  # Set callback for monitoring current sender
                self._set_internet_station_active(False)
                if kob_:
                    kob_.power_save(False)
                    kob_.wire_connected = True
                if inet:
                    inet.connect(self._wire)
                self._connected.set()
            else:
                msg = "Internet not available. Unable to connect at this time."
                log.info("{}".format(msg))
                msgbox.showinfo(title=self.app_ver, message=msg)
        else:
            # Disconnect
            log.debug("mkmain.toggle_connect - disconnect", 3)
            self._connected.clear()
            if inet:
                inet.monitor_IDs(None)  # don't monitor stations
                inet.monitor_sender(None)  # don't monitor current sender
                inet.disconnect(self._on_disconnect)
            if kob_:
                kob_.wire_connected = False
        self._kw.connected_set(self.connected)
        return

    def _on_disconnect_followup(self, *args):
        if self._shutdown.is_set():
            return
        log.debug("mkmain._on_disconnect_followup", 3)
        self._odc_fu = None
        if self._wire_data_received:
            self.Reader.decode(LATCH_CODE, use_flusher=False)
            self.Reader.flush()
            self._ka.trigger_reader_append_text("\n#####\n")
        # Sounder should be energized when disconnected.
        kob_ = self.Kob
        if kob_:
            kob_.energize_sounder(not self._kob.virtual_closer_is_open, kob.CodeSource.local, from_disconnect=True)
        self._ka.trigger_station_list_clear()
        self._wire_data_received = False
        self._set_internet_station_active(False)
        return

    def _on_disconnect(self):
        if self._shutdown.is_set():
            return
        # These should be false and blank from the 'disconnect', but make sure.
        log.debug("mkmain._on_disconnect", 3)
        self._set_internet_station_active(False)
        self._sender_ID = ""
        if self._wire_data_received:
            self.Reader.flush()
        kob_ = self.Kob
        if kob_:
            kob_.power_save(False)
        if not self._odc_fu:
            self._odc_fu = self._tkroot.after(950, self._on_disconnect_followup)
        if self._wire == 0:
            self._kw.connect_enable(False)
        return

    def _op_playback_finished_fu(self):
        if self._shutdown.is_set():
            return
        if self.Player:  # Should be True, but just in case...
            file_path = self.Player.source_file_path
            dirpath, filename = os.path.split(file_path)
            self._ka.trigger_reader_append_text("\n\n[Done playing: {}]\n".format(filename))
            self._ka.trigger_status_msg_clear()
            kob_ = self.Kob
            if kob_:
                kob_.virtual_closer_is_open = self._player_vco
            pass
        return

    def _on_playback_finished(self):
        # Called from the Player when playback is finished.
        if self._shutdown.is_set():
            return
        self._player_fu = self._tkroot.after(950, self._op_playback_finished_fu)
        return

    # callback functions

    def _packet_callback(self, pckt_text):
        """
        Set as a callback for the Internet package to print packets
        """
        if self._shutdown.is_set():
            return
        if self.show_packets:
            self._ka.trigger_reader_append_text(pckt_text)
        return

    def _reader_callback(self, char, spacing):
        """display characters returned from the decoder"""
        if self._shutdown.is_set():
            return
        rec = self._recorder
        if rec:
            rec.record([], "", text=char)
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
            kob_ = self.Kob
            inet = self.Internet
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
                    if inet:
                        inet.set_officeID(cfg.station)
            # Update KOB
            if kob_:
                kob_.sound_local = cfg.local
                kob_.sounder_power_save_secs = cfg.sounder_power_save
                if cfg.sound_changed or cfg.audio_type_changed:
                    kob_.change_audio(cfg.sound, cfg.audio_type)
                if cfg.interface_type_changed or cfg.serial_port_changed or cfg.gpio_changed:
                    kob_.change_hardware(cfg.interface_type, cfg.serial_port, cfg.gpio, cfg.sounder)
                elif cfg.sounder_changed:
                    kob_.use_sounder = cfg.sounder
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

    def record_session(self, filepath: Optional[str] = None, show_msgbox: bool=True):
        """
        Start recording if not already started.
        """
        rec = self.Recorder
        if not rec or filepath:
            self._create_recorder(filepath)
        msg = "Recording session to: {}".format(self._recorder.target_file_path)
        self._ka.trigger_status_msg_set(msg)
        if show_msgbox:
            msgbox.showinfo(title=self.app_ver, message=msg)
        return

    def recording_end(self):
        msg = "Session was not being recorded."
        rec = self._recorder
        if rec:
            self._recorder = None
            msg = "Session recorded to: {}".format(rec.target_file_path)
            rec.playback_stop()
        self._ka.trigger_status_msg_set(msg)
        msgbox.showinfo(title=self.app_ver, message=msg)
        self.tkroot.after(10000, self._ka.trigger_status_msg_clear)
        return

    def _recording_play_followup(self):
        if self._shutdown.is_set():
            return
        kob_ = self._kob
        plyr = self.Player
        self._player_vco = False
        if kob_:
            self._player_vco = self._kob.virtual_closer_is_open
            self._kob.virtual_closer_is_open = False
        if plyr:
            plyr.playback_start(list_data=False, max_silence=5)  # Limit the silence to 5 seconds
        return

    def _recording_play_wait_stop(self):
        if self._shutdown.is_set():
            return
        plyr = self.Player
        if plyr and not plyr.playback_state == PlaybackState.idle:
            self._player_fu = self._tkroot.after(500, self._recording_play_wait_stop)
            return
        self._create_player()
        self.disconnect()
        self._ka.trigger_station_list_clear()
        self._ka.trigger_reader_clear()
        self._sender_ID = None
        dirpath, filename = os.path.split(self._player_file_to_play)
        msg = "Playing: {}".format(filename)
        self._ka.trigger_reader_append_text("[{}\n".format(msg))
        self._ka.trigger_status_msg_set(msg)
        plyr = self.Player
        if plyr:
            plyr.source_file_path = self._player_file_to_play
        self._player_fu = self._tkroot.after(1500, self._recording_play_followup)
        return

    def recording_play(self, file_path:str):
        if self._shutdown.is_set():
            return
        plyr = self.Player
        log.debug(" Play: {}".format(file_path))
        self._player_file_to_play = file_path
        if plyr and not plyr.playback_state == PlaybackState.idle:
            plyr.playback_stop()
            self._player_fu = self._tkroot.after(1500, self._recording_play_wait_stop)
        else:
            self._recording_play_wait_stop()
        return

    def reset_wire_state(self):
        """regain control of the wire"""
        self._set_internet_station_active(False)
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
        if self._shutdown.is_set():
            return
        if id != self._sender_ID:  # new sender
            self._sender_ID = id
            self._ka.trigger_reader_append_text("\n<{}>".format(self._sender_ID))
        return
