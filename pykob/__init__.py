# PyKOB package
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

VERSION = '1.2.3'

"""

Change history:

1.2.3  2020-06-16
- add `Internet.set_officeID` method

1.2.2  2020-06-13
- get 'station' and 'wire' settings correctly from config

1.2.1  2020-04-18
- added config module

1.1.4  2020-03-20
- internet: added option to send text with code for CWCom compatibility

1.1.3  2018-07-13
- newsreader: strip <![CDATA[...]]> tag from title and description

1.1.2  2018-01-16
- morse: fixed bug in updateWPM

1.1.1  2018-01-08
- morse: changed updateWPM function to ignore very short dots

1.1.0  2018-01-07
- morse: redesigned decode section to adapt to incoming Morse speed and handle
    tapped dots and dashes; (temporarily) removed autoflush

1.0.1
- morse: added lock mechanism to prevent autoflush from double-decoding

1.0.0  2014-11-11
- changed package name from morsekob to PyKOB
- kob: switched from pygame to PyAudio
- kob: added callback function for key input
- kob: changed default echo to False
- kob: set clock resolution to 1ms (Windows only)
- internet: added callback function for incoming code packets
- morse: autopurge to decode final character upon pause in sending
- dropped display module from package

"""
