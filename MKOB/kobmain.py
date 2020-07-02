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

sender_ID = ""

def from_KOB(code):
    global kob_latched, keyboard_latched, internet_latched
    if keyboard_latched and internet_latched:
        kob_latched = False
        myReader.decode(code)
        myInternet.write(code)
    if len(code) > 0 and code[len(code)-1] == +1:
        kob_latched = True
        myReader.flush()

def from_keyboard(code):
    global kob_latched, keyboard_latched, internet_latched
    if kob_latched and internet_latched:
        keyboard_latched = False
        myKOB.sounder(code)
        myReader.decode(code)
        myInternet.write(code)
    if len(code) > 0 and code[len(code)-1] == +1:
        keyboard_latched = True
        myReader.flush()

def from_internet(code):
    global kob_latched, keyboard_latched, internet_latched
    if not connected:
        return
    if kob_latched and keyboard_latched:
        internet_latched = False
        myKOB.sounder(code)
        myReader.decode(code)
    if len(code) > 0 and code[len(code)-1] == +1:
        internet_latched = True
        myReader.flush()

# callback functions

def readerCallback(char, spacing):
    if spacing > 0.5:
        ka.kw.txtReader.insert('end', " ")
    ka.kw.txtReader.insert('end', char)
    ka.kw.txtReader.yview_moveto(1)

# initialization

myKOB = kob.KOB(port=kc.config.serial_port, audio=kc.config.sound,
        callback=from_KOB)
myInternet = internet.Internet(kc.config.station, callback=from_internet)
kobstationlist.init()
kobkeyboard.init()
