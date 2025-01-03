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
morse.py

Provides classes for sending and reading American and International Morse code.
"""

import sys
import codecs
from pathlib import Path
from threading import current_thread, Event, Timer
from pykob import config, log

DOTSPERWORD = 45     # dot units per word, including all spaces (MORSE is 43, PARIS is 47)
MAXINT = sys.maxsize # a very large integer

# Resource folder
root_folder = Path(__file__).parent
data_folder = root_folder / "data"

# read code tables
encodeTable = [{}, {}]  # one dictionary each for American and International

def readEncodeTable(codeType, filename):
    fn = data_folder / filename
    # print("Load encode table: ", fn)
    f = codecs.open(fn, encoding='utf-8')
    cti = 0 if codeType == config.CodeType.american else 1
    f.readline()  # ignore first line
    for s in f:
        a, t, c = s.rstrip().partition('\t')
        encodeTable[cti][a] = c  # dictionary key is character
    f.close()
    return

readEncodeTable(config.CodeType.american, 'codetable-american.txt')
readEncodeTable(config.code_type.international, 'codetable-international.txt')

class Sender:
    """
    Code sender class used to convert text into code (down/up duration) sequences.
    """

    """ Constant approximate duration for a dot at 20 Words per Minute. """
    DOT_LEN_20WPM = 60

    def __init__(self, wpm, cwpm=0, codeType=config.CodeType.american, spacing=config.Spacing.char):
        self._codeType = codeType
        self._spacing = spacing
        self.setWPM(wpm, cwpm)
        self._space = self._wordSpace  # delay before next code element (ms)
        self._shutdown: Event = Event()
        return

    @property
    def dot_len(self):
        return self._dotLen

    @property
    def dash_len(self):
        return (3.0 * self._dotLen)

    @property
    def long_dash_len(self):
        if self._codeType == config.CodeType.american:
            return (6.0 * self._dotLen)
        else:
            return (-1.0)

    @property
    def xl_dash_len(self):
        if self._codeType == config.CodeType.american:
            return (8.0 * self._dotLen)
        else:
            return (-1.0)

    @property
    def intra_char_space_len(self):
        if self._codeType == config.CodeType.american:
            return (3 * self._dotLen)
        else:
            return (-1.0)

    @property
    def char_space_len(self):
        return (self._charSpace)

    @property
    def word_space_len(self):
        return (self._wordSpace)

    def encode(self, char, printChar=False):
        c = char.upper()
        if (printChar):
            print(c, end="", flush=True)
        code = ()
        cti = 0 if self._codeType == config.CodeType.american else 1
        if not c in encodeTable[cti]:
            if c == '-' or c == '\'' or c == 'curly apostrophe':  # Linux
                        # doesn't recognize the UTF-8 encoding of this file
                self._space += int((self._wordSpace - self._charSpace) / 2)
            elif c == '\r':
                pass
            elif c == '+':
                code = (-self._space, +1)
                self._space = self._charSpace
            elif c == '~':
                code = (-self._space, +2)
                self._space = self._charSpace
            else:
                self._space += self._wordSpace - self._charSpace
        else:
            for e in encodeTable[cti][c]:
                if e == ' ':
                    self._space = 3 * self._dotLen
                else:
                    code += (-self._space,)
                    if e == '.':
                        code += (self._dotLen,)
                    elif e == '-':
                        code += (3 * self._dotLen,)
                    elif e == '=':
                        code += (6 * self._dotLen,)
                    elif e == '#':
                        code += (9 * self._dotLen,)
                    self._space = self._dotLen
            self._space = self._charSpace
        return code

    def exit(self):
        """
        Exit this instance.
        """
        self.shutdown()
        return

    def setWPM(self, wpm, cwpm=0):
        if cwpm == 0:
            cwpm = wpm  # adjust for legacy clients
        if self._spacing == config.Spacing.none:
            wpm = cwpm  # send text at character speed
        else:
            maxs = max(wpm, cwpm)  # send at Farnsworth speed
            mins = min(wpm, cwpm)
            cwpm = maxs
            wpm = mins
        self._dotLen    = int(1200 / cwpm)  # dot length (ms)
        self._charSpace = 3 * self._dotLen  # space between characters (ms)
        self._wordSpace = 7 * self._dotLen  # space between words (ms)
        if self._codeType == config.CodeType.american:
            self._charSpace += int((60000 / cwpm - self._dotLen * DOTSPERWORD) / 6)
            self._wordSpace = 2 * self._charSpace
        delta = (60000 / wpm) - (60000 / cwpm)  # amount to stretch each word
        if self._spacing == config.Spacing.char:
            self._charSpace += int(delta / 6)
            self._wordSpace += int(delta / 3)
        elif self._spacing == config.Spacing.word:
            self._wordSpace += int(delta)
        return

    def shutdown(self):
        """
        Initiate shutdown of our operations (and don't start anything new),
        but DO NOT BLOCK.
        """
        self._shutdown.set()
        return


"""
Code reader class

Callback function is called whenever a character is decoded:
    def callback(char, spacing)
        char - decoded character
        spacing - spacing adjustment in space widths (can be negative)
"""

MINDASHLEN      = 1.5  # dot vs dash threshold (in dots)
MAXDASHLEN      = 9.0  # long dash vs circuit closure threshold (in dots)
MINMORSESPACE   = 2.0  # intrasymbol space vs Morse (in dots)
MAXMORSESPACE   = 6.0  # maximum length of Morse space (in dots)
MINCHARSPACE    = 2.7  # intrasymbol space vs character space (in dots)
MINLLEN         = 5.0  # minimum length of L character (in dots)
MAXLLEN         = 6.9  # maximum length of L character (in dots), else it is a ZERO
MINXLLEN        = 7.0  # minimum length of 0 character (in dots)
MORSERATIO      = 0.95 # length of Morse space relative to surrounding spaces
ALPHA           = 0.5  # weight given to wpm update values (for smoothing)

# read code tables
decodeTable = [{}, {}]  # one dictionary each for American and International
def readDecodeTable(codeType, filename):
    fn = data_folder / filename
    f = codecs.open(fn, encoding='utf-8')
    f.readline()  # ignore first line
    for s in f:
        a, t, c = s.rstrip().partition('\t')
        decodeTable[codeType][c] = a  # dictionary key is code
    f.close()
    return

readDecodeTable(0, 'codetable-american.txt') # American code table is at 0 index
readDecodeTable(1, 'codetable-international.txt') # International code table is at 1 index

class Reader:
    """
    The Morse decoding algorithm has to wait until two characters have been received before
    decoding either of them. This is because what appears to be two characters may be two
    halves of a single spaced character. The two characters are kept in a buffer which (clumsily)
    is represented as three lists: codeBuf, spaceBuf, and markBuf (see details in the
    `__init__` definition below).
    """

    def __init__(self, wpm=20, cwpm=0, codeType=config.CodeType.american, callback=None, decode_at_detected=False):
        self._codeType  = codeType     # American or International
        self.setWPM(wpm, cwpm)
        self._codeBuf   = ['', '']     # code elements for two characters
        self._spaceBuf  = [0, 0]       # space before each character
        self._markBuf   = [0, 0]       # length of last dot or dash in character
        self._nChars    = 0            # number of complete characters in buffer
        self._char_callback  = callback     # function to call when character decoded
        self._decode_at_detected = decode_at_detected
        self._shutdown  = Event()      # Used to cancel running threads and shutdown operations
        self._flusher   = None         # holds Timer (thread) to call flush if no code received
        self._latched   = False        # True if cicuit has been latched closed by a +1 code element
        self._mark      = 0            # accumulates the length of a mark as positive code elements are received
        self._space     = 1            # accumulates the length of a space as negative code elements are received
        # Detected code speed values. Start with the configured speed and calculated values
        self._d_wpm:int = self._wpm
        self._d_dotLen = self._dotLen
        self._d_truDot = self._truDot
        self._d_update_missed:int = 0  # accumulates how many times the detected speed calculation wasn't performed
        return

    @property
    def char_space_max(self):
        return (self._dotLen * MAXMORSESPACE)

    @property
    def dash_len_min(self):
        return (self._dotLen * MINDASHLEN)

    @property
    def dash_len_max(self):
        return ((self._dotLen * MINLLEN) - 0.1)

    @property
    def dashlong_len_max(self):
        return ((self._dotLen * MINXLLEN) - 0.1)

    @property
    def dashxl_len_max(self):
        return (self._dotLen * MAXDASHLEN)

    @property
    def detected_dot_len(self) -> int:
        return self._d_dotLen

    @property
    def detected_dot_tru(self) -> int:
        return self._d_truDot

    @property
    def detected_wpm(self) -> int:
        return self._d_wpm

    @property
    def dot_len(self):
        return self._dotLen

    @property
    def dot_len_max(self):
        return ((self._dotLen * MINDASHLEN) - 0.1)

    @property
    def dot_tru(self):
        return self._truDot

    @property
    def intra_char_space_min(self):
        return (self._dotLen * 1.45)

    @property
    def intra_char_space_max(self):
        return ((self._dotLen + (self._dotLen * MINCHARSPACE)) - 0.1)

    @property
    def wpm(self):
        return self._wpm

    def decode(self, codeSeq, use_flusher=True):
        # Code received - cancel an existing 'flusher'
        f = self._flusher
        self._flusher = None
        if f and f.is_alive():
            f.cancel()
            f.join(0.38)
        self.updateDWPM(codeSeq)  # Update the 'detected' WPM
        nextSpace = 0  # space before next dot or dash
        i = 0
        for i in range(0, len(codeSeq)):
            c = codeSeq[i]
            if c < 0:  # start or continuation of space, or continuation of mark (if latched)
                c = -c
                if self._latched:  # circuit has been latched closed
                    self._mark += c
                elif self._space > 0:  # continuation of space
                    self._space += c
                else:  # end of mark
                    if self._mark > MINDASHLEN * self._truDot:
                        self._codeBuf[self._nChars] += '-'  # dash
                    else:
                        self._codeBuf[self._nChars] += '.'  # dot
                    self._markBuf[self._nChars] = self._mark
                    self._mark = 0
                    self._space = c
            elif c == 1:  # start (or continuation) of extended mark
                self._latched = True
                if self._space > 0:  # start of mark
                    if self._space > MINMORSESPACE * self._dotLen:  # possible Morse or word space
                        self.decodeChar(self._space)
                    self._mark = 0
                    self._space = 0
                else: # continuation of mark
                    pass
            elif c == 2:  # end of mark (or continuation of space)
                self._latched = False
            elif c > 2:  # mark
                self._latched = False
                if self._space > 0:  # start of new mark
                    if self._space > MINMORSESPACE * self._dotLen:  # possible Morse or word space
                        self.decodeChar(self._space)
                    self._mark = c
                    self._space = 0
                elif self._mark > 0:  # continuation of mark
                    self._mark += c
        if use_flusher and not self._shutdown.is_set():
            self._flusher = Timer(((20.0 * self._truDot) / 1000.0), self._flushHandler)  # if idle call `flush`
            self._flusher.setName("Reader-Flusher <:{}".format(current_thread().name))
            self._flusher.start()
        else:
            pass # To allow breakpoint for debugging
        return

    def exit(self):
        """
        Cancel the flusher (if it exists) and exit.
        """
        self.shutdown()
        f = self._flusher
        self._flusher = None
        if f and f.is_alive():
            f.cancel()
            f.join()
        return

    def setCallback(self, callback):
        self._char_callback = callback
        return

    def setWPM(self, wpm, cwpm=0):
        self._wpm       = max(wpm, cwpm)  # configured code speed
        self._dotLen    = int(1200.0 / self._wpm)  # nominal dot length (ms)
        self._truDot    = self._dotLen  # actual length of typical dot (ms)
        return

    def updateDWPM(self, codeSeq):
        """
        Update the detected WPM value from the incoming code.
        """
        for i in range(1, len(codeSeq) - 2, 2):
            minDotLen = int(0.5 * self._d_dotLen)
            maxDotLen = int(1.5 * self._d_dotLen)
            c1 = codeSeq[i]
            c2 = codeSeq[i+1]
            c3 = codeSeq[i+2]
            du_len = c1 - c2
            if ((c1 > minDotLen)
                and (c1 < maxDotLen)
                and (du_len < (2 * maxDotLen))
                and (c3 < maxDotLen)
            ):
                dotLen = int(du_len / 2.0)
                self._d_truDot = int(ALPHA * c1 + (1 - ALPHA) * self._d_truDot)
                self._d_dotLen = int(ALPHA * dotLen + (1 - ALPHA) * self._d_dotLen)
                self._d_wpm = int(1200.0 / self._d_dotLen)
                self._d_update_missed = 0
            else:
                self._d_update_missed += 1
                if self._d_update_missed > 8:
                    # We haven't matched the criteria to get into the update calculation
                    # for over 8 code pairs. Try a less granular value. This might not
                    # be correct, but will hopefully get us to fall into the calculation
                    # on subsequent code sequences.
                    d2 = c1 * 2
                    du_diff = abs(d2 - du_len)
                    du_delta = du_diff / 100.0
                    if du_delta < 0.05:
                        # The down/up appears to be a dot. Use this as a new speed
                        self._d_truDot = int(du_len / 2.0)
                        self._d_dotLen = self._d_truDot
                        self._d_wpm = int(2400.0 / du_len)
                        self._d_update_missed = 0
                    pass
                pass
            pass
        #
        # If the decode_at_detected option is on and the detected WPM is different than
        # the current WPM/CPM, set the WPM/CPM.
        if self._decode_at_detected and not self._d_wpm == self._wpm:
            self.setWPM(self._d_wpm)
        return

    def _flushHandler(self):
        f = self._flusher
        self._flusher = None
        if f:
            self.flush()
        return

    def flush(self):
        f = self._flusher
        self._flusher = None
        if f:
            f.cancel()
            if f.is_alive():
                f.join(0.40)
            pass
        if self._mark > 0 or self._latched:
            spacing = self._spaceBuf[self._nChars]
            if self._mark > MINDASHLEN * self._truDot:
                self._codeBuf[self._nChars] += '-'  # dash
            elif self._mark > 2:
                self._codeBuf[self._nChars] += '.'  # dot
            self._markBuf[self._nChars] = self._mark
            self._mark = 0
            self._space = 1  # to prevent circuit opening mistakenly decoding as 'E'
            self.decodeChar(MAXINT)
            self.decodeChar(MAXINT)  # a second time, to flush both characters
            self._codeBuf = ['', '']
            self._spaceBuf = [0, 0]
            self._markBuf = [0, 0]
            self._nChars = 0
            cb = self._char_callback
            if self._latched and cb:
                cb('\n_', float(spacing) / (3 * self._truDot) - 1)
        return

    def decodeChar(self, nextSpace):
        self._nChars += 1  # number of complete characters in buffer (1 or 2)
        sp1 = self._spaceBuf[0]  # space before 1st character
        sp2 = self._spaceBuf[1]  # space before 2nd character
        sp3 = nextSpace  # space before next character
        code = ''  # the dots and dashes
        s = ''  # the decoded character or pair of characters
        if self._nChars == 2 and sp2 < MAXMORSESPACE * self._dotLen and \
                MORSERATIO * sp1 > sp2 and sp2 < MORSERATIO * sp3:  # could be two halves of a spaced character
            code = self._codeBuf[0] + ' ' + self._codeBuf[1]  # try combining the two halves
            s = self.lookupChar(code)
            if s != '' and s != '&':  # yes, it's a spaced character, clear the whole buffer
                self._codeBuf[0] = ''
                self._markBuf[0] = 0
                self._codeBuf[1] = ''
                self._spaceBuf[1] = 0
                self._markBuf[1] = 0
                self._nChars = 0
            else:  # it's not recognized as a spaced character,
                code = ''
                s = ''
        if self._nChars == 2 and sp2 < MINCHARSPACE * self._dotLen:  # it's a single character, merge the two halves
            self._codeBuf[0] += self._codeBuf[1]
            self._markBuf[0] = self._markBuf[1]
            self._codeBuf[1] = ''
            self._spaceBuf[1] = 0
            self._markBuf[1] = 0
            self._nChars = 1
        if self._nChars == 2:  # decode the first character, otherwise wait for the next one to arrive
            code = self._codeBuf[0]
            s = self.lookupChar(code)
            if s == 'T' and self._markBuf[0] > MAXDASHLEN * self._dotLen:
                s = '_'
            elif s == 'T' and self._markBuf[0] > MINLLEN * self._dotLen and \
                    self._codeType == config.CodeType.american:
                s = 'L'
            elif s == 'E':
                if self._markBuf[0] == 1:
                    s = '_'
                elif self._markBuf[0] == 2:
                    s = '_'
                    sp1 = 0  ### ZZZ eliminate space between underscores
            self._codeBuf[0] = self._codeBuf[1]
            self._spaceBuf[0] = self._spaceBuf[1]
            self._markBuf[0] = self._markBuf[1]
            self._codeBuf[1] = ''
            self._spaceBuf[1] = 0
            self._markBuf[1] = 0
            self._nChars = 1
        self._spaceBuf[self._nChars] = nextSpace
        if code != '' and s == '':
            s = '[' + code + ']'
        cb = self._char_callback
        if s != '' and cb:
            cb(s, float(sp1) / (3 * self._truDot) - 1)
        return

    def lookupChar(self, code):
        codeTableIndex = 0 if self._codeType == config.CodeType.american else 1
        if code in decodeTable[codeTableIndex]:
            return(decodeTable[codeTableIndex][code])
        else:
            return('')

    def shutdown(self):
        """
        Initiate shutdown of our operations (and don't start anything new),
        but DO NOT BLOCK.
        """
        self._shutdown.set()
        self._char_callback = None
        f = self._flusher
        if not f is None and f.is_alive():
            f.cancel()
        return

    def displayBuffers(self, text):
        """Display the code buffer and other information for troubleshooting"""
        log.debug("{}: nChars = {}".format(text, self._nChars))
        for i in range(2):
            print("{} '{}' {}".format(self._spaceBuf[i], self._codeBuf[i], self._markBuf[i]))
        return
