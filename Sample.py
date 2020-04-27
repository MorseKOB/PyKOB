#! python
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
Sample.py

Sends Morse code to a serial port and/or the speakers.

Serial port, code speed, and audio preferences should be specified by running the
'configure.sh' script or executing 'python3 Configure.py'.
"""

from pykob import config, kob, morse
import time

PORT = config.Port # serial port for KOB interface
WPM = config.Speed  # code speed (words per minute)
SOUND = config.Sound # whether to enable computer sound for sounder
TEXT = '~ The quick brown fox +'  # ~ opens the circuit, + closes it

myKOB = kob.KOB(PORT, audio=SOUND)
mySender = morse.Sender(WPM)

# send HI at 20 wpm as an example
print("HI");
code = (-1000, +2, -1000, +60, -60, +60, -60, +60, -60, +60,
        -180, +60, -60, +60, -1000, +1)
myKOB.sounder(code)
time.sleep(2)

# then send the text
print(TEXT);
for c in TEXT:
    code = mySender.encode(c)
    myKOB.sounder(code)

time.sleep(1)
