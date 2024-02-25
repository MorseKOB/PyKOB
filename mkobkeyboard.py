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
        self._waiting_for_sent_code = False

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

    def handle_clear(self, event_data=None):
        """
        Event handler to clear the Sender (keyboard) window.
        """
        self.kw.keyboard_win.delete('1.0', END)

    def _keyboard_send_complete(self):
        self.kw.keyboard_win.tag_remove(HIGHLIGHT, MARK_SEND)
        self._last_send_pos = self.kw.keyboard_win.index(MARK_SEND)
        new_pos = MARK_SEND + '+1c'
        self.kw.keyboard_win.mark_set(MARK_SEND, new_pos)
        if self.kw.keyboard_win.compare(MARK_SEND, '<', 'end-1c'):
            self.kw.keyboard_win.tag_add(HIGHLIGHT, MARK_SEND)
        self._waiting_for_sent_code = False
        self.ka.trigger_keyboard_send()

    def handle_keyboard_send(self, event_data):
        """
        Process a character out of the keyboard send window.

        This handles an event posted from the keyboard-send thread.
        """
        if self._enabled and not self._waiting_for_sent_code:
            if self.kw.keyboard_win.compare(MARK_SEND, '==', 'end-1c'):
                if not self.kw.keyboard_win.compare(MARK_SEND, '==', INSERT):
                    self.kw.keyboard_win.mark_set(INSERT, MARK_SEND) # Move the cursor to the END
                if self._repeat and not self.kw.keyboard_win.compare(MARK_SEND, '==', '1.0'):
                    self.kw.keyboard_win.mark_set(MARK_SEND, '1.0')
                else:
                    # Remove the Send mark highlight
                    self.kw.keyboard_win.tag_remove(HIGHLIGHT, MARK_SEND)
            if self.kw.keyboard_win.compare(MARK_SEND, '<', 'end-1c'):
                self._waiting_for_sent_code = True
                self.kw.keyboard_win.see(MARK_SEND)
                self.kw.keyboard_win.tag_add(HIGHLIGHT, MARK_SEND)
                c = self.kw.keyboard_win.get(MARK_SEND)
                if c == '~':
                    self.ka.trigger_circuit_open()
                    self._keyboard_send_complete()
                elif c == '+':
                    self.ka.trigger_circuit_close()
                    self._keyboard_send_complete()
                else:
                    code = self.km.Sender.encode(c)
                    self.km.from_keyboard(code, self._keyboard_send_complete)

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
        log.debug("KB insert end insert/send point: {}:{}".format(ip, ms), 3)
        return r

    def on_mark(self, *args):
        ip = self.kw.keyboard_win.index(INSERT)
        ms = self.kw.keyboard_win.index(MARK_SEND)
        op = args[0]
        mark = args[1]
        pos = args[2]
        log.debug("KB mark: {}:{} {}".format(ip, ms, args), 3)
        r = None
        try:
            r = self.original_mark(*args)
        except:
            pass
        ip = self.kw.keyboard_win.index(INSERT)
        ms = self.kw.keyboard_win.index(MARK_SEND)
        if mark == INSERT and not pos == MARK_SEND:
            if (self._enabled and (float(ip) < float(ms))) or not self._enabled:
                self.kw.keyboard_win.tag_remove(HIGHLIGHT, MARK_SEND)
                self.kw.keyboard_win.mark_set(MARK_SEND, INSERT)
                self.kw.keyboard_win.tag_add(HIGHLIGHT, MARK_SEND)
                ms = self.kw.keyboard_win.index(MARK_SEND)
                self.ka.trigger_keyboard_send()
        log.debug("KB mark end insert/send point: {}:{}".format(ip, ms), 3)
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
            print("File inserted with the sender at the end.")
        self.kw.give_keyboard_focus()
