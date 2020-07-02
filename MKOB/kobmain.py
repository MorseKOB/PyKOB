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
kobmain.py

Handle the flow of Morse code throughout the program.
"""

import time
from pykob import kob, morse, internet
import kobconfig as kc
import kobactions as ka
import kobstationlist
import kobkeyboard

mySender = None
myReader = None
myInternet = None
connected = False

kob_latched = True
keyboard_latched = True
internet_latched = True
latch_code = (-1000, +1)  # code sequence to force latching

sender_ID = ""

def from_KOB(code):
    """handle inputs received from the external key"""
    global kob_latched, keyboard_latched, internet_latched
    kob_latched = False
    if keyboard_latched:
        if connected:
            myInternet.write(code)
        if internet_latched:
            update_sender(kc.config.station)
            myReader.decode(code)
    if len(code) > 0 and code[len(code)-1] == +1:
        kob_latched = True
        myReader.flush()

def from_keyboard(code):
    """handle inputs received from the keyboard sender"""
    global kob_latched, keyboard_latched, internet_latched
    keyboard_latched = False
    if kob_latched:
        if connected:
            myInternet.write(code)
        if internet_latched:
            myKOB.sounder(code)
            update_sender(kc.config.station)
            myReader.decode(code)
    if len(code) > 0 and code[len(code)-1] == +1:
        keyboard_latched = True
        myReader.flush()

def from_internet(code):
    """handle inputs received from the internet"""
    global kob_latched, keyboard_latched, internet_latched
    internet_latched = False
    if connected and kob_latched and keyboard_latched:
        myKOB.sounder(code)
        myReader.decode(code)
    if len(code) > 0 and code[len(code)-1] == +1:
        internet_latched = True
        myReader.flush()
        
def toggle_connect():
    """connect or disconnect when user clicks on the Connect button"""
    global kob_latched, keyboard_latched, internet_latched
    global connected
    connected = not connected
    if connected:
        kobstationlist.clear_station_list()
        myInternet.connect(kc.WireNo)
    else:
        myInternet.disconnect()
        myReader.flush()
        time.sleep(0.5)  # wait for any buffered code to complete
        connected = False  # just to make sure
        if not internet_latched:
            internet_latched = True
            if kob_latched and keyboard_latched:
                myKOB.sounder(latch_code)
                myReader.decode(latch_code)
                myReader.flush()
        kobstationlist.clear_station_list()

def change_wire():
    global kob_latched, keyboard_latched, internet_latched
    global connected
    connected = False
    myReader.flush()
    time.sleep(0.5)  # wait for any buffered code to complete
    if not internet_latched:
        internet_latched = True
        if kob_latched and keyboard_latched:
            myKOB.sounder(latch_code)
            myReader.decode(latch_code)
            myReader.flush()
    myInternet.connect(kc.WireNo)
    connected = True
    
# callback functions

def update_sender(id):
    """display station ID in reader window when there's a new sender"""
    global sender_ID
    if id != sender_ID:
        sender_ID = id
        myReader.flush()
        ka.codereader_append("\n<{}>".format(sender_ID))
        kobstationlist.new_sender(sender_ID)

def readerCallback(char, spacing):
    """display characters returned from the decoder"""
    s = char
    if spacing > 0.5:
        s = " " + s
    ka.codereader_append(s)

# initialization

myKOB = kob.KOB(port=kc.config.serial_port, audio=kc.config.sound,
        callback=from_KOB if kc.config.serial_port else None)
                # workaround for callback until issue #87 is fixed
myInternet = internet.Internet(kc.config.station, callback=from_internet)
myInternet.monitor_IDs(kobstationlist.refresh_stations)
myInternet.monitor_sender(update_sender)
kobkeyboard.init()
