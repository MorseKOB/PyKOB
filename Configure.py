#! python
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
    -h | --help                     : Print help information for using the application
    -i | --sysInfo                  : Print information about the system that relates to PyKOB
    -p | --port <port>              : Set the system PORT (COM or tty) value to use for a sounder
    -a | --sound <ON|OFF>           : Set preference for using/not-using the computer sound
    -A | --sounder <ON|OFF>         : Set preference for using a physical sounder (`port` must be configured)
    -c | --chars                    : Set preferance for speed in WPM (used with word speed for Farnsworth timing)
    -s | --spacing CHAR|WORD:       : Set preferance for how to apply Farnsworth spacing
    -S | --station <station|NONE>:  : Set preferance for the station to connect to
    -w | --words <words_per_minute> : Set preference for Words-Per-Minute speed
    -W | --wire <wire-number>:      : Set preference for wire number to connect to
Examples:
    configure -port COM3
    configure -c 20 -w 16 --sound ON

"""
import sys, getopt
from pykob import config

NONE_CFG_VALUE = "NONE"

def help():
    print(" Configure settings/preferences for PyKOB")
    print("  Usage: Configure {[{-h|--help} | {-p|--port port} \
        {-a|--sound [ON|OFF]) {-c|--chars n} {-s|--spacing [CHAR|WORD]} \
        {-w|--words n} {-A|--sounder [ON|OFF]} \
        {-S|--station [station|NONE]} {-W|--wire n} \
        {-i|--sysInfo}]}")
    print("      Values are:")
    print("          -h | --help:                           Pring this help message.")
    print("")
    print("          -i | --sysInfo:                        Print information about the system that relates to MorseKOB")
    print("")
    print("          -p | --port <serial_port|NONE>:        Set the serial communication port for the interface.")
    print("")
    print("          -c | --chars <words_per_minute>:       Set the character speed in WPM (used with word speed for Farnsworth timing).")
    print("          -w | --words <words_per_minute>:       Set the word speed in WPM (used with character speed for Farnsworth timing).")
    print("          -a | --sound ON|OFF:                   Use the computer sound to simulate a sounder.")
    print("          -A | --sounder ON|OFF:                 Use the physical sounder (if 'PORT' is configured).")
    print("          -s | --spacing CHAR|WORD:              How to apply Farnsworth spacing.")
    print("          -S | --station <station|NONE>:         Set the Station to connect to.")
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
    sound = None
    sounder = None
    spacing = None
    station = None
    wire = None
    char_speed = None
    word_speed = None

    try:
        opts, args = getopt.getopt(argv,"hp:c:w:a:A:s:S:W:i",["help","port=", \
            "chars=","words=", "sound=", "sounder=", "spacing=", "station=", \
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
        elif opt in ("-c", "--chars"):
            char_speed = arg
        elif opt in ("-w", "--words"):
            word_speed = arg
        elif opt in ("-a", "--sound"):
            sound = arg
        elif opt in ("-A", "--sounder"):
            sounder = arg
        elif opt in ("-s", "--spacing"):
            spacing = arg
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
    if char_speed:
        #print(char_speed)
        config.set_cwpm_speed(char_speed)
        save_config = True
    if word_speed:
        #print(word_speed)
        config.set_wpm_speed(word_speed)
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
   main(sys.argv[1:])
