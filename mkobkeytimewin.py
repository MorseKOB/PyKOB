"""
MIT License

Copyright (c) 2020 PyKOB - MorseKOB in Python

Permission is hereby granted, free of charge, to any person obtaining a copy
of this so_ftware and associated documentation files (the "So_ftware"), to deal
in the So_ftware without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the So_ftware, and to permit persons to whom the So_ftware is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the So_ftware.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

"""
mkobkeytimewin.py

Child windows that contains a running timing graph of the key. This can
optionally show the local key and/or the remote (wire) key.

The graph looks like this:
 >15 (80) -  612       ^ |------------------------------------------------------------!
 >15 (80)    256   20% - |################################
 >15 (80) -   75 -  6%   |---------
 >15 (80)     83    4% . |##########

"""

import tkinter as tk
import tkinter.scrolledtext as tkst
from tkinter import ttk

from pykob import config
from pykob.morse import Reader
from pykob.morse import Sender

INITIAL_HEIHGT = 380
INITIAL_WIDTH = 520
OPTIONS_HEIGHT = 20

TAG_ERROR = "error"
TAG_NORMAL = "normal"
TAG_MARK = "mark"
TAG_WARN_N = "warn_n"
TAG_WARN_P = "warn_p"

GRAPH_UPPER_BOUND = 800.0
GRAPH_LINES_TO_DEL = "100.end"

class MKOBKeyTimeWin(tk.Toplevel):
    # Class attribute that indicates whether this child window
    # is being used (active) or not.
    active = False

    def __init__(self, wpm, codeType=config.CodeType.american, local_enable=True, wire_enable=False):
        super().__init__()
        self.config(width=INITIAL_WIDTH, height=INITIAL_HEIHGT)
        self.title("MKOB Key Timing")
        self._wpm = wpm
        self._codetype = codeType
        #
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        # frames
        self._ft = tk.Frame(self, height=OPTIONS_HEIGHT)
        self._ft.grid(row=0, column=0, padx=0, pady=0, sticky=tk.E+tk.W)
        self._fb = tk.Frame(self, width=INITIAL_WIDTH, height=INITIAL_HEIHGT-OPTIONS_HEIGHT)
        self._fb.grid(row=1, column=0, columnspan=3, padx=1, pady=1, sticky=tk.E+tk.W+tk.N+tk.S)
        self._fb.columnconfigure(0, weight=1)
        self._fb.rowconfigure(0, weight=1)
        # graph
        self._txtGraph = tkst.ScrolledText(self._fb, wrap='none', font=("Courier", -14))
        #self._txtGraph.rowconfigure(0, weight=1)
        #self._txtGraph.columnconfigure(0, weight=2)
        self._txtGraph.grid(row=0, column=0, padx=2, pady=2, sticky=tk.E+tk.W+tk.N+tk.S)
        self._txtGraph.tag_config(TAG_NORMAL)
        self._txtGraph.tag_config(TAG_ERROR, foreground="#EE0000") # Medium red
        self._txtGraph.tag_config(TAG_MARK, foreground="#1C86EE")  # Dodger blue
        self._txtGraph.tag_config(TAG_WARN_P, foreground="#FFA500")  # Dark orange
        self._txtGraph.tag_config(TAG_WARN_N, foreground="#FFD700")  # Gold-2
        # options
        self._varLocalOn = tk.BooleanVar()
        self._varLocalOn.set(local_enable)
        self._chkLocalOn = tk.Checkbutton(self._ft, text="Local", variable=self._varLocalOn)
        self._chkLocalOn.grid(row=0, column=0, padx=8, pady=8)
        self._varWireOn = tk.BooleanVar()
        self._varWireOn.set(wire_enable)
        self._chkWireOn = tk.Checkbutton(self._ft, text="Wire", variable=self._varWireOn)
        self._chkWireOn.grid(row=0, column=1, padx=8, pady=8)
        self._btnClear = tk.Button(self._ft, text='Clear', command=self.do_clear)
        self._btnClear.grid(row=0, column=2, ipady=2, sticky='EW')
        tk.Label(self._ft, text="Mark").grid(row=0, column=3, padx=4, pady=8)
        self._varMarkTxt = tk.StringVar()
        self._entMarkTxt = tk.Entry(self._ft, bd=2, font=("Helvetica", -15), textvariable=self._varMarkTxt)
        self._entMarkTxt.bind("<Return>", self.do_mark_text_enter)
        self._entMarkTxt.grid(row=0, column=4, columnspan=3, padx=2, pady=2, sticky=tk.E+tk.W)
        #
        self.__class__.active = True  # Indicate that the window is 'active'
        #
        self._morse_reader = Reader(self._wpm, self._codetype)
        self._morse_sender = Sender(self._wpm, self._codetype)

    @property
    def local_enabled(self):
        return self._varLocalOn.get()

    @local_enabled.setter
    def local_enabled(self, b):
        self._varLocalOn.set(b)

    @property
    def wire_enabled(self):
        return self._varWireOn.get()

    @wire_enabled.setter
    def wire_enabled(self, b):
        self._varWireOn.set(b)

    @property
    def wpm(self):
        return self._wpm

    @wpm.setter
    def wpm(self, wpm):
        self._wpm = wpm
        self._morse_reader.setWPM(wpm)
        self._morse_sender.setWPM(wpm)

    def destroy(self):
        # Restore the attribute on close.
        self.__class__.active = False
        return super().destroy()

    def do_clear(self):
        """
        Clear the contents of the graph.
        """
        self._txtGraph.delete("1.0", "end")
        self._txtGraph.see("end")

    def do_mark_text_enter(self, event):
        """
        Called when text has been entered as a 'mark'. Put the
        text entered into the graph.
        """
        txt = self._varMarkTxt.get()
        self.append(txt+'\n', tag="mark")

    def append(self, text, tag="normal"):
        """
        Append a line of text to the graph.
        """
        self._check_graph_full()
        self._txtGraph.insert("end", text, tag)
        self._txtGraph.see("end")

    def _check_graph_full(self):
        index = float(self._txtGraph.index("end"))
        if index >= GRAPH_UPPER_BOUND:
            self._txtGraph.delete("0.0", GRAPH_LINES_TO_DEL)

    def _gen_line(self, indicator, val, exp, err, like, fc, fl, tc='', lc='|'):
        sign = '-' if val < 0 else ' '
        value = int(abs(val))
        err_sign = '-' if err < 0 else ' '
        error = abs(err)
        # Generate a string of fill characters (fc) that is fill length (fl) long.
        bar = fc * fl
        return "{0}{1:2d} ({2:4d}) {3}{4:4d} {5}{6:6.1%} {7} {8}{9}{10}".format(
            indicator, self._wpm, exp, sign, value, err_sign, error, like, lc, bar, tc)

    def key_closed(self):
        """
        Call when the key is closed to cause a marker to be put in the graph.
        """
        if self._varLocalOn.get():
            self.append(">{}\n".format('\u21A7' * 100)) # 100 Down Arrows

    def key_opened(self):
        """
        Call when the key is opened to cause a marker to be put in the graph.
        """
        if self._varLocalOn.get():
            self.append(">{}\n".format('\u21A5' * 100)) # 100 Up Arrows

    def key_code(self, code):
        """
        Call when the key has code.
        """
        if self._varLocalOn.get():
            self.output_code_lines(code, '>')

    def wire_code(self, code):
        """
        Call when code comes in from the wire.
        """
        if self._varWireOn.get():
            self.output_code_lines(code, '<')

    def output_code_lines(self, code, indicator):
        wpm = self._wpm
        dot_len = int(self._morse_sender.dot_len)
        dash_len = int(self._morse_sender.dash_len)
        ldash_len = int(self._morse_sender.long_dash_len)
        xldash_len = int(self._morse_sender.xl_dash_len)
        icspace_len = int(self._morse_sender.intra_char_space_len)
        mspace_len = int(self._morse_sender.dot_len)
        cspace_len = int(self._morse_sender.char_space_len)
        wspace_len = int(self._morse_sender.word_space_len)
        bar_div = 12.0 / dot_len
        for i in code:
            i_abs = abs(i)
            bar_value = int(i_abs * bar_div)
            bar_end = ''
            # Figure out what would be expected given this duration
            like = "?"
            expected_len = 0
            if i < 0:
                # Some type of space (key up)
                if i_abs < self._morse_reader.intra_char_space_min:
                    like = '\u25CB' # open circle
                    expected_len = mspace_len
                elif i_abs <= self._morse_reader.intra_char_space_max:
                    like = '\u25AD' # open rectangle
                    expected_len = icspace_len
                elif i_abs <= self._morse_reader.char_space_max:
                    like = '\u2192' # right arrow (->)
                    expected_len = cspace_len
                else:
                    like = ' '
                    expected_len = wspace_len
            else:
                # Some type of dot/dash (key down)
                if i <= self._morse_reader.dot_len_max:
                    like = '\u25CF' # Black dot (circle)
                    expected_len = dot_len
                elif i <= self._morse_reader.dash_len_max:
                    like = '\u25AC' # Black rectangle
                    expected_len = dash_len
                elif i > self._morse_reader.dash_len_max and self._codetype == config.CodeType.american:
                    if i <= self._morse_reader.dashlong_len_max:
                        like = '\u2517' # box drawing 'L'
                        expected_len = ldash_len
                    else:
                        like = '0'
                        expected_len = xldash_len
                else:
                    like = '\u25AC' # Black rectangle
                    expected_len = dash_len
            # Calculate the error from what was expected
            error = (i_abs - expected_len)/expected_len
            err_abs = abs(error)
            tag = TAG_NORMAL
            if err_abs >= 10:
                error = -9.999 if error < 0 else 9.999
            if err_abs >= 0.10:
                if error < 0:
                    tag = TAG_WARN_N
                else:
                    tag = TAG_WARN_P
            if bar_value > 120:
                bar_value = 119
                bar_end = '!'
                tag = TAG_ERROR
            bar_char = '\u2501' if i < 0 else '\u2587' # line or 7/8 block
            if i_abs >= 10000:
                i = 9999 * (-1 if i < 0 else 1)
            s = self._gen_line(indicator, i, expected_len, error, like, bar_char, bar_value, bar_end)
            self.append(s + '\n',tag)
