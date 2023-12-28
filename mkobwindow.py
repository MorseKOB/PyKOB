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

Create the main KOB window for MKOB and lay out its widgets
(controls).
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
import tkinter.scrolledtext as tkst



class MKOBWindow:
    def __init__(self, root, MKOB_VERSION_TEXT):

        # KOBWindow pointers for other modules
        self.krdr = MKOBReader(self)
        self.ksl = MKOBStationList(self)
        self.ka = MKOBActions(self, self.ksl, self.krdr)

        # window
        self.root = root
        self.__MKOB_VERSION_TEXT = MKOB_VERSION_TEXT
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)
        self.root.title(MKOB_VERSION_TEXT)
        self.root.bind_all('<KeyPress-Escape>', self.ka.handle_escape)
        self.root.bind_all('<Control-KeyPress-s>', self.ka.handle_playback_stop)
        self.root.bind_all('<Control-KeyPress-p>', self.ka.handle_playback_pauseresume)
        self.root.bind_all('<Control-KeyPress-h>', self.ka.handle_playback_move_back15)
        self.root.bind_all('<Control-KeyPress-l>', self.ka.handle_playback_move_forward15)
        self.root.bind_all('<Control-KeyPress-j>', self.ka.handle_playback_move_sender_start)
        self.root.bind_all('<Control-KeyPress-k>', self.ka.handle_playback_move_sender_end)

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
        self.toolsMenu.add_checkbutton(label="Show Packets", variable=self.showPacketsBV,
                                  command=self.ka.doShowPacketsChanged)
        self.toolsMenu.add_command(label="Key Timing Graph...", command=self.ka.doKeyGraphShow)

        # Help menu
        self.helpMenu = tk.Menu(self.menu)
        self.menu.add_cascade(label='Help', menu=self.helpMenu)
        self.helpMenu.add_command(label='About', command=self.ka.doHelpAbout)

        # paned windows
        self.pwd1 = tk.PanedWindow(
                root, orient=tk.HORIZONTAL, sashwidth=4,
                borderwidth=0)  # left/right side
        self.pwd1.grid(sticky='NESW', padx=6, pady=6)
        self.pwd2 = tk.PanedWindow(self.pwd1, orient=tk.VERTICAL, sashwidth=4)  # reader/keyboard
        self.pwd1.add(self.pwd2, stretch='first')

        # frames
        self.frm1 = tk.Frame(self.pwd2, padx=3, pady=0)  # reader
        self.frm1.rowconfigure(0, weight=1)
        self.frm1.columnconfigure(0, weight=2)
        self.pwd2.add(self.frm1, stretch='always')

        self.frm2 = tk.Frame(self.pwd2, padx=3, pady=6)  # keyboard
        self.frm2.rowconfigure(0, weight=1)
        self.frm2.columnconfigure(0, weight=1)
        self.pwd2.add(self.frm2, stretch='always')

        self.frm3 = tk.Frame(self.pwd1)  # right side
        self.frm3.rowconfigure(0, weight=1)
        self.frm3.columnconfigure(0, weight=1)
        self.pwd1.add(self.frm3)

        self.frm4 = tk.Frame(self.frm3)  # right side rows
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
        self.__txtKeyboard.grid(row=0, column=0, sticky='NESW')
        self.__txtKeyboard.focus_set()

        # station list
        self.__txtStnList = tkst.ScrolledText(
                self.frm3, width=36, height=8, bd=2,
                wrap='none', font=('Arial', -14))
        self.__txtStnList.grid(row=0, column=0, sticky='NESW', padx=3, pady=0)

        # office ID
        self.varOfficeID = tk.StringVar()
        self.entOfficeID = tk.Entry(
                self.frm3, bd=2, font=('Helvetica', -14),
                textvariable=self.varOfficeID)
        self.entOfficeID.bind('<Any-KeyRelease>', self.ka.doOfficeID)
        self.entOfficeID.grid(row=1, column=0, sticky='EW', padx=3, pady=6)

        # circuit closer
        self.lfm1 = tk.LabelFrame(self.frm4, padx=5, pady=5)
        self.lfm1.grid(row=0, column=0, columnspan=2, padx=3, pady=6)
        self.varCircuitCloser = tk.IntVar()
        self.chkCktClsr = tk.Checkbutton(
                self.lfm1, text='Circuit Closer', variable=self.varCircuitCloser,
                command=self.ka.doCircuitCloser)
        self.chkCktClsr.grid(row=0, column=0)
        # WPM
        tk.Label(self.lfm1, text='  WPM ').grid(row=0, column=1)
        self.spnWPM = tk.Spinbox(
                self.lfm1, from_=5, to=40, justify='center',
                width=4, borderwidth=2, command=self.ka.doWPM)
        self.spnWPM.bind('<Any-KeyRelease>', self.ka.doWPM)
        self.spnWPM.grid(row=0, column=2)

        # code sender
        self.lfm2 = tk.LabelFrame(self.frm4, text='Code Sender', padx=5, pady=5)
        self.lfm2.grid(row=1, column=0, padx=3, pady=6, sticky='NESW')
        self.varCodeSenderOn = tk.IntVar()
        self.chkCodeSenderOn = tk.Checkbutton(
                self.lfm2, text='On', variable=self.varCodeSenderOn)
        self.chkCodeSenderOn.grid(row=0, column=0, sticky='W')
        self.varCodeSenderRepeat = tk.IntVar()
        self.chkCodeSenderRepeat = tk.Checkbutton(
                self.lfm2, text='Repeat', variable=self.varCodeSenderRepeat)
        self.chkCodeSenderRepeat.grid(row=1, column=0, sticky='W')

        # wire no. / connect
        self.lfm3 = tk.LabelFrame(self.frm4, text='Wire No.', padx=5, pady=5)
        self.lfm3.grid(row=1, column=1, padx=3, pady=6, sticky='NS')
        self.spnWireNo = tk.Spinbox(
                self.lfm3, from_=1, to=32000, justify='center',
                width=7, borderwidth=2, command=self.ka.doWireNo)
        self.spnWireNo.bind('<Any-KeyRelease>', self.ka.doWireNo)
        self.spnWireNo.grid()
        self.cvsConnect = tk.Canvas(
                self.lfm3, width=6, height=10, bd=2,
                relief=tk.SUNKEN, bg='white')
        self.cvsConnect.grid(row=0, column=2)
        tk.Canvas(self.lfm3, width=1, height=2).grid(row=1, column=1)
        self.btnConnect = tk.Button(self.lfm3, text='Connect', command=self.ka.doConnect)
        self.btnConnect.grid(row=2, columnspan=3, ipady=2, sticky='EW')

        ###########################################################################################
        # Register messages and bind handlers
        ## For messages that need the 'data' element of an event
        ## need to use tk commands because tkinter doesn't provide wrapper methods.

        #### Circuit Open/Close
        self.root.bind(mkobevents.EVENT_CIRCUIT_CLOSE, self.ka.handle_circuit_close)
        self.root.bind(mkobevents.EVENT_CIRCUIT_OPEN, self.ka.handle_circuit_open)

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
        self.varCircuitCloser.set(True)         # Previously kc.CircuitCloser (=True)
        self.spnWPM.delete(0)
        self.spnWPM.insert(tk.END, config.text_speed)
        self.varCodeSenderOn.set(True)          # Previously kc.CodeSenderOn (=True)
        self.varCodeSenderRepeat.set(False)     # Previously kc.CodeSenderRepeat (=False)
        self.spnWireNo.delete(0)
        self.spnWireNo.insert(tk.END, config.wire)

        # Now that the windows and controls are initialized, initialize the kobmain module.
        self.km = MKOBMain(self.ka, self.ksl, self)
        self.ka.setMKobMain(self.km)
        self.kkb = MKOBKeyboard(self.ka, self, self.km)
        self.ka.doWPM()
        self.km.start()

    @property
    def code_sender_enabled(self):
        """
        The state of the code sender checkbox.
        """
        return self.varCodeSenderOn.get()

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
    def station_list_win(self):
        return self.__txtStnList

    @property
    def wire_number(self):
        """
        Currently set wire number.
        """
        # Guard against the possibility the text field will not have
        # a valid number (e.g. an empty string, or non-numeric text)
        try:
            new_wire = int(self.spnWireNo.get())
            return self.spnWireNo.get()
        except ValueError as ex:
            return "1"

    @property
    def wpm(self):
        """
        Currently set code/text speed in words per minute.
        """
        # Guard against the possibility the text field will not have
        # a valid number (e.g. an empty string, or non-numeric text)
        try:
            return int(self.spnWPM.get())
        except ValueError as ex:
            return 1

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
