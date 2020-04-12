#!/usr/bin/env python

"""

Weather.py

Waits for a station to send a message ending in WX XXXX, where XXXX is the
4- or 5-character code for a U.S. weather reporting station, and replies
with the current weather conditions and short term forecast for that area.

Change history:

1.0.5  2018-05-28
- changed NOAA API format from JSON-LD to GeoJSON

1.0.4  2018-02-27
- changed some error messages to make them clearer

1.0.3  2018-02-03
- removed redundant slash from URL

1.0.2  2018-01-15
- fixed problem converting % to PC

1.0.1  2018-01-12
- convert hyphen in weather report to MINUS

1.0.0  2018-01-09
- initial release

"""

try:
    from urllib.request import Request, urlopen  # Python 3
except:
    from urllib2 import Request, urlopen  # Python 2
import re
import time
from pykob import internet, morse, kob, log
import pykob  # to access PyKOB version number

VERSION = '1.0.5'
WIRE    = 106
IDTEXT  = 'KOB Weather Service, AC'
WPM     = 20  # initial guess at received Morse speed

log.log('Starting Weather ' + VERSION)
log.log('PyKOB version ' + pykob.VERSION)

def readerCallback(char, spacing):
    global msg, bracket
    if spacing * 3 * myReader.dotLen > 20000 and char != '~':  # dropped packet
        msg += ' QN ? QJ '
    for i in range(0, len(char)):
        if char[i] == '[':
            msg += ' QN '
            bracket = True
        elif char[i] == ']':
            msg += ' QJ '
            bracket = False
        elif bracket:
            if char[i] == '.':
                msg += 'E'
            elif char[i] == '-':
                msg += 'T'
            else:
                msg += '?'
        else:
            msg += char
    if msg[-1] == '+':
        log.log('Weather.py: {} @ {:.1f} wpm ({} ms)'.format(msg,
                1200. / myReader.dotLen, myReader.truDot))
        mySender.__init__(myReader.wpm)  # send at same speed as received
        sendForecast(msg)
        myReader.setWPM(WPM)
        msg = ''
    
FLAGS = re.IGNORECASE + re.DOTALL

def sendForecast(msg):
    m = re.search(r'WX(.{4,5})\+', msg)
    if not m:
        send('~ ? ' + msg[1:-1] + ' ?  +')
        log.log('Weather.py: Invalid request')
        return
    station = m.group(1)

    # Station data
    url = 'https://api.weather.gov/stations/' + station
    req = Request(url)
    req.add_header('User-Agent', 'MorseKOB/les@morsekob.org')
    req.add_header('Accept', 'application/geo+json')
    try:
        s = urlopen(req).read().decode('utf-8')
    except:
        send('~ WX ' + station + ' UNKNOWN +')
        log.err('Weather.py: Can\'t open ' + url)
        return
    m = re.search(r'"coordinates":\s*\[\s*(.+?),\s+(.+?)\s*\].*?"name":\s*"(.*?)[,"]', s, FLAGS)
    if not m:
        send('~ WX ' + station + ' UNAVAILABLE +')
        log.log('Weather.py: Can\'t find forecast for ' + station)
        return
    lon = m.group(1)
    lat = m.group(2)
    name = m.group(3)
    send('~ WX FOR ' + name + ' = ')

    # Current conditions
    url = 'https://api.weather.gov/stations/' + station + '/observations/current'
    req = Request(url)
    req.add_header('User-Agent', 'MorseKOB/les@morsekob.org')
    req.add_header('Accept', 'application/geo+json')
    try:
        s = urlopen(req).read().decode('utf-8')
    except:
        send('CURRENT WX UNAVAILABLE +')
        log.err('Weather.py: Can\'t open ' + url)
        return
    m = re.search(r'"textDescription":\s*"(.*?)".*?"temperature":.*?"value":\s*(.*?),', s, FLAGS)
    if not m:
        send('CURRENT WX MISSING +')
        log.log('Weather.py: Can\'t parse forecast ' + station)
        return
    cdx = m.group(1)
    temp = m.group(2)
    try:
        t = int(float(m.group(2))*1.8 + 32.5)
        send('NOW {} AND {} DEG = '.format(cdx, t))
    except:
        send('NOW {} = '.format(cdx))
        log.log('Weather.py: Current temp error: ' + temp)

    # Forecast
    url = 'https://api.weather.gov/points/{},{}/forecast'.format(lat, lon)
    req = Request(url)
    req.add_header('User-Agent', 'MorseKOB/les@morsekob.org')
    req.add_header('Accept', 'application/geo+json')
    try:
        s = urlopen(req).read().decode('utf-8')
    except:
        send('FORECAST UNAVAILABLE +')
        log.err('Weather.py: Can\'t open ' + url)
        return
    m = re.search(r'"name":\s*"(.*?)".*?"detailedForecast":\s*"(.*?)".*?"name":\s*"(.*?)".*?"detailedForecast":\s*"(.*?)"', s, FLAGS)
    if not m:
        send('FORECAST MISSING +')
        log.log('Weather.py: Can\'t parse forecast ' + station)
        return
    time1 = m.group(1)
    forecast1 = m.group(2)
    time2 = m.group(3)
    forecast2 = m.group(4)
    send(' {}. {} = {}. {} = 30 +'.format(time1, forecast1,
            time2, forecast2))

def send(text):
    s = text.replace('%', ' PC ')
    s = s.replace('-', ' MINUS ')
    for char in s:
        code = mySender.encode(char)
        myKOB.sounder(code)  # to pace the code sent to the wire
        myInternet.write(code)

myInternet = internet.Internet(IDTEXT)
myInternet.connect(WIRE)
myReader = morse.Reader(callback=readerCallback)
mySender = morse.Sender(WPM)
myKOB = kob.KOB(port=None, audio=False)
myReader.setWPM(WPM)
code = []
bracket = False
msg = ''
while True:
    try:
        code += myInternet.read()
        if code[-1] == 1:
            log.log('Weather.py: {}'.format(code))
            myReader.decode(code)
            myReader.flush()
            code = []
            bracket = False
            msg = ''
    except:
        log.err('Weather.py: Recovering from fatal error.')
        time.sleep(30)
        code = []
        bracket = False
        msg = ''
