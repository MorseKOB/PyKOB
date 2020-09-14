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
Recorder class

Records wire and local station information for analysis and playback.
Plays back recorded information.

The information is recorded in packets in a JSON structure that includes:
1. Timestamp
2. Source (`local`/`wire`)
3. Station ID
4. Wire Number
5. Code type
6. Code Sequence (key timing information)

Though the name of the class is `recorder` it is typical that a 'recorder' can also 
play back. For example, a 'tape recorder', a 'video casset recorder (VCR)', 
a 'digital video recorder' (DVR), etc. can all play back what they (and compatible 
devices) have recorded. This class is no exception. It provides methods to play back 
recordings in addition to making recordings.

"""

import json
import time
from datetime import datetime
from pykob import config, kob

def getTimestamp():
    """
    Return the current  millisecond timestamp.

    Return
    ------
    ts : number
        milliseconds since the epoc
    """
    ts = int(time.time() * 1000)
    return ts
    
class Recorder:
    def __init__(self, target_file_path, source_file_path, station_id="", wire=-1):
        self.__target_file_path = target_file_path
        self.__source_file_path = source_file_path
        self.__station_id = station_id
        self.__wire = wire

        # Test that we can access the files with appropriate access
        if (self.__source_file_path == None and self.__target_file_path == None):
            raise ValueError("Source File Path and Target File Path are both 'None'. At least one must be specified.")
        if self.__source_file_path:
            # Open to read
            self.__source_file = None # ZZZ open for reading or throw an error

    @property
    def source_file_path(self):
        return self.__source_file_path

    @property
    def target_file_path(self):
        return self.__target_file_path

    @property
    def station_id(self):
        return self.__station_id

    @station_id.setter
    def station_id(self, station_id):
        self.__station_id = station_id

    @property
    def wire(self):
        return self.__wire

    @wire.setter
    def wire(self, wire):
        self.__wire = wire

    def record(self, code, source):
        """
        Record a code sequence in JSON format with additional context information.
        """
        timestamp = getTimestamp()
        data = {
            "ts":timestamp,
            "w":self.__wire,
            "s":self.__station_id,
            "o":source,
            "c":code
        }
        with open(self.__target_file_path, "a+") as fp:
            json.dump(data, fp)
            fp.write('\n')

    def playback(self, kob, showDateTime=False):
        """
        Play a recording to the configured sounder.
        """
        with open(self.__source_file_path, "r") as fp:
            startTime = time.time()  # Get the current time when this playback starts
            firstTS = -1  # Save the first timestamp in the playback
##            lastCode = []
            for line in fp:
                dateTimeStr = ""
                if showDateTime:
                    dateTime = datetime.fromtimestamp(ts / 1000.0)
                    dateTimeStr = str(dateTime.ctime()) + ": "
##                print(dateTimeStr, line, end='')
                data = json.loads(line)
                ts = data['ts'] # Get the timestamp to know when to play
                if firstTS < 0:
                   firstTS = ts
                timediff = startTime + (ts - firstTS) / 1000.0 - time.time()  # Time difference in seconds
                if timediff > 0:
                    # For very long delays, sleep a maximum of 5 seconds
                    # ZZZ - 5 second msx will be configurable
                    if timediff > 5.0:
                        print("Realtime pause of {} seconds being reduced to 5 seconds".format(round(timediff, 3)))
                        firstTS += timediff - 5.0  # Adjust start time to account for shortened pause
                        timediff = 5.0
                    timediff = round(timediff, 4)
##                    print("Sleep: ", timediff)
                    time.sleep(timediff)
                code = data['c']
##                # Keep track of how long it takes to sound the code
##                codePlayStart = getTimestamp()
                kob.sounder(code)
##                codePlayDuration = getTimestamp() - codePlayStart
##                print("tsd: {} codePlayDuration: {}".format(round((ts - self.__lastTS) / 1000.0, 6), round(codePlayDuration, 6)))
##                self.__lastTS = ts
##                lastCode = code


"""
Test code
"""
if __name__ == "__main__":
    # Self-test
    from pykob import morse

    test_target_filename = "test." + str(getTimestamp()) + ".json"
    myRecorder = Recorder(test_target_filename, test_target_filename, station_id="Test Recorder", wire=-1)
    mySender = morse.Sender(20)

    # 'HI' at 20 wpm as a test
    print("HI")
    code = (-1000, +2, -1000, +60, -60, +60, -60, +60, -60, +60,
            -180, +60, -60, +60, -1000, +1)
    myRecorder.record(code, kob.CodeSource.local)
    # Append more text to the same file
    for c in "This is a test":
        code = mySender.encode(c, True)
        myRecorder.record(code, kob.CodeSource.local)
    print()
    # Play the file
    myKOB = kob.KOB(port=None, audio=True)
    myRecorder.playback(myKOB)

