#!/usr/bin/env python

"""
News

Fetches articles from an RSS news feed and sends them in American Morse
to a sounder.
"""

import sys, time
import morsekob
from morsekob import newsreader, morse, sounder

SOURCE   = 'http://news.yahoo.com/rss/'  # news feed
WPM      = 20  # default code speed
CWPM     = 18  # minimum character speed
PAUSE    = 5  # gap to leave between articles (seconds)

SERIALPORT_WINDOWS = 'COM4'  # typical for Windows
#SERIALPORT_WINDOWS = None
SERIALPORT_LINUX = '/dev/ttyUSB0'  # typical for Linux
#SERIALPORT_LINUX = None
AUDIO = True  # enable simulated sounder

print('Python ' + sys.version + ' on ' + sys.platform)
print('MorseKOB ' + morsekob.VERSION)

# get command line parameter, if any
if len(sys.argv) > 1:
    WPM = int(sys.argv[1])

# pick serial port appropriate to particular OS
if sys.platform.startswith('win'):
    serialPort = SERIALPORT_WINDOWS
elif sys.platform.startswith('linux'):
    serialPort = SERIALPORT_LINUX
else:
    print('Platform not recognized. Serial port set to None.')
    serialPort = None

mySender = morse.Sender(WPM, CWPM, morse.AMERICAN, morse.CHARSPACING)
mySounder = morsekob.sounder.Sounder(serialPort, AUDIO)

while True:
    print('')
    articles = newsreader.getArticles(SOURCE)
    for (title, description, pubDate) in articles:
        text = title + ' = ' + description + ' ='
        for char in text:
            code = mySender.encode(char)
            mySounder.sound(code)
            if code:
                sys.stdout.write(char)
            else:
                sys.stdout.write(' ')
            sys.stdout.flush()
            if char == '=':
                print('')
        print('')
        time.sleep(PAUSE)
