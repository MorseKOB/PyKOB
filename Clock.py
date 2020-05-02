#! python

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
Clock.py

Cuckoo clock substitute.

Serial port, code speed, and audio preferences should be specified by running the
"configure.sh" script or executing "python3 Configure.py".
"""

NUMBER = [ "oh", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve"]

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
# Take an starting point and round up to the next interval-multiple:
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
        if hours == 0:
            msg += "midnight"
        elif hours == 12:
            msg += "noon" + 12 * "L "
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
def announce(s, kob, sender):
    print(">", s)
    for c in s:
        code = sender.encode(c)
        kob.sounder(code)

try:
    import argparse
    import sys
    import time
    from pykob import config, kob, morse, log

    log.log("Starting Clock")

    clock_parser = argparse.ArgumentParser(parents=[config.WPM_OVERRIDE])
    clock_parser.add_argument("-b", "--begin", default=900, type=int, help="Beginning of time announcements ", metavar="time", dest="Begin")
    clock_parser.add_argument("-e", "--end", default=2230, type=int, help="End of time announcements ", metavar="time", dest="End")
    clock_parser.add_argument("-i", "--interval", default=60, type=int, help="The time announcement interval in minutes", metavar="minutes", dest="Interval")
    args = clock_parser.parse_args()
    
    PORT = config.Port # serial port for KOB interface
    WPM = args.Speed  # code speed (words per minute)
    SOUND = config.Sound # whether to enable computer sound for sounder
    start_time = hms_to_seconds(int(args.Begin/100), args.Begin % 100, 0)  # start time (sec)
    end_time = hms_to_seconds(int(args.End/100), args.End % 100, 0)  # end time (sec)
    annc_interval = args.Interval * 60      # announcement interval (sec)
    
    myKOB = kob.KOB(port=PORT, audio=SOUND)
    mySender = morse.Sender(WPM)
    
    # Announce the current time right now
    now = time.localtime()
    msg = announcement(now.tm_hour, now.tm_min)
    announce(msg, myKOB, mySender)

    # Loop, making announcements as configured (every hour, on the hour, during the daytime)
    while True:
        t = time.localtime()
        next_time = round_up(hms_to_seconds(t.tm_hour, t.tm_min, t.tm_sec), annc_interval)  # next announcement (sec)
        if next_time < start_time:
            next_time = start_time
        # print("Next time announcement at {0}:{1:02d}".format(clock_hour(next_time), clock_minutes(next_time)))
        now = hms_to_seconds(t.tm_hour, t.tm_min, t.tm_sec)  # current time (sec)
        if next_time <= end_time:
            if now < next_time:
                # print("sleeping for {0} seconds until next time announcement...".format(next_time - now))
                time.sleep(next_time - now)
            msg = announcement(clock_hour(next_time), clock_minutes(next_time))
            announce(msg, myKOB, mySender)
        else:
            # print("sleeping for {0} seconds until midnight...")
            time.sleep(24*3600 - now)  # wait until midnight and start over
except KeyboardInterrupt:
    print()
    sys.exit(0)
