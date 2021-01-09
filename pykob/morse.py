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
        self.codeType = codeType
        if spacing == config.Spacing.none:
            cwpm = wpm  # send characters at overall code speed
        else:
            cwpm = max(wpm, cwpm)  # send at Farnsworth speed
        self.dotLen    = int(1200 / cwpm)  # dot length (ms)
        self.charSpace = 3 * self.dotLen  # space between characters (ms)
        self.wordSpace = 7 * self.dotLen  # space between words (ms)
        if codeType == config.CodeType.american:
            self.charSpace += int((60000 / cwpm - self.dotLen *
                    DOTSPERWORD) / 6)
            self.wordSpace = 2 * self.charSpace
        delta = 60000 / wpm - 60000 / cwpm  # amount to stretch each word
        if spacing == config.Spacing.char:
            self.charSpace += int(delta / 6)
            self.wordSpace += int(delta / 3)
        elif spacing == config.Spacing.word:
            self.wordSpace += int(delta)
        self.space = self.wordSpace  # delay before next code element (ms)
        
    def encode(self, char, printChar=False):
        c = char.upper()
        if (printChar):
            print(c, end="", flush=True)
        code = ()
        cti = 0 if self.codeType == config.CodeType.american else 1
        if not c in encodeTable[cti]:
            if c == '-' or c == '\'' or c == 'curly apostrophe':  # Linux
                        # doesn't recognize the UTF-8 encoding of this file
                self.space += int((self.wordSpace - self.charSpace) / 2)
            elif c == '\r':
                pass
            elif c == '+':
                code = (-self.space, +1)
                self.space = self.charSpace
            elif c == '~':
                code = (-self.space, +2)
                self.space = self.charSpace
            else:
                self.space += self.wordSpace - self.charSpace
        else:
            for e in encodeTable[cti][c]:
                if e == ' ':
                    self.space = 3 * self.dotLen
                else:
                    code += (-self.space,)
                    if e == '.':
                        code += (self.dotLen,)
                    elif e == '-':
                        code += (3 * self.dotLen,)
                    elif e == '=':
                        code += (6 * self.dotLen,)
                    elif e == '#':
                        code += (9 * self.dotLen,)
                    self.space = self.dotLen
            self.space = self.charSpace
        return code


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
    
    def __init__(self, wpm=20, codeType=config.CodeType.american, callback=None):
        self.codeType  = codeType    # American or International
        self.wpm       = wpm         # current code speed estimate
        self.dotLen    = int(1200. / wpm)  # nominal dot length (ms)
        self.truDot    = self.dotLen # actual length of typical dot (ms)
        self.codeBuf   = ['', '']    # code elements for two characters
        self.spaceBuf  = [0, 0]      # space before each character
        self.markBuf   = [0, 0]      # length of last dot or dash in character
        self.nChars    = 0           # number of complete characters in buffer
        self.callback  = callback    # function to call when character decoded
        self.flusher   = None        # holds Timer (thread) to call flush if no code received
        self.latched   = False       # True if cicuit has been latched closed by a +1 code element
        self.mark      = 0           # accumulates the length of a mark as positive code elements are received
        self.space     = 1           # accumulates the length of a space as negative code elements are received

    def decode(self, codeSeq):
        # Code received - cancel an existing 'flusher'
        if self.flusher:
            self.flusher.cancel()
            self.flusher = None
