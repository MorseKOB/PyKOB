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
from pykob import config, log
import mkobevents

from tkinter import N, S, W, E
import tkinter as tk
from tkinter import ttk
import tkinter.scrolledtext as tkst

DEBUG_GUI = False
DEBUG_LEVEL = 1

def print_hierarchy(w, depth=0):
    log.debug('  '*depth + w.winfo_class() + ' w=' + str(w.winfo_width()) + ' h=' + str(w.winfo_height()) + ' x=' + str(w.winfo_x()) + ' y=' + str(w.winfo_y()))
    for i in w.winfo_children():
        print_hierarchy(i, depth+1)


def ignore_event(e):
    """
    Event handler that simply does nothing, but continues propagation.
    """
    return

def ignore_event_no_propagate(e):
    """
    Event handler that does nothing and stops further processing.
    """
    return "break"

class ConnectIndicator(tk.Canvas):
    """
    Class that shows a rectangle that is filled with white or red.
    """
    def __init__(self, parent, width=8, height=15):
        tk.Canvas.__init__(self, parent, width=width, height=height, background='white',
                borderwidth=2, relief='sunken')
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    @connected.setter
    def connected(self, t:bool) -> None:
        self._connected = t
        self['background'] = 'red' if t else 'white'


class MKOBWindow(ttk.Frame):
    def __init__(self, root, mkob_version_text, cfg: config):
        ttk.Frame.__init__(self, root)

        self.root = root
        self._MKOB_VERSION_TEXT = mkob_version_text
        # Hide the window from view until its content can be fully initialized
        self.root.withdraw()

        # Pointers for other modules
        self._krdr = MKOBReader(self)
        self._ksl = MKOBStationList(self)
        self._ka = MKOBActions(self, self._ksl, self._krdr)
        self._kkb = MKOBKeyboard(self._ka, self)

        # Operational values (from config)
        self._cfg = cfg
        self._code_type = config.code_type
        self._spacing = config.spacing
        self._cwpm = config.min_char_speed
        self._twpm = config.text_speed
        self._station_name = config.station
        self._wire = config.wire

        # validators
        self._digits_only_validator = root.register(self._validate_number_entry)

        # Keyboard bindings
        self.root.bind_all('<Key-Escape>', self._ka.handle_toggle_closer)
        self.root.bind_all('<Key-Pause>', self._ka.handle_toggle_code_sender)
        self.root.bind_all('<Key-F1>', self._ka.handle_toggle_code_sender)
        self.root.bind_all('<Key-F4>', self._ka.handle_decrease_wpm)
        self.root.bind_all('<Key-F5>', self._ka.handle_increase_wpm)
        self.root.bind_all('<Key-F11>', self._ka.handle_clear_reader_window)
        self.root.bind_all('<Key-F12>', self._ka.handle_clear_sender_window)
        self.root.bind_all('<Key-Next>', self._ka.handle_decrease_wpm)
        self.root.bind_all('<Key-Prior>', self._ka.handle_increase_wpm)
        self.root.bind_all('<Control-KeyPress-s>', self._ka.handle_playback_stop)
        self.root.bind_all('<Control-KeyPress-p>', self._ka.handle_playback_pauseresume)
        self.root.bind_all('<Control-KeyPress-h>', self._ka.handle_playback_move_back15)
        self.root.bind_all('<Control-KeyPress-l>', self._ka.handle_playback_move_forward15)
        self.root.bind_all('<Control-KeyPress-j>', self._ka.handle_playback_move_sender_start)
        self.root.bind_all('<Control-KeyPress-k>', self._ka.handle_playback_move_sender_end)
        self.root.bind_class('<Key-F4>', ignore_event) # Needed to avoid F4 inserting clipboard

        # Menu Bar
        self.menu = tk.Menu()
        self.root.config(menu=self.menu)

        # File menu
        self.fileMenu = tk.Menu(self.menu)
        self.menu.add_cascade(label='File', menu=self.fileMenu)
        self.fileMenu.add_command(label='New', command=self._ka.doFileNew)
        self.fileMenu.add_command(label='Open...', command=self._ka.doFileOpen)
        self.fileMenu.add_separator()
        self.fileMenu.add_command(label='Play...', command=self._ka.doFilePlay)
        self.fileMenu.add_separator()
        self.fileMenu.add_command(label='Preferences...', command=self._ka.doFilePreferences)
        self.fileMenu.add_separator()
        self.fileMenu.add_command(label='Exit', command=self._ka.doFileExit)

        # Tools menu
        self.toolsMenu = tk.Menu(self.menu)
        self.menu.add_cascade(label="Tools", menu=self.toolsMenu)
        self.showPacketsBV = tk.BooleanVar()
        self.toolsMenu.add_checkbutton(
                label="Show Packets", variable=self.showPacketsBV,
                command=self._ka.doShowPacketsChanged)
        self.toolsMenu.add_command(label="Key Timing Graph...", command=self._ka.doKeyGraphShow)

        # Help menu
        self.helpMenu = tk.Menu(self.menu)
        self.menu.add_cascade(label='Help', menu=self.helpMenu)
        self.helpMenu.add_command(label='About', command=self._ka.doHelpAbout)

        # Paned/Splitter windows
        ## left (the Reader|Sender paned window) / right: Stations Connected & Controls)
        pw_left_right = tk.PanedWindow(self, orient=tk.HORIZONTAL, sashrelief='raised')
        # top: Reader / bottom: Sender
        pw_topbottom_lf = tk.PanedWindow(pw_left_right, orient=tk.VERTICAL, sashrelief='raised')

        # Reader (top left)
        style_reader = ttk.Style()
        style_reader.configure('Reader.TFrame')
        fm_reader = ttk.Frame(pw_topbottom_lf, style='Reader.TFrame', padding=2)
        self._txtReader = tkst.ScrolledText(fm_reader, width=40, height=20, highlightthickness=0,
                font='TkTextFont', wrap='word', takefocus=False)
        # Code Sender w/controls (bottom left)
        ## Sender  w/controls
        style_sender = ttk.Style()
        style_sender.configure('Sender.TFrame')
        fm_sender_pad = ttk.Frame(pw_topbottom_lf, style='Sender.TFrame', padding=4)
        fm_sender = ttk.Frame(fm_sender_pad, borderwidth=2, relief='groove')
        self._txtKeyboard = tkst.ScrolledText(fm_sender, width=60, height=10, highlightthickness=0,
                font='TkFixedFont', wrap='word')
        self._txtKeyboard.bind('<Key-F4>', self._ka.handle_decrease_wpm)
        self._txtKeyboard.focus_set()
        ### code sender checkboxes and clear
        fm_sndr_controls = ttk.Frame(fm_sender)
        lbl_sender = ttk.Label(fm_sndr_controls, text='Code Sender:')
        self._varCodeSenderOn = tk.IntVar()
        chkCodeSenderOn = ttk.Checkbutton(fm_sndr_controls, text='Enable', variable=self._varCodeSenderOn)
        self._varCodeSenderRepeat = tk.IntVar()
        chkCodeSenderRepeat = ttk.Checkbutton(fm_sndr_controls, text='Repeat', variable=self._varCodeSenderRepeat)
        btnCodeSenderClear = ttk.Button(fm_sndr_controls, text='Clear', command=self._kkb.handle_clear)

        # Stations Connected | Office | Closer & Speed | Sender controls | Wire/Connect
        #  (right)
        fm_right = ttk.Frame(pw_left_right)
        style_spinbox = ttk.Style() # Add padding around the spinbox entry fields to move the text away from the arrows
        style_spinbox.configure('MK.TSpinbox', padding=(1,1,6,1)) # padding='W N E S'
        ## Station list
        self._txtStnList = tkst.ScrolledText(fm_right, width=26, height=25, highlightthickness=0,
                font='TkTextFont', wrap='none', takefocus=False)
        ## Office ID (station)
        lbl_office = ttk.Label(fm_right, text='Office:')
        self._varOfficeID = tk.StringVar()
        self._varOfficeID.set(cfg.station)
        entOfficeID = ttk.Entry(fm_right, textvariable=self._varOfficeID)
        entOfficeID.bind('<Key-Return>', self._ka.doOfficeID)
        entOfficeID.bind('<FocusOut>', self._ka.doOfficeID)
        # Closer & Speed
        fm_closer_speed = ttk.Frame(fm_right, borderwidth=3, relief='groove')
        ## circuit closer
        self._varCircuitCloser = tk.IntVar()
        chkCCircuitCloser = ttk.Checkbutton(fm_closer_speed, text='Circuit Closed',
                variable=self._varCircuitCloser, command=self._ka.doCircuitCloser)
        ## Character speed
        lbl_cwpm = ttk.Label(fm_closer_speed, text='Speed:')
        self._varCWPM = tk.StringVar()
        self._varCWPM.set(cfg.min_char_speed)
        self._varCWPM.trace_add('write', self._handle_speed_change)
        spnCWPM = ttk.Spinbox(fm_closer_speed, style='MK.TSpinbox', from_=5, to=40, width=4, format="%1.0f", justify=tk.RIGHT,
                validate="key", validatecommand=(self._digits_only_validator,'%P'), textvariable=self._varCWPM)
        # Wire & Connect
        fm_wire_connect = ttk.Frame(fm_right, borderwidth=3, relief='groove')
        ## Wire
        lbl_wire = ttk.Label(fm_wire_connect, text='Wire:')
        self._varWireNo = tk.StringVar()
        self._varWireNo.set(cfg.wire)
        self._varWireNo.trace_add('write', self._handle_wire_change)
        spnWireNo = ttk.Spinbox(fm_wire_connect, style='MK.TSpinbox', from_=1, to=32000, width=7, format="%1.0f", justify=tk.RIGHT,
                validate="key", validatecommand=(self._digits_only_validator,'%P'), textvariable=self._varWireNo)
        ## Connect
        self._btnConnect = ttk.Button(fm_wire_connect, text='Connect', width=10, command=self._ka.doConnect)
        self._connect_indicator = ConnectIndicator(fm_wire_connect)
        ## Farnsworth
        # fm_farnsworth = ttk.Frame(fm_sender)
        # self._CHARACTER_SPACING_OPTIONS = ["None", "Characters", "Words"]
        # self._CHARACTER_SPACING_SETTINGS = ['NONE', 'CHAR', 'WORD']
        # self._CHARACTER_SPACING_NONE = 0
        # self._CHARACTER_SPACING_CHARACTER = 1
        # self._CHARACTER_SPACING_WORD = 2
        # self._DEFAULT_CHARACTER_SPACING = 2
        ### Farnsworth Spacing
        # lbl_farnspacing = ttk.Label(fm_farnsworth, text='Farnsworth\nSpacing (between):')
        ### Spacing radio-buttons
        # self._characterSpacing = tk.IntVar(value=self._DEFAULT_CHARACTER_SPACING)
        # self._spacingRadioButtons = []
        # for spacingRadioButton in range(len(self._CHARACTER_SPACING_OPTIONS)):
        #     self._spacingRadioButtons.append(
        #         ttk.Radiobutton(fm_farnsworth, text=self._CHARACTER_SPACING_OPTIONS[spacingRadioButton],
        #                         command=self._handle_spacing_change,
        #                         variable=self._characterSpacing,
        #                         value=spacingRadioButton + 1))
        #     self._spacingRadioButtons[spacingRadioButton].grid(row=0, column=(1+spacingRadioButton), sticky=(N,S,W))
        #     # If current config matches this radio button, update the selected value
        #     if cfg.spacing.name.upper() == self._CHARACTER_SPACING_SETTINGS[spacingRadioButton]:
        #         self._original_configured_spacing = spacingRadioButton + 1
        #         self._characterSpacing.set(spacingRadioButton + 1)
        ### Text/Word speed
        # lbl_twpm = ttk.Label(fm_farnsworth, text='Apparent Text Speed:')
        # self._varTWPM = tk.StringVar()
        # self._varTWPM.set(cfg.text_speed)
        # self._varTWPM.trace_add('write', self._ka.doWPM)
        # spnTWPM = ttk.Spinbox(fm_farnsworth, from_=5, to=40, width=4, format="%1.0f", justify=tk.RIGHT,
        #         validate="key", validatecommand=(self._digits_only_validator,'%P'), textvariable=self._varTWPM)

        ###########################################################################################
        # Layout...
        #  Make this the whole content of the application.
        #  We will subdivide below to hold the different widgets
        self.grid(column=0, row=0, sticky=(N, S, E, W))
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=0)
        ## Reader (top)
        fm_reader.rowconfigure(0, weight=1, minsize=20, pad=2)
        fm_reader.columnconfigure(0, weight=1, minsize=100)
        ## Sender (bottom)
        fm_sender_pad.rowconfigure(0, weight=1, minsize=1)
        fm_sender_pad.columnconfigure(0, weight=1)
        fm_sender.grid(row=0, column=0, sticky=(N,S,W,E), padx=2, pady=2, ipadx=2, ipady=2)
        fm_sender.rowconfigure(0, weight=1, minsize=50, pad=2)
        fm_sender.rowconfigure(1, weight=0, minsize=20, pad=2)
        fm_sender.columnconfigure(0, weight=1, minsize=80)
        ## Right:
        fm_right.rowconfigure(0, weight=1)
        fm_right.rowconfigure(1, weight=0)
        fm_right.columnconfigure(0, weight=0)
        fm_right.columnconfigure(1, weight=1)
        ## Major Frames
        ### Reader
        self._txtReader.grid(row=0, column=0, sticky=(N,S,W,E), padx=2, pady=2)
        ### Sender
        self._txtKeyboard.grid(row=0, column=0, sticky=(N,S,W,E), padx=2, pady=2)
        #### Sender Controls
        fm_sndr_controls.grid(row=1, column=0, sticky=(N,S,W,E))
        fm_sndr_controls.rowconfigure(0, minsize=22, weight=0)
        fm_sndr_controls.rowconfigure(1, minsize=1, weight=0)
        fm_sndr_controls.columnconfigure(0, weight=0)
        fm_sndr_controls.columnconfigure(1, weight=0)
        fm_sndr_controls.columnconfigure(2, weight=1)
        fm_sndr_controls.columnconfigure(3, weight=0)
        lbl_sender.grid(row=0, column=0, sticky=(W), padx=(0,2))
        chkCodeSenderOn.grid(row=0, column=1, sticky=(W), padx=4)
        chkCodeSenderRepeat.grid(row=0, column=2, sticky=(W), padx=4)
        btnCodeSenderClear.grid(row=0, column=3, sticky=(E), padx=2)
        ### Stations
        self._txtStnList.grid(row=0, column=0, columnspan=2, sticky=(N,S,W,E), padx=(2,6), pady=(6,2))
        ### Office
        lbl_office.grid(row=1, column=0, sticky=(N,S,W), padx=2)
        entOfficeID.grid(row=1, column=1, sticky=(W,E), padx=(0,5))
        ### Closer & Speed
        fm_closer_speed.grid(row=2, column=0, columnspan=2, sticky=(N,S,W,E), padx=(0,6), pady=(0,6))
        fm_closer_speed.rowconfigure(0, weight=0)
        fm_closer_speed.columnconfigure(0, weight=0)
        fm_closer_speed.columnconfigure(1, weight=1)
        chkCCircuitCloser.grid(row=0, column=0, sticky=(W))
        lbl_cwpm.grid(row=0, column=1, sticky=(N,S,E), padx=2)
        spnCWPM.grid(row=0, column=2, sticky=(E))
        ### Wire & Connect
        fm_wire_connect.grid(row=3, column=0, columnspan=2, sticky=(N,S,W,E), padx=(0,6), pady=(0,8))
        fm_wire_connect.columnconfigure(0, weight=1)
        fm_wire_connect.columnconfigure(1, weight=0)
        fm_wire_connect.columnconfigure(2, weight=0)
        fm_wire_connect.columnconfigure(3, weight=0)
        fm_wire_connect_pad = ttk.Frame(fm_wire_connect)
        fm_wire_connect_pad.grid(row=0, rowspan=2, column=0, sticky=(N,S,W,E), padx=1, pady=0)
        lbl_wire.grid(row=0, column=1, sticky=(E))
        spnWireNo.grid(row=0, column=2, sticky=(W))
        self._connect_indicator.grid(row=0, column=3, sticky=(E), padx=2, pady=2)
        self._btnConnect.grid(row=1, column=1, columnspan=3, sticky=(E), padx=(0,2), pady=(2,3))
        ## Splitters (Paned Windows (Panels))
        ### Left: Top | Bottom
        pw_topbottom_lf.grid(row=0, column=0, sticky=(N,S,W,E))
        pw_topbottom_lf.add(fm_reader, minsize=100, padx=4, pady=2, sticky=(N,S,W,E), stretch='always')
        pw_topbottom_lf.add(fm_sender_pad, minsize=98, padx=0, pady=0, sticky=(N,S,W,E), stretch='always')
        ### Left | Right (paned window left | Stations & Controls)
        pw_left_right.grid(row=0, column=0, sticky=(N,S,W,E))
        pw_left_right.add(pw_topbottom_lf, minsize=200, padx=1, pady=1, sticky=(N,S,W,E), stretch='always')
        pw_left_right.add(fm_right, minsize=98, padx=2, pady=1, sticky=(N,S,W,E), stretch='always')

        if DEBUG_GUI:
            style_reader.configure('Reader.TFrame', background='red')
            style_sender.configure('Sender.TFrame', background='blue')

        ###########################################################################################
        # Register virtual events and bind handlers
        ## For events that need the 'data' element,
        ## direct tcl/tk commands must be used, because tkinter
        ## doesn't provide wrapper methods that include data.
        ##
        ## For these cases, a commented line is included that shows what the
        ## wrapper method call would be if data wasn't needed.

        #### Circuit Open/Close
        self.root.bind(mkobevents.EVENT_CIRCUIT_CLOSE, self._ka.handle_circuit_close)
        self.root.bind(mkobevents.EVENT_CIRCUIT_OPEN, self._ka.handle_circuit_open)

        #### Set Code Sender On/Off
        ### self.root.bind(mkobevents.EVENT_SET_CODE_SENDER_ON, self._ka.handle_set_code_sender_on)
        cmd = self.root.register(self._ka.handle_set_code_sender_on)
        self.root.tk.call("bind", root, mkobevents.EVENT_SET_CODE_SENDER_ON, cmd + " %d")

        #### Emit code sequence (from KEY)
        ### self.root.bind(mkobevents.EVENT_EMIT_KEY_CODE, self._ka.handle_emit_key_code)
        cmd = self.root.register(self._ka.handle_emit_key_code)
        self.root.tk.call("bind", root, mkobevents.EVENT_EMIT_KEY_CODE, cmd + " %d")
        #### Emit code sequence (from KB (keyboard))
        ### self.root.bind(mkobevents.EVENT_EMIT_KB_CODE, self._ka.handle_emit_kb_code)
        cmd = self.root.register(self._ka.handle_emit_kb_code)
        self.root.tk.call("bind", root, mkobevents.EVENT_EMIT_KB_CODE, cmd + " %d")
        #### Current Sender and Station List
        self.root.bind(mkobevents.EVENT_STATIONS_CLEAR, self._ka.handle_clear_stations)
        ### self.root.bind(mkobevents.EVENT_CURRENT_SENDER, self._ka.handle_sender_update)
        cmd = self.root.register(self._ka.handle_sender_update)
        self.root.tk.call("bind", root, mkobevents.EVENT_CURRENT_SENDER, cmd + " %d")
        self.root.bind(mkobevents.EVENT_SPEED_CHANGE, self._ka.doWPM)
        ### self.root.bind(mkobevents.EVENT_STATION_ACTIVE, ksl.handle_update_station_active)
        cmd = self.root.register(self._ksl.handle_update_station_active)
        self.root.tk.call("bind", root, mkobevents.EVENT_STATION_ACTIVE, cmd + " %d")

        #### Reader
        self.root.bind(mkobevents.EVENT_READER_CLEAR, self._ka.handle_reader_clear)
        ### self.root.bind(mkobevents.EVENT_APPEND_TEXT, krdr.handle_append_text)
        cmd = self.root.register(self._ka.handle_reader_append_text)
        self.root.tk.call("bind", root, mkobevents.EVENT_READER_APPEND_TEXT, cmd + " %d")

        # set option values
        self._varCircuitCloser.set(True)
        self._varCodeSenderOn.set(True)
        self._varCodeSenderRepeat.set(False)

        # Now that the windows and controls are initialized, create our MKOBMain.
        self._km = MKOBMain(self._ka, self._ksl, self)
        self._ka.start(self._km, self._kkb)
        #### Keyboard events
        self.root.bind(mkobevents.EVENT_KB_PROCESS_SEND, self._kkb.handle_keyboard_send)

        self.root.update() # Make sure window size reflects all widgets
        # Set to disconnected state
        self.connected(False)
        # Finish up...
        self._ka.doWPM()


    def _validate_number_entry(self, P):
        """
        Assure that 'P' is a number or blank.
        """
        p_is_ok = (P.isdigit() or P == '')
        return p_is_ok

    def _handle_spacing_change(self, *args):
        if self._characterSpacing.get() == self._CHARACTER_SPACING_NONE + 1:
            # Farnsworth spacing has been turned off - make sure only the "Code speed" control is enabled:
            if str(self._dotSpeedControl.cget('state')) == tk.NORMAL:
                # Separate "dot speed" control is still active - disable it now
                self._dotSpeedControl.config(state = tk.DISABLED)
                # Set the speed to the dot speed if it was higher than the selected code speed:
                if self._codeSpeed.get() <= self._dotSpeed.get():
                    self._codeSpeed.set(int(self._dotSpeed.get()))
        else:
            # Farnsworth mode is on: enable the separate "dot speed" control:
            if str(self._dotSpeedControl.cget('state')) == tk.DISABLED:
                # Separate "dot speed" control has been disabled - enable it now
                # lower the overall code speed to the selected dot speed if the latter is lower
                if self._dotSpeed.get() < self._codeSpeed.get():
                    self._codeSpeed.set(int(self._dotSpeed.get()))
                self._dotSpeedControl.config(state = tk.NORMAL)

    def _handle_speed_change(self, *args):
        log.debug("_handle_speed_change")
        wpmstr = self._varCWPM.get().strip()
        if not wpmstr == "":
            new_wpm = int(wpmstr)
            if new_wpm < 5:
                new_wpm = 5
            elif new_wpm > 40:
                new_wpm = 40
            self._cwpm = new_wpm
            twpm = self._twpm
            if new_wpm < twpm:
                self._twpm = new_wpm
            self._ka.trigger_speed_change()

    def _handle_wire_change(self, *args):
        log.debug("_handle_wire_change")
        wstr = self._varWireNo.get().strip()
        if not wstr == "":
            new_wire = int(wstr)
            if new_wire < 0:
                new_wire = 0
            elif new_wire > 32000:
                new_wire = 32000
            self._wire = new_wire
            self._ka.doWireNo()

    @property
    def code_sender_enabled(self):
        """
        The state of the code sender checkbox.
        """
        return self._varCodeSenderOn.get()

    @code_sender_enabled.setter
    def code_sender_enabled(self, on: bool):
        """
        Set the state of the code sender checkbox ON|OFF
        """
        self._varCodeSenderOn.set(on)

    @property
    def code_sender_repeat(self):
        """
        The state of the code sender repeat checkbox.
        """
        return self._varCodeSenderRepeat.get()

    @property
    def circuit_closer(self):
        return self._varCircuitCloser.get()

    @circuit_closer.setter
    def circuit_closer(self, v):
        self._varCircuitCloser.set(v)

    @property
    def MKOB_VERSION_TEXT(self):
        return self._MKOB_VERSION_TEXT

    @property
    def show_packets(self):
        """
        Boolean indicating if the 'show packets' option is set.
        """
        return self.showPacketsBV.get()

    @property
    def keyboard_win(self):
        return self._txtKeyboard

    @property
    def reader_win(self):
        return self._txtReader

    @property
    def root_win(self):
        return self.root

    @property
    def keyboard_sender(self):
        return self._kkb

    @property
    def station_list_win(self):
        return self._txtStnList

    @property
    def code_type(self):
        """
        The current code type (AMERICAN | INTERNATIONAL)
        """
        return self._code_type

    @code_type.setter
    def code_type(self, ct:config.CodeType):
        self._code_type = ct

    @property
    def cwpm(self) -> int:
        """
        Current code/char speed in words per minute.
        """
        return self._cwpm

    @cwpm.setter
    def cwpm(self, speed:int):
        new_wpm = speed
        if speed < 5:
            new_wpm = 5
        elif speed > 40:
            new_wpm = 40
        self._cwpm = new_wpm
        self._varCWPM.set(new_wpm)
        self._ka.doWPM()

    @property
    def spacing(self):
        return self._spacing

    @spacing.setter
    def spacing(self, sp:config.Spacing):
        self._spacing = sp

    @property
    def twpm(self) -> int:
        """
        Current text (Farnsworth) speed in words per minute.
        """
        return self._twpm

    @twpm.setter
    def twpm(self, speed:int):
        new_wpm = speed
        if speed < 5:
            new_wpm = 5
        elif speed > 40:
            new_wpm = 40
        self._twpm = new_wpm
        self._varTWPM.set(new_wpm)
        if new_wpm > self._cwpm:
            # Character speed must be at least the text speed
            self.cwpm = new_wpm
        else:
            # doWPM will be called in the above if cwpm changed
            self._ka.doWPM()

    @property
    def office_id(self):
        return self._varOfficeID.get()

    @office_id.setter
    def office_id(self, v):
        self._varOfficeID.set(v)

    @property
    def wire_number(self) -> int:
        """
        Current wire number.
        """
        wire = self._varWireNo.get()
        try:
            return int(wire)
        except ValueError:
            pass
        return -1

    @wire_number.setter
    def wire_number(self, wire:int):
        self._wire = wire
        self._varWireNo.set(wire)

    def start(self):
        self._kkb.start(self._km)
        self._km.start()

    def connected(self, connected):
        """
        Fill the connected indicator and change the button label based on state.
        """
        self._connect_indicator.connected = connected
        self._btnConnect['text'] = 'Disconnect' if connected else 'Connect'

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
        self._txtKeyboard.focus_set()
