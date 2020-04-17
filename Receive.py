"""

Receive.py

Monitors a KOB wire, and displays decoded text on the system console.

Command line parameters:
    KOB wire no. (defaults to 101)
    approximate code speed of incoming Morse (defaults to 20)

Example:
    python Receive.py 110
    
"""

from __future__ import print_function  ###
import sys
from time import sleep
from pykob import VERSION, internet, morse
import codecs

WIRE     = 109  # default KOB wire to connect to
WPM      = 20  # approximate speed of incoming Morse (for decoder)
OFFICEID = 'MorseKOB 4.0 test, AC (listening)'
THINSPACE = '\u202F'  # narrow (half width) non-breaking space

print('Python ' + sys.version + ' on ' + sys.platform)
print('MorseKOB ' + VERSION)

# get command line parameters, if any
if len(sys.argv) > 1:
    WIRE = int(sys.argv[1])
if len(sys.argv) > 2:
    WPM = int(sys.argv[2])

def readerCallback(char, spacing):
##    outFile.write('{} {}\n'.format(spacing, char))
##    return
    halfSpaces = min(max(int(2 * spacing + 0.5), 0), 10)
    fullSpace = False
    if halfSpaces >= 2:
        fullSpace = True
        halfSpaces -= 2
    for i in range(halfSpaces):
        outFile.write(THINSPACE)
    if fullSpace:
        outFile.write(' ')
    outFile.write(char)

myInternet = internet.Internet(OFFICEID)
myReader = morse.Reader(callback=readerCallback)
myInternet.connect(WIRE)
outFile = codecs.open( "log.txt", "w", "utf-8" )
sleep(0.5)
while True:
    code = myInternet.read()
    myReader.decode(code)
