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
Play
======
Play a recorded file from the `Recorder` class.
"""
import argparse
import sys
import time
from pykob import config, kob, morse, log, recorder
from distutils.util import strtobool

try:
    #log.log("Starting Play")

    arg_parser = argparse.ArgumentParser(description="MorseKOB record player", parents=\
     [\
      config.serial_port_override, \
      config.code_type_override, \
      config.sound_override, \
      config.sounder_override])
    arg_parser.add_argument('playbackFile', metavar='file',
                    help='file (in recorder format) to be played back')
    arg_parser.add_argument("--datetime", action='store_true', default=False, help="Display the date and time the data was recorded", dest="showDatetime")
    args = arg_parser.parse_args()
    
    port = args.serial_port # serial port for KOB interface
    sound = strtobool(args.sound)
    playbackFile = args.playbackFile

    # Validate that the file can be opened
    try:
        fp = open(playbackFile, 'r')
        fp.close()
    except FileNotFoundError:
        log.err("File not found: {}".format(playbackFile))

    myKOB = kob.KOB(port=port, audio=sound)
    myRecorder = recorder.Recorder(None, playbackFile, station_id="Player")
    myRecorder.playback(myKOB, showDateTime=args.showDatetime)

except KeyboardInterrupt:
    print()
    sys.exit(0)     # Since normal operation is an infinite loop, ^C is actually a normal exit.

