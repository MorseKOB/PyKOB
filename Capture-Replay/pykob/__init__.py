# PyKOB package

VERSION = '1.1.4'

"""

Change history:

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
