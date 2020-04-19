#! python

"""

News

Fetches articles from an RSS news feed and sends them in American Morse
to a sounder.

"""

import sys
import time
import pykob
from pykob import newsreader, morse, kob

SOURCE   = 'https://www.ansa.it/sito/ansait_rss.xml'  # news feed
PORT = None
#PORT = 'COM3'  # typical for Windows
#PORT = '/dev/ttyUSB0'  # typical for Linux
WPM      = 20  # default code speed
CWPM     = 18  # minimum character speed
PAUSE    = 5  # gap to leave between articles (seconds)
AUDIO = True  # enable simulated sounder

mySender = morse.Sender(WPM, CWPM, morse.INTERNATIONAL, morse.CHARSPACING)
myKOB = kob.KOB(PORT, AUDIO)

while True:
    print('')
    articles = newsreader.getArticles(SOURCE)
    for (title, description, pubDate) in articles:
        text = title + ' = ' + description + ' ='
        for char in text:
            code = mySender.encode(char)
            myKOB.sounder(code)
            if code:
                sys.stdout.write(char)
            else:
                sys.stdout.write(' ')
            sys.stdout.flush()
            if char == '=':
                print('')
        print('')
        time.sleep(PAUSE)
