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

from pykob import kob, log

from enum import Enum, IntEnum, unique
from idlelib.redirector import WidgetRedirector
from threading import Event, Lock, Thread
import time
from tkinter import EventType, END, INSERT
from typing import Optional

HIGHLIGHT = 'highlight'
MARK_SEND = 'send'

@unique
class VKSendState(IntEnum):
    """
    The state of the Virtual Key (controlled by the cursor left/right keys)
    """
    IDLE = 0
    DITS = 1
    DAH  = 2

class MKOBKeyboard():
    """
    kobkeyboard.py

    Text area used to send code from the keyboard.

    Calls to the 'handle_' methods should be made on the main GUI thread as a result
    of the GUI handling message events.
    """

    MAX_VKEY_IDLE_TIME = 3000
    VKEY_OVERHEAD_TIME = 15

    def __init__(self, mkactions, mkwindow) -> None:
        self._kw = mkwindow
        self._ka = mkactions
        self._km = None
        self._enabled = False
        self._repeat = False
        self._last_send_pos = 1.0
        self._in_key_press: Event = Event()
        self._vkey_code = ()  # Tuple of key down/up ms values
        self._vkey_send_state: VKSendState = VKSendState.IDLE
        self._t_vkey_llast_change: float = time.time()  # time of last-last virtual key transition
        self._t_vkey_last_change: float = time.time()  # time of last virtual key transition
        self._waiting_for_sent_code:Event = Event()
        self._send_guard:Lock = Lock()
        self._dit_sender_thread:Thread = Thread(name="MKKeyboard-DitSender", target=self._dits_sender_run)
        self._shutdown: Event = Event()
        return

    def _dit_send_complete(self):
        if self._vkey_send_state == VKSendState.DITS:
            dot_len = self._km.Sender.dot_len
            self._dit_send(dot_len)
        return

    def _dit_send(self, idle_time=-1):
        if self._vkey_send_state == VKSendState.DITS:
            now = time.time()
            dot_len = self._km.Sender.dot_len
            if idle_time < 0:
                idle_time = int((now - self._t_vkey_llast_change) * 1000)
                if idle_time > MKOBKeyboard.MAX_VKEY_IDLE_TIME:
                    idle_time = MKOBKeyboard.MAX_VKEY_IDLE_TIME
            self._t_vkey_llast_change = self._t_vkey_last_change
            self._t_vkey_last_change = now
            code = (-idle_time, dot_len)
            self._km.from_keyboard_vkey(code, True, finished_callback=self._dit_send_complete)

        return

    def _dits_sender_run(self):
        """
        Dits Sender Thread - Run routine
        """
        while not self._shutdown.is_set():
            self._shutdown.wait(0.01)
            pass
        return

    def _keyboard_send_complete(self):
        log.debug("mkkb._keyboard_send_complete", 3)
        with self._send_guard:
            self._kw.keyboard_win.tag_remove(HIGHLIGHT, MARK_SEND)
            self._last_send_pos = self._kw.keyboard_win.index(MARK_SEND)
            new_pos = MARK_SEND + '+1c'
            self._kw.keyboard_win.mark_set(MARK_SEND, new_pos)
            if self._kw.keyboard_win.compare(MARK_SEND, '<', 'end-1c'):
                self._kw.keyboard_win.tag_add(HIGHLIGHT, MARK_SEND)
            self._waiting_for_sent_code.clear()
        self._ka.trigger_keyboard_send()
        return

    def _on_ctrl_cursor_left(self, event):
        if self._kw.vkey_closed:
            return  # Do normal processing if the Virtual Key is closed
        if ((event.type == EventType.KeyPress and not self._in_key_press.is_set())
            or (event.type == EventType.KeyRelease and self._in_key_press.is_set())):
            if event.type == EventType.KeyPress:
                self._in_key_press.set()
                self._vkey_send_state = VKSendState.DITS
                self._dit_send()
            else:
                self._vkey_send_state = VKSendState.IDLE
                self._in_key_press.clear()
            log.debug("KB ctrl-curlf: {}".format(event), 3)
        return "break"  # Don't perform normal processing

    def _on_ctrl_cursor_right(self, event):
        if self._kw.vkey_closed:
            return  # Do normal processing if the Virtual Key is closed
        if ((event.type == EventType.KeyPress and not self._in_key_press.is_set())
            or (event.type == EventType.KeyRelease and self._in_key_press.is_set())):
            now = time.time()
            kob_: Optional[kob.KOB] = self._km.Kob
            if event.type == EventType.KeyPress:
                self._in_key_press.set()
                self._vkey_send_state = VKSendState.DAH
                self._t_vkey_llast_change = self._t_vkey_last_change
                self._t_vkey_last_change = now
                if not kob_ is None:
                    kob_.energize_sounder(True, kob.CodeSource.keyboard)
            else:
                if not kob_ is None:
                    kob_.energize_sounder(False, kob.CodeSource.keyboard)
                # Create the code tuple to send
                idle_time = int((self._t_vkey_last_change - self._t_vkey_llast_change) * 1000)
                if idle_time > MKOBKeyboard.MAX_VKEY_IDLE_TIME:
                    idle_time = MKOBKeyboard.MAX_VKEY_IDLE_TIME
                down_time = int((now - self._t_vkey_last_change) * 1000) - MKOBKeyboard.VKEY_OVERHEAD_TIME
                self._t_vkey_last_change = now
                code = (-idle_time, down_time)
                self._km.from_keyboard_vkey(code, False)
                # Update the flags
                self._vkey_send_state = VKSendState.IDLE
                self._in_key_press.clear()
            log.debug("KB ctrl-currt: {}".format(event), 3)
        return "break"  # Don't perform normal processing

    def _on_delete(self, *args):
        ip = self._kw.keyboard_win.index(INSERT)
        ms = self._kw.keyboard_win.index(MARK_SEND)
        log.debug("KB delete: {}:{} {}".format(ip, ms, args), 4)
        r = None
        try:
            r = self.original_delete(*args)
        except:
            pass
        ip = self._kw.keyboard_win.index(INSERT)
        ms = self._kw.keyboard_win.index(MARK_SEND)
        self._ka.trigger_keyboard_send()
        log.debug("KB delete end insert/send point: {}:{}".format(ip, ms), 4)
        return r

    def _on_insert(self, *args):
        ip = self._kw.keyboard_win.index(INSERT)
        ms = self._kw.keyboard_win.index(MARK_SEND)
        log.debug("KB insert: {}:{} {}".format(ip, ms, args), 4)
        s = args[1]
        r = None
        try:
            r = self.original_insert(*args)
        except:
            pass
        ip = self._kw.keyboard_win.index(INSERT)
        ms = self._kw.keyboard_win.index(MARK_SEND)
        self._ka.trigger_keyboard_send()
        log.debug("KB insert end [i:s]: {}:{}".format(ip, ms), 4)
        return r

    def _on_mark(self, *args):
        r = None
        try:
            r = self.original_mark(*args)
        except:
            pass
        op = args[0]
        mark = args[1]
        pos = args[2]
        ip = self._kw.keyboard_win.index(INSERT)
        ipl = ip.split('.')
        iline = int(ipl[0])
        ichar = int(ipl[1])
        ms = self._kw.keyboard_win.index(MARK_SEND)
        msl = ms.split(".")
        sline = int(msl[0])
        schar = int(msl[1])
        en = self._enabled
        log.debug("KB mark [i:s]:en={} op={} mark={} pos={} [{}:{}] {}".format(en, op, mark, pos, ip, ms, args), 4)
        if op == 'set' and mark == INSERT and not pos == MARK_SEND:
            if (not en) or (en and ((iline < sline) or (iline == sline and ichar < schar))):
                self._kw.keyboard_win.tag_remove(HIGHLIGHT, MARK_SEND)
                self._kw.keyboard_win.mark_set(MARK_SEND, ip)
                self._kw.keyboard_win.tag_add(HIGHLIGHT, MARK_SEND)
                ms = self._kw.keyboard_win.index(MARK_SEND)
                self._ka.trigger_keyboard_send()
        elif op == 'set' and mark == MARK_SEND and pos[0] == '@':
                self._kw.keyboard_win.tag_remove(HIGHLIGHT, MARK_SEND)
                lc = self._kw.keyboard_win.index(pos)
                self._kw.keyboard_win.mark_set(MARK_SEND, lc)
                self._kw.keyboard_win.tag_add(HIGHLIGHT, MARK_SEND)
                ms = self._kw.keyboard_win.index(MARK_SEND)
                self._ka.trigger_keyboard_send()
        log.debug("KB mark end [i:s]: {}:{}".format(ip, ms), 4)
        return r

    def _on_right_click(self, event):
        log.debug("KB mrc: {}".format(event), 4)
        pos = "@{},{}".format(event.x, event.y)
        self._kw.keyboard_win.mark_set(MARK_SEND, pos)
        return

    @property
    def enabled(self) -> bool:
        return self._enabled
    @enabled.setter
    def enabled(self, en:bool):
        self._enabled = en
        if en:
            self._ka.trigger_keyboard_send()

    @property
    def repeat(self) -> bool:
        return self._repeat
    @repeat.setter
    def repeat(self, en:bool):
        self._repeat = en
        if en:
            self._ka.trigger_keyboard_send()

    def exit(self):
        self.shutdown()
        if self._dit_sender_thread.is_alive():
            self._dit_sender_thread.join()
        return

    def handle_clear(self, event_data=None):
        """
        Event handler to clear the Sender (keyboard) window.
        """
        self._kw.keyboard_win.delete('1.0', END)
        self._ka.trigger_keyboard_send()

    def handle_keyboard_send(self, event_data=None):
        """
        Process a character out of the keyboard send window.

        This handles an event posted from a character being sent, a character
        being added, the send position changing, the sender being enabled,
        or repeat being enabled.
        """
        km_isa = self._km.internet_station_active
        log.debug("mkkb.handle_keyboard_send: KM.ISA:{} Enabled:{} Waiting on sent:{}".format(
            km_isa, self._enabled, self._waiting_for_sent_code.is_set()), 3)

        if km_isa:
            self._km.tkroot.after(800, self.handle_keyboard_send)
            return

        c = None
        with self._send_guard:
            if self._enabled:
                if not self._waiting_for_sent_code.is_set():
                    if self._kw.keyboard_win.compare(MARK_SEND, '==', 'end-1c'):
                        if not self._kw.keyboard_win.compare(MARK_SEND, '==', INSERT):
                            self._kw.keyboard_win.mark_set(INSERT, MARK_SEND) # Move the cursor to the END
                        if self._repeat and not self._kw.keyboard_win.compare(MARK_SEND, '==', '1.0'):
                            self._kw.keyboard_win.mark_set(MARK_SEND, '1.0')
                        else:
                            # Remove the Send mark highlight
                            self._kw.keyboard_win.tag_remove(HIGHLIGHT, MARK_SEND)
                    if self._kw.keyboard_win.compare(MARK_SEND, '<', 'end-1c'):
                        self._waiting_for_sent_code.set()
                        self._kw.keyboard_win.see(MARK_SEND)
                        self._kw.keyboard_win.tag_add(HIGHLIGHT, MARK_SEND)
                        c = self._kw.keyboard_win.get(MARK_SEND)
                    pass
                pass
            pass
        if c == '~':
            self._ka.trigger_circuit_open()
            self._keyboard_send_complete()
        elif c == '+':
            self._ka.trigger_circuit_close()
            self._keyboard_send_complete()
        elif c:
            code = self._km.Sender.encode(c)
            self._km.from_keyboard(code, self._keyboard_send_complete)
        return

    def load_file(self, fp):
        """
        Read the file identified by the file path fp into the sender window,
        then move the cursor to the beginning for it to play.
        """
        ip = self._kw.keyboard_win.index(INSERT)
        send_at_eof = self._kw.keyboard_win.compare(MARK_SEND, '>=', 'end-1c')
        with open(fp, 'r') as f:
            self._kw.keyboard_win.insert(INSERT, f.read())
        if send_at_eof:
            # The sender was at the end
            log.debug("File inserted with the sender at the end.")
        self._kw.give_keyboard_focus()
        return

    def shutdown(self):
        """
        Initiate shutdown of our operations (and don't start anything new),
        but DO NOT BLOCK.
        """
        self._shutdown.set()
        return

    def start(self, mkmain):
        self._km = mkmain
        self._kw.keyboard_win.bind("<Button-2>", self._on_right_click)
        self._kw.keyboard_win.bind("<Button-3>", self._on_right_click)
        self._kw.keyboard_win.bind("<Control-KeyPress-Left>", self._on_ctrl_cursor_left)
        self._kw.keyboard_win.bind("<Control-KeyPress-Right>", self._on_ctrl_cursor_right)
        self._kw.keyboard_win.bind("<Control-KeyRelease-Left>", self._on_ctrl_cursor_left)
        self._kw.keyboard_win.bind("<Control-KeyRelease-Right>", self._on_ctrl_cursor_right)
        self._kw.keyboard_win.tag_config(HIGHLIGHT, background='gray75', underline='yes')
        redirector = WidgetRedirector(self._kw.keyboard_win)
        self.original_delete = redirector.register("delete", self._on_delete)
        self.original_insert = redirector.register("insert", self._on_insert)
        self.original_mark = redirector.register("mark", self._on_mark)
        self._kw.keyboard_win.mark_set(MARK_SEND, '1.0')
        self._kw.keyboard_win.mark_gravity(MARK_SEND, "left")
        self._dit_sender_thread.start()
        self._ka.trigger_keyboard_send()
        return
