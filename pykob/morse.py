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
morse.py

Provides classes for sending and reading American and International Morse code.
"""

import sys
import codecs
from pathlib import Path
from threading import Timer
from pykob import config, log

DOTSPERWORD = 45     # dot units per word, including all spaces
                     #   (MORSE is 43, PARIS is 47)
MAXINT = sys.maxsize # a very large integer

"""
Code sender class
"""

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

readEncodeTable(config.CodeType.american, 'codetable-american.txt')
readEncodeTable(config.code_type.international, 'codetable-international.txt')

class Sender:
    def __init__(self, wpm, cwpm=0, codeType=config.CodeType.american, spacing=config.Spacing.char):
        self.__codeType = codeType
        self.__spacing = spacing
        self.setWPM(wpm, cwpm)
        self.__space = self.__wordSpace  # delay before next code element (ms)
        
    @property
    def dot_len(self):
        return self.__dotLen
    
    @property
    def dash_len(self):
        return (3.0 * self.__dotLen)
    
    @property
    def long_dash_len(self):
        if self.__codeType == config.CodeType.american:
            return (6.0 * self.__dotLen)
        else:
            return (-1.0)
        
    @property
    def xl_dash_len(self):
        if self.__codeType == config.CodeType.american:
            return (8.0 * self.__dotLen)
        else:
            return (-1.0)
        
    @property
    def intra_char_space_len(self):
        if self.__codeType == config.CodeType.american:
            return (3 * self.__dotLen)
        else:
            return (-1.0)
        
    @property
    def char_space_len(self):
        return (self.__charSpace)
    
    @property
    def word_space_len(self):
        return (self.__wordSpace)

    def encode(self, char, printChar=False):
        c = char.upper()
        if (printChar):
            print(c, end="", flush=True)
        code = ()
        cti = 0 if self.__codeType == config.CodeType.american else 1
        if not c in encodeTable[cti]:
            if c == '-' or c == '\'' or c == 'curly apostrophe':  # Linux
                        # doesn't recognize the UTF-8 encoding of this file
                self.__space += int((self.__wordSpace - self.__charSpace) / 2)
            elif c == '\r':
                pass
            elif c == '+':
                code = (-self.__space, +1)
                self.__space = self.__charSpace
            elif c == '~':
                code = (-self.__space, +2)
                self.__space = self.__charSpace
            else:
                self.__space += self.__wordSpace - self.__charSpace
        else:
            for e in encodeTable[cti][c]:
                if e == ' ':
                    self.__space = 3 * self.__dotLen
                else:
                    code += (-self.__space,)
                    if e == '.':
                        code += (self.__dotLen,)
                    elif e == '-':
                        code += (3 * self.__dotLen,)
                    elif e == '=':
                        code += (6 * self.__dotLen,)
                    elif e == '#':
                        code += (9 * self.__dotLen,)
                    self.__space = self.__dotLen
            self.__space = self.__charSpace
        return code

    def setWPM(self, wpm, cwpm=0):
        if self.__spacing == config.Spacing.none:
            cwpm = wpm  # send characters at overall code speed
        else:
            cwpm = max(wpm, cwpm)  # send at Farnsworth speed
        self.__dotLen    = int(1200 / cwpm)  # dot length (ms)
        self.__charSpace = 3 * self.__dotLen  # space between characters (ms)
        self.__wordSpace = 7 * self.__dotLen  # space between words (ms)
        if self.__codeType == config.CodeType.american:
            self.__charSpace += int((60000 / cwpm - self.__dotLen * DOTSPERWORD) / 6)
            self.__wordSpace = 2 * self.__charSpace
        delta = 60000 / wpm - 60000 / cwpm  # amount to stretch each word
        if self.__spacing == config.Spacing.char:
            self.__charSpace += int(delta / 6)
            self.__wordSpace += int(delta / 3)
        elif self.__spacing == config.Spacing.word:
            self.__wordSpace += int(delta)


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
    
    def __init__(self, wpm=20, cwpm=0, codeType=config.CodeType.american, callback=None):
        self.__codeType  = codeType     # American or International
        self.setWPM(wpm, cwpm)
        self.__codeBuf   = ['', '']     # code elements for two characters
        self.__spaceBuf  = [0, 0]       # space before each character
        self.__markBuf   = [0, 0]       # length of last dot or dash in character
        self.__nChars    = 0            # number of complete characters in buffer
        self.__callback  = callback     # function to call when character decoded
        self.__flusher   = None         # holds Timer (thread) to call flush if no code received
        self.__latched   = False        # True if cicuit has been latched closed by a +1 code element
        self.__mark      = 0            # accumulates the length of a mark as positive code elements are received
        self.__space     = 1            # accumulates the length of a space as negative code elements are received
        # Detected code speed values. Start with the configured speed and calculated values
        self.__d_wpm = self.__wpm
        self.__d_dotLen = self.__dotLen
        self.__d_truDot = self.__truDot

    @property
    def wpm(self):
        return self.__wpm
    
    @property
    def dot_len(self):
        return self.__dotLen
    
    @property
    def dot_len_max(self):
        return ((self.__dotLen * MINDASHLEN) - 0.1)
    
    @property
    def dash_len_min(self):
        return (self.__dotLen * MINDASHLEN)
    
    @property
    def dash_len_max(self):
        return ((self.__dotLen * MINLLEN) - 0.1)
    
    @property
    def dashlong_len_max(self):
        return ((self.__dotLen * MINXLLEN) - 0.1)
    
    @property
    def dashxl_len_max(self):
        return (self.__dotLen * MAXDASHLEN)

    @property
    def intra_char_space_min(self):
        return (self.__dotLen * 1.45)
    
    @property
    def intra_char_space_max(self):
        return ((self.__dotLen + (self.__dotLen * MINCHARSPACE)) - 0.1)
    
    @property
    def char_space_max(self):
        return (self.__dotLen * MAXMORSESPACE)

    def decode(self, codeSeq):
        # Code received - cancel an existing 'flusher'
        if self.__flusher:
            self.__flusher.cancel()
            self.__flusher = None
        self.updateDWPM(codeSeq)  # Update the 'detected' WPM
        nextSpace = 0  # space before next dot or dash
        i = 0
        for i in range(0, len(codeSeq)):
            c = codeSeq[i]
            if c < 0:  # start or continuation of space, or continuation of mark (if latched)
                c = -c
                if self.__latched:  # circuit has been latched closed
                    self.__mark += c
                elif self.__space > 0:  # continuation of space
                    self.__space += c
                else:  # end of mark
                    if self.__mark > MINDASHLEN * self.__truDot:
                        self.__codeBuf[self.__nChars] += '-'  # dash
                    else:
                        self.__codeBuf[self.__nChars] += '.'  # dot
                    self.__markBuf[self.__nChars] = self.__mark
                    self.__mark = 0
                    self.__space = c
            elif c == 1:  # start (or continuation) of extended mark
                self.__latched = True
                if self.__space > 0:  # start of mark
                    if self.__space > MINMORSESPACE * self.__dotLen:  # possible Morse or word space
                        self.decodeChar(self.__space)
                    self.__mark = 0
                    self.__space = 0
                else: # continuation of mark
                    pass
            elif c == 2:  # end of mark (or continuation of space)
                self.__latched = False
            elif c > 2:  # mark
                self.__latched = False
                if self.__space > 0:  # start of new mark
                    if self.__space > MINMORSESPACE * self.__dotLen:  # possible Morse or word space
                        self.decodeChar(self.__space)
                    self.__mark = c
                    self.__space = 0
                elif self.__mark > 0:  # continuation of mark
                    self.__mark += c
        self.__flusher = Timer(((20.0 * self.__truDot) / 1000.0), self.flush)  # if idle call `flush`
        self.__flusher.setName("Reader-Flusher")
        self.__flusher.start()

    def exit(self):
        """
        Cancel the flusher (if it exists) and exit.
        """
        if self.__flusher:
            self.__flusher.cancel()
            self.__flusher = None
            
    def setWPM(self, wpm, cwpm=0):
        self.__wpm       = max(wpm, cwpm)  # configured code speed
        self.__dotLen    = int(1200.0 / self.__wpm)  # nominal dot length (ms)
        self.__truDot    = self.__dotLen  # actual length of typical dot (ms)

    def updateDWPM(self, codeSeq):
        for i in range(1, len(codeSeq) - 2, 2):
            minDotLen = int(0.5 * self.__d_dotLen)
            maxDotLen = int(1.5 * self.__d_dotLen)
            if codeSeq[i] > minDotLen and codeSeq[i] < maxDotLen and \
                    codeSeq[i] - codeSeq[i+1] < 2 * maxDotLen and \
                    codeSeq[i+2] < maxDotLen:
                dotLen = (codeSeq[i] - codeSeq[i+1]) / 2
                self.__d_truDot = int(ALPHA * codeSeq[i] + (1 - ALPHA) * self.__d_truDot)
                self.__d_dotLen = int(ALPHA * dotLen + (1 - ALPHA) * self.__d_dotLen)
                self.__d_wpm = 1200. / self.__d_dotLen

    def flush(self):
        if self.__flusher:
            self.__flusher.cancel()
            self.__flusher = None
        if self.__mark > 0 or self.__latched:
            spacing = self.__spaceBuf[self.__nChars]
            if self.__mark > MINDASHLEN * self.__truDot:
                self.__codeBuf[self.__nChars] += '-'  # dash
            elif self.__mark > 2:
                self.__codeBuf[self.__nChars] += '.'  # dot
            self.__markBuf[self.__nChars] = self.__mark
            self.__mark = 0
            self.__space = 1  # to prevent circuit opening mistakenly decoding as 'E'
            self.decodeChar(MAXINT)
            self.decodeChar(MAXINT)  # a second time, to flush both characters
            self.__codeBuf = ['', '']
            self.__spaceBuf = [0, 0]
            self.__markBuf = [0, 0]
            self.__nChars = 0
            if self.__latched:
                self.__callback('_', float(spacing) / (3 * self.__truDot) - 1)

    def decodeChar(self, nextSpace):
        self.__nChars += 1  # number of complete characters in buffer (1 or 2)
        sp1 = self.__spaceBuf[0]  # space before 1st character
        sp2 = self.__spaceBuf[1]  # space before 2nd character
        sp3 = nextSpace  # space before next character
        code = ''  # the dots and dashes
        s = ''  # the decoded character or pair of characters
        if self.__nChars == 2 and sp2 < MAXMORSESPACE * self.__dotLen and \
                MORSERATIO * sp1 > sp2 and sp2 < MORSERATIO * sp3:  # could be two halves of a spaced character
            code = self.__codeBuf[0] + ' ' + self.__codeBuf[1]  # try combining the two halves
            s = self.lookupChar(code)
            if s != '' and s != '&':  # yes, it's a spaced character, clear the whole buffer
                self.__codeBuf[0] = ''
                self.__markBuf[0] = 0
                self.__codeBuf[1] = ''
                self.__spaceBuf[1] = 0
                self.__markBuf[1] = 0
                self.__nChars = 0
            else:  # it's not recognized as a spaced character,
                code = ''
                s = ''
        if self.__nChars == 2 and sp2 < MINCHARSPACE * self.__dotLen:  # it's a single character, merge the two halves
            self.__codeBuf[0] += self.__codeBuf[1]
            self.__markBuf[0] = self.__markBuf[1]
            self.__codeBuf[1] = ''
            self.__spaceBuf[1] = 0
            self.__markBuf[1] = 0
            self.__nChars = 1
        if self.__nChars == 2:  # decode the first character, otherwise wait for the next one to arrive
            code = self.__codeBuf[0]
            s = self.lookupChar(code)
            if s == 'T' and self.__markBuf[0] > MAXDASHLEN * self.__dotLen:
                s = '_'
            elif s == 'T' and self.__markBuf[0] > MINLLEN * self.__dotLen and \
                    self.__codeType == config.CodeType.american:
                s = 'L'
            elif s == 'E':
                if self.__markBuf[0] == 1:
                    s = '_'
                elif self.__markBuf[0] == 2:
                    s = '_'
                    sp1 = 0  ### ZZZ eliminate space between underscores
            self.__codeBuf[0] = self.__codeBuf[1]
            self.__spaceBuf[0] = self.__spaceBuf[1]
            self.__markBuf[0] = self.__markBuf[1]
            self.__codeBuf[1] = ''
            self.__spaceBuf[1] = 0
            self.__markBuf[1] = 0
            self.__nChars = 1
        self.__spaceBuf[self.__nChars] = nextSpace
        if code != '' and s == '':
            s = '[' + code + ']'
        if s != '':
            self.__callback(s, float(sp1) / (3 * self.__truDot) - 1)

    def lookupChar(self, code):
        codeTableIndex = 0 if self.__codeType == config.CodeType.american else 1
        if code in decodeTable[codeTableIndex]:
            return(decodeTable[codeTableIndex][code])
        else:
            return('')

    def displayBuffers(self, text):
        """Display the code buffer and other information for troubleshooting"""
        log.debug("{}: nChars = {}".format(text, self.__nChars))
        for i in range(2):
            print("{} '{}' {}".format(self.__spaceBuf[i], self.__codeBuf[i], self.__markBuf[i]))
