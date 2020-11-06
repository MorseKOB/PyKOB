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
import kobactions as ka
import kobevents as ke
import kobmain as km

root = None # Must be set from the root window

__active_stations = {} # Dictionary of station ID to time last pinged, initially connected, and received from ({"id":[ping,connected,received]})
__last_sender = None # Keep last sender to know when a sender changes

def update_current_sender(id: str):
    """
    Generate an event to record the current sender.
    """
    root.event_generate(ke.EVENT_CURRENT_SENDER, when='tail', data=id)

def handle_update_current_sender(event_data):
    """
    Event handler to record the station that is now sending. Add it if it doesn't exist.
    Update the ping and received timestamps of the station in the station list.
    """
    global __active_stations, __last_sender
    station_name = event_data
    now = time.time()
    __active_stations[station_name] = [now,now,now]
    if not station_name == __last_sender:
        __last_sender = station_name
        trim_station_list()
        display_station_list()

def update_station_active(id: str):
    """
    Generate an event to update the active status (timestamp) of a station.
    """
    root.event_generate(ke.EVENT_STATION_ACTIVE, when='tail', data=id)

def handle_update_station_active(event_data):
    """
    Update the station ping time. Add the station:[ping,connected,0] if it doesn't exist.
    """
    global __active_stations
    station_name = event_data
    now = time.time()
    station_times = []
    if station_name in __active_stations:
        station_times = __active_stations[station_name]
        station_times[0] = now # update ping time
    else:
        # create new entry with ping of now, connected of now, and never received from
        station_times = [now,now, 0] 
    __active_stations[station_name] = station_times
    if trim_station_list():
        display_station_list()

def clear_station_list():
    """
    Generate an event to clear the station list and the window.
    """
    root.event_generate('<<Clear>>', when='tail')

def handle_clear_station_list(event):
    """
    reset the station list
    """
    global __active_stations
    __active_stations = {}
    ka.kw.txtStnList.delete('1.0', 'end')

def trim_station_list() -> bool:
    """
    Check the timestamp of the stations and remove old ones.

    Return: True is a station was removed from the list
    """
    global __active_stations
    now = time.time()
    station_removed = False

    # find and purge inactive stations 
    new_station_list = {}
    for station in __active_stations.items():
        station_name = station[0]
        station_times = station[1]
        if station_times[0] > now - 60: # station active within last minute - keep it
            new_station_list[station_name] = station_times
        else:
            station_removed = True
    __active_stations = new_station_list
    return station_removed

def display_station_list():
    """
    Display the updated station list 
    ordered by last send time (most recent at the bottom).
    For stations that have only connected and not sent, order them by time connected.
    """
    global __active_stations
    # Delete the current window contents
    ka.kw.txtStnList.delete('1.0', 'end')
    for station_name in sorted(__active_stations, key=lambda k: (__active_stations[k][2], __active_stations[k][1])): # Sort by received from time
        ka.kw.txtStnList.insert('end', "{}\n".format(station_name))
