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
kobactions.py

Defines actions for MKOB
"""

import tkinter.messagebox as mb
from pykob import config, kob, internet, morse
import kobconfig as kc
import stationlist as sl
import time

import pykob  # for version number
print("PyKOB " + pykob.VERSION)

kw = None  # initialized by KOBWindow
mySender = None
myReader = None
myInternet = None
##running = True
connected = False

def internetCallback(code):
    if connected:
        myKOB.sounder(code)
        myReader.decode(code)

def readerCallback(char, spacing):
    if spacing > 0.5:
        kw.txtReader.insert('end', " ")
    kw.txtReader.insert('end', char)
    kw.txtReader.yview_moveto(1)

station_ID_list = []
station_ID_times = []

def ID_monitor_callback(id):
    """update the station list when an ID is sent or received"""
    global station_ID_list, station_ID_times
    global connected
    if not connected:
        return
    i = len(station_ID_list) - 1
    while i >= 0:
        if station_ID_list[i] == id:
            break
        i -= 1
    if i < 0:
        station_ID_list += [id]
        station_ID_times += [0]
        i = len(station_ID_list) - 1
    station_ID_times[i] = time.time()
    display_station_list()

def sender_monitor_callback(id):
    """update the station list when a new sender is detected"""
    print("sender:", id)

def display_station_list():
    """purge inactive stations and display the updated station list"""
    global station_ID_list, station_ID_times
    now = time.time()
    # find and purge inactive stations
    while True:
        i = len(station_ID_list) - 1
        while i >= 0:
            if now > station_ID_times[i] + 60:  # inactive station
                break
            i -= 1
        if i < 0:  # all stations are active
            break
        # purge inactive station
        station_ID_list = station_ID_list[:i] + station_ID_list[i+1:]
        station_ID_list = station_ID_list[:i] + station_ID_list[i+1:]
    # display station list
    kw.txtStnList.delete('1.0', 'end')
    for i in range(len(station_ID_list)):
        kw.txtStnList.insert('end', "{}\n".format(station_ID_list[i]))

myKOB = kob.KOB(port=config.serial_port, audio=config.sound, callback=None)
myInternet = internet.Internet(config.station, callback=internetCallback)
myInternet.monitor_IDs(ID_monitor_callback)
myInternet.monitor_sender(sender_monitor_callback)

# File menu

def doFileNew():
    kw.txtKeyboard.delete('1.0', tk.END)

def doFileOpen():
##    newFile()
    kw.txtKeyboard.insert(tk.END, "~  Now is the time for all good men to come to the aid of their country.  +")
    kw.txtKeyboard.mark_set('mark', '0.0')
    kw.txtKeyboard.mark_gravity('mark', tk.LEFT)
    kw.txtKeyboard.tag_config('highlight', underline=1)
    kw.txtKeyboard.tag_add('highlight', 'mark')

def doFileExit():
    kw.root.destroy()
    kw.root.quit()

# Help menu

def doHelpAbout():
    mb.showinfo(title="About", message=kw.VERSION)

def doOfficeID(event=None):
    global myInternet
    kc.OfficeID = kw.varOfficeID.get()
    config.set_station(kc.OfficeID)
    config.save_config()
    myInternet.set_officeID(kc.OfficeID)

def doWPM(event=None):
    global mySender, myReader
    kc.WPM = int(kw.spnWPM.get())
    config.set_text_speed(kw.spnWPM.get())
    config.save_config()
    mySender = morse.Sender(wpm=kc.WPM, cwpm=kc.CWPM,
            codeType=kc.CodeType, spacing=kc.Spacing)
    myReader = morse.Reader(wpm=kc.WPM, codeType=kc.CodeType,
            callback=readerCallback)

def doWireNo(event=None):
    global connected
    kc.WireNo = int(kw.spnWireNo.get())
    config.set_wire(kw.spnWireNo.get())
    config.save_config()
    if connected:
        myInternet.connect(kc.WireNo)

def doConnect():
    global connected
    connected = not connected
    color = 'red' if connected else 'white'
    kw.cvsConnect.create_rectangle(0, 0, 20, 20, fill=color)
    if connected:
        myInternet.connect(kc.WireNo)
    else:
        myInternet.disconnect()

##def codeSender():
##    while running:
##        if kw.txtKeyboard.compare('mark', '<', tk.END) and \
##                kw.varCodeSenderOn.get():
##            c = kw.txtKeyboard.get('mark')
##            code = mySender.encode(c)
##            myKOB.sounder(code)
##            kw.txtKeyboard.tag_remove('highlight', 'mark')
##            kw.txtKeyboard.mark_set('mark', 'mark+1c')
##            kw.txtKeyboard.mark_gravity('mark', tk.LEFT)
##            kw.txtKeyboard.tag_add('highlight', 'mark')
##        else:
##            time.sleep(0.1)
