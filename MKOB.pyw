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
MKOB.pyw

Python Morse Code Sending, Receiving, and Learning/Training application
influenced by the MorseKOB 2.5 application by Les Kerr.
"""
import argparse
import tkinter as tk
import sys
from pykob import config2, log
from pykob import VERSION as PKVERSION
import pkappargs
import mkobwindow as mkw
from mkobwindow import MKOBWindow

__version__ = "4.2.1"
VERSION = __version__
MKOB_VERSION_TEXT = "MKOB " + VERSION
print(MKOB_VERSION_TEXT)
print(" Python: " + sys.version + " on " + sys.platform)
print(" pykob: " + PKVERSION)
print(" Tcl/Tk: {}/{}".format(tk.TclVersion, tk.TkVersion))

destoy_on_exit = True
mkobwin: MKOBWindow = None
try:
    arg_parser = argparse.ArgumentParser(description="Morse KOB application. This provides a full graphical interface to "
            + "send and receive Morse over the internet, "
            + "as well as practice locally.\nFor a text-only (command line version), try 'MRT'. "
            + "The Global Configuration is used unless a configuration file is specified.",
        parents= [
            config2.config_file_override,
            config2.logging_level_override,
            pkappargs.record_session_override,
            pkappargs.sender_datetime_override
        ]
    )
    args = arg_parser.parse_args()
    cfg = config2.process_config_args(args)
    cfg.clear_dirty()  # Assume that what they loaded is what they want.

    record_filepath = pkappargs.record_filepath_from_args(args)
    sender_dt = args.sender_dt

    log.set_logging_level(cfg.logging_level)
    log.debug("MKOB: Logging level: {}".format(cfg.logging_level))

    root = tk.Tk(className="MKOB")
    icon = tk.PhotoImage(file="resources/mkob-icon_64.png")
    root.iconphoto(True, icon)
    root.rowconfigure(0, weight=1)
    root.columnconfigure(0, weight=1)
    # Our content
    mkobwin = MKOBWindow(root, MKOB_VERSION_TEXT, cfg, sender_dt, record_filepath)

    # Set a minsize for the window, and place it in the middle
    root.update()
    root.geometry("+30+30")
    root.state('normal')

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
    sys.exit(0)
except Exception as ex:
    print("Error: {}".format(ex))
    sys.exit(1)
finally:
    if mkobwin:
        mkobwin.exit(destoy_on_exit)
    print("~73")
sys.exit(0)

