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

"""Configure.py

Configures system values and user preferences for the suite of PyKOB applications.

Provides a Command Line Interface (CLI) the the pykob.config module.
"""
import argparse
import sys
from pykob import config

NONE_CFG_VALUE = "NONE"

def stringOrNone(s:str) -> str:
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
    invert_key_input = None
    local = None
    remote = None
    interface_type = None
    sound = None
    sounder = None
    spacing = None
    station = None
    code_type = None
    wire = None
    min_char_speed = None
    text_speed = None

    try:
        arg_parser = argparse.ArgumentParser(description="Display the PyKOB configuration as well as key system values. "
            + "Allow configuration values to be set and saved.", \
            parents=\
            [\
            config.code_type_override, \
            config.interface_type_override, \
            config.invert_key_input_override, \
            config.local_override, \
            config.min_char_speed_override, \
            config.remote_override, \
            config.serial_port_override, \
            config.sound_override, \
            config.sounder_override, \
            config.spacing_override, \
            config.station_override, \
            config.text_speed_override, \
            config.wire_override])

        args = arg_parser.parse_args()

        # Set config values if they were specified
        save_config = False
        if not args.code_type == config.code_type:
            config.set_code_type(args.code_type)
            save_config = True
        if not args.interface_type == config.interface_type:
            config.set_interface_type(args.interface_type)
            save_config = True
        if not args.invert_key_input == config.invert_key_input:
            config.set_invert_key_input(args.invert_key_input)
            save_config = True
        if not args.local == config.local:
            config.set_local(args.local)
            save_config = True
        if not args.min_char_speed == config.min_char_speed:
            config.set_min_char_speed(args.min_char_speed)
            save_config = True
        if not args.remote == config.remote:
            config.set_remote(args.remote)
            save_config = True
        if not args.serial_port == config.serial_port:
            config.set_serial_port(args.serial_port)
            save_config = True
        if not args.sound == config.sound:
            config.set_sound(args.sound)
            save_config = True
        if not args.sounder == config.sounder:
            config.set_sounder(args.sounder)
            save_config = True
        if not args.spacing == config.spacing:
            config.set_spacing(args.spacing)
            save_config = True
        if not args.station == config.station:
            config.set_station(args.station)
            save_config = True
        if not args.text_speed == config.text_speed:
            config.set_text_speed(args.text_speed)
            save_config = True
        if not args.wire == config.wire:
            config.set_wire(args.wire)
            save_config = True

        # If any of the configuration values changed, save the configuration.
        if save_config:
            config.save_config()
    except Exception as ex:
        print("Error processing arguments: {}".format(ex))
        sys.exit(1)

    # If no arguments were given print the system info in addition to the configuration.
    if len(argv) == 0:
        print("======================================")
        print("        System Information")
        print("======================================")
        config.print_system_info()
        print("======================================")
        print("          Configuration")

    config.print_config()
    sys.exit(0)

if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except ValueError as ex:
        print(ex.args[0])
        sys.exit(1)     # Indicate this was an abnormal exit
    except KeyboardInterrupt:
        print()
        sys.exit(0)     # Indicate this was a normal exit
    
