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
kobkeyboard.py

Send code from the keyboard.
"""

import threading
import time
import kobactions as ka
import kobmain as km

def init():
    keyboard_send_thread = threading.Thread(target=keyboard_send)
    keyboard_send_thread.daemon = True
    keyboard_send_thread.start()

def keyboard_send():
    """thread to send Morse from the code sender window"""
    time.sleep(1)  # wait for kobwindows to initialize on startup
    kw = ka.kw
    kw.txtKeyboard.tag_config('highlight', background='gray75',
            underline=0)
    kw.txtKeyboard.tag_remove('highlight', '1.0', 'end')
    kw.txtKeyboard.mark_set('mark', '1.0')
    while True:
        if kw.txtKeyboard.compare('mark', '<', 'end-1c') and \
                kw.varCodeSenderOn.get():
            kw.txtKeyboard.tag_add('highlight', 'mark')
            c = kw.txtKeyboard.get('mark')
            code = km.mySender.encode(c)
            km.from_keyboard(code)
            kw.txtKeyboard.tag_remove('highlight', 'mark')
            kw.txtKeyboard.mark_set('mark', 'mark+1c')
        else:
            time.sleep(0.1)

