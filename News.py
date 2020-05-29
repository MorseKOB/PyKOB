#!/usr/bin/env python3

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
News

Fetches articles from an RSS news feed and sends them in American Morse
to a sounder.

Serial port, code speed, and audio preferences should be specified by running the
'configure.sh' script or executing 'python3 Configure.py'.
"""

import sys
import time
import pykob
from pykob import config,newsreader, morse, kob

SOURCE   = 'https://www.ansa.it/sito/ansait_rss.xml'  # news feed
PORT = config.serial_port # serial port for KOB interface
WPM = config.words_per_min_speed  # code speed (words per minute)
SOUND = config.sound # whether to enable computer sound for sounder
CWPM     = 18  # minimum character speed
PAUSE    = 5  # gap to leave between articles (seconds)

mySender = morse.Sender(WPM, CWPM, morse.INTERNATIONAL, morse.CHARSPACING)
myKOB = kob.KOB(PORT, SOUND)

try:
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
except KeyboardInterrupt:
    print()
    sys.exit(0)     # Since normal operation is an infinite loop, ^C is actually a normal exit.
