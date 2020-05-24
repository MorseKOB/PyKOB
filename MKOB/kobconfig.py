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
