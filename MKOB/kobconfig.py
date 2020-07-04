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

from pykob import config

OfficeID       = config.station         # user's ID (e.g., office call, name, location)

Port           = config.serial_port     # e.g., 'COM3', '/dev/ttyUSB0', None
Sounder        = config.sounder         # external sounder on or off
Audio          = config.sound           # simulated sounder on or off

WPM            = config.text_speed      # overall code speed
CWPM           = config.min_char_speed  # minimum character speed (Farnsworth)
Spacing        = 1 if config.spacing == config.Spacing.word else 0
                                        # 0: character, 1: word (Farnsworth spacing)
CodeType       = 1 if config.code_type == config.CodeType.international else 0
                                        # 0: American, 1: International
if not config.wire:
    config.set_wire("101")
    config.save_config()
    
WireNo         = int(config.wire)       # wire number

Local          = config.local           # monitor traffic on local sounder and audio
Remote         = config.remote          # send traffic to internet
##Connect        = False                  # automatically connect on startup

CircuitCloser  = True                   # initial checkbox settings
CodeSenderOn   = True                   #    "
CodeSenderRepeat = False                #    "

WindowSize     = (800, 500)             # size of KOB window (in pixels)
Position       = (-1, -1)               # location of upper left corner of window
