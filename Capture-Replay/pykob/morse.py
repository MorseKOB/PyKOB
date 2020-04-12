"""

morse.py

Provides classes for sending and reading American and International Morse code.

"""

import sys, os
import codecs
import threading
import time

AMERICAN = 0         # American Morse
INTERNATIONAL = 1    # International Morse
ESPERANTO = 2        # International Morse with Esperanto letters
CHARSPACING = 0      # add Farnsworth spacing between all characters
WORDSPACING = 1      # add Farnsworth spacing only between words
DOTSPERWORD = 45     # dot units per word, including all spaces
                     #   (MORSE is 43, PARIS is 47)
FLUSH = 0.5          # delay before forcing decoding of last character (sec)
MAXINT = 1000000     # sys.maxint not supported in Python 3

"""
Code sender class
"""

# read code tables
encodeTable = [{}, {}, {}]  # one dictionary each for American and International
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
readEncodeTable(ESPERANTO, 'codetable-esperanto.txt')

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

# read code tables
decodeTable = [{}, {}, {}]  # one dictionary each for American and International
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
readDecodeTable(ESPERANTO, 'codetable-esperanto.txt')

class Reader:
    def __init__(self, wpm=20, codeType=AMERICAN, callback=None):
        self.codeType  = codeType
        self.dotLen    = 1200 / wpm  # dot length (ms)
        self.currSpace = 0   # space before current character
        self.currCode  = ''  # code elements for current character
        self.currMark  = 0   # length of last dot or dash in current character
        self.prevSpace = 0   # space before previous character
        self.prevCode  = ''  # code elements for previous character
        self.prevMark  = 0   # length of last dot or dash in previous character
        self.callback  = callback
        self.tLastDecode = sys.float_info.max  # no decodes so far
        self.decodeLock = threading.Lock()
        autoFlushThread = threading.Thread(target=self.autoFlush)
        autoFlushThread.daemon = True
##        autoFlushThread.start()  # TEMP

    def decode(self, code):
        with self.decodeLock:
##            self.tLastDecode = sys.float_info.max
            for c in code:
                if c < 0:
                    sp = -c
                    if self.currCode[-1:] == '.' and \
                            self.currMark + sp > 3 * self.dotLen or \
                            self.currCode[-1:] == '-' and \
                            sp > 2 * self.dotLen:
                        self.decodeCodePair(sp)
                    elif self.currCode == '':
                        self.currSpace = sp
                elif c == 1:  # latch into mark state
                    self.flush()
                    self.callback('+', self.currSpace)
                elif c == 2:  # unlatch into space state
                    self.flush()
                    self.callback('~', self.currSpace)
                elif c > 2:
                    mk = c
                    if mk < 2 * self.dotLen:
                        self.currCode += '.'
                    else:
                        self.currCode += '-'
                    self.currMark = mk;
            self.tLastDecode = time.time()

    def decodeCodePair(self, sp):
        codePair = self.prevCode + ' ' + self.currCode
        if self.prevSpace > self.currSpace * 1.05 and \
                self.currSpace * 1.05 < sp and \
                codePair in decodeTable[self.codeType] and \
                codePair != '. ...':
            self.decodeChar(self.prevSpace, codePair)
            self.currCode = ''
        else:
            self.decodeChar(self.prevSpace, self.prevCode, self.prevMark)
        self.prevSpace = self.currSpace
        self.prevCode = self.currCode
        self.prevMark = self.currMark
        self.currSpace = sp
        self.currCode = ''
        self.currMark = 0
 
    def decodeChar(self, space, codeString, mark=0):
        if codeString == '':
            return ''
        if codeString == '-' and self.codeType == AMERICAN and \
                mark > 4.5 * self.dotLen:
            codeString = '='
        if codeString in decodeTable[self.codeType]:
            s = decodeTable[self.codeType][codeString]
        else:
            s = '[' + codeString + ']'
        spacing = (float(space) / self.dotLen - 3) / 3
        self.callback(s, spacing)
            
    def flush(self):
        self.tLastDecode = sys.float_info.max
        for i in range(2):
            self.decodeCodePair(MAXINT)

    def autoFlush(self):
        while True:
            with self.decodeLock:
                if time.time() > self.tLastDecode + FLUSH:
                    self.flush()
            time.sleep(0.1)
        
