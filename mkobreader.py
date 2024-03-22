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
kobreader.py

Manage the reader window.

Calls to the 'handle_' methods should be made on the main GUI thread as a result of the GUI handling
message events.
"""
from pykob import log
from threading import Event

class MKOBReader():
    """
    The main text window for the MKOB app. This primarily displays the
    decoded Morse that is received from a wire or keyed locally.

    It is also used to display various other content (messages to the user).
    """

    def __init__(self, mkwindow) -> None:
        self.kw = mkwindow
        self._shutdown: Event = Event()

    def exit(self):
        self.shutdown()
        return

    def handle_append_text(self, event_data):
        """
        Event handler to append text to the window.
        """
        if self._shutdown.is_set():
            return
        text = event_data
        log.debug("mkrdr.handle_append_text - [{}]".format(text), 5)
        self.kw.reader_win.insert('end', text)
        self.kw.reader_win.see('end')
        return

    def handle_clear(self, event_data=None):
        """
        Event handler to clear the contents.
        """
        if self._shutdown.is_set():
            return
        log.debug("mkrdr.handle_clear", 5)
        self.kw.reader_win.delete('1.0', 'end')
        return

    def shutdown(self):
        """
        Initiate shutdown of our operations (and don't start anything new),
        but DO NOT BLOCK.
        """
        self._shutdown.set()
        return
