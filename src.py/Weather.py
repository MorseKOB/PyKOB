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

"""Weather.py

Waits for a station to send a message ending in WX XXXX, where XXXX is the
4- or 5-character code for a U.S. weather reporting station, and replies
with the current weather conditions and short term forecast for that area.

Command line parameters (required):
    wire - KOB wire no.
    idText - office call, etc.

Change history:

1.0.8  2024-03-13
- Create Internet instance with all parameters needed to adapt to new config
  usage (modules no longer read directly from config).
  Use (required) command line parameters for the Wire and Office ID.

1.0.7  2020-05-28
- changed header to `#!/usr/bin/env python3`

1.0.6  2020-02-10
- added DEBUG capability
- removed #!/usr/bin/env python header, which fails with Windows 10

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

import argparse
from urllib.request import Request, urlopen
import re
import sys
import time
from pykob import config, internet, morse, kob, log
import pykob  # to access PyKOB version number

VERSION = '1.0.9'
WPM     = 20  # initial guess at received Morse speed
DEBUG   = '~IESWXKSEA+'  # run locally, don't connect to wire
#DEBUG   = ''  # run normally

global app_ver
app_ver = "Weather {}".format(VERSION)

log.log('Starting {}'.format(app_ver))
log.log('PyKOB version ' + pykob.VERSION)

def readerCallback(char, spacing):
    global msg, bracket
    if spacing * 3 * myReader.dot_len > 20000 and char != '~':  # dropped packet
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
        log.debug('Weather.py: {} @ {:.1f} wpm ({} ms) (Reader detected: {}:{}:{})'.format(
            msg, 1200.0 / myReader.dot_len, myReader.dot_tru, myReader.detected_dot_len, myReader.detected_dot_tru, myReader.detected_wpm))
        mySender.setWPM(myReader.detected_wpm)  # send at same speed as received
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
    if DEBUG:
        print('Station data:', s)
    m = re.search(r'"coordinates":\s*\[\s*(.+?),\s+(.+?)\s*\].*?"name":\s*"(.*?)[,"]', s, FLAGS)
    if not m:
        send('~ WX ' + station + ' UNAVAILABLE +')
        log.log('Weather.py: Can\'t find forecast for ' + station)
        return
    lon = m.group(1)
    lat = m.group(2)
    name = m.group(3)
    if DEBUG:
        print('lon, lat, name:', lon, lat, name)
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
    if DEBUG:
        print('Current wx data:', s)
    m = re.search(r'"timestamp":\s*"(.*?)".*?"textDescription":\s*"(.*?)".*?"temperature":.*?"value":\s*(.*?),', s, FLAGS)
    if not m:
        send('CURRENT WX MISSING +')
        log.log('Weather.py: Can\'t parse forecast ' + station)
        return
    timestamp = m.group(1)
    cdx = m.group(2)
    temp = m.group(3)
    if DEBUG:
        print('time, cdx, temp:', timestamp, cdx, temp)
    try:
        t = int(float(temp)*1.8 + 32.5)
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
    if DEBUG:
        print('Forecast data:', s)
    m = re.search(r'"name":\s*"(.*?)".*?"detailedForecast":\s*"(.*?)".*?"name":\s*"(.*?)".*?"detailedForecast":\s*"(.*?)"', s, FLAGS)
    if not m:
        send('FORECAST MISSING +')
        log.log('Weather.py: Can\'t parse forecast ' + station)
        return
    time1 = m.group(1)
    forecast1 = m.group(2)
    time2 = m.group(3)
    forecast2 = m.group(4)
    if DEBUG:
        print('time1, forecast1:', time1, forecast1)
        print('time2, forecast2:', time2, forecast2)
    send(' {}. {} = {}. {} = 30 +'.format(time1, forecast1,
            time2, forecast2))

def send(text):
    s = text.replace('%', ' PC ')
    s = s.replace('-', ' MINUS ')
    if DEBUG:
        print(s)
        return
    for char in s:
        code = mySender.encode(char)
        myKOB.soundCode(code)  # to pace the code sent to the wire
        myInternet.write(code)

exit_status = 1
try:
    arg_parser = argparse.ArgumentParser(description="Morse weather conditions and forcast service.",
        epilog="Waits for a station to send a message ending in WX XXXX, where XXXX is the 4- or 5-character "
         + "code for a U.S. weather reporting station, and replies with the current weather conditions and "
         + "short term forecast for that area.",
        parents= [
            config.code_type_override,
            config.server_url_override,
        ])
    arg_parser.add_argument("wire", type=int, help="The wire no. for the service.")
    arg_parser.add_argument("station", metavar="station-id", type=str,
                            help="The station identifier for the service.")

    args = arg_parser.parse_args()

    # Wire number for service:
    wire = args.wire

    # Station ID for service:
    service_id = args.station

    # Check optional arguments
    server_url = args.server_url
    code_type = args.code_type

    if DEBUG:
        print(DEBUG)
        sendForecast(DEBUG)
        exit()

    myInternet = internet.Internet(service_id, appver=app_ver, server_url=server_url)
    myInternet.connect(wire)
    myReader = morse.Reader(WPM, WPM, codeType=code_type, callback=readerCallback)
    mySender = morse.Sender(WPM, WPM, codeType=code_type)
    myKOB = kob.KOB(portToUse=None, useAudio=False)
    myReader.setWPM(WPM)
    code = []
    bracket = False
    msg = ''
    while True:
#        try:
        c = myInternet.read()
        if c:
            code += c
            if code[-1] == 1:
                log.log('Weather.py: {}'.format(code))
                myReader.decode(code)
                myReader.flush()
                code = []
                bracket = False
                msg = ''
#        except Exception as ex:
#            log.err('Weather.py: Recovering from fatal error: {}.'.format(ex))
#            time.sleep(15)
#            code = []
#            bracket = False
#            msg = ''
except KeyboardInterrupt:
    exit_status = 0  # Ctrl-C is a normal exit
finally:
    if myInternet:
        myInternet.exit()
    if myKOB:
        myKOB.exit()
    if myReader:
        myReader.exit()
    if mySender:
        mySender.exit()
    print()
sys.exit(exit_status)
