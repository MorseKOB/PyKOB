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
from queue import Queue
from threading import Event, Thread

from pykob import config, config2, kob, morse, internet, recorder, log
from pykob.config2 import Config
from mkobkeytimewin import MKOBKeyTimeWin

NNBSP = "\u202f"  # narrow no-break space
LATCH_CODE = (-0x7FFF, +1)  # code sequence to force latching (close)
UNLATCH_CODE = (-0x7FFF, +2)  # code sequence to unlatch (open)


class MKOBMain:
    def __init__(self, app_ver, mkactions, mkwindow, cfg: Config) -> None:
        self.app_ver = app_ver
        self._ka = mkactions
        self._mreader = None  # Set by MKOBActions.doWPM
        self._msender = None  # Set by MKOBActions.doWPM
        self._kw = mkwindow
        self._cfg = cfg

        self._key_graph_win = None

        self._connected = Event()
        self._show_packets = False
        self._lastCharWasParagraph = False

        self._internet_station_active = False  # True if a remote station is sending

        self._sender_ID = ""
        self._cwpm = self._kw.cwpm
        self._twpm = self._kw.twpm

        # For emitting code
        self._emit_code_queue = Queue()
        self._emit_code_thread = Thread(
            name="MKMain-EmitCode", daemon=True, target=self._thread_emit_code
        )

        self._kob = None
        self._create_kob()
        self._internet = None
        self._create_internet()

        # Let the user know if 'invert key input' is enabled (typically only used for MODEM input)
        if self._cfg.invert_key_input:
            log.warn(
                "IMPORTANT! Key input signal invert is enabled (typically only used with a MODEM). "
                + "To enable/disable this setting use `Configure --iki`."
            )
        self._cfg.register_listener(self._cfg_change_listener, config2.ChangeType.any)

    def _cfg_change_listener(self, ct):
        """
        Adjust to changes to the configuration values.
        """
        log.debug("MKMain tracking all Changes. Change type: {}".format(ct))
        with self._cfg.notification_pauser() as muted_cfg: # Don't trigger change listeners...
            log.set_debug_level(muted_cfg.debug_level)
            if (ct & config2.ChangeType.hardware):
                self._create_kob()  # If the hardware changed, we need a new KOB instance.
            if (ct & config2.ChangeType.morse):
                self._kw.spacing = muted_cfg.spacing
                self._kw.twpm = muted_cfg.text_speed
                self._kw.cwpm = muted_cfg.min_char_speed
                # Update the Reader and Sender instances
                self.setwpm(cwpm=muted_cfg.min_char_speed, twpm=muted_cfg.text_speed)
            if (ct & config2.ChangeType.operations):
                self._kw.office_id = muted_cfg.station
                self._kw.wire_number = muted_cfg.wire
                self._create_internet()
            muted_cfg.clear_pending_notifications()

    def _create_internet(self):
        if self._internet:
            self._internet.exit()
        self._internet = internet.Internet(
            officeID=self._cfg.station,
            code_callback=self.from_internet,
            pckt_callback=self._packet_callback,
            appver=self.app_ver,
            server_url=self._cfg.server_url,
            mka=self._ka,
        )

    def _create_kob(self):
        if self._kob:
            self._kob.exit()
        self._kob = kob.KOB(
            portToUse=self._cfg.serial_port,
            useGpio=self._cfg.gpio,
            useAudio=self._cfg.sound,
            useSounder=self._cfg.sounder,
            invertKeyInput=self._cfg.invert_key_input,
            sounderPowerSaveSecs=self._cfg.sounder_power_save,
            keyCallback=self.from_key,
        )
        self._kob.virtualCloserIsOpen = False  # True if sending on key or keyboard

    def start(self):
        """
        Start the main processing.
        """
        ts = recorder.get_timestamp()
        dt = datetime.fromtimestamp(ts / 1000.0)
        dateTimeStr = str("{:04}{:02}{:02}-{:02}{:02}").format(
            dt.year, dt.month, dt.day, dt.hour, dt.minute
        )
        targetFileName = "Session-" + dateTimeStr + ".json"
        log.info("Record to '{}'".format(targetFileName))
        self._recorder = recorder.Recorder(
            targetFileName,
            None,
            station_id=self._sender_ID,
            wire=self._cfg.wire,
            play_code_callback=self.from_recorder,
            play_sender_id_callback=self._ka.trigger_update_current_sender,
            play_station_list_callback=self._ka.trigger_update_station_active,
            play_wire_callback=self._ka.trigger_player_wire_change,
        )
        self._emit_code_thread.start()
        # If the configuration indicates that an application should automatically connect -
        # connect to the currently configured wire.
        if self._cfg.auto_connect:
            self._ka.doConnect()  # Suggest a connect.

    @property
    def connected(self):
        """
        True if connected to a wire.
        """
        return self._connected.is_set()

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
    def Reader(self):
        return self._mreader
    @Reader.setter
    def Reader(self, morse_reader):
        self._mreader = morse_reader

    @property
    def Recorder(self):
        return self._recorder

    @property
    def Sender(self):
        return self._msender
    @Sender.setter
    def Sender(self, morse_sender):
        self._msender = morse_sender

    @property
    def wpm(self):
        return self._cwpm

    def setwpm(self, cwpm, twpm):
        self._cwpm = cwpm
        self._twpm = twpm
        self.Sender = morse.Sender(
            wpm=twpm,
            cwpm=cwpm,
            codeType=self._cfg.code_type,
            spacing=self._cfg.spacing
        )
        self.Reader = morse.Reader(
            wpm=twpm,
            cwpm=cwpm,
            codeType=self._cfg.code_type,
            callback=self.readerCallback,
        )
        if self.key_graph_is_active():
            self._key_graph_win.wpm = cwpm

    def _packet_callback(self, pckt_text):
        """
        Set as a callback for the Internet package to print packets
        """
        if self.show_packets:
            self._ka.trigger_reader_append_text(pckt_text)

    def _thread_emit_code(self):
        while True:
            # Read from the emit code queue
            emit_code_packet = (
                self._emit_code_queue.get()
            )  # Blocks until a packet is available
            #
            code = emit_code_packet[0]
            code_source = emit_code_packet[1]
            closer_open = emit_code_packet[2]
            done_callback = emit_code_packet[3]
            cb_arg = emit_code_packet[4]

            if closer_open:
                self.update_sender(self._cfg.station)
                self._mreader.decode(code)
                self._recorder.record(
                    code, code_source
                )  # ZZZ ToDo: option to enable/disable recording
                if self._connected.is_set() and self._cfg.remote:
                    self._internet.write(code)
                if self.key_graph_is_active():
                    self._key_graph_win.key_code(code)
            if self._cfg.local and not code_source == kob.CodeSource.key:
                # Don't call if from key. Local sounder handled in key processing.
                # Call even if closer closed in order to take the appropriate amount of time.
                self._kob.soundCode(code, code_source, closer_open)
            if done_callback:
                if cb_arg:
                    done_callback(cb_arg)
                else:
                    done_callback()

    def emit_code(
        self, code, code_source, closer_open=True, done_callback=None, cb_arg=None
    ):
        """
        Emit local code. That involves:
        1. Record code if recording is enabled
        2. Send code to the wire if connected

        This is used from the keyboard or indirectly from the key thread to emit code once they
        determine it should be emitted.

        It should be called by an event handler in response to a 'EVENT_EMIT_KEY_CODE' message,
        or from the keyboard sender.
        """
        emit_code_packet = [code, code_source, closer_open, done_callback, cb_arg]
        self._emit_code_queue.put(emit_code_packet)

    def from_key(self, code):
        """
        Handle inputs received from the external key.
        Only send if the circuit is open.
        Note: typically this will be the case, but it is possible to
        close the circuit from the GUI while the key's physical closer
        is still open.

        Called from the 'KOB-KeyRead' thread.
        """
        if len(code) > 0:
            if code[-1] == 1:  # special code for 'LATCH' (key/circuit closed)
                self._ka.trigger_circuit_close()
                return
            elif code[-1] == 2:  # special code for 'UNLATCH' (key/circuit open)
                self._ka.trigger_circuit_open()
                return
        if not self._internet_station_active and self._kob.virtualCloserIsOpen:
            self._ka.trigger_emit_key_code(code)

    def from_keyboard(self, code, finished_callback=None, cb_arg=None):
        """
        Handle inputs received from the keyboard sender.

        Called from the 'Keyboard-Send' thread.
        """
        if not self._internet_station_active:
            self.emit_code(
                code,
                kob.CodeSource.keyboard,
                self._kob.virtualCloserIsOpen,
                finished_callback,
                cb_arg,
            )

    def from_internet(self, code):
        """handle inputs received from the internet"""
        if self._connected.is_set():
            self._kob.soundCode(code, kob.CodeSource.wire)
            self._mreader.decode(code)
            self._recorder.record(code, kob.CodeSource.wire)
            if len(code) > 0 and code[-1] == +1:
                self._internet_station_active = False
            else:
                self._internet_station_active = True
            if self.key_graph_is_active():
                self._key_graph_win.wire_code(code)

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

    def virtualCloserClosed(self, closed):
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
        self._kob.virtualCloserIsOpen = not closed
        if not self._internet_station_active:
            if self._cfg.local:
                if not closed:
                    self._ka.handle_sender_update(
                        self._cfg.station
                    )  # Can call 'handle_' as this is run on the UI thread
                self._kob.energizeSounder(closed)
                self._mreader.decode(code)
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
            self._internet.connect(self._cfg.wire)
            self._connected.set()
        else:
            # Disconnect
            self._connected.clear()
            self._internet.monitor_IDs(None)  # don't monitor stations
            self._internet.monitor_sender(None)  # don't monitor current sender
            self._internet.disconnect(self._on_disconnect)

    def _on_disconnect(self):
        # These should be false and blank from the 'disconnect', but make sure.
        self._internet_station_active = False
        self._sender_ID = ""
        self._ka.trigger_station_list_clear()
        self._mreader.flush()
        self._mreader.decode(LATCH_CODE, use_flusher=False)
        self._mreader.flush()
        self._ka.trigger_reader_append_text("\n#####\n")
        if not self._kob.virtualCloserIsOpen:
            self._kob.energizeSounder(
                True
            )  # Sounder should be energized when disconnected.

    def change_wire(self, wire: int):
        """
        Change the current wire. If connected, drop the current connection and
        connect to the new wire.
        """
        # Disconnect, change wire, reconnect.
        was_connected = self._connected.is_set()
        self.disconnect()
        self._recorder.wire = wire
        if was_connected:
            time.sleep(0.50)  # Needed to allow UTP packets to clear
            self.toggle_connect()

    # callback functions

    def update_sender(self, id):
        """display station ID in reader window when there's a new sender"""
        if id != self._sender_ID:  # new sender
            self._sender_ID = id
            self._ka.trigger_reader_append_text("\n<{}>".format(self._sender_ID))
        ### ZZZ not necessary if code speed recognition is disabled in pykob/morse.py
        ##        Reader = morse.Reader(
        ##                wpm=self._cfg.text_speed, codeType=self._cfg.code_type,
        ##                callback=readerCallback)  # reset to nominal code speed

    def readerCallback(self, char, spacing):
        """display characters returned from the decoder"""
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

    def preferences_closed(self):
        """
        The properties window returned. Our change listener will perform updates.
        """
        log.debug("mkm - Preferences Dialog closed.")
