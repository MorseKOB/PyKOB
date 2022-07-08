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
import threading
import time
from pykob import config, kob, morse, log, recorder
from distutils.util import strtobool

myKOB = None
playback_finished = threading.Event()

def callbackPlay(code):
    """
    Called by the Recorder to play each code block.
    """
    global myKOB, playback_finished
    try:
        myKOB.soundCode(code, code_source=kob.CodeSource.player)
    except:
        playback_finished.set()

def callbackPlayFinished():
    """
    Called by the Recorder when the playback is finished.
    """
    global playback_finished
    playback_finished.set()
    print("Playback finished.")

try:
    #log.log("Starting Play")

    arg_parser = argparse.ArgumentParser(description="MorseKOB record player", parents=\
     [\
      config.interface_type_override, \
      config.serial_port_override, \
      config.gpio_override, \
      config.sound_override, \
      config.sounder_override])
    arg_parser.add_argument('playback_file', metavar='file',
                    help='file (in MorseKOB recorder format) to be played back.')
    arg_parser.add_argument("--list", action="store_true", default=False, help="Display the recorded data as it is played.", dest="listData")
    arg_parser.add_argument("--speedfactor", type=int, metavar="n", default=100, help="Factor (percentage) to adjust playback speed by (Default 100).", dest="speedFactor")
    arg_parser.add_argument("--maxsilence", type=int, metavar="n", default=5, help="Longest silence duration to play, in seconds. A value of '0' will reproduce all silence as recorded (Defalut 5).", dest="maxSilence")
    args = arg_parser.parse_args()
    
    interface_type = args.interface_type
    port = args.serial_port # serial port for KOB/sounder interface
    useGpio = strtobool(args.gpio) # use GPIO (Raspberry Pi)
    sound = strtobool(args.sound)
    sounder = strtobool(args.sounder)
    playback_file = args.playback_file

    # Validate that the file can be opened
    try:
        fp = open(playback_file, 'r')
        fp.close()
    except FileNotFoundError:
        log.err("Recording file not found: {}".format(playback_file))

    myKOB = kob.KOB(portToUse=port, useGpio=useGpio, useAudio=sound, interfaceType=interface_type)

    myRecorder = recorder.Recorder(None, playback_file, play_code_callback=callbackPlay, play_finished_callback=callbackPlayFinished, station_id="Player")
    myRecorder.playback_start(list_data=args.listData, max_silence=args.maxSilence, speed_factor=args.speedFactor)
    # Wait until playback is finished
    while not playback_finished.is_set():
        time.sleep(0.5)
except KeyboardInterrupt:
    print("\nEarly exit.")
    myRecorder.playback_stop()
    sys.exit(0)     # ^C is considered a normal exit.
