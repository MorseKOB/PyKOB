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

"""
MKOB.py

Python Morse Code Sending, Receiving, and Learning/Training application
influenced by the MorseKOB 2.5 application by Les Kerr.
"""
import argparse
from os import path
from sys import exit as sys_exit
from sys import platform as sys_platform
from sys import version as sys_version
import tkinter as tk
import traceback

from pykob import config, config2, log
from pykob import VERSION as PKVERSION
import pkappargs
from mkobenv import MKOBEnv
import mkobwindow as mkw
from mkobwindow import MKOBWindow

COMPILE_INFO = globals().get("__compiled__")
__version__ = "4.4.0"
VERSION = __version__ if COMPILE_INFO is None else __version__ + 'c'
MKOB_VERSION_TEXT = "MKOB " + VERSION

print(MKOB_VERSION_TEXT)
print(" Python: " + sys_version + " on " + sys_platform)
print(" pykob: " + PKVERSION)
print(" Tcl/Tk: {}/{}".format(tk.TclVersion, tk.TkVersion))

destoy_on_exit = True
# type: Optional[MKOBWindow]
mkobwin = None
# type: Optional[MKOBEnv]
mkobenv = None

try:
    arg_parser = argparse.ArgumentParser(description="Morse KOB application. This provides a full graphical interface to "
            + "send and receive Morse over the internet, "
            + "as well as practice locally.\nFor a text-only (command line version), try 'MRT'. "
            + "A configuration file can be specified using the '--config' option, otherwise the last "
            + "configuration will be used.",
        parents= [
            config2.config_file_override,
            config2.logging_level_override,
            pkappargs.record_session_override,
            pkappargs.sender_datetime_override
        ]
    )
    args = arg_parser.parse_args()

    # Get the startup config file path to use if needed.
    env = MKOBEnv()

    # Make sure it exists
    startup_cfg_path = env.cfg_filepath if (not env.cfg_filepath is None and path.isfile(env.cfg_filepath)) else None

    cfg = config2.process_config_args(args, fallback=startup_cfg_path)
    cfg.clear_dirty()  # Assume that what they loaded is what they want.

    # Save the filepath of the configuration we loaded
    env.cfg_filepath = cfg.get_filepath()

    record_filepath = pkappargs.record_filepath_from_args(args)
    sender_dt = args.sender_dt

    log.set_logging_level(cfg.logging_level)
    log.debug("MKOB: Logging level: {}".format(cfg.logging_level))
    log.debug("Compiled: {}".format(COMPILE_INFO), 2, dt="")

    root = tk.Tk(className="MKOB")
    icon_file = "resources/MKOB-Logo.png"
    icon_file_exists = False
    if (path.isfile(icon_file)):
        icon = tk.PhotoImage(file=icon_file)
        root.iconphoto(True, icon)
        icon_file_exists = True
    root.rowconfigure(0, weight=1)
    root.columnconfigure(0, weight=1)
    # Our content
    mkobwin = MKOBWindow(root, MKOB_VERSION_TEXT, cfg, env, sender_dt, record_filepath)

    # Set a minsize for the window, and place it in the middle
    root.update()
    root.geometry("+30+30")
    root.state('normal')

    if cfg.logging_level > 5:
        print("Globals:")
        for k, v in list(globals().items()):
            print("    '{}'='{}'".format(str(k), str(v)))
    if cfg.logging_level > 9:
        mkw.print_hierarchy(root)

    # Schedule a couple things to run after we have entered the main loop.
    root.after(100, mkobwin.set_minimum_sizes)
    root.after(800, mkobwin.on_app_started)
    #
    root.mainloop()
    destoy_on_exit = False  # App is already destoyed at this point
except KeyboardInterrupt:
    print()
    sys_exit(0)
except Exception as ex:
    print("Error: {}\n".format(ex))
    print(traceback.format_exc())
    sys_exit(1)
finally:
    if mkobwin:
        mkobwin.exit(destoy_on_exit)
    print("~73")
sys_exit(0)

