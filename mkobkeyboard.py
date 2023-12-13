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


import threading
import time

class MKOBKeyboard():
    """
    kobkeyboard.py

    Text area used to send code from the keyboard.
    """

    def __init__(self, mkactions, mkwindow, mkmain) -> None:
        self.kw = mkwindow
        self.ka = mkactions
        self.km = mkmain
        self.keyboard_send_thread = threading.Thread(name='Keyboard-Send', target=self.keyboard_send)
        self.keyboard_send_thread.daemon = True
        self.keyboard_send_thread.start()

    def keyboard_send(self):
        """
        thread to send Morse from the code sender window
        """
        self.kw.keyboard_win.tag_config('highlight', background='gray75', underline=0)
        self.kw.keyboard_win.mark_set('mark', '1.0')
        self.kw.keyboard_win.mark_gravity('mark', 'left')
        while True:
            if self.kw.keyboard_win.compare('mark', '==', 'end-1c') and self.kw.code_sender_repeat:
                self.kw.keyboard_win.mark_set('mark', '1.0')
            if self.kw.keyboard_win.compare('mark', '<', 'end-1c') and self.kw.code_sender_enabled:
                self.kw.keyboard_win.see('mark')
                self.kw.keyboard_win.tag_add('highlight', 'mark')
                c = self.kw.keyboard_win.get('mark')
                if c == '~':
                    self.ka.trigger_circuit_open()
                elif c == '+':
                    self.ka.trigger_circuit_close()
                else:
                    code = self.km.Sender.encode(c)
                    self.km.from_keyboard(code)
                self.kw.keyboard_win.tag_remove('highlight', 'mark')
                self.kw.keyboard_win.mark_set('mark', 'mark+1c')
            else:
                time.sleep(0.1)

