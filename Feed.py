#!/usr/bin/env python3

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

"""Feed.py

Waits for a station to connect to a KOB wire and sends text from a RSS-formatted
local file or news feed, or a PyKOB recording json file, in Morse at a given speed.

If the wait parameter is nonzero, then the feed will stop sending if
another station starts sending, and will wait until the wire is idle for the
specified number of seconds before sending again.

Command line parameters (required):
    wire - KOB wire no.
    idText - office call, etc.
    URI - RSS formatted text source (URI) or a PyKOB recording file.
    wpm - overall code speed (WPM).
    
Additional command line parameters (optional):
    cwpm - individual character speed (default: same as overall code speed)
    artPause - delay between articles (default: 2 sec)
    grpPause - delay between article groups (default: 5 sec)
    days - number of days of articles to read before repeating, starting with
            current day (default: all)
    wait - number of seconds to wait for the wire to be idle before sending
            (default: ignore other senders)

Note: artPause and grpPause can be decimal numbers.  wire, wpm, cwpm, and
days must be integers.  idText and URI should be enclosed in quotes.

Examples:
    python Feed.py 105 "Today's News, 20 wpm, AC" "http://rss.cnn.com/rss/cnn_topstories.rss" 20
    python Feed.py 111 "Civil War News, 15 wpm, AC" "file://civilwar.xml" 15 18 5 20 3

Change history:

Feed 1.9  2021-01-04
- support using a PyKOB recording (json) file as a source

Feed 1.8  2021-01-04
- updated to use new PyKOB library

Feed 1.7  2020-05-28
- changed header to `#!/usr/bin/env python3`

Feed 1.6  2020-02-13
- replaced #!/usr/bin/env python header, which fails with Windows 10

Feed 1.5  2018-07-13
- include title (headline) if present (for compatibility with BBC News)

Feed 1.4  2018-07-10
- converted from legacy morsekob module to use pykob module
"""

import os
import sys
import time, datetime
import threading
import pykob
import traceback
from pathlib import Path
from pykob import newsreader, morse, internet, kob, log, recorder

VERSION     = '1.9'
DATEFORMAT  = '%a, %d %b %Y %H:%M:%S'
TIMEOUT     = 30.0  # time to keep sending after last indication of live listener (sec)

log.log('Starting Feed {0}'.format(VERSION))

wire = int(sys.argv[1])
idText = sys.argv[2]
uri = sys.argv[3]
wpm = int(sys.argv[4])
n = len(sys.argv)
cwpm = int(sys.argv[5]) if n > 5 else 0
artPause = float(sys.argv[6]) if n > 6 else 2.0
grpPause = max(float(sys.argv[7]) if n > 7 else 5.0, artPause)
days = int(sys.argv[8]) if n > 8 else 0
wait = int(sys.argv[9]) if n > 9 else 0

playback_finished = threading.Event()
playback_last_sender = None

mySender = morse.Sender(wpm, cwpm)
myInternet = internet.Internet(idText)
myKOB = kob.KOB(port=None, audio=False)

myInternet.connect(wire)

# create thread to listen for activity on the wire
tLastSender = time.time()  # time of last activity
def checkForActivity():
    global tLastSender
    while True:
        myInternet.read()
        tLastSender = time.time()
listenerThread = threading.Thread(target=checkForActivity)
listenerThread.daemon = True
listenerThread.start()

def activeListener():
    return time.time() < myInternet.tLastListener + TIMEOUT

def activeSender():
    return time.time() < tLastSender + wait

def send(code):
    myInternet.write(code)
    myKOB.sounder(code, code_source=kob.CodeSource.player)  # to pace the code sent to the wire

def sendParagraph():
    paragraphMark = (-211, 162, -54, 162, -54, 162, -54, 162)
    myInternet.write(paragraphMark)
    myKOB.sounder(paragraphMark, code_source=kob.CodeSource.player) # to pace the code sent to the wire

def callbackPlay(code):
    """
    Called by the Recorder to play each code block.
    """
    global myKOB, playback_finished
    try:
        send(tuple(code)) # Playback calls with a list, internet.write needs a tuple.
    except BaseException as e:
        print(e)
        traceback.print_exc()
        playback_finished.set()

