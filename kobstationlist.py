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

Calls to the 'handle_' methods should be made on the main GUI thread as a result of the GUI handling 
message events.
"""

import time
import kobwindow as kw
import kobevents as ke
import kobmain as km

__active_stations = [] # List of lists with [station ID, time initially connected, time received from, ping time]
__last_sender = "" # Keep last sender to know when a sender changes

def handle_clear_station_list(event):
    """
    reset the station list
    """
    global __active_stations, __last_sender
    __active_stations = []
    __last_sender = ""
    kw.txtStnList.delete('1.0', 'end')

def handle_update_current_sender(station_name: str):
    """
    Update the station's last send time. 
    Add the [station_name,connected_time,received_time,ping_time] if it doesn't exist.
    If it is a different sender from the last, move it to the end.
    """
    global __active_stations, __last_sender
    now = time.time()

    existing_entry_updated = False
    sender_changed = False
    for i in range(0, len(__active_stations)): # better way to do this?
        station_info = __active_stations[i]
        if (station_info[0] == station_name):
            # update the last received from time for this station
            station_info[2] = now
            if not station_name == __last_sender:
                __active_stations.pop(i)
                __active_stations.append(station_info)
                sender_changed = True
            existing_entry_updated = True
            break
    if not existing_entry_updated:
        # add an entry
        __active_stations.append([station_name, now, now, now])
    if __trim_station_list() or (not existing_entry_updated) or sender_changed:
        __last_sender = station_name
        __display_station_list()

def handle_update_station_active(station_name: str):
    """
    Update the station's ping time. 
    Add the [station_name,connected_time,received_time,ping_time] if it doesn't exist
    (connected_time is now).
    """
    global __active_stations
    now = time.time()

    existing_entry_updated = False
    for i in range(0, len(__active_stations)): # is there a better way to do this?
        station_info = __active_stations[i]
        if (station_info[0] == station_name):
            # update the ping time for this station
            station_info[3] = now
            existing_entry_updated = True
            break
    if not existing_entry_updated:
        # new station, add an entry
        station_info = [station_name, now, -1, now]
        if __last_sender: # if there is a sender add this just before it
            __active_stations.insert(-1,station_info)
        else:
            __active_stations.append(station_info)
    if  __trim_station_list() or not existing_entry_updated:
        __display_station_list()

def __trim_station_list() -> bool:
    """
    Check the timestamp of the stations and remove old ones.

    Return: True is a station was removed from the list
    """
    global __active_stations
    now = time.time()

    # find and purge inactive stations
    ## keep stations with ping time (element 3) within a minute of now
    new_station_list = [row for row in __active_stations if row[3] > now - 60]
    station_removed = len(new_station_list) < len(__active_stations)
    __active_stations = new_station_list
    return station_removed

def __display_station_list():
    """
    Display the updated station list 
    ordered by last send time (most recent at the bottom).
    For stations that have only connected and not sent, order them by time connected.
    """
    global __active_stations
    # Delete the current window contents
    kw.txtStnList.delete('1.0', 'end')
    # ZZZ need to put these in the proper order
    for station_info in __active_stations: 
        #sorted(__active_stations, key=lambda k: (__active_stations[k][2], __active_stations[k][1])): 
        # Sort by received then connected from time
        kw.txtStnList.insert('end', "{}\n".format(station_info[0]))
