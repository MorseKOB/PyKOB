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
import kobwindow

VERSION = "4.0.13"
MKOB_VERSION_TEXT = "MorseKOB " + VERSION
print(MKOB_VERSION_TEXT)
print("Tcl/Tk {}/{}".format(tk.TclVersion, tk.TkVersion))

try:
    root = tk.Tk()
##    root.iconbitmap("resources/mkob.ico")  # TODO: fails with Linux
    kobwindow.KOBWindow(root, MKOB_VERSION_TEXT)
    root.mainloop()
except KeyboardInterrupt:
    print()
sys.exit(0)