##        self.updateWPM(codeSeq)  ### ZZZ temporarily disable code speed recognition
        nextSpace = 0  # space before next dot or dash
        i = 0
        for i in range(0, len(codeSeq)):
            c = codeSeq[i]
            if c < 0:  # start or continuation of space, or continuation of mark (if latched)
                c = -c
                if self.latched:  # circuit has been latched closed
                    self.mark += c
                elif self.space > 0:  # continuation of space
                    self.space += c
                else:  # end of mark
                    if self.mark > MINDASHLEN * self.truDot:
                        self.codeBuf[self.nChars] += '-'  # dash
                    else:
                        self.codeBuf[self.nChars] += '.'  # dot
                    self.markBuf[self.nChars] = self.mark
                    self.mark = 0
                    self.space = c
            elif c == 1:  # start (or continuation) of extended mark
                self.latched = True
                if self.space > 0:  # start of mark
                    if self.space > MINMORSESPACE * self.dotLen:  # possible Morse or word space
                        self.decodeChar(self.space)
                    self.mark = 0
                    self.space = 0
                else: # continuation of mark
                    pass
            elif c == 2:  # end of mark (or continuation of space)
                self.latched = False
            elif c > 2:  # mark
                self.latched = False
                if self.space > 0:  # start of new mark
                    if self.space > MINMORSESPACE * self.dotLen:  # possible Morse or word space
                        self.decodeChar(self.space)
                    self.mark = c
                    self.space = 0
                elif self.mark > 0:  # continuation of mark
                    self.mark += c
        self.flusher = Timer(((20.0 * self.truDot) / 1000.0), self.flush)  # if idle call `flush`
        self.flusher.setName("Reader-Flusher")
        self.flusher.start()

    def setWPM(self, wpm):
        self.wpm = wpm
        self.dotLen = int(1200. / wpm)
        self.truDot = self.dotLen

    def updateWPM(self, codeSeq):
        for i in range(1, len(codeSeq) - 2, 2):
            minDotLen = int(0.5 * self.dotLen)
            maxDotLen = int(1.5 * self.dotLen)
            if codeSeq[i] > minDotLen and codeSeq[i] < maxDotLen and \
                    codeSeq[i] - codeSeq[i+1] < 2 * maxDotLen and \
                    codeSeq[i+2] < maxDotLen:
                dotLen = (codeSeq[i] - codeSeq[i+1]) / 2
                self.truDot = int(ALPHA * codeSeq[i] + (1 - ALPHA) * self.truDot)
                self.dotLen = int(ALPHA * dotLen + (1 - ALPHA) * self.dotLen)
                self.wpm = 1200. / self.dotLen

    def flush(self):
        if self.flusher:
            self.flusher.cancel()
            self.flusher = None
        if self.mark > 0 or self.latched:
            spacing = self.spaceBuf[self.nChars]
            if self.mark > MINDASHLEN * self.truDot:
                self.codeBuf[self.nChars] += '-'  # dash
            elif self.mark > 2:
                self.codeBuf[self.nChars] += '.'  # dot
            self.markBuf[self.nChars] = self.mark
            self.mark = 0
            self.space = 1  # to prevent circuit opening mistakenly decoding as 'E'
            self.decodeChar(MAXINT)
            self.decodeChar(MAXINT)  # a second time, to flush both characters
            self.codeBuf = ['', '']
            self.spaceBuf = [0, 0]
            self.markBuf = [0, 0]
            self.nChars = 0
            if self.latched:
                self.callback('_', float(spacing) / (3 * self.truDot) - 1)

    def decodeChar(self, nextSpace):
        self.nChars += 1  # number of complete characters in buffer (1 or 2)
        sp1 = self.spaceBuf[0]  # space before 1st character
        sp2 = self.spaceBuf[1]  # space before 2nd character
        sp3 = nextSpace  # space before next character
        code = ''  # the dots and dashes
        s = ''  # the decoded character or pair of characters
        if self.nChars == 2 and sp2 < MAXMORSESPACE * self.dotLen and \
                MORSERATIO * sp1 > sp2 and sp2 < MORSERATIO * sp3:  # could be two halves of a spaced character
            code = self.codeBuf[0] + ' ' + self.codeBuf[1]  # try combining the two halves
            s = self.lookupChar(code)
            if s != '' and s != '&':  # yes, it's a spaced character, clear the whole buffer
                self.codeBuf[0] = ''
                self.markBuf[0] = 0
                self.codeBuf[1] = ''
                self.spaceBuf[1] = 0
                self.markBuf[1] = 0
                self.nChars = 0
            else:  # it's not recognized as a spaced character,
                code = ''
                s = ''
        if self.nChars == 2 and sp2 < MINCHARSPACE * self.dotLen:  # it's a single character, merge the two halves
            self.codeBuf[0] += self.codeBuf[1]
            self.markBuf[0] = self.markBuf[1]
            self.codeBuf[1] = ''
            self.spaceBuf[1] = 0
            self.markBuf[1] = 0
            self.nChars = 1
        if self.nChars == 2:  # decode the first character, otherwise wait for the next one to arrive
            code = self.codeBuf[0]
            s = self.lookupChar(code)
            if s == 'T' and self.markBuf[0] > MAXDASHLEN * self.dotLen:
                s = '_'
            elif s == 'T' and self.markBuf[0] > MINLLEN * self.dotLen and \
                    self.codeType == config.CodeType.american:
                s = 'L'
            elif s == 'E':
                if self.markBuf[0] == 1:
                    s = '_'
                elif self.markBuf[0] == 2:
                    s = '_'
                    sp1 = 0  ### ZZZ eliminate space between underscores
            self.codeBuf[0] = self.codeBuf[1]
            self.spaceBuf[0] = self.spaceBuf[1]
            self.markBuf[0] = self.markBuf[1]
            self.codeBuf[1] = ''
            self.spaceBuf[1] = 0
            self.markBuf[1] = 0
            self.nChars = 1
        self.spaceBuf[self.nChars] = nextSpace
        if code != '' and s == '':
            s = '[' + code + ']'
        if s != '':
            self.callback(s, float(sp1) / (3 * self.truDot) - 1)

    def lookupChar(self, code):
        codeTableIndex = 0 if self.codeType == config.CodeType.american else 1
        if code in decodeTable[codeTableIndex]:
            return(decodeTable[codeTableIndex][code])
        else:
            return('')

    def displayBuffers(self, text):
        """Display the code buffer and other information for troubleshooting"""
        log.debug("{}: nChars = {}".format(text, self.nChars))
        for i in range(2):
            print("{} '{}' {}".format(self.spaceBuf[i], self.codeBuf[i], self.markBuf[i]))