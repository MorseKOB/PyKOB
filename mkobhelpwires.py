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
mkobhelpwires

Dialog that displays the active wires from the current KOBServer and allows
selecting a wire from it to connect to.
"""
from http.server import BaseHTTPRequestHandler
import json
from json import JSONDecodeError
import re  # RegEx
import tkinter as tk
from tkinter import ttk
from tkinter import N, S, W, E
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pykob import config, config2, internet, log
from pykob.config2 import Config


global ROOT, SUBROOT, TEXT, UPDATE_PERIOD
ROOT = "root"
SUBROOT = "subroot"
TEXT = "text"
UPDATE_PERIOD = 5000

class MKOBHelpWires(tk.Toplevel):
    # Class attribute that indicates whether this child window
    # is being used (active) or not.
    active = False

    def __init__(self, mkwin:'MKOBWindow', cfg:Config) -> None:
        super().__init__()
        self._mkwin = mkwin
        self._cfg = cfg

        self.title("KOB Server Active Wires")
        self.withdraw()  # Hide until built
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self._tree = ttk.Treeview(self, columns=("w", "id"))
        self._tree.column("w", width=10, anchor=tk.CENTER)
        self._tree.column("id", width=250, anchor=tk.W)
        self._tree.heading("w", text="Wire")
        self._tree.heading("id", text="ID (Feed/Office/Station)")
        self._tree.configure(show="headings", selectmode="browse")
        # Add a root item to put all other under
        self._tree.insert("", 0, SUBROOT, text="")

        self._tree.grid(row=0, column=0, sticky=(N, E, S, W))
        self._tree_vs = ttk.Scrollbar(
            self, orient=tk.VERTICAL, command=self._tree.yview
        )
        self._tree_vs.grid(row=0, column=1, sticky=(N, S))
        self._tree["yscrollcommand"] = self._tree_vs.set
        #
        # Status bar
        self._status_msg = ttk.Label(self, text=" ")
        self._status_msg.grid(row=1, column=0, columnspan=2, sticky=(W,E), padx=(0, 0))

        #
        # Bind to the Tree's selected event
        self._tree.bind("<<TreeviewSelect>>", self._on_tree_item_select)
        self._tree.bind("<Double-1>", self._on_tree_dbl_click)

        #
        # Finish up
        self.update()
        self.state("normal")
#        self._set_win_size()
        self.__class__.active = True  # Indicate that the window is 'active'
        self.after(80, self._set_win_size)
        self._refresh_after = self.after(800, self._get_active_wires)
        return

    def _gen_iid(self, wire, id) -> str:
        cid = id.replace(' ', '_')
        cid = cid.replace(',', '_')
        iid = "{}-{}".format(wire, cid)
        return iid

    def _get_active_wires(self):
        """
        Access the current KOBServer and pull the active wires. Refresh the
        tree.
        """
        server_url = self._cfg.server_url
        host = internet.HOST_DEFAULT
        port = internet.PORT_DEFAULT
        s = None if not server_url else server_url.strip()
        if s and len(s) > 0:
            # Parse the URL into components
            ex = re.compile("^([^: ]*)((:?)([0-9]*))$")
            m = ex.match(s)
            h = m.group(1)
            cp = m.group(2)
            c = m.group(3)
            p = m.group(4)
            if h and len(h) > 0:
                host = h
            if p and len(p) > 0:
                try:
                    port = int(p)
                except ValueError:
                    port = internet.PORT_DEFAULT
                pass
            pass
        pass
        wires_url = "http://" + host + "/active_wires.json"
        data_str = None
        status = ""
        req = Request(wires_url)
        try:
            response = urlopen(req)
            data_str = response.read().decode("utf-8")
        except TimeoutError as te:
            status = "Request timed out trying to reach {}".format(host)
        except URLError as e:
            if hasattr(e, 'code'):
                code = e.code
                if code == 404:  # Not found
                    status = "Active wires information is not available from {}".format(host)
                else:
                    status = "Could not get active wires information. Received {} - [{}] from {}".format(code, BaseHTTPRequestHandler.responses[code], host)
            elif hasattr(e, 'reason'):
                status = "{} could not be reached. Error: {}".format(host, e.reason)
            else:
                # not sure how we would get here
                status = "Could not retrieve active wire information from {}.".format(host)
            pass
        except Exception as ex:
            status = "Error retrieving active wire information from {}: {}".format(host, ex)
        finally:
            pass
        if status:
            self._status_msg[TEXT] = status
        else:
            self._status_msg[TEXT] = host
        if not data_str is None:
            data = []  # An empty list incase we can't decode the content
            our_wire = self._mkwin.wire_number
            our_id = self._mkwin.office_id
            our_iid = self._gen_iid(our_wire, our_id)
            try:
                data = json.loads(data_str)
            except JSONDecodeError as jde:
                log.debug(jde)
            # Populate the tree
            # Clear the tree
            self._tree.delete(SUBROOT)  # Deleting SUBROOT deletes all of the children
            self._tree.insert("", 0, SUBROOT, text="")  # Put SUBROOT back
            self._tree.item(SUBROOT, open=True)
            # Keep a dictionary of the first entry for each wire
            wires: dict[int:str] = dict()
            for wire_item in data:
                wire = wire_item["wire"]
                id = wire_item["id"]
                iid = self._gen_iid(wire, id)
                if not wire in wires:
                    wires[wire] = iid
                self._tree.insert(SUBROOT, tk.END, iid, values=(str(wire), id))
            # See if we exist in the tree
            our_item = None
            if self._tree.exists(our_iid):
                # Select our item
                self._tree.selection_set(our_iid)
                self._tree.see(our_iid)
            else:
                # We are not in the tree (we aren't connected)
                # If there is a wire in the tree that matches our wire, select it
                wire_iid = wires.get(our_wire, None)
                if not wire_iid is None:
                    self._tree.selection_set(wire_iid)
                else:
                    # Our current wire number isn't in the tree, so make sure nothing is selected
                    self._tree.selection_remove()
        else:
            # Clear the tree
            self._tree.delete(SUBROOT)  # Deleting SUBROOT deletes all of the children
            self._tree.insert("", 0, SUBROOT, text="")  # Put SUBROOT back
        #
        self._refresh_after = self.after(UPDATE_PERIOD, self._get_active_wires)
        return

    def _on_tree_dbl_click(self, event=None):
        """
        Handle double-click on a tree item.

        Since the first click with cause our '_on_tree_item_select' to be
        executed, we don't need to bother with the 'selection' of the item
        here. The 'additional' functionality of double-click is to connect
        if we aren't currently connected (if we are connected, selecting a
        new wire will change the connection to it).
        """
        self._mkwin.mkmain.connect()
        return

    def _on_tree_item_select(self, event=None):
        """
        An item was selected in the tree.
        Get the wire and set our wire to it.
        """
        if not self._refresh_after is None:
            # Cancel our after so we don't refresh while handling this event
            self.after_cancel(self._refresh_after)
            self._refresh_after = None
        iid = self._tree.selection()
        item = self._tree.item(iid)
        values = item['values']
        if len(values) > 0:
            selected_wire = values[0]
            if not selected_wire == self._mkwin.wire_number:
                # Trigger an event to change our wire to the one selected
                self._mkwin.wire_number = selected_wire
        # Reenable our update
        self._refresh_after = self.after(UPDATE_PERIOD, self._get_active_wires)
        return

    def _set_win_size(self):
        w = self._tree.winfo_width()
        ws = "{}".format(2 * w)
        geo = "{}x{}+{}+{}".format(ws, "600", "40", "40")
        self.geometry(geo)
        return

    def destroy(self):
        # Restore the attribute on close.
        if not self._refresh_after is None:
            self.after_cancel(self._refresh_after)
        self._refresh_after = None
        self._tree = None
        self.__class__.active = False
        return super().destroy()
