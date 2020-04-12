# PyKOB package

VERSION = '1.0.1'

"""

Change history:

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
