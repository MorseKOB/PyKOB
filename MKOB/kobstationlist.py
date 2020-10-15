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
kobstationlist.py

Manage the station list window.
"""

import time
import kobactions as ka
import kobmain as km

station_ID_list = []
station_ID_times = []

def refresh_stations(id):
    """update the station list when an ID is sent or received"""
    global station_ID_list, station_ID_times
    if not km.connected:
        clear_station_list()
        return
    try:
        i = station_ID_list.index(id)
    except:
        station_ID_list.append(id)
        station_ID_times.append(0)
        i = len(station_ID_list) - 1
    station_ID_times[i] = time.time()
    display_station_list()

def new_sender(id):
    """update the station list when a new sender is detected"""
    global station_ID_list, station_ID_times
# ZZZ   if not km.connected:
# ZZZ       clear_station_list()
# ZZZ       return
    try:
        i = station_ID_list.index(id)
        station_ID_list.pop(i)
        station_ID_times.pop(i)
    except:
        pass
    station_ID_list.append(id)
    station_ID_times.append(time.time())
    display_station_list()

def clear_station_list():
    """reset the station list"""
    global station_ID_list, station_ID_times
    station_ID_list = []
    station_ID_times = []
    ka.kw.txtStnList.delete('1.0', 'end')

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
        station_ID_list.pop(i)
        station_ID_times.pop(i)
    # display station list
    ka.kw.txtStnList.delete('1.0', 'end')
    for i in range(len(station_ID_list)):
        ka.kw.txtStnList.insert('end', "{}\n".format(station_ID_list[i]))
