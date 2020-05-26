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

kobconfig.py

Preference settings for MKOB.

"""

OfficeID       = 'AC Les - Seattle, WA'

Port           = None        # e.g., 'COM3', 'COM4', None
Audio          = True        # simulated sounder on or off

WPM            = 30          # overall code speed
CWPM           = 18          # minimum character speed (Farnsworth)
Spacing        = 0           # 0: character, 1: word (Farnsworth spacing)
CodeType       = 0           # 0: American, 1: International

WireNo         = 105         # wire number
Connect        = False       # automatically connect on startup

CircuitCloser  = True        # initial checkbox settings
CodeSenderOn   = True        #    "
CodeSenderLoop = False       #    "

WindowSize     = (800, 500)  # size of KOB window (in pixels)
Position       = (-1, -1)    # location of upper left corner of window
                             #    (-1, -1): center in screen
