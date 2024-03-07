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

global __debug_level
__debug_level = 0

def get_debug_level():
    global __debug_level
    return __debug_level

def set_debug_level(level):
    global __debug_level
    __debug_level = level if level >= 0 else 0

def log(msg, type="", dt=None):
    dtl = dt if dt else str(datetime.datetime.now())[:19]
    typestr = " {0}".format(type) if type else ""
    sys.stdout.write('{0}{1}: \t{2}\n'.format(dtl, typestr, msg))
    sys.stdout.flush()

def logErr(msg):
    dtstr = str(datetime.datetime.now())[:19]
    typestr = "ERROR"
    log(msg, type=typestr, dt=dtstr) # Output to the normal output
    sys.stderr.write('{0} {1}:\t{2}\n'.format(dtstr, typestr, msg))
    sys.stderr.flush()

def debug(msg, level=1):
    global __debug_level
    if level > 0 and __debug_level >= level:
        log(msg, type="DEBUG")

def err(msg):
    typ, val, trc = sys.exc_info()
    logErr("{0}\n{1}".format(msg, val))

def error(msg):
    typ, val, trc = sys.exc_info()
    logErr("{0}\n{1}".format(msg, val))

def info(msg):
    log(msg, type="INFO")

def warn(msg):
    log(msg, type="WARN")
