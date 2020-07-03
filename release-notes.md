# Release notes

This is a provisional file where I can record changes I've made to the MKOB GUI app and the PyKOB library package. The format of this file is very much subject to change. It may even be split into separate files if MKOB and PyKOB end up having their own repositories. @leskerr

## MKOB change history:

4.0.7  2020-07-03
- fix VERSION

4.0.6  2020-06-29
- restructure modules; add kobmain
- enable external key

4.0.5  2020-06-26
- tweak reader window line spacing
- move revision history to release-notes file
- change code sender label from 'Loop' to 'Repeat'

4.0.4  2020-06-25
- implement station list

4.0.3  2020-06-16
- use Internet.set_officeID to change user's ID

4.0.2  2020-06-14
- fetch and save config settings

4.0.1  2020-06-10
- fix jitter in code reader window
- tweak widget attributes

## PyKOB change history:

1.2.4  2020-06-23
- add capability to monitor office IDs and current sender

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
    tapped dots and dashes

1.0.0  2014-11-11
- changed package name from morsekob to PyKOB
- kob: switched from pygame to PyAudio
- kob: added callback function for key input
- kob: changed default echo to False
- kob: set clock resolution to 1ms (Windows only)
- internet: added callback function for incoming code packets
- morse: autopurge to decode final character upon pause in sending
- dropped display module from package
