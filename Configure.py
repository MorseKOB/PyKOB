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

"""
Configure.py

Configures system values and user preferences for the suite of PyKOB applications.

Command line parameters:
    -h | --help                        : Print help information for using the application
    -i | --sysInfo                     : Print information about the system that relates to PyKOB
    -p | --port <port>                 : Set the system PORT (COM or tty) value to use for a sounder
    -L | --local <ON|OFF>              : Enable/disable local copy of code  
    -R | --remote <ON|OFF>             : Enable/disable sending code to remote wire (over the internet)
    -a | --sound <ON|OFF>              : Enable the computer sound to simulate a sounder
    -A | --sounder <ON|OFF>            : Use a physical sounder (`port` must be configured)
    -t | --textspeed wpm               : Set the text speed in words per minute
    -c | --charspeed                   : Set the minimum character speed in words per minute (used for Farnsworth timing)
    -s | --spacing NONE|CHAR|WORD      : Set preferance for how to apply Farnsworth spacing
    -T | --type AMERICAN|INTERNATIONAL : Set the code type
    -S | --station <station|NONE>      : Set preferance for the station to connect to
    -W | --wire <wire-number>          : Set preference for wire number to connect to
Examples:
    configure --port COM3
    configure --charspeed 20 -t 16 --sound ON

"""
import sys, getopt
from pykob import config

NONE_CFG_VALUE = "NONE"

def help():
    print(" Configure settings/preferences for PyKOB")
    print("  Usage: Configure {[{-h|--help} | {-p|--port port} \
{-L|--local [ON|OFF]} {-R|--remote [ON|OFF]} \
{-a|--sound [ON|OFF]} {-c|--chars n} {-s|--spacing [NONE|CHAR|WORD]} \
{-w|--words n} {-A|--sounder [ON|OFF]} \
{-S|--station [station|NONE]} {-W|--wire n} \
{-i|--sysInfo}]}")
    print("      Values are:")
    print("          -h | --help:                           Print this help message.")
    print("")
    print("          -i | --sysInfo:                        Print information about the system that relates to MorseKOB")
    print("")
    print("          -p | --port <serial_port|NONE>:        Set the serial communication port for the interface.")
    print("")
    print("          -t | --textspeed <words_per_minute>:   Set the overall code speed in WPM.")
    print("          -c | --charspeed <words_per_minute>:   Set the minimum character speed in WPM (used for Farnsworth timing).")
    print("          -a | --sound ON|OFF:                   Set preference for using the computer sound to simulate a sounder.")
    print("          -A | --sounder ON|OFF:                 Set preference for using a physical sounder ('PORT' must be configured).")
    print("          -L | --local ON|OFF:                   Produce local copy of generated/transmitted text.")
    print("          -R | --remote ON|OFF:                  Transmit over the internet on the specified wire.")
    print("          -s | --spacing NONE|CHAR|WORD:         How to apply Farnsworth spacing.")
    print("          -T | --type AMERICAN|INTERNATIONAL:    Set the code type.")
    print("          -S | --station <station|NONE>:         Set the Station ID.")
    print("          -W | --wire <wire-number>:             Set the Wire number to connect to.")

def missingArgsErr(msg):
    print(msg)
    help()
    exit

def stringOrNone(s):
    """Return `None` if the value is "NONE" (case insensitive) or the value

    Parameters
    ----------
    s : str
        'NONE' (case insensitive) or a string value.

    Return
    ------
    None or `String value`
    """

    r = None if s.upper() == "NONE" else s
    return r

def main(argv):
    # Check for command line parameters...
    #  If none are supplied, print the current configuration
    #  If arguments are given, process them for 'help' or the setting values.
    #  If values are specified, update the config and save it, then 
    #  print the configuration.

    # System configuration
    port = None
    # User preferences
    local = None
    remote = None
    sound = None
    sounder = None
    spacing = None
    station = None
    code_type = None
    wire = None
    min_char_speed = None
    text_speed = None

    try:
        opts, args = getopt.getopt(argv,"hp:t:c:L:R:a:A:s:T:S:W:i",["help", "port=", \
            "textspeed=", "charspeed=", "local=", "remote=", "sound=", "sounder=", "spacing=", "type=", "station=", \
            "wire=", "sysInfo"])
    except getopt.GetoptError as ex:
        print(" {}".format(ex.args[0]))
        print()
        help()
        sys.exit(2)

    # Process the options
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            help()
            sys.exit()
        elif opt in ("-p", "--port"):
            port = arg
        elif opt in ("-L", "--local"):
            local = arg
        elif opt in ("-R", "--remote"):
            remote = arg
        elif opt in ("-c", "--charspeed"):
            min_char_speed = arg
        elif opt in ("-t", "--textspeed"):
            text_speed = arg
        elif opt in ("-a", "--sound"):
            sound = arg
        elif opt in ("-A", "--sounder"):
            sounder = arg
        elif opt in ("-s", "--spacing"):
            spacing = arg
        elif opt in ("-T", "--type"):
            code_type = arg
        elif opt in ("-S", "--station"):
            station = arg
        elif opt in ("-W", "--wire"):
            wire = arg
        elif opt in ("-i", "--sysInfo"):
            config.print_system_info()

    # Set config values if they were specified
    save_config = False
    if port:
        #print(port)
        port = stringOrNone(port)
        config.set_serial_port(port)
        save_config = True
    if local:
        #print(local)
        config.set_local(local)
        save_config = True
    if remote:
        #print(remote)
        config.set_remote(remote)
        save_config = True
    if min_char_speed:
        #print(min_char_speed)
        config.set_min_char_speed(min_char_speed)
        save_config = True
    if text_speed:
        #print(text_speed)
        config.set_text_speed(text_speed)
        save_config = True
    if sound:
        #print(sound)
        sound = stringOrNone(sound)
        config.set_sound(sound)
        save_config = True
    if sounder:
        #print(sounder)
        config.set_sounder(sounder)
        save_config = True
    if spacing:
        #print(spacing)
        config.set_spacing(spacing)
        save_config = True
    if code_type:
        #print(code_type)
        config.set_code_type(code_type)
        save_config = True
    if station:
        #print(station)
        station = stringOrNone(station)
        config.set_station(station)
        save_config = True
    if wire:
        #print(wire)
        wire = stringOrNone(wire)
        config.set_wire(wire)
        save_config = True

    if save_config:
        config.save_config()

    config.print_config()
    exit

if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except KeyboardInterrupt:
        print()
        sys.exit(1)     # Indicate this was an abnormal exit
