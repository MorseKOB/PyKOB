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
log module

logs status, debug and error messages.
"""
import sys
import datetime

global __logging_level
__logging_level = 0

global DEBUG_MIN_LEVEL
DEBUG_MIN_LEVEL = 1

global INFO_LEVEL
INFO_LEVEL = 0

global WARN_LEVEL
WARN_LEVEL = -1

global ERROR_LEVEL
ERROR_LEVEL = -2

global LOGGING_MIN_LEVEL
""" Minimum logging level. This disables all logging. """
LOGGING_MIN_LEVEL = -3

def log(msg, type="", dt=None, level_threshold=INFO_LEVEL):
    global __logging_level
    if __logging_level >= level_threshold:
        dtl = dt if not dt is None else str(datetime.datetime.now())[:19]
        typestr = " {0}".format(type) if type else ""
        if not typestr and not dtl:
            sys.stdout.write(msg)
        else:
            sys.stdout.write('{0}{1}: \t{2}\n'.format(dtl, typestr, msg))
        sys.stdout.flush()
    return

def logErr(msg, dt=None):
    global __logging_level
    if __logging_level >= ERROR_LEVEL:
        dtstr = (str(datetime.datetime.now())[:19] + " ") if dt is None else ""
        typestr = "ERROR"
        log(msg, type=typestr, dt=dtstr) # Output to the normal output
        sys.stderr.write('{0}{1}:\t{2}\n'.format(dtstr, typestr, msg))
        sys.stderr.flush()
    return

def debug(msg, level=DEBUG_MIN_LEVEL, dt=None):
    global __logging_level
    if __logging_level >= level:
        log(msg, type="DEBUG[{}]".format(level), level_threshold=level, dt=dt)
    return

def err(msg, dt=None):
    typ, val, trc = sys.exc_info()
    logErr("{0}\n{1}".format(msg, val), dt=dt)
    return

def error(msg, dt=None):
    typ, val, trc = sys.exc_info()
    logErr("{0}\n{1}".format(msg, val), dt=dt)
    return

def info(msg, dt=None):
    log(msg, type="INFO", dt=dt, level_threshold=INFO_LEVEL)
    return

def warn(msg, dt=None):
    log(msg, type="WARN", dt=dt, level_threshold=WARN_LEVEL)
    return

def get_logging_level():
    global __logging_level
    return __logging_level

def set_logging_level(level):
    global __logging_level
    __logging_level = level if level >= LOGGING_MIN_LEVEL else INFO_LEVEL
    debug("log.set_logging_level: " + str(__logging_level))
    return
