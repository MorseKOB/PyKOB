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

import kobmain
import kobevents
import tkinter as tk
import tkinter.scrolledtext as tkst 
import kobactions as ka
import kobconfig as kc
import kobstationlist as ksl
import kobreader as krdr

class KOBWindow:
    def __init__(self, root, MKOB_VERSION_TEXT):       

        # KOBWindow pointers for other modules
        ka.kw = self
        krdr.kw = self
        ksl.kw = self

        # window
        self.root = root
        self.MKOB_VERSION_TEXT = MKOB_VERSION_TEXT
        root.rowconfigure(0, weight=1)
        root.columnconfigure(0, weight=1)
        root.title(MKOB_VERSION_TEXT)
        root.bind_all('<KeyPress-Escape>', ka.handle_escape)
        root.bind_all('<Control-KeyPress-s>', ka.handle_playback_stop)
        root.bind_all('<Control-KeyPress-p>', ka.handle_playback_pauseresume)
        root.bind_all('<Control-KeyPress-h>', ka.handle_playback_move_back15)
        root.bind_all('<Control-KeyPress-l>', ka.handle_playback_move_forward15)
        root.bind_all('<Control-KeyPress-j>', ka.handle_playback_move_sender_start)
        root.bind_all('<Control-KeyPress-k>', ka.handle_playback_move_sender_end)
        
        # File menu
        menu = tk.Menu()
        root.config(menu=menu)
        fileMenu = tk.Menu(menu)
        menu.add_cascade(label='File', menu=fileMenu)
        fileMenu.add_command(label='New', command=ka.doFileNew)
        fileMenu.add_command(label='Open...', command=ka.doFileOpen)
        fileMenu.add_separator()
        fileMenu.add_command(label='Play...', command=ka.doFilePlay)
        fileMenu.add_separator()
        fileMenu.add_command(label='Exit', command=ka.doFileExit)

        # Help menu
        helpMenu = tk.Menu(menu)
        menu.add_cascade(label='Help', menu=helpMenu)
        helpMenu.add_command(label='About', command=ka.doHelpAbout)

        # paned windows
        pwd1 = tk.PanedWindow(
                root, orient=tk.HORIZONTAL, sashwidth=4,
                borderwidth=0)  # left/right side
        pwd1.grid(sticky='NESW', padx=6, pady=6)    
        pwd2 = tk.PanedWindow(pwd1, orient=tk.VERTICAL, sashwidth=4)  # reader/keyboard
        pwd1.add(pwd2, stretch='first')

        # frames
        frm1 = tk.Frame(pwd2, padx=3, pady=0)  # reader
        frm1.rowconfigure(0, weight=1)
        frm1.columnconfigure(0, weight=2)
        pwd2.add(frm1, stretch='always')

        frm2 = tk.Frame(pwd2, padx=3, pady=6)  # keyboard
        frm2.rowconfigure(0, weight=1)
        frm2.columnconfigure(0, weight=1)
        pwd2.add(frm2, stretch='always')

        frm3 = tk.Frame(pwd1)  # right side
        frm3.rowconfigure(0, weight=1)
        frm3.columnconfigure(0, weight=1)
        pwd1.add(frm3)

        frm4 = tk.Frame(frm3)  # right side rows
        frm4.columnconfigure(0, weight=1)
        frm4.grid(row=2)

        # reader
        self.txtReader = tkst.ScrolledText(
                frm1, width=40, height=15, bd=2,
                wrap='word', font=('Arial', -14))
        self.txtReader.grid(row=0, column=0, sticky='NESW')
        self.txtReader.rowconfigure(0, weight=1)
        self.txtReader.columnconfigure(0, weight=2)

        # keyboard
        self.txtKeyboard = tkst.ScrolledText(
                frm2, width=40, height=5, bd=2,
                wrap='word', font=('Arial', -14))
        self.txtKeyboard.grid(row=0, column=0, sticky='NESW')
        self.txtKeyboard.focus_set()
        
        # station list
        self.txtStnList = tkst.ScrolledText(
                frm3, width=10, height=8, bd=2,
                wrap='none', font=('Arial', -14))
        self.txtStnList.grid(row=0, column=0, sticky='NESW', padx=3, pady=0)
        
        # office ID
        self.varOfficeID = tk.StringVar()
        self.entOfficeID = tk.Entry(
                frm3, bd=2, font=('Helvetica', -14),
                textvariable=self.varOfficeID)
        self.entOfficeID.bind('<Any-KeyRelease>', ka.doOfficeID)
        self.entOfficeID.grid(row=1, column=0, sticky='EW', padx=3, pady=6)

        # circuit closer / WPM
        lfm1 = tk.LabelFrame(frm4, padx=5, pady=5)
        lfm1.grid(row=0, column=0, columnspan=2, padx=3, pady=6)
        self.varCircuitCloser = tk.IntVar()
        chkCktClsr = tk.Checkbutton(
                lfm1, text='Circuit Closer', variable=self.varCircuitCloser,
                command=ka.doCircuitCloser)
        chkCktClsr.grid(row=0, column=0)
        tk.Label(lfm1, text='  WPM ').grid(row=0, column=1)
        self.spnWPM = tk.Spinbox(
                lfm1, from_=5, to=40, justify='center',
                width=4, borderwidth=2, command=ka.doWPM)
        self.spnWPM.bind('<Any-KeyRelease>', ka.doWPM)
        self.spnWPM.grid(row=0, column=2)

        # code sender
        lfm2 = tk.LabelFrame(frm4, text='Code Sender', padx=5, pady=5)
        lfm2.grid(row=1, column=0, padx=3, pady=6, sticky='NESW')
        self.varCodeSenderOn = tk.IntVar()
        chkCodeSenderOn = tk.Checkbutton(
                lfm2, text='On', variable=self.varCodeSenderOn)
        chkCodeSenderOn.grid(row=0, column=0, sticky='W')
        self.varCodeSenderRepeat = tk.IntVar()
        chkCodeSenderRepeat = tk.Checkbutton(
                lfm2, text='Repeat', variable=self.varCodeSenderRepeat)
        chkCodeSenderRepeat.grid(row=1, column=0, sticky='W')

        # wire no. / connect
        lfm3 = tk.LabelFrame(frm4, text='Wire No.', padx=5, pady=5)
        lfm3.grid(row=1, column=1, padx=3, pady=6, sticky='NS')
        self.spnWireNo = tk.Spinbox(
                lfm3, from_=1, to=32000, justify='center',
                width=7, borderwidth=2, command=ka.doWireNo)
        self.spnWireNo.bind('<Any-KeyRelease>', ka.doWireNo)
        self.spnWireNo.grid()
        self.cvsConnect = tk.Canvas(
                lfm3, width=6, height=10, bd=2,
                relief=tk.SUNKEN, bg='white')
        self.cvsConnect.grid(row=0, column=2)
        tk.Canvas(lfm3, width=1, height=2).grid(row=1, column=1)
        self.btnConnect = tk.Button(lfm3, text='Connect', command=ka.doConnect)
        self.btnConnect.grid(row=2, columnspan=3, ipady=2, sticky='EW')

        # Register messages and bind handlers
        ## For messages that need the 'data' element of an event
        ## need to use tk commands because tkinter doesn't provide wrapper methods.
        self.root.bind(kobevents.EVENT_STATIONS_CLEAR, ka.handle_clear_stations)
        ### self.root.bind(kobevents.EVENT_CURRENT_SENDER, ka.handle_sender_update)
        cmd = root.register(ka.handle_sender_update)
        root.tk.call("bind", root, kobevents.EVENT_CURRENT_SENDER, cmd + " %d")
        ### self.root.bind(kobevents.EVENT_STATION_ACTIVE, ksl.handle_update_station_active)
        cmd = root.register(ksl.handle_update_station_active)
        root.tk.call("bind", root, kobevents.EVENT_STATION_ACTIVE, cmd + " %d")
        self.root.bind(kobevents.EVENT_READER_CLEAR, ka.handle_reader_clear)
        ### self.root.bind(kobevents.EVENT_APPEND_TEXT, krdr.handle_append_text)
        cmd = root.register(ka.handle_reader_append_text)
        root.tk.call("bind", root, kobevents.EVENT_READER_APPEND_TEXT, cmd + " %d")


        # get configuration settings
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        w, h = kc.WindowSize
        x, y = kc.Position
        if x < 0:
            x = (sw - w) // 2
            y = (sh - h) // 2
        self.root.geometry('{}x{}+{}+{}'.format(w, h, x, y))
        self.varOfficeID.set(kc.OfficeID)
        self.varCircuitCloser.set(kc.CircuitCloser)
        self.spnWPM.delete(0)
        self.spnWPM.insert(tk.END, kc.WPM)
        ka.doWPM()
        self.varCodeSenderOn.set(kc.CodeSenderOn)
        self.varCodeSenderRepeat.set(kc.CodeSenderRepeat)
        self.spnWireNo.delete(0)
        self.spnWireNo.insert(tk.END, kc.WireNo)

        # Now that the windows and controls are initialized, initialize the kobmain module.
        kobmain.init()

    def make_keyboard_focus(self):
        """
        Make the keyboard window the active (focused) window.
        """
        self.txtKeyboard.focus_set()
        