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
    -p | --port <port>              : Set the system PORT (COM or tty) value to use for a sounder
    -a | --sound <ON|OFF>           : Set the user preference for using/not-using the computer sound
    -s | --speed <words_per_minute> : Set the user Words-Per-Minute speed preference
    -i | --sysInfo                  : Print information about the system that relates to PyKOB
Examples:
    configure -port COM3
    configure -speed 22 -sound ON

"""
import sys, getopt
from pykob import config

def help():
    print(' Configure settings/preferences for PyKOB')
    print('  Usage: Configure {[{-h|--help} | {-p|--port port} {-a|--sound [ON|OFF]) {-s|--speed wpm} {-i|--sysInfo}]}')
    print('      Values are:')
    print('          -h | --help:                      Pring this help message.')
    print('          -p | --port <serial_port|NONE>:   Set the serial communication port for the interface.')
    print('          -a | --sound ON|OFF:              Use the computer sound or not.')
    print('          -s | --speed <words_per_minute>:  Set the WPM value to use for playing and analyzing.')
    print('          -i | --sysInfo:                   Print information about the system that relates to MorseKOB')

def missingArgsErr(msg):
    print(msg)
    help()
    exit

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
    speed = None

    try:
        opts, args = getopt.getopt(argv,"hp:a:s:i",["help","port=","sound=","speed=", "sysInfo"])
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
            if arg.upper == 'NONE':
                port = ""
            else:
                port = arg
        elif opt in ("-a", "--sound"):
            sound = arg
        elif opt in ("-s", "--speed"):
            speed = arg
        elif opt in ("-i", "--sysInfo"):
            config.print_system_info()

    # Set config values if they were specified
    save_config = False
    if not port == None:
        if port.upper() == "NONE":
            port = ''
        config.set_serial_port(port)
        save_config = True
    if not sound == None:
        config.set_sound(sound)
        save_config = True
    if not speed == None:
        config.set_wpm_speed(speed)
        save_config = True

    if save_config:
        config.save_config()

    config.print_config()
    exit

if __name__ == "__main__":
   main(sys.argv[1:])
