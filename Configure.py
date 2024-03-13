#!/usr/bin/env python3
"""
MIT License

Copyright (c) 2020-24 PyKOB - MorseKOB in Python

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
from pykob.util import strtobool
import os.path
import sys
from typing import Optional

GUI = True                              # Hope for the best
try:
    import tkinter as tk
except ModuleNotFoundError:
    GUI = False

from pykob import config, config2
from pykob.config2 import Config
from pykob import preferencesWindow

NONE_CFG_VALUE = "NONE"

def stringOrNone(s:str) -> Optional[str]:
    """
    Return `None` if the value is "NONE" (case insensitive) or the value

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

def _doFilePreferences():
    prefs = preferencesWindow.PreferencesWindow()

def _doFileExit():
    sys.exit(0)

def main(argv):
    # Check for command line parameters...
    #  If none are supplied, print the current configuration
    #  If arguments are given, process them for 'help' or the setting values.
    #  If values are specified, update the config and save it, then
    #  print the configuration.
    #
    cfg:Config = Config()
    cfg.load_from_global()
    cfg.set_using_global(True)
    cfg.clear_dirty()
    original_cfg:Config = cfg.copy()
    try:
        arg_parser = argparse.ArgumentParser(prog="Configure",
                description="Display the PyKOB configuration as well as key system values. "
                + "Allow configuration values to be set and saved.",
                epilog="If configuration values are changed, the configuration will be saved.\n",
                parents=
                [
                    config2.server_url_override,
                    config2.station_override,
                    config2.wire_override,
                    config2.auto_connect_override,
                    config2.gpio_override,
                    config2.serial_port_override,
                    config2.interface_type_override,
                    config2.invert_key_input_override,
                    config2.local_override,
                    config2.remote_override,
                    config2.sound_override,
                    config2.audio_type_override,
                    config2.sounder_override,
                    config2.sounder_pwrsv_override,
                    config2.code_type_override,
                    config2.min_char_speed_override,
                    config2.text_speed_override,
                    config2.spacing_override,
                    config2.debug_level_override
                ])
        arg_parser.add_argument('--gload', dest="global_load", action='store_true',
                help="Load configuration from the global store. " +
                "Allows setting an existing configuration file to the global values.")
        arg_parser.add_argument('--gsave', dest="global_only_save", action='store_true',
                help="Save configuration to the global store.")
        if GUI:
            arg_parser.add_argument('-G', '--gui', dest="gui_config", action='store_true',
                    help="Use preferences panel GUI for interactive configuration.")
        # Optional positional argument #1: Config file to use
        arg_parser.add_argument("pkcfg", metavar="config-file", nargs='?',
                help="PyKOB configuration file to use. " +
                "If specified, this will be used rather than the global configuration. " +
                "If the file doesn't exist it will be created. To save this configuration " +
                "to the global store, use the '--global' option along with this.")
        # Optional positional argument #2: Config file to save to
        arg_parser.add_argument("pkcfg_save_to", metavar="save-as-file", nargs='?',
                help="PyKOB configuration file to save to. " +
                "If specified, the configuration will be saved to this file rather than 'config-file'.")

        try:
            args = arg_parser.parse_args()
        except Exception as ex:
            print("Error parsing arguments: {}".format(ex), file=sys.stderr)
            sys.exit(2)

        load_from_global = False
        save_to_global = False
        save_only_to_global = False
        save_to_filepath = None
        # See if we have a 'save to' config.
        if args.pkcfg_save_to:
            s = args.pkcfg_save_to
            save_to_filepath = config2.add_ext_if_needed(s.strip())

        # See if a pkcfg file was specified to use
        if args.pkcfg:
            # They specified a config file, load it if it exists.
            file_path = config2.add_ext_if_needed(args.pkcfg)
            cfg.set_filepath(file_path)
            load_from_global = args.global_load
            save_only_to_global = args.global_only_save
            save_to_global = save_only_to_global
            if os.path.isfile(file_path):
                # The file exists. Load it unless 'load_from_global'. Then apply any changes.
                if not load_from_global:
                    cfg.load_config(file_path)
                if save_to_filepath:
                    # Set the file path to save to and mark as dirty to assure it gets saved.
                    cfg.set_filepath(save_to_filepath)
                    cfg.set_dirty()
            else:
                # The file does not exist.
                # That's okay if they want to create a new configuration, but
                # if a 'save to' file was specified, it's an error.
                if save_to_filepath:
                    print("The source configuration file specified does not exist. File: '{}'".format(file_path), file=sys.stderr)
                    sys.exit(1)
                cfg.set_dirty()  # Mark as dirty so the file will be saved/created even if no changes are made.
        else:
            # They did not specify a config file, so they want to work with the global config
            save_to_global = True

        if save_only_to_global:
            cfg.set_filepath(None)  # Clear the filepath so is doesn't save there

        # Keep the original config at this point
        original_cfg.copy_from(cfg)

        # Set config values if they were specified
        config2.process_config_args(args, cfg)
    except Exception as ex:
        print("Error processing arguments: {}".format(ex))
        sys.exit(1)

    if GUI and args.gui_config:
        try:
            root = tk.Tk()
            root.overrideredirect(1)
            root.withdraw()

            menu = tk.Menu()
            root.config(menu=menu)
            fileMenu = tk.Menu(menu)
            menu.add_cascade(label='File', menu=fileMenu)
            fileMenu.add_command(label='Preferences...', command=_doFilePreferences)
            fileMenu.add_separator()
            fileMenu.add_command(label='Quit', command=_doFileExit)

            prefs = preferencesWindow.PreferencesWindow(cfg, quitWhenDismissed=True)
            prefs.display()
            # root.quit()
        except KeyboardInterrupt:
            print()
            sys.exit(0)
    else:
        # If any of the configuration values changed, save the configuration.
        if cfg.is_dirty():
            if cfg.get_filepath():
                cfg.save_config()
            if save_to_global:
                cfg.load_to_global()
                cfg.save_global()
                cfg.clear_dirty()

    # If no arguments were given print the system info in addition to the configuration.
    if len(argv) == 0:
        print("======================================")
        print("         System Information")
        print("======================================")
        config.print_system_info()
    config_header = \
          "        Global Configuration" \
        if save_to_global else \
          "           Configuration"
    print("======================================")
    print(config_header)

    # Check if the cfg is dirty at this point. If so, it wasn't saved, so print the original.
    if cfg.is_dirty():
        original_cfg.print_config()
    else:
        cfg.print_config()
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

