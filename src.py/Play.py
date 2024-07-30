"""
MIT License

Copyright (c) 2020-24 PyKOB - MorseKOB in Python

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
from pykob import config2, kob, morse, log, recorder
from pykob.config2 import Config
from pykob.util import strtobool

myKOB = None
myRecorder = None
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
    return

def callbackPlayFinished():
    """
    Called by the Recorder when the playback is finished.
    """
    global playback_finished
    playback_finished.set()
    print("Playback finished.")
    return

try:
    arg_parser = argparse.ArgumentParser(description="MorseKOB record player", parents= [
        config2.interface_type_override,
        config2.use_serial_override,
        config2.serial_port_override,
        config2.use_gpio_override,
        config2.sound_override,
        config2.audio_type_override,
        config2.sounder_override,
        config2.logging_level_override,
        config2.config_file_override,
      ])
    arg_parser.add_argument('playback_file', metavar='recording_file',
            help='Recording file (in PyKOB Recorder format) to be played back.')
    arg_parser.add_argument("--list", action="store_true", default=False, 
            help="Display the recorded data as it is played.", dest="list_data")
    arg_parser.add_argument("--speedfactor", type=int, metavar="n", default=100, 
            help="Factor (percentage) to adjust playback speed by (Default 100).", dest="speed_factor")
    arg_parser.add_argument("--maxsilence", type=int, metavar="n", default=5, 
            help="Longest silence duration to play, in seconds. A value of '0' will reproduce all silence as recorded (Defalut 5).", dest="max_silence")
    args = arg_parser.parse_args()
    cfg:Config = config2.process_config_args(args)

    log.set_logging_level(cfg.logging_level)
    log.debug("Starting Play")

    interface_type = cfg.interface_type
    port = cfg.serial_port              # serial port for KOB/sounder interface
    useGpio = cfg.use_gpio                  # use GPIO (Raspberry Pi)
    sound = cfg.sound                   # use audio
    audio_type = cfg.audio_type         # Sounder or Tone
    sounder = cfg.sounder               # use the physical sounder
    playback_file = args.playback_file


    if playback_file:
        playback_file = recorder.add_ext_if_needed(playback_file)

    # Validate that the file can be opened
    try:
        fp = open(playback_file, 'r')
        fp.close()
    except FileNotFoundError:
        log.err("Recording file not found: {}".format(playback_file))
        sys.exit(1)

    myKOB = kob.KOB(portToUse=port, useGpio=useGpio, useAudio=sound, audioType=audio_type, useSounder=sounder, interfaceType=interface_type)

    myRecorder = recorder.Recorder(None, playback_file, play_code_callback=callbackPlay, play_finished_callback=callbackPlayFinished, station_id="PyKOB Player")
    myRecorder.playback_start(list_data=args.list_data, max_silence=args.max_silence, speed_factor=args.speed_factor)
    # Wait until playback is finished
    while not playback_finished.is_set():
        time.sleep(0.5)
    pass
except KeyboardInterrupt:
    print("\nEarly exit.")
    myRecorder.playback_stop()
finally:
    if myRecorder:
        myRecorder.exit()
    if myKOB:
        myKOB.exit()
sys.exit(0)     # ^C is considered a normal exit.
