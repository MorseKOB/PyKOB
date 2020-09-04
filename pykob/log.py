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
log module

logs status, debug and error messages.
"""
import sys
import datetime

def log(type, msg, dt=None):
    dtl = dt if dt else str(datetime.datetime.now())[:19]
    sys.stdout.write('{0} \t{1}: \t{2}\n'.format(dtl, type, msg))
    sys.stdout.flush()

def logErr(msg):
    dt = str(datetime.datetime.now())[:19]
    log('ERROR', msg, dt) # Output to the normap output
    sys.stderr.write('{0} \t{1}: \t{2}\n'.format(dt, type, msg))
    sys.stderr.flush()
    
def debug(msg):
    log('DEBUG', msg)
    sys.stderr.flush()
    
def info(msg):
    log('INFO', msg)
    
def err(msg):
    typ, val, trc = sys.exc_info()
    log('ERROR', '{0}: \t({1})'.format(msg, val))

