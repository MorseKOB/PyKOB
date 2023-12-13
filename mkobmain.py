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
from mkobkeytimewin import MKOBKeyTimeWin

NNBSP = "\u202f"  # narrow no-break space
LATCH_CODE = (-0x7fff, +1)  # code sequence to force latching (close)
UNLATCH_CODE = (-0x7fff, +2)  # code sequence to unlatch (open)

class MKOBMain:
    def __init__(self, mkactions, mkstationlist, mkwindow):
        self.__ka = mkactions
        self.__mreader = None  # Set by MKOBActions.doWPM
        self.__msender = None  # Set by MKOBActions.doWPM
        self.__station_list = mkstationlist
        self.__kw = mkwindow
        self.__wpm = mkwindow.wpm

        self.__key_graph_win = None

        self.__connected = False
        self.__show_packets = False
        self.__lastCharWasParagraph = False

        self.__local_loop_active = False  # True if sending on key or keyboard
        self.__internet_station_active = False  # True if a remote station is sending

        self.__sender_ID = ""

        """
        Initialize the main class. This must be called by the main window class once all windows,
        menus, etc. are created, configured and ready.
        """
        self.__kob = kob.KOB(
                portToUse=config.serial_port, useGpio=config.gpio, interfaceType=config.interface_type,
                useAudio=config.sound, keyCallback=self.from_key)
        self.__internet = internet.Internet(config.station, code_callback=self.from_internet,
                                            pckt_callback=self.__packet_callback, mka=self.__ka)
        # Let the user know if 'invert key input' is enabled (typically only used for MODEM input)
        if config.invert_key_input:
            log.warn("IMPORTANT! Key input signal invert is enabled (typically only used with a MODEM). " + \
                "To enable/disable this setting use `Configure --iki`.")
        ts = recorder.get_timestamp()
        dt = datetime.fromtimestamp(ts / 1000.0)
        dateTimeStr = str("{:04}{:02}{:02}-{:02}{:02}").format(dt.year, dt.month, dt.day, dt.hour, dt.minute)
        targetFileName = "Session-" + dateTimeStr + ".json"
        log.info("Record to '{}'".format(targetFileName))
        self.__recorder = recorder.Recorder(targetFileName, None, station_id=self.__sender_ID, wire=config.wire, \
            play_code_callback=self.from_recorder, \
            play_sender_id_callback=self.__ka.trigger_update_current_sender, \
            play_station_list_callback=self.__ka.trigger_update_station_active, \
            play_wire_callback=self.__ka.trigger_player_wire_change)
        # If the configuration indicates that an application should automatically connect -
        # connect to the currently configured wire.
        if config.auto_connect:
            self.__ka.doConnect() # Suggest a connect.

    @property
    def connected(self):
        """
        True if connected to a wire.
        """
        return self.__connected

    @property
    def show_packets(self):
        """
        True if the user requested the received and sent packets be displayed.
        """
        return self.__show_packets

    @show_packets.setter
    def show_packets(self, b: bool):
        """
        Set whether to display the received and sent packets.
        """
        self.__show_packets = b

    @property
    def Internet(self):
        return self.__internet

    @property
    def Reader(self):
        return self.__mreader

    @Reader.setter
    def Reader(self, morse_reader):
        self.__mreader = morse_reader

    @property
    def Recorder(self):
        return self.__recorder

    @property
    def Sender(self):
        return self.__msender

    @Sender.setter
    def Sender(self, morse_sender):
        self.__msender = morse_sender

    @property
    def StationList(self):
        return self.__station_list

    @property
    def wpm(self):
        return self.__wpm

    @wpm.setter
    def wpm(self, v):
        self.__wpm = v
        if self.key_graph_is_active():
            self.__key_graph_win.wpm = v

    def __packet_callback(self, pckt_text):
        """
        Set as a callback for the Internet package to print packets
        """
        if self.show_packets:
            self.__ka.trigger_reader_append_text(pckt_text)

    def set_local_loop_active(self, state):
        """
        Set local_loop_active state

        True: Key or Keyboard active (Ciruit Closer OPEN)
        False: Circuit Closer (physical and virtual) CLOSED
        """
        self.__local_loop_active = state
        log.debug("local_loop_active:{}".format(state))

    def emit_code(self, code, code_source):
        """
        Emit local code. That involves:
        1. Record code if recording is enabled
        2. Send code to the wire if connected

        This is used indirectly from the key or the keyboard threads to emit code once they
        determine it should be emitted.

        It should be called by an event handler in response to a 'EVENT_EMIT_KEY_CODE' or
        'EVENT_EMIT_KB_CODE' message.
        """
        self.update_sender(config.station)
        self.__mreader.decode(code)
        self.__recorder.record(code, code_source) # ZZZ ToDo: option to enable/disable recording
        if config.local:
            self.__kob.soundCode(code, code_source)
        if self.__connected and config.remote:
            self.__internet.write(code)
        if self.key_graph_is_active():
            self.__key_graph_win.key_code(code)

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
            if code[-1] == 1: # special code for closer/circuit closed
                self.__ka.trigger_circuit_close()
                return
            elif code[-1] == 2: # special code for closer/circuit open
                self.__ka.trigger_circuit_open()
                return
        if not self.__internet_station_active and self.__local_loop_active:
            self.__ka.trigger_emit_key_code(code)

    def from_keyboard(self, code):
        """
        Handle inputs received from the keyboard sender.
        Only send if the circuit is open.

        Called from the 'Keyboard-Send' thread.
        """
        if not self.__internet_station_active and self.__local_loop_active:
            self.__ka.trigger_emit_kb_code(code)

    def from_internet(self, code):
        """handle inputs received from the internet"""
        if self.__connected:
            self.__kob.soundCode(code, kob.CodeSource.wire)
            self.__mreader.decode(code)
            self.__recorder.record(code, kob.CodeSource.wire)
            if len(code) > 0 and code[-1] == +1:
                self.__internet_station_active = False
            else:
                self.__internet_station_active = True
            if self.key_graph_is_active():
                self.__key_graph_win.wire_code(code)


    def from_recorder(self, code, source=None):
        """
        Handle inputs received from the recorder during playback.
        """
        if self.__connected:
            self.disconnect()
        self.__kob.soundCode(code, kob.CodeSource.player)
        self.__mreader.decode(code)
        if self.key_graph_is_active():
            self.__key_graph_win.key_code(code)

    def circuit_closer_closed(self, state):
        """
        Handle change of Circuit Closer state.
        This must be called from the GUI thread handling the Circuit-Closer checkbox,
        the ESC keyboard shortcut, or by posting a message (from the Key handler).

        A state of:
        True: 'latch'
        False: 'unlatch'

        """
        code = LATCH_CODE if state == 1 else UNLATCH_CODE
        if not self.__internet_station_active:
            if config.local:
                self.__ka.handle_sender_update(config.station) # Okay to call 'handle_...' as this is run on the main thread
                self.__kob.soundCode(code, kob.CodeSource.key)
                self.__mreader.decode(code)
            self.__recorder.record(code, kob.CodeSource.local)
        if self.__connected and config.remote:
            self.__internet.write(code)
        if len(code) > 0:
            if code[-1] == 1:
                # Unlatch
                self.set_local_loop_active(False)
                self.__mreader.flush()
            elif code[-1] == 2:
                # Latch
                self.set_local_loop_active(True)
        self.__kw.circuit_closer = (1 if not self.__local_loop_active else 0)
        if self.key_graph_is_active():
            if state:
                self.__key_graph_win.key_closed()
            else:
                self.__key_graph_win.key_opened()

    def disconnect(self):
        """
        Disconnect if connected.
        """
        if self.__connected:
            self.toggle_connect()

    def toggle_connect(self):
        """connect or disconnect when user clicks on the Connect button"""
        if not self.__connected:
            self.__sender_ID = ""
            self.__ka.trigger_station_list_clear()
            self.__internet.monitor_IDs(self.__ka.trigger_update_station_active) # Set callback for monitoring stations
            self.__internet.monitor_sender(self.__ka.trigger_update_current_sender) # Set callback for monitoring current sender
            self.__internet.connect(config.wire)
            self.__connected = True
        else:
            self.__connected = False
            self.__internet.monitor_IDs(None) # don't monitor stations
            self.__internet.monitor_sender(None) # don't monitor current sender
            self.__internet.disconnect()
            self.__mreader.flush()
            if not self.__local_loop_active:
                self.__kob.soundCode(LATCH_CODE)
                self.__mreader.decode(LATCH_CODE)
            self.__sender_ID = ""
            self.__ka.trigger_station_list_clear()
        self.__internet_station_active = False

    def change_wire(self):
        """
        Change the current wire. If connected, drop the current connection and
        connect to the new wire.
        """
        # Disconnect, change wire, reconnect.
        was_connected = self.__connected
        self.disconnect()
        self.__recorder.wire = config.wire
        if was_connected:
            time.sleep(0.350) # Needed to allow UTP packets to clear
            self.toggle_connect()


    # callback functions

    def update_sender(self, id):
        """display station ID in reader window when there's a new sender"""
        if id != self.__sender_ID:  # new sender
            self.__sender_ID = id
            self.__ka.trigger_reader_append_text("\n\n<{}>".format(self.__sender_ID))
        ### ZZZ not necessary if code speed recognition is disabled in pykob/morse.py
        ##        Reader = morse.Reader(
        ##                wpm=config.text_speed, codeType=config.code_type,
        ##                callback=readerCallback)  # reset to nominal code speed

    def readerCallback(self, char, spacing):
        """display characters returned from the decoder"""
        self.__recorder.record([], '', text=char)
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
        if char == "=":
            self.__lastCharWasParagraph = True
        else:
            if self.__lastCharWasParagraph:
                txt += "\n"
            self.__lastCharWasParagraph = False
        txt += char
        self.__ka.trigger_reader_append_text(txt)

    def reset_wire_state(self):
        """regain control of the wire"""
        self.__internet_station_active = False

    def show_key_graph(self):
        """
        Show the Key Timing graph.
        """
        if not (self.__key_graph_win and MKOBKeyTimeWin.active):
            self.__key_graph_win = MKOBKeyTimeWin(self.__wpm)
        self.__key_graph_win.focus()

    def key_graph_is_active(self):
        """
        True if the key graph is currently active.
        """
        return (self.__key_graph_win and MKOBKeyTimeWin.active)

