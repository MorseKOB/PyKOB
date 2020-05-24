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
