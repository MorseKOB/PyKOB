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

from pykob import log
from idlelib.redirector import WidgetRedirector
import threading
import time
from tkinter import END, INSERT

HIGHLIGHT = 'highlight'
MARK_SEND = 'send'

class MKOBKeyboard():
    """
    kobkeyboard.py

    Text area used to send code from the keyboard.

    Calls to the 'handle_' methods should be made on the main GUI thread as a result
    of the GUI handling message events.
    """
    def __init__(self, mkactions, mkwindow) -> None:
        self.kw = mkwindow
        self.ka = mkactions
        self.km = None
        self._enabled = False
        self._repeat = False
        self._last_send_pos = 1.0
        self._waiting_for_sent_code:threading.Event = threading.Event()
        self._send_guard:threading.Lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        return self._enabled
    @enabled.setter
    def enabled(self, en:bool):
        self._enabled = en
        if en:
            self.ka.trigger_keyboard_send()

    @property
    def repeat(self) -> bool:
        return self._repeat
    @repeat.setter
    def repeat(self, en:bool):
        self._repeat = en
        if en:
            self.ka.trigger_keyboard_send()

    def start(self, mkmain):
        self.km = mkmain
        self.kw.keyboard_win.bind("<Button-2>", self.on_right_click)
        self.kw.keyboard_win.bind("<Button-3>", self.on_right_click)
        self.kw.keyboard_win.tag_config(HIGHLIGHT, background='gray75', underline='yes')
        redirector = WidgetRedirector(self.kw.keyboard_win)
        self.original_mark = redirector.register("mark", self.on_mark)
        self.original_insert = redirector.register("insert", self.on_insert)
        self.original_delete = redirector.register("delete", self.on_delete)
        self.kw.keyboard_win.mark_set(MARK_SEND, '1.0')
        self.kw.keyboard_win.mark_gravity(MARK_SEND, "left")
        self.ka.trigger_keyboard_send()

    def handle_clear(self, event_data=None):
        """
        Event handler to clear the Sender (keyboard) window.
        """
        self.kw.keyboard_win.delete('1.0', END)
        self.ka.trigger_keyboard_send()

    def _keyboard_send_complete(self):
        log.debug("mkkb._keyboard_send_complete", 3)
        with self._send_guard:
            self.kw.keyboard_win.tag_remove(HIGHLIGHT, MARK_SEND)
            self._last_send_pos = self.kw.keyboard_win.index(MARK_SEND)
            new_pos = MARK_SEND + '+1c'
            self.kw.keyboard_win.mark_set(MARK_SEND, new_pos)
            if self.kw.keyboard_win.compare(MARK_SEND, '<', 'end-1c'):
                self.kw.keyboard_win.tag_add(HIGHLIGHT, MARK_SEND)
            self._waiting_for_sent_code.clear()
        self.ka.trigger_keyboard_send()

    def handle_keyboard_send(self, event_data=None):
        """
        Process a character out of the keyboard send window.

        This handles an event posted from a character being sent, a character
        being added, the send position changing, the sender being enabled,
        or repeat being enabled.
        """
        if self.km.internet_station_active:
            self.km.tkroot.after(100, self.handle_keyboard_send)
            return
        
        log.debug("mkkb.handle_keyboard_send: Enabled:{} Waiting on sent:{}".format(
            self._enabled, self._waiting_for_sent_code.is_set()), 3)
        c = None
        with self._send_guard:
            if self._enabled:
                if not self._waiting_for_sent_code.is_set():
                    if self.kw.keyboard_win.compare(MARK_SEND, '==', 'end-1c'):
                        if not self.kw.keyboard_win.compare(MARK_SEND, '==', INSERT):
                            self.kw.keyboard_win.mark_set(INSERT, MARK_SEND) # Move the cursor to the END
                        if self._repeat and not self.kw.keyboard_win.compare(MARK_SEND, '==', '1.0'):
                            self.kw.keyboard_win.mark_set(MARK_SEND, '1.0')
                        else:
                            # Remove the Send mark highlight
                            self.kw.keyboard_win.tag_remove(HIGHLIGHT, MARK_SEND)
                    if self.kw.keyboard_win.compare(MARK_SEND, '<', 'end-1c'):
                        self._waiting_for_sent_code.set()
                        self.kw.keyboard_win.see(MARK_SEND)
                        self.kw.keyboard_win.tag_add(HIGHLIGHT, MARK_SEND)
                        c = self.kw.keyboard_win.get(MARK_SEND)
                    pass
                pass
            pass
        if c == '~':
            self.ka.trigger_circuit_open()
            self._keyboard_send_complete()
        elif c == '+':
            self.ka.trigger_circuit_close()
            self._keyboard_send_complete()
        elif c:
            code = self.km.Sender.encode(c)
            self.km.from_keyboard(code, self._keyboard_send_complete)
        return

    def on_delete(self, *args):
        ip = self.kw.keyboard_win.index(INSERT)
        ms = self.kw.keyboard_win.index(MARK_SEND)
        log.debug("KB delete: {}:{} {}".format(ip, ms, args), 3)
        r = None
        try:
            r = self.original_delete(*args)
        except:
            pass
        ip = self.kw.keyboard_win.index(INSERT)
        ms = self.kw.keyboard_win.index(MARK_SEND)
        self.ka.trigger_keyboard_send()
        log.debug("KB delete end insert/send point: {}:{}".format(ip, ms), 3)
        return r

    def on_insert(self, *args):
        ip = self.kw.keyboard_win.index(INSERT)
        ms = self.kw.keyboard_win.index(MARK_SEND)
        log.debug("KB insert: {}:{} {}".format(ip, ms, args), 3)
        s = args[1]
        r = None
        try:
            r = self.original_insert(*args)
        except:
            pass
        # self.ka.trigger_keyboard_text_inserted(s)
        ip = self.kw.keyboard_win.index(INSERT)
        ms = self.kw.keyboard_win.index(MARK_SEND)
        self.ka.trigger_keyboard_send()
        log.debug("KB insert end [i:s]: {}:{}".format(ip, ms), 3)
        return r

    def on_mark(self, *args):
        r = None
        try:
            r = self.original_mark(*args)
        except:
            pass
        op = args[0]
        mark = args[1]
        pos = args[2]
        ip = self.kw.keyboard_win.index(INSERT)
        ipl = ip.split('.')
        iline = int(ipl[0])
        ichar = int(ipl[1])
        ms = self.kw.keyboard_win.index(MARK_SEND)
        msl = ms.split(".")
        sline = int(msl[0])
        schar = int(msl[1])
        en = self._enabled
        log.debug("KB mark [i:s]:en={} op={} mark={} pos={} [{}:{}] {}".format(en, op, mark, pos, ip, ms, args), 3)
        if op == 'set' and mark == INSERT and not pos == MARK_SEND:
            if (not en) or (en and ((iline < sline) or (iline == sline and ichar < schar))):
                self.kw.keyboard_win.tag_remove(HIGHLIGHT, MARK_SEND)
                self.kw.keyboard_win.mark_set(MARK_SEND, ip)
                self.kw.keyboard_win.tag_add(HIGHLIGHT, MARK_SEND)
                ms = self.kw.keyboard_win.index(MARK_SEND)
                self.ka.trigger_keyboard_send()
        log.debug("KB mark end [i:s]: {}:{}".format(ip, ms), 3)
        return r

    def on_right_click(self, event):
        log.debug("KB mrc: {}".format(event), 3)
        pos = "@{},{}".format(event.x, event.y)
        self.kw.keyboard_win.mark_set(MARK_SEND, pos)

    def load_file(self, fp):
        """
        Read the file identified by the file path fp into the sender window,
        then move the cursor to the beginning for it to play.
        """
        ip = self.kw.keyboard_win.index(INSERT)
        send_at_eof = self.kw.keyboard_win.compare(MARK_SEND, '>=', 'end-1c')
        with open(fp, 'r') as f:
            self.kw.keyboard_win.insert(INSERT, f.read())
        if send_at_eof:
            # The sender was at the end
            log.debug("File inserted with the sender at the end.")
        self.kw.give_keyboard_focus()
