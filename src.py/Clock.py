#!/usr/bin/env python3

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

"""Clock.py

Cuckoo clock substitute.

Serial port, use GPIO, text speed, and audio preferences should be specified by running the
"configure.sh" script or executing "python3 Configure.py".
"""
import argparse
import sys
import time
from pykob import config, kob, morse, log, recorder
from pykob.util import strtobool

#
# For numeric-to-text translation.  Note that "0" is only referneced for midnight, and then it's
# referred to more commonly as "twelve": "a quarter past 12" instead of "a quarter past midnight"
# Hence the "twelve" in the slot for '0'.
NUMBER = [ "twelve", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve"]

#
# Convert hours/minutes/seconds since midnight to seconds since midnight:
#
def hms_to_seconds(hours, minutes, seconds):
    return hours * 3600 + minutes * 60 + seconds

#
# Convert from numeric representation to text ("9" to "nine")
#
def number_to_text(n):
    if (n < 0) or ( n > 12):
        return ""
    return NUMBER[n]
#
# Convert 0-24 hours to 0-12 hours by subtracting 12 if needed:
#
def truncate_hours(h):
    if h <= 12:
        return h        # 0-12 is returned as-is
    else:
        return h % 12   # 13-on is truncated to 1-on

#
# Convert seconds since midnight to corresponding clock hour
#
def clock_hour(t):
    return int(t / 3600)

#
# Convert seconds since midnight to the corresponding clock minute
#
def clock_minutes(t):
    return int(int(t % 3600) / 60)

#
# Take a starting point and round up to the next interval-multiple:
#
def round_up(start, interval):
    return start - (start % interval) + interval # Round up to next interval (sec)

#
# Generate a proper time announcement:
#
#   "midnight"
#   "Nine o"clock"
#   "A quarter past nine"
#   "9:20"
#   "Half past nine"
#   "A quarter to ten"
#   "noon"
#
def announcement(hours, minutes):
    msg = "The time is "
    if minutes == 0:
        if truncate_hours(hours) == 0:
            msg += "midnight"
        elif hours == 12:
            msg += "noon     " + 12 * "L "
        else:
            msg += number_to_text(truncate_hours(hours)) + " o'clock     " + truncate_hours(hours) * "L "
    elif minutes == 15:
        msg += "a quarter past " + number_to_text(truncate_hours(hours))
    elif minutes == 30:
        msg += "half past " + number_to_text(truncate_hours(hours))
    elif minutes == 45:
        msg += "a quarter to " + number_to_text(truncate_hours(hours + 1))
    else:
        # Last resort: just generate the time in hh:mm format
        msg += "{hour}:{minute:02d}".format(hour=hours, minute=minutes)
    return msg

#
# Send a message as morse on the sounder:
#
def announce(s, kob, sender, recorder, source=kob.CodeSource.local):
    global local_text
    if local_text: print('> ', end='', flush=True)
    for c in s:
        code = sender.encode(c)
        kob.soundCode(code)
        if local_text: print(c, end='', flush=True)
        if recorder:
            recorder.record(code, source)
    if local_text: print('')

try:
    #log.log("Starting Clock")

    arg_parser = argparse.ArgumentParser(description="Morse Cuckoo Clock", parents=\
     [\
        config.use_serial_override, \
        config.serial_port_override, \
        config.use_gpio_override, \
        config.code_type_override, \
        config.sound_override, \
        config.sounder_override, \
        config.spacing_override, \
        config.min_char_speed_override, \
        config.text_speed_override])
    arg_parser.add_argument("-b", "--begin", default=900, type=int, help="Beginning of time announcements (24-hour value 0-2400)", metavar="time", dest="Begin")
    arg_parser.add_argument("-e", "--end", default=2200, type=int, help="End of time announcements  (24-hour value 0-2400)", metavar="time", dest="End")
    arg_parser.add_argument("-i", "--interval", default=60, type=int, help="The time announcement interval in minutes", metavar="minutes", dest="Interval")
    arg_parser.add_argument("-P", "--print", action='store_true', default=False, help="Print the text sent as code to the sounder", dest="Text")
    arg_parser.add_argument("--record", action='store_true', default=False, help="Record the code to the `Clock.'ts'.json` file", dest="Record")
    args = arg_parser.parse_args()
    
    useSerial = strtobool(args.use_serial)
    port = args.serial_port # serial port for KOB interface
    useGpio = strtobool(args.use_gpio) # True to use GPIO interface
    if (args.text_speed < 1) or (args.text_speed > 50):
        print("text_speed specified must be between 1 and 50")
        sys.exit(1)
    text_speed = args.text_speed  # text speed (words per minute)
    sound = strtobool(args.sound)
    #
    # start_time argument is limited to 0..2400:
    #
    if (args.Begin < 0) or (args.Begin > 2400):
        print("Start time must be betwen 0 and 2400.")
        sys.exit(1)
    start_time = hms_to_seconds(int(args.Begin/100), args.Begin % 100, 0)  # start time (sec)
    print("args.Begin = {0}; start_time = {1}".format(args.Begin, start_time))
    #
    # end_time argument is limited to 0..2400; end_time in seconds can therefore be 0..144000:
    #
    if (args.End < 0) or (args.End > 2400):
        print("End time must be betwen 0 and 2400.")
        sys.exit(1)
    end_time = hms_to_seconds(int(args.End/100), args.End % 100, 0)  # end time (sec)
    #
    # Limit for announcement interval is 1440 minutes (24 hours):
    #
    if (args.Interval < 1) or (args.Interval > 1440):
        print("Time announcement interval must be betwen 1 and 1440.")
        sys.exit(1)
    annc_interval = args.Interval * 60      # announcement interval (sec)
    local_text = args.Text

    myRecorder = None
    if (args.Record):
        ts = recorder.get_timestamp()
        targetFileName = "Clock." + str(ts) + ".json"
        myRecorder = recorder.Recorder(targetFileName, None, station_id="Clock")
    
    myKOB = kob.KOB(portToUse=port, useGpio=useGpio, useAudio=sound)
    mySender = morse.Sender(text_speed)
    
    # Announce the current time right now
    now = time.localtime()
    msg = announcement(now.tm_hour, now.tm_min)
    announce(msg, myKOB, mySender, myRecorder)

    # Loop, making announcements as configured (every hour, on the hour, during the daytime)
    while True:
        t = time.localtime()
        next_time = round_up(hms_to_seconds(t.tm_hour, t.tm_min, t.tm_sec), annc_interval)  # next announcement (sec)
        if next_time < start_time:
            next_time = start_time
        now = hms_to_seconds(t.tm_hour, t.tm_min, t.tm_sec)  # current time (sec)
        if next_time <= end_time:
            if now < next_time:
                time.sleep(next_time - now)
            msg = announcement(clock_hour(next_time), clock_minutes(next_time))
            announce(msg, myKOB, mySender, myRecorder, kob.CodeSource.local)
        else:
            # print("sleeping for {0} seconds until midnight...")
            time.sleep(24*3600 - now)  # wait until midnight and start over
except KeyboardInterrupt:
    print()
    sys.exit(0)     # Since normal operation is an infinite loop, ^C is actually a normal exit.
