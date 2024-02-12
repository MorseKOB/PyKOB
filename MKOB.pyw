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
MKOB.pyw

Python version of MorseKOB 2.5
"""

import tkinter as tk
import sys
from pykob import config, log
import mkobwindow as mkw
from mkobwindow import MKOBWindow

VERSION = "4.1.4"
MKOB_VERSION_TEXT = "MKOB " + VERSION
print(MKOB_VERSION_TEXT)
print("Tcl/Tk {}/{}".format(tk.TclVersion, tk.TkVersion))

try:
    root = tk.Tk(className="MKOB")
    icon = tk.PhotoImage(file="resources/mkob-icon_64.png")
    root.iconphoto(True, icon)
    # Set the theme
    #root.tk.call("source", "azure.tcl")
    #root.tk.call("set_theme", "light")
    root.rowconfigure(0, weight=1)
    root.columnconfigure(0, weight=1)
    root.title(MKOB_VERSION_TEXT)
    # Our content
    mkobwin = MKOBWindow(root, MKOB_VERSION_TEXT, config)

    # Set a minsize for the window, and place it in the middle
    root.update()
    root.minsize(int(root.winfo_width() * 0.66), int(root.winfo_height() * 0.66))
    x_cordinate = int((root.winfo_screenwidth() / 2) - (root.winfo_width() / 2))
    y_cordinate = int((root.winfo_screenheight() / 2) - (root.winfo_height() / 2))
    root.geometry("+{}+{}".format(x_cordinate, y_cordinate-20))
    root.state('normal')

    mkobwin.start()

    mkw.print_hierarchy(root)

    root.mainloop()

except KeyboardInterrupt:
    print()
sys.exit(0)