def callbackPlayFinished():
    """
    Called by the Recorder when the playback is finished.
    """
    global playback_finished
    playback_finished.set()

def callbackSenderId(sender_id):
    """
    Called by the Recorder with the sender ID in a recording.

    If the sender changes we send a paragraph to make the change easier to notice.
    """
    global playback_last_sender
    if not playback_last_sender:
        playback_last_sender = sender_id
    elif playback_last_sender != sender_id:
        playback_last_sender = sender_id
        sendParagraph()

def processRecording():
    """
    Process a PyKOB recording file.
    """
    global uri, grpPause, idText

    playback_finished.clear()
    while True:
        myRecorder = recorder.Recorder(None, uri, station_id=idText, 
          play_code_callback=callbackPlay, 
          play_finished_callback=callbackPlayFinished, 
          play_sender_id_callback = callbackSenderId)
        # Wait until there is an active listener on the wire and there isn't an active sender
        while activeSender() or not activeListener():
            time.sleep(1)
        send((-0x7fff, +2, -1000, +2))  # open circuit and wait 1 sec
        myRecorder.playback_start(max_silence=artPause)
        # Wait until playback is finished
        while not playback_finished.is_set():
            if activeSender():
                # If someone is sending pause the playback
                myRecorder.playback_pause()
                time.sleep(0.5)
                send((-500, +1))  # close circuit after 1/2 sec
                while activeSender():
                    time.sleep(0.5) # wait for the sender to stop
                send((-0x7fff, +2, -1000, +2))  # open circuit and wait 1 sec
                myRecorder.playback_resume()
            if not activeListener():
                # Nobody is listening so stop the recording
                myRecorder.playback_stop()
                time.sleep(0.5) # give it some time to stop
                send((-500, +1))  # close circuit after 1/2 sec
                playback_finished.set() # set finished so we will start over
            time.sleep(0.5)
        # Once finished wait a bit and replay it.
        sendParagraph()
        sendParagraph()
        send((-1000, +1))  # close circuit after 1 sec
        time.sleep(grpPause)
        playback_finished.clear()

def processRSS():
    """
    Process an RSS file/feed.
    """
    global uri, days, artPause, grpPause
    while True:
        articles = newsreader.getArticles(uri)
        for (title, description, pubDate) in articles:
            if days and pubDate:
                today = datetime.date.today()
                pd = datetime.datetime.strptime(pubDate[:-6], DATEFORMAT).date()
                if pd > today or today - pd >= datetime.timedelta(days):
                    continue
            text = ''
            if title:
                text += title + '. '
            text += description
            if pubDate:  # treat as an article, not freeform text
                text += '  ='
            while activeSender() or not activeListener():
                time.sleep(1)
            send((-0x7fff, +2, -1000, +2))  # open circuit and wait 1 sec
            for char in text:
                if activeSender() or not activeListener():
                    break
                code = mySender.encode(char)
                if code:
                    send(code)
            send((-1000, +1))  # close circuit after 1 sec
            time.sleep(artPause)
        time.sleep(grpPause - artPause)

try:
    # See if the URI is a PyKOB recorder file or a RSS file/feed
    isRecording = False
    # See if the URI is a recording file
    #  There are more effecient ways to do this with Mac/Linux, 
    #  but this seems to be needed with Windows.
    #
    # `Path` has problems handling paths that aren't local/absolute. The recorder class 
    # only handles a local file path. If the URI isn't a local file path assume it is 
    # a URL to a RSS feed.
    #
    fileExists = os.path.isfile(uri)
    if fileExists:
        # Deal with it as a local file
        filepath = Path(uri)
        isJson = filepath.suffix == ".json"
        if fileExists and isJson:
            # URI is a file that has a '.json' extention
            # this isn't a foolproof test, but is what we will use  
            # for now to see if this is a PyKOB recording file.
            isRecording = True
    if isRecording:
        processRecording()
    else:
        processRSS()
except KeyboardInterrupt:
    print()
    sys.exit(0)     # Since normal operation is an infinite loop, ^C is actually a normal exit.
