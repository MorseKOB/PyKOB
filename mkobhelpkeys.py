"""
MIT License

Copyright (c) 2020-24 PyKOB - MorseKOB in Python

Permission is hereby granted, free of charge, to any person obtaining a copy
of this so_ftware and associated documentation files (the "So_ftware"), to deal
in the So_ftware without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the So_ftware, and to permit persons to whom the So_ftware is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the So_ftware.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

"""
mkobhelpkeys

Dialog that displays the MKOB keyboard shortcuts.
"""
import tkinter as tk
from tkinter import ttk
from tkinter import N, S, W, E

from pykob import log


class MKOBHelpKeys(tk.Toplevel):
    # Class attribute that indicates whether this child window
    # is being used (active) or not.
    active = False

    def __init__(self) -> None:
        super().__init__()
        self.title("MKOB Keyboard Shortcuts")
        self.withdraw()  # Hide until built
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self._tree = ttk.Treeview(self, columns=("k", "op"))
        self._tree.column("k", width=100, anchor=tk.CENTER)
        self._tree.column("op", width=260, anchor=tk.W)
        self._tree.heading("k", text="Key")
        self._tree.heading("op", text="Operation")
        self._tree.configure(show="headings", selectmode="none")

        self._tree.insert("", tk.END, values=("ESC", "Toggle key open/closed"))
        self._tree.insert(
            "", tk.END, values=("Pause", "Toggle keyboard code sender on/off")
        )
        self._tree.insert(
            "", tk.END, values=("F1", "Toggle keyboard code sender on/off")
        )
        self._tree.insert("", tk.END, values=("F2", "Toggle connect/disconnect"))
        self._tree.insert("", tk.END, values=("F4", "Decrease speed"))
        self._tree.insert("", tk.END, values=("F5", "Increase speed"))
        self._tree.insert("", tk.END, values=("F11", "Clear code reader window"))
        self._tree.insert(
            "", tk.END, values=("F12", "Clear keyboard code sender window")
        )
        self._tree.insert("", tk.END, values=("Next (Pg-Down)", "Decrease speed"))
        self._tree.insert("", tk.END, values=("Prior (Pg-Up)", "Increase speed"))
        #
        self._tree.insert("", tk.END, values=("----------", "-- Keyboard Code Sender (within text) --"))
        self._tree.insert("", tk.END, values=("~", "Open the key"))
        self._tree.insert("", tk.END, values=("+", "Close the key"))
        #
        self._tree.insert("", tk.END, values=("----------", "-- Keyer (Active when key is open) --"))
        self._tree.insert("", tk.END, values=("Ctrl+LEFT", "Dits"))
        self._tree.insert("", tk.END, values=("Ctrl+RIGHT", "Dah (key down while pressed)"))
        #
        self._tree.insert("", tk.END, values=("----------", "-- Recording Playback Control --"))
        self._tree.insert("", tk.END, values=("Ctrl+S", "Stop recording playback"))
        self._tree.insert(
            "", tk.END, values=("Ctrl+P", "Pause/Resume playback")
        )
        self._tree.insert(
            "", tk.END, values=("Ctrl+H", "Move back 15 seconds")
        )
        self._tree.insert(
            "", tk.END, values=("Ctrl+L", "Move forward 15 seconds")
        )
        self._tree.insert(
            "", tk.END, values=("Ctrl+J", "Move to start of current sender")
        )
        self._tree.insert(
            "", tk.END, values=("Ctrl+K", "Move to end of current sender")
        )

        self._tree.grid(row=0, column=0, sticky=(N, E, S, W))
        self._tree_vs = ttk.Scrollbar(
            self, orient=tk.VERTICAL, command=self._tree.yview
        )
        self._tree_vs.grid(row=0, column=1, sticky=(N, S))
        self._tree["yscrollcommand"] = self._tree_vs.set

        self.update()
        self.state("normal")
#        self._set_win_size()
        self.__class__.active = True  # Indicate that the window is 'active'
        self.after(80, self._set_win_size)
        return

    def _set_win_size(self):
        w = self._tree.winfo_width()
        ws = "{}".format(2 * w)
        geo = "{}x{}+{}+{}".format(ws, "600", "40", "40")
        self.geometry(geo)
        return

    def destroy(self):
        # Restore the attribute on close.
        self._tree = None
        self.__class__.active = False
        return super().destroy()
