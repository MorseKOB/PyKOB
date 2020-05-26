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

stationlist.py

Gets the activity page from the KOB server and returns it as a formatted
string.

"""

try:
    from urllib.request import urlopen  # Python 3.3
except ImportError:
    from urllib import urlopen  # Python 2.7
import re

def getStationList():
    s = urlopen('http://mtc-kob.dyndns.org/').read().decode('utf-8')
    s = re.sub('.*?</tr>.*?(<tr>.*</tr>).*', '\\1', s, 1, re.DOTALL)
    s = re.sub('<tr><td>(.*?)</td><td.*?>(.*?)</td></tr>',
            '\\1: \\2', s, 0)
    return s
