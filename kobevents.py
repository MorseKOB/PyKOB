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
kobevents.py

Event strings used to perform actions on window widgits or other features needing 
to be executed on the MAIN thread.

If standard events exist they should be used rather than creating/using custom 
events.

"""

# Define event messages
EVENT_CIRCUIT_CLOSE = "<<Circuit_Close>>" # Close the local circuit
EVENT_CIRCUIT_OPEN = "<<Circuit_Open>>" # Open the local circuit
EVENT_CURRENT_SENDER = "<<Current_Sender>>" # Record the current sender (station)
EVENT_EMIT_CODE = "<<Emit_Code>>" # Emit a code sequence
EVENT_PLAYER_WIRE_CHANGE = "<<Player_Wire_Change>>" # The player detected a wire change
EVENT_READER_APPEND_TEXT = "<<Reader_Append_Text>>" # Append text to the reader window
EVENT_READER_CLEAR = "<<Clear_Reader>>" # Clear the reader window
EVENT_STATION_ACTIVE = "<<Station_Active>>" # A station has indicated that it is still listening
EVENT_STATIONS_CLEAR = "<<Clear_Stations>>" # Clear the station window and station list
