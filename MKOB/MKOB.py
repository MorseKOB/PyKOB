#!/usr/bin/env python3

"""

MKOB.pyw

Python version of MorseKOB 2.5

"""

import tkinter as tk
import kobwindow as kw
import kobactions as ka
import threading

VERSION = 'MKOB 1.0.0'

root = tk.Tk()
kw.KOBWindow(root, VERSION)
root.mainloop()
##ka.running = False
print('normal exit')
