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

from pykob import log
from idlelib.redirector import WidgetRedirector
import threading
import time

MARK_SEND = 'send'

class MKOBKeyboard():
    """
    kobkeyboard.py

    Text area used to send code from the keyboard.

    Calls to the 'handle_' methods should be made on the main GUI thread as a result
    of the GUI handling message events.
    """
    def __init__(self, mkactions, mkwindow, mkmain) -> None:
        self.kw = mkwindow
        self.ka = mkactions
        self.km = mkmain
        self.kw.keyboard_win.bind("<Button-2>", self.on_right_click)
        self.__last_send_pos = 1.0
        self.kw.keyboard_win.mark_set(MARK_SEND, '1.0')
        self.kw.keyboard_win.mark_gravity(MARK_SEND, 'left')
        self.kw.keyboard_win.tag_config('highlight', background='gray75', underline='yes')
        redirector = WidgetRedirector(self.kw.keyboard_win)
        self.original_mark = redirector.register("mark", self.on_mark)
        self.original_insert = redirector.register("insert", self.on_insert)
        self.original_delete = redirector.register("delete", self.on_delete)
        self.__waiting_for_sent_code = False
        self.keyboard_send_thread = threading.Thread(name='Keyboard-Send', target=self.keyboard_send)
        self.keyboard_send_thread.daemon = True

    def start(self):
        self.keyboard_send_thread.start()

    def on_mark(self, *args):
        ip = self.kw.keyboard_win.index('insert')
        ms = self.kw.keyboard_win.index(MARK_SEND)
        op = args[0]
        mark = args[1]
        pos = args[2]
        log.debug("KB mark: {}:{} {}".format(ip, ms, args))
        r = None
        try:
            r = self.original_mark(*args)
        except:
            pass
        if mark == 'insert' and not pos == MARK_SEND:
            ip = self.kw.keyboard_win.index('insert')
            self.ka.trigger_set_code_sender_on(False)
            self.kw.keyboard_win.tag_remove('highlight', MARK_SEND)
            self.kw.keyboard_win.mark_set(MARK_SEND, 'insert')
            self.kw.keyboard_win.tag_add('highlight', MARK_SEND)
            ms = self.kw.keyboard_win.index(MARK_SEND)
        log.debug("KB mark end insert/send point: {}:{}".format(ip, ms))
        return r

    def on_insert(self, *args):
        ip = self.kw.keyboard_win.index('insert')
        ms = self.kw.keyboard_win.index(MARK_SEND)
        log.debug("KB insert: {}:{} {}".format(ip, ms, args))
        s = args[1]
        r = None
        try:
            r = self.original_insert(*args)
        except:
            pass
        # self.ka.trigger_keyboard_text_inserted(s)
        ip = self.kw.keyboard_win.index('insert')
        ms = self.kw.keyboard_win.index(MARK_SEND)
        log.debug("KB insert end insert/send point: {}:{}".format(ip, ms))
        return r

    def on_delete(self, *args):
        ip = self.kw.keyboard_win.index('insert')
        ms = self.kw.keyboard_win.index(MARK_SEND)
        log.debug("KB delete: {}:{} {}".format(ip, ms, args))
        r = None
        try:
            r = self.original_delete(*args)
        except:
            pass
        ip = self.kw.keyboard_win.index('insert')
        ms = self.kw.keyboard_win.index(MARK_SEND)
        log.debug("KB delete end insert/send point: {}:{}".format(ip, ms))
        return r

    def on_right_click(self, event):
        log.debug("KB mrc: {}".format(event))
        pos = "@{},{}".format(event.x, event.y)
        self.kw.keyboard_win.mark_set(MARK_SEND, pos)

    def __keyboard_send_complete(self):
        self.kw.keyboard_win.tag_remove('highlight', MARK_SEND)
        self.__last_send_pos = self.kw.keyboard_win.index(MARK_SEND)
        new_pos = MARK_SEND + '+1c'
        self.kw.keyboard_win.mark_set(MARK_SEND, new_pos)
        self.kw.keyboard_win.tag_add('highlight', MARK_SEND)
        self.__waiting_for_sent_code = False

    def handle_keyboard_send(self, event_data):
        """
        Process a character out of the keyboard send window.

        This handles an event posted from the keyboard-send thread.
        """
        if self.kw.code_sender_enabled and not self.__waiting_for_sent_code:
            if self.kw.keyboard_win.compare(MARK_SEND, '==', 'end-1c'):
                if not self.kw.keyboard_win.compare(MARK_SEND, '==', 'insert'):
                    self.kw.keyboard_win.mark_set('insert', MARK_SEND) # Move the cursor to the END
                if self.kw.code_sender_repeat:
                    self.kw.keyboard_win.mark_set(MARK_SEND, '1.0')
            if self.kw.keyboard_win.compare(MARK_SEND, '<', 'end-1c'):
                self.__waiting_for_sent_code = True
                self.kw.keyboard_win.see(MARK_SEND)
                self.kw.keyboard_win.tag_add('highlight', MARK_SEND)
                c = self.kw.keyboard_win.get(MARK_SEND)
                if c == '~':
                    self.ka.trigger_circuit_open()
                    self.__keyboard_send_complete()
                elif c == '+':
                    self.ka.trigger_circuit_close()
                    self.__keyboard_send_complete()
                else:
                    code = self.km.Sender.encode(c)
                    self.km.from_keyboard(code, self.__keyboard_send_complete)

    def keyboard_send(self):
        """
        thread to send Morse from the code sender window
        """
        while True:
            if not self.__waiting_for_sent_code:
                self.ka.trigger_keyboard_send()
                time.sleep(0.005)
            else:
                time.sleep(0.8)

    def handle_clear(self, event_data=None):
        """
        Event handler to clear the Sender (keyboard) window.
        """
        self.kw.keyboard_win.delete('1.0', 'end')
