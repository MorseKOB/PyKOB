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

from re import L
import time
import mkobevents as ke

class MKOBStationList:
    """
    Manages a window that displays the stations that are currently
    connected to the wire that this station is connected to.

    It keeps the list in order based on how lately the station has sent
    on the wire. The station that is currently sending is at the very
    top. After that is a divider, then the rest of the stations. The
    stations that have not sent (as seen by this station) are indented at,
    the top, then from the station that least recently sent to the station
    that most recently sent.
    """

    def __init__(self, kw) -> None:
        ## Station Info:
        #  0: Station name
        #  1: Time initially connected
        #  2: Time received from
        #  3: Last PING time
        self.__active_stations = [] # List of lists with [station ID, time initially connected, time received from, ping time]
        self.__last_sender = "" # Keep last sender to know when a sender changes
        self.kw = kw

    def handle_clear_station_list(self, event):
        """
        reset the station list
        """
        self.__active_stations = []
        self.__last_sender = ""
        self.kw.station_list_win.delete('1.0', 'end')

    def handle_update_current_sender(self, station_name: str):
        """
        Update the station's last send time.
        Add the [station_name,connected_time,received_time,ping_time] if it doesn't exist.
        If it is a different sender from the last, put it at the beginning and put the current
        sender at the end.

        This is intended to order the list as:
        Current Sender
        Oldest sender (suggest next to send)
        Next-oldest sender
        Next-next-oldest sender
        etc.
        Most recent sender -or- new station
        """
        now = time.time()

        existing_entry_updated = False
        sender_changed = False
        for i in range(0, len(self.__active_stations)): # better way to do this?
            station_info = self.__active_stations[i]
            if (station_info[0] == station_name):
                # update the last received from time for this station
                station_info[2] = now
                if not station_name == self.__last_sender:
                    self.__active_stations.pop(i)
                    # find the entry for the last (current) sender
                    for j in range(0, len(self.__active_stations)):
                        si = self.__active_stations[j]
                        if (si[0] == self.__last_sender):
                            # move this entry to the end
                            self.__active_stations.pop(j)
                            self.__active_stations.append(si)
                    self.__active_stations.insert(0, station_info)
                    sender_changed = True
                existing_entry_updated = True
                break
        if not existing_entry_updated:
            # add an entry
            self.__active_stations.append([station_name, now, now, now])
        if self.__trim_station_list() or (not existing_entry_updated) or sender_changed:
            self.__last_sender = station_name
            self.__display_station_list()

    def handle_update_station_active(self, station_name: str):
        """
        Update the station's ping time.
        Add the [station_name,connected_time,received_time,ping_time] if it doesn't exist
        (connected_time is now).
        """
        now = time.time()

        existing_entry_updated = False
        for i in range(0, len(self.__active_stations)): # is there a better way to do this?
            station_info = self.__active_stations[i]
            if (station_info[0] == station_name):
                # update the ping time for this station
                station_info[3] = now
                existing_entry_updated = True
                break
        if not existing_entry_updated:
            # new station, add an entry
            station_info = [station_name, now, -1, now]
            if self.__last_sender: # if there is a sender add this just before it
               self. __active_stations.insert(-1,station_info)
            else:
                self.__active_stations.append(station_info)
        if  self.__trim_station_list() or not existing_entry_updated:
            self.__display_station_list()

    def __trim_station_list(self) -> bool:
        """
        Check the timestamp of the stations and remove old ones.

        Return: True is a station was removed from the list
        """
        now = time.time()

        # find and purge inactive stations
        ## keep stations with ping time (element 3) within the last 2/3rds a minute
        new_station_list = [row for row in self.__active_stations if row[3] > now - 40]
        station_removed = len(new_station_list) < len(self.__active_stations)
        if station_removed:
            last_sender_found = False
            # If the last sender was removed, clear __last_sender
            for station_info in new_station_list:
                if station_info[0] == self.__last_sender:
                    last_sender_found = True
                    break
                if not last_sender_found:
                    self.__last_sender = ''
        self.__active_stations = new_station_list
        return station_removed

    def __display_station_list(self):
        """
        Display the updated station list
        ordered by last send time (new sender at the top, then most recent at the bottom).
        For stations that have only connected and not sent, order them by time connected.
        """
        # Delete the current window contents
        self.kw.station_list_win.delete('1.0', 'end')
        for i in range(0, len(self.__active_stations)):
            station_info = self.__active_stations[i]
            indent = "    " if station_info[2] < 0 else ""
            self.kw.station_list_win.insert('end', "{}{}\n".format(indent, station_info[0]))
            if i == 0 and len(self.__active_stations) > 1 and self.__last_sender:
                # Insert a line of dashes (-----------------)
                self.kw.station_list_win.insert('end', "------------------------\n")

