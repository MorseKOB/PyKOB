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

from __future__ import print_function  ###

import sys, os
import codecs

AMERICAN = 0         # American Morse
INTERNATIONAL = 1    # International Morse
CHARSPACING = 0      # add Farnsworth spacing between all characters
WORDSPACING = 1      # add Farnsworth spacing only between words
DOTSPERWORD = 45     # dot units per word, including all spaces
                     #   (MORSE is 43, PARIS is 47)
MAXINT = 1000000     # sys.maxint not supported in Python 3

"""
Code sender class
"""

# read code tables
encodeTable = [{}, {}]  # one dictionary each for American and International
dir = os.path.dirname(os.path.abspath(__file__))
def readEncodeTable(codeType, filename):
    fn = os.path.join(dir, filename)
    f = codecs.open(fn, encoding='utf-8')
    f.readline()  # ignore first line
    for s in f:
        a, t, c = s.rstrip().partition('\t')
        encodeTable[codeType][a] = c  # dictionary key is character
    f.close()
readEncodeTable(AMERICAN, 'codetable-american.txt')
readEncodeTable(INTERNATIONAL, 'codetable-international.txt')

class Sender:
    def __init__(self, wpm, cwpm=0, codeType=AMERICAN, spacing=CHARSPACING):
        self.codeType = codeType
        cwpm = max(wpm, cwpm)
        self.dotLen    = int(1200 / cwpm)  # dot length (ms)
        self.charSpace = 3 * self.dotLen  # space between characters (ms)
        self.wordSpace = 7 * self.dotLen  # space between words (ms)
        if codeType == AMERICAN:
            self.charSpace += int((60000 / cwpm - self.dotLen *
                    DOTSPERWORD) / 6)
            self.wordSpace = 2 * self.charSpace
        delta = 60000 / wpm - 60000 / cwpm  # amount to stretch each word
        if spacing == CHARSPACING:
            self.charSpace += int(delta / 6)
            self.wordSpace += int(delta / 3)
        elif spacing == WORDSPACING:
            self.wordSpace += int(delta)
        self.space = self.wordSpace  # delay before next code element (ms)
        
    def encode(self, char):
        c = char.upper()
        code = ()
        if not c in encodeTable[self.codeType]:
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
            for e in encodeTable[self.codeType][c]:
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

Optional callback function is called whenever a character is decoded:
    def callback(char, spacing)
        char - decoded character
        spacing - spacing adjustment in space widths (can be negative)
"""

MINDASHLEN      = 1.5  # dot vs dash threshold (in dots)
MINMORSESPACE   = 2.0  # intrasymbol space vs Morse (in dots)
MAXMORSESPACE   = 6.0  # maximum length of Morse space (in dots)
MINCHARSPACE    = 2.7  # intrasymbol space vs character space (in dots)
MINLLEN         = 4.5  # minimum length of L character (in dots)
MORSERATIO      = 0.95 # length of Morse space relative to surrounding spaces
ALPHA           = 0.5  # weight given to wpm update values (for smoothing)

# read code tables
decodeTable = [{}, {}]  # one dictionary each for American and International
def readDecodeTable(codeType, filename):
    fn = os.path.dirname(os.path.abspath(__file__)) + '/' + filename
    f = codecs.open(fn, encoding='utf-8')
    f.readline()  # ignore first line
    for s in f:
        a, t, c = s.rstrip().partition('\t')
        decodeTable[codeType][c] = a  # dictionary key is code
    f.close()
readDecodeTable(AMERICAN, 'codetable-american.txt')
readDecodeTable(INTERNATIONAL, 'codetable-international.txt')

class Reader:
    def __init__(self, wpm=20, codeType=AMERICAN, callback=None):
        self.codeType  = codeType    # American or International
        self.wpm       = wpm         # current code speed estimate
        self.dotLen    = int(1200. / wpm)  # nominal dot length (ms)
        self.truDot    = self.dotLen # actual length of typical dot (ms)
        self.codeBuf   = ['', '']    # code elements for two characters
        self.spaceBuf  = [0, 0]      # space before each character
        self.markBuf   = [0, 0]      # length of last dot or dash in character
        self.nChars    = 0           # number of complete characters in buffer
        self.callback  = callback    # function to call when character decoded

    def decode(self, codeSeq):
        self.updateWPM(codeSeq)
        i = 0
        for i in range(0, len(codeSeq), 2):
            sp = -codeSeq[i]
            mk = codeSeq[i+1]
            if self.codeBuf[self.nChars] == '':
                self.spaceBuf[self.nChars] = sp  # start of new char
            else:
                if sp > MINMORSESPACE * self.dotLen:
                    self.decodeChar(sp)  # possible Morse or word space
            if mk > MINDASHLEN * self.truDot:
                self.codeBuf[self.nChars] += '-'  # dash
            else:
                self.codeBuf[self.nChars] += '.'  # dot
            self.markBuf[self.nChars] = mk

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
##                print('{} {:.1f} {}'.format(self.dotLen, self.wpm, self.truDot))

    def flush(self):
        self.decodeChar(MAXINT)
        self.decodeChar(MAXINT)

    def decodeChar(self, nextSpace):
        self.nChars += 1
        sp1 = self.spaceBuf[0]
        sp2 = self.spaceBuf[1]
        sp3 = nextSpace
        code = ''
        s = ''
        if self.nChars == 2 and sp2 < MAXMORSESPACE * self.dotLen and \
                MORSERATIO * sp1 > sp2 and sp2 < MORSERATIO * sp3:
            code = self.codeBuf[0] + ' ' + self.codeBuf[1]
            s = self.lookupChar(code)
            if s != '' and s != '&':
                self.codeBuf[0] = ''
                self.markBuf[0] = 0
                self.codeBuf[1] = ''
                self.spaceBuf[1] = 0
                self.markBuf[1] = 0
                self.nChars = 0
            else:
                code = ''
                s = ''
        if self.nChars == 2 and sp2 < MINCHARSPACE * self.dotLen:
            self.codeBuf[0] += self.codeBuf[1]
            self.markBuf[0] = self.markBuf[1]
            self.codeBuf[1] = ''
            self.spaceBuf[1] = 0
            self.markBuf[1] = 0
            self.nChars = 1
        if self.nChars == 2:
            code = self.codeBuf[0]
            s = self.lookupChar(code)
            if s == 'T' and self.markBuf[0] > MINLLEN * self.dotLen:
                s = 'L'
            elif s == 'E':
                if self.markBuf[0] == 1:
                    s = '+'
                elif self.markBuf[0] == 2:
                    s = '~'
            self.codeBuf[0] = self.codeBuf[1]
            self.spaceBuf[0] = self.spaceBuf[1]
            self.markBuf[0] = self.markBuf[1]
            self.codeBuf[1] = ''
            self.spaceBuf[1] = 0
            self.markBuf[1] = 0
            self.nChars -= 1
        self.spaceBuf[self.nChars] = nextSpace
        if code != '' and s == '':
            s = '[' + code + ']'
        if s != '':
            self.callback(s, float(sp1) / (3 * self.dotLen) - 1)

    def lookupChar(self, code):
        if code in decodeTable[self.codeType]:
            return(decodeTable[self.codeType][code])
        else:
            return('')
