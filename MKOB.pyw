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

Python version of MorseKOB 2.5
"""
import argparse
import tkinter as tk
import sys
from pykob import config2, log
from pykob import VERSION as PKVERSION
import mkobwindow as mkw
from mkobwindow import MKOBWindow

__version__ = "4.2.1"
VERSION = __version__
MKOB_VERSION_TEXT = "MKOB " + VERSION
print(MKOB_VERSION_TEXT)
print(" Python: " + sys.version + " on " + sys.platform)
print(" pykob: " + PKVERSION)
print(" Tcl/Tk: {}/{}".format(tk.TclVersion, tk.TkVersion))

distroy_on_exit = True
mkobwin: MKOBWindow = None
try:
    arg_parser = argparse.ArgumentParser(description="Morse KOB application. This provides a full graphical interface to "
                                         + "send and receive Morse over the internet, "
                                         + "as well as practice locally.\nFor a text-only (command line version), try 'MRT'. "
                                         + "The Global Configuration is used unless a configuration file is specified.",
        parents= [
            config2.config_file_override,
            config2.debug_level_override
        ]
    )
    args = arg_parser.parse_args()
    cfg = config2.process_config_args(args)
    cfg.clear_dirty()  # Assume that what they loaded is what they want.

    log.set_debug_level(cfg.debug_level)

    root = tk.Tk(className="MKOB")
    icon = tk.PhotoImage(file="resources/mkob-icon_64.png")
    root.iconphoto(True, icon)
    root.rowconfigure(0, weight=1)
    root.columnconfigure(0, weight=1)
    # Our content
    mkobwin = MKOBWindow(root, MKOB_VERSION_TEXT, cfg)

    # Set a minsize for the window, and place it in the middle
    root.update()
    root.geometry("+30+30")
    root.state('normal')

    mkobwin.start()

    if log.get_debug_level() > 10:
        mkw.print_hierarchy(root)

    root.after(400, mkobwin.set_minimum_sizes)
    root.after(800, mkobwin.give_keyboard_focus())

    root.mainloop()
    distroy_on_exit = False  # App is already distroyed at this point
except KeyboardInterrupt:
    print()
    sys.exit(0)
except Exception as ex:
    print("Error: {}".format(ex))
    sys.exit(1)
finally:
    if mkobwin:
        mkobwin.exit(distroy_on_exit)
    print("~73")
sys.exit(0)

