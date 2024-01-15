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
kobwindow.py

Create the main window for MKOB and lay out its widgets (controls).
"""

from mkobactions import MKOBActions
from mkobkeyboard import MKOBKeyboard
from mkobmain import MKOBMain
from mkobreader import MKOBReader
from mkobstationlist import MKOBStationList
from pykob import config
from pykob.morse import Reader

import mkobevents
import tkinter as tk
from tkinter import ttk
import tkinter.scrolledtext as tkst

def ignore_event(e):
    return

def ignore_event_no_propagate(e):
    return "break"

class MKOBWindow:
    def __init__(self, root, MKOB_VERSION_TEXT):

        # KOBWindow pointers for other modules
        self.krdr = MKOBReader(self)
        self.ksl = MKOBStationList(self)
        self.ka = MKOBActions(self, self.ksl, self.krdr)

        # validators
        self._digits_only_validator = root.register(self._validate_number_entry)

        # window
        self.root = root
        self.__MKOB_VERSION_TEXT = MKOB_VERSION_TEXT
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)
        self.root.title(MKOB_VERSION_TEXT)
        self.root.bind_all('<Key-Escape>', self.ka.handle_toggle_closer)
        self.root.bind_all('<Key-Pause>', self.ka.handle_toggle_code_sender)
        self.root.bind_all('<Key-F1>', self.ka.handle_toggle_code_sender)
        self.root.bind_all('<Key-F4>', self.ka.handle_decrease_wpm)
        self.root.bind_all('<Key-F5>', self.ka.handle_increase_wpm)
        self.root.bind_all('<Key-F11>', self.ka.handle_clear_reader_window)
        self.root.bind_all('<Key-F12>', self.ka.handle_clear_sender_window)
        self.root.bind_all('<Key-Next>', self.ka.handle_decrease_wpm)
        self.root.bind_all('<Key-Prior>', self.ka.handle_increase_wpm)
        self.root.bind_all('<Control-KeyPress-s>', self.ka.handle_playback_stop)
        self.root.bind_all('<Control-KeyPress-p>', self.ka.handle_playback_pauseresume)
        self.root.bind_all('<Control-KeyPress-h>', self.ka.handle_playback_move_back15)
        self.root.bind_all('<Control-KeyPress-l>', self.ka.handle_playback_move_forward15)
        self.root.bind_all('<Control-KeyPress-j>', self.ka.handle_playback_move_sender_start)
        self.root.bind_all('<Control-KeyPress-k>', self.ka.handle_playback_move_sender_end)
        self.root.bind_class('<Key-F4>', ignore_event)

        # File menu
        self.menu = tk.Menu()
        self.root.config(menu=self.menu)

        # Hide the window from view until its content can be fully initialized
        self.root.withdraw()

        # File menu
        self.fileMenu = tk.Menu(self.menu)
        self.menu.add_cascade(label='File', menu=self.fileMenu)
        self.fileMenu.add_command(label='New', command=self.ka.doFileNew)
        self.fileMenu.add_command(label='Open...', command=self.ka.doFileOpen)
        self.fileMenu.add_separator()
        self.fileMenu.add_command(label='Play...', command=self.ka.doFilePlay)
        self.fileMenu.add_separator()
        self.fileMenu.add_command(label='Preferences...', command=self.ka.doFilePreferences)
        self.fileMenu.add_separator()
        self.fileMenu.add_command(label='Exit', command=self.ka.doFileExit)

        # Tools menu
        self.toolsMenu = tk.Menu(self.menu)
        self.menu.add_cascade(label="Tools", menu=self.toolsMenu)
        self.showPacketsBV = tk.BooleanVar()
        self.toolsMenu.add_checkbutton(
                label="Show Packets", variable=self.showPacketsBV,
                command=self.ka.doShowPacketsChanged)
        self.toolsMenu.add_command(label="Key Timing Graph...", command=self.ka.doKeyGraphShow)

        # Help menu
        self.helpMenu = tk.Menu(self.menu)
        self.menu.add_cascade(label='Help', menu=self.helpMenu)
        self.helpMenu.add_command(label='About', command=self.ka.doHelpAbout)

        # paned windows
        self.pwd1 = ttk.PanedWindow(root, orient=tk.HORIZONTAL)  # left/right side
        self.pwd1.grid(sticky='NESW', padx=6, pady=6)
        self.pwd2 = ttk.PanedWindow(self.pwd1, orient=tk.VERTICAL)  # reader/keyboard
        self.pwd1.add(self.pwd2)

        # frames
        self.frm1 = ttk.Frame(self.pwd2)  # reader
        self.frm1.rowconfigure(0, weight=1)
        self.frm1.columnconfigure(0, weight=2)
        self.pwd2.add(self.frm1)

        self.frm2 = ttk.Frame(self.pwd2)  # keyboard
        self.frm2.rowconfigure(0, weight=1)
        self.frm2.columnconfigure(0, weight=1)
        self.pwd2.add(self.frm2)

        self.frm3 = ttk.Frame(self.pwd1)  # right side
        self.frm3.rowconfigure(0, weight=1)
        self.frm3.columnconfigure(0, weight=1)
        self.pwd1.add(self.frm3)

        self.frm4 = ttk.Frame(self.frm3)  # right side rows
        self.frm4.columnconfigure(0, weight=1)
        self.frm4.grid(row=2)

        # reader
        self.__txtReader = tkst.ScrolledText(
                self.frm1, width=54, height=21, bd=2,
                wrap='word', font=('Arial', -14))
        self.__txtReader.grid(row=0, column=0, sticky='NESW')
        self.__txtReader.rowconfigure(0, weight=1)
        self.__txtReader.columnconfigure(0, weight=2)

        # keyboard
        self.__txtKeyboard = tkst.ScrolledText(
                self.frm2, width=40, height=7, bd=2,
                wrap='word', font=('Arial', -14))
        self.__txtKeyboard.bind('<Key-F4>', self.ka.handle_decrease_wpm)
        self.__txtKeyboard.grid(row=0, column=0, sticky='NESW')
        self.__txtKeyboard.focus_set()

        # station list
        self.__txtStnList = tkst.ScrolledText(
                self.frm3, width=36, height=8, bd=2,
                wrap='none', font=('Arial', -14))
        self.__txtStnList.grid(row=0, column=0, sticky='NESW', padx=3, pady=0)

        # office ID
        self.varOfficeID = tk.StringVar()
        self.entOfficeID = ttk.Entry(self.frm3, font=('Helvetica', -14), textvariable=self.varOfficeID)
        self.entOfficeID.bind('<Any-KeyRelease>', self.ka.doOfficeID)
        self.entOfficeID.grid(row=1, column=0, sticky='EW', padx=3, pady=6)

        # circuit closer
        self.lfm1 = ttk.LabelFrame(self.frm4)
        self.lfm1.grid(row=0, column=0, columnspan=2, padx=3, pady=6)
        self.varCircuitCloser = tk.IntVar()
        self.chkCktClsr = ttk.Checkbutton(
                self.lfm1, text='Circuit Closer', variable=self.varCircuitCloser,
                command=self.ka.doCircuitCloser)
        self.chkCktClsr.grid(row=0, column=0)

        # WPM
        ttk.Label(self.lfm1, text='  WPM ').grid(row=0, column=1)
        self._wpmvar = tk.StringVar()
        self._wpmvar.set(config.text_speed)
        self._wpmvar.trace('w', self.ka.doWPM)
        self.spnWPM = ttk.Spinbox(self.lfm1, from_=5, to=40,
                        width=4, format="%1.0f", justify=tk.RIGHT,
                        validate="key", validatecommand=(self._digits_only_validator,'%P'),
                        textvariable=self._wpmvar)
        self.spnWPM.grid(row=0, column=2)
        self.spnWPM.bind('KeyRelease', self.ka.doWPM)

        # code sender
        self.lfm2 = ttk.LabelFrame(self.frm4, text='Code Sender')
        self.lfm2.grid(row=1, column=0, padx=3, pady=6, sticky='NESW')
        self.varCodeSenderOn = tk.IntVar()
        self.chkCodeSenderOn = ttk.Checkbutton(
                self.lfm2, text='On', variable=self.varCodeSenderOn)
        self.chkCodeSenderOn.grid(row=0, column=0, sticky='W')
        self.varCodeSenderRepeat = tk.IntVar()
        self.chkCodeSenderRepeat = ttk.Checkbutton(
                self.lfm2, text='Repeat', variable=self.varCodeSenderRepeat)
        self.chkCodeSenderRepeat.grid(row=1, column=0, sticky='W')

        # wire no. / connect
        self.lfm3 = ttk.LabelFrame(self.frm4, text='Wire No.')
        self.lfm3.grid(row=1, column=1, padx=3, pady=6, sticky='NS')
        self._wirevar = tk.StringVar()
        self._wirevar.set(config.wire)
        self._wirevar.trace('w', self.ka.doWireNo)
        self.spnWireNo = ttk.Spinbox(
                self.lfm3, from_=1, to=32000, width=7, format="%1.0f", justify=tk.RIGHT,
                validate="key", validatecommand=(self._digits_only_validator,'%P'),
                textvariable=self._wirevar)
        self.spnWireNo.grid()
        self.cvsConnect = tk.Canvas(
                self.lfm3, width=6, height=10, bd=2,
                relief=tk.SUNKEN, bg='white')
        self.cvsConnect.grid(row=0, column=2)
        tk.Canvas(self.lfm3, width=1, height=2).grid(row=1, column=1)
        self.btnConnect = ttk.Button(self.lfm3, text='Connect', command=self.ka.doConnect)
        self.btnConnect.grid(row=2, columnspan=3, ipady=2, sticky='EW')

        ###########################################################################################
        # Register messages and bind handlers
        ## For messages that need the 'data' element of an event
        ## need to use tk commands because tkinter doesn't provide wrapper methods.

        #### Circuit Open/Close
        self.root.bind(mkobevents.EVENT_CIRCUIT_CLOSE, self.ka.handle_circuit_close)
        self.root.bind(mkobevents.EVENT_CIRCUIT_OPEN, self.ka.handle_circuit_open)

        #### Set Code Sender On/Off
        ### self.root.bind(kobevents.EVENT_SET_CODE_SENDER_ON, self.ka.handle_set_code_sender_on)
        cmd = self.root.register(self.ka.handle_set_code_sender_on)
        self.root.tk.call("bind", root, mkobevents.EVENT_SET_CODE_SENDER_ON, cmd + " %d")

        #### Emit code sequence (from KEY)
        ### self.root.bind(kobevents.EVENT_EMIT_KEY_CODE, self.ka.handle_emit_key_code)
        cmd = self.root.register(self.ka.handle_emit_key_code)
        self.root.tk.call("bind", root, mkobevents.EVENT_EMIT_KEY_CODE, cmd + " %d")
        #### Emit code sequence (from KB (keyboard))
        ### self.root.bind(kobevents.EVENT_EMIT_KB_CODE, self.ka.handle_emit_kb_code)
        cmd = self.root.register(self.ka.handle_emit_kb_code)
        self.root.tk.call("bind", root, mkobevents.EVENT_EMIT_KB_CODE, cmd + " %d")
        #### Current Sender and Station List
        self.root.bind(mkobevents.EVENT_STATIONS_CLEAR, self.ka.handle_clear_stations)
        ### self.root.bind(kobevents.EVENT_CURRENT_SENDER, self.ka.handle_sender_update)
        cmd = self.root.register(self.ka.handle_sender_update)
        self.root.tk.call("bind", root, mkobevents.EVENT_CURRENT_SENDER, cmd + " %d")
        ### self.root.bind(kobevents.EVENT_STATION_ACTIVE, ksl.handle_update_station_active)
        cmd = self.root.register(self.ksl.handle_update_station_active)
        self.root.tk.call("bind", root, mkobevents.EVENT_STATION_ACTIVE, cmd + " %d")

        #### Reader
        self.root.bind(mkobevents.EVENT_READER_CLEAR, self.ka.handle_reader_clear)
        ### self.root.bind(kobevents.EVENT_APPEND_TEXT, krdr.handle_append_text)
        cmd = self.root.register(self.ka.handle_reader_append_text)
        self.root.tk.call("bind", root, mkobevents.EVENT_READER_APPEND_TEXT, cmd + " %d")

        # Finally, show the window in its full glory
        self.root.update()                      # Make sure window size reflects changes so far
        self.root.deiconify()

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        x = (sw - w) / 2
        y = (sh - h) * 0.4                      # about 40% from top
        self.root.geometry('%dx%d+%d+%d' % (w, h, x, y))

        # get configuration settings
        self.varOfficeID.set(config.station)
        self.varCircuitCloser.set(True)
        self.varCodeSenderOn.set(True)
        self.varCodeSenderRepeat.set(False)

        # Now that the windows and controls are initialized, create our MKOBMain and MKOBKeyboard.
        self.km = MKOBMain(self.ka, self.ksl, self)
        self.ka.setMKobMain(self.km)
        self.kkb = MKOBKeyboard(self.ka, self, self.km)
        #### Keyboard events
        self.root.bind(mkobevents.EVENT_KB_PROCESS_SEND, self.kkb.handle_keyboard_send)

        # Finish up...
        self.ka.doWPM()
        self.km.start()


    def _validate_number_entry(self, P):
        """
        Assure that 'P' is a number or blank.
        """
        p_is_ok = (P.isdigit() or P == '')
        return p_is_ok

    @property
    def code_sender_enabled(self):
        """
        The state of the code sender checkbox.
        """
        return self.varCodeSenderOn.get()

    @code_sender_enabled.setter
    def code_sender_enabled(self, on: bool):
        """
        Set the state of the code sender checkbox ON|OFF
        """
        self.varCodeSenderOn.set(on)

    @property
    def code_sender_repeat(self):
        """
        The state of the code sender repeat checkbox.
        """
        return self.varCodeSenderRepeat.get()

    @property
    def circuit_closer(self):
        return self.varCircuitCloser.get()

    @circuit_closer.setter
    def circuit_closer(self, v):
        self.varCircuitCloser.set(v)

    @property
    def MKOB_VERSION_TEXT(self):
        return self.__MKOB_VERSION_TEXT

    @property
    def office_id(self):
        return self.varOfficeID.get()

    @office_id.setter
    def office_id(self, v):
        self.varOfficeID.set(v)

    @property
    def show_packets(self):
        """
        Boolean indicating if the 'show packets' option is set.
        """
        return self.showPacketsBV.get()

    @property
    def keyboard_win(self):
        return self.__txtKeyboard

    @property
    def reader_win(self):
        return self.__txtReader

    @property
    def root_win(self):
        return self.root

    @property
    def keyboard_sender(self):
        return self.kkb

    @property
    def station_list_win(self):
        return self.__txtStnList

    @property
    def wire_number(self) -> int:
        """
        Current wire number.
        """
        wire = self._wirevar.get()
        try:
            return int(wire)
        except ValueError:
            pass
        return -1

    @wire_number.setter
    def wire_number(self, wire:int):
        self._wirevar.set(wire)

    @property
    def wpm(self) -> int:
        """
        Current code/text speed in words per minute.
        """
        wpm = self._wpmvar.get()
        try:
            return int(wpm)
        except ValueError:
            pass
        return -1

    @wpm.setter
    def wpm(self, speed:int):
        new_wpm = speed
        if speed < 5:
            new_wpm = 5
        elif speed > 40:
            new_wpm = 40
        self._wpmvar.set(new_wpm)
        self.ka.doWPM()

    def connected(self, connected):
        """
        Fill the connected indicator based on state.
        """
        color = 'red' if  connected else 'white'
        self.cvsConnect.create_rectangle(0, 0, 20, 20, fill=color)

    def event_generate(self, event, when='tail', data=None):
        """
        Generate a main message loop event.
        """
        return self.root.event_generate(event, when=when, data=data)

    def exit(self):
        """
        Exit the program by distroying the main window and quiting
        the message loop.
        """
        self.root.destroy()
        self.root.quit()

    def give_keyboard_focus(self):
        """
        Make the keyboard window the active (focused) window.
        """
        self.__txtKeyboard.focus_set()
