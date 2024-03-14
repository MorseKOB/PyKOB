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
kobwindow.py

Create the main window for MKOB and lay out its widgets (controls).
"""
from mkobactions import MKOBActions
from mkobhelpkeys import MKOBHelpKeys
from mkobkeyboard import MKOBKeyboard
from mkobmain import MKOBMain
from mkobreader import MKOBReader
from mkobstationlist import MKOBStationList
from pykob import config, config2, log
from pykob import VERSION as PKVERSION
from pykob.config2 import Config
import mkobevents

import sys
from tkinter import N, S, W, E
import tkinter as tk
from tkinter import ttk
import tkinter.scrolledtext as tkst


def print_hierarchy(w, depth=0):
    log.debug(
        "  " * depth
        + w.winfo_class()
        + " i="
        + str(w.winfo_id())
        + " n="
        + str(w.winfo_name())
        + " w="
        + str(w.winfo_width())
        + " h="
        + str(w.winfo_height())
        + " x="
        + str(w.winfo_x())
        + " y="
        + str(w.winfo_y())
    )
    children = w.winfo_children()
    for i in children:
        print_hierarchy(i, depth + 1)


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


class ConnectIndicator():
    """
    Class that shows a rectangle that is filled with white or red.
    """

    def __init__(self, parent, width=8, height=15):
        self.window = tk.Canvas(
            parent,
            width=width,
            height=height,
            background="white",
            borderwidth=2,
            relief="sunken",
        )
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    @connected.setter
    def connected(self, t: bool) -> None:
        self._connected = t
        self.window["background"] = "red" if t else "white"


class SenderControls:
    """
    Frame to encapsulate the Code Sender controls.
    """

    def __init__(
        self,
        parent,
        mkkbd,
        spacing: config.Spacing,
        text_speed: int,
        input_validator,
        text_change_callback,
        farns_change_callback,
        width=100,
        height=40,
        borderwidth=3,
        relief="groove",
    ):
        self.window = ttk.Frame(
            parent, width=width, height=height, borderwidth=borderwidth, relief=relief
        )
        self._mkkbd = mkkbd
        self._spacing = spacing
        self._text_speed = text_speed
        self._input_validator = input_validator
        self._farns_change_callback = farns_change_callback
        self._text_change_callback = text_change_callback
        self._lbl_code_sender = ttk.Label(self.window, text="Keyboard Code Sender:")
        self._varCodeSenderOn = tk.IntVar()
        self._chkCodeSenderOn = ttk.Checkbutton(
            self.window, text="Enable", variable=self._varCodeSenderOn
        )
        self._varCodeSenderRepeat = tk.IntVar()
        self._chkCodeSenderRepeat = ttk.Checkbutton(
            self.window, text="Repeat", variable=self._varCodeSenderRepeat
        )
        self._btnCodeSenderClear = ttk.Button(
            self.window, text="Clear", command=self._mkkbd.handle_clear
        )
        self._varCodeSenderOn.trace_add("write", self._handle_enable_change)
        self._varCodeSenderRepeat.trace_add("write", self._handle_repeat_change)
        #
        # Farnsworth control
        #
        self._lbl_farnsworth_speed = ttk.Label(self.window, text="Farnsworth Speed:")
        self._lbl_farnsworth_spacing = ttk.Label(self.window, text="Add Space Between:")
        self._FARNSWORTH_SPACING_OPTIONS = ["None", "Characters", "Words"]
        self._FARNSWORTH_SPACING_SETTINGS = ["NONE", "CHAR", "WORD"]
        self._FARNSWORTH_SPACING_NONE = config.Spacing.none
        self._FARNSWORTH_SPACING_CHARACTER = config.Spacing.char
        self._FARNSWORTH_SPACING_WORD = config.Spacing.word
        self._DEFAULT_FARNSWORTH_SPACING = config.Spacing.none
        ## Spacing radio-buttons
        self._farnsworthSpacing = tk.IntVar(value=self._DEFAULT_FARNSWORTH_SPACING)
        self._spacingRadioButtons = []
        for spacingRadioButton in range(len(self._FARNSWORTH_SPACING_OPTIONS)):
            self._spacingRadioButtons.append(
                ttk.Radiobutton(
                    self.window,
                    text=self._FARNSWORTH_SPACING_OPTIONS[spacingRadioButton],
                    command=self._handle_spacing_change,
                    variable=self._farnsworthSpacing,
                    value=spacingRadioButton + 1,
                )
            )
            # self._spacingRadioButtons[spacingRadioButton].grid(row=1, column=(1+spacingRadioButton), sticky=(N,S,W))
            # If current config matches this radio button, update the selected value
            if (
                self._spacing.name.upper()
                == self._FARNSWORTH_SPACING_SETTINGS[spacingRadioButton]
            ):
                self._original_configured_spacing = spacingRadioButton + 1
                self._farnsworthSpacing.set(spacingRadioButton + 1)
        ## Text/Word speed
        self._varTWPM = tk.StringVar()
        self._varTWPM.set(self._text_speed)
        self._varTWPM.trace_add("write", self._text_change_callback)
        self._spnTWPM = ttk.Spinbox(
            self.window,
            style="MK.TSpinbox",
            from_=5,
            to=40,
            width=4,
            format="%1.0f",
            justify=tk.RIGHT,
            validate="key",
            validatecommand=(self._input_validator, "%P"),
            textvariable=self._varTWPM,
        )

    def _adjust_text_speed_enable(self, v: config.Spacing):
        if v == config.Spacing.none:
            # Farnsworth spacing has been turned off - disable the 'Text Speed' control:
            if str(self._spnTWPM.cget("state")) == tk.NORMAL:
                self._spnTWPM.config(state=tk.DISABLED)
        else:
            # Farnsworth spacing is on: enable the "Text Speed" control:
            if str(self._spnTWPM.cget("state")) == tk.DISABLED:
                self._spnTWPM.config(state=tk.NORMAL)

    def _handle_enable_change(self, *args):
        self._mkkbd.enabled = self._varCodeSenderOn.get()

    def _handle_repeat_change(self, *args):
        self._mkkbd.repeat = self._varCodeSenderRepeat.get()

    def _handle_spacing_change(self, *args):
        self._adjust_text_speed_enable(self._farnsworthSpacing.get() - 1)
        if self._farns_change_callback:
            self._farns_change_callback()

    @property
    def code_sender_enabled(self) -> bool:
        return self._varCodeSenderOn.get()

    @code_sender_enabled.setter
    def code_sender_enabled(self, b: bool) -> None:
        self._varCodeSenderOn.set(b)

    @property
    def code_sender_repeat(self) -> bool:
        return self._varCodeSenderRepeat.get()

    @code_sender_repeat.setter
    def code_sender_repeat(self, b: bool) -> None:
        self._varCodeSenderRepeat.set(b)

    @property
    def farnsworth_spacing(self) -> config.Spacing:
        v = self._farnsworthSpacing.get() - 1
        sp = config.Spacing(v)
        return sp

    @farnsworth_spacing.setter
    def farnsworth_spacing(self, v: config.Spacing) -> None:
        self._farnsworthSpacing.set(v + 1)
        self._adjust_text_speed_enable(v)

    @property
    def text_speed(self) -> int:
        return int(self._varTWPM.get())

    @text_speed.setter
    def text_speed(self, v: int) -> None:
        self._varTWPM.set(str(v))

    def get_minimum_width(self):
        """
        Get the width of the Farnsworth controls (they are the widest)
        """
        w = 0
        w += self._lbl_farnsworth_speed.winfo_width()
        w += self._lbl_farnsworth_spacing.winfo_width()
        for spacingRadioButton in self._spacingRadioButtons:
            w += spacingRadioButton.winfo_width()
        w += self._spnTWPM.winfo_width()
        w += 12  # Some padding
        return w

    def layout(self):
        """
        Layout the frame.
        """
        self.window.rowconfigure(0, minsize=22, weight=0)
        self.window.rowconfigure(1, minsize=22, weight=0)
        self.window.columnconfigure(0, weight=0)
        self.window.columnconfigure(1, weight=0)
        self.window.columnconfigure(2, weight=0)
        self.window.columnconfigure(3, weight=0)
        self.window.columnconfigure(4, weight=0)
        self.window.columnconfigure(5, weight=1)
        # Farnsworth
        ## Speed
        self._lbl_farnsworth_speed.grid(row=1, column=0, sticky=(E), padx=(0, 2))
        self._spnTWPM.grid(row=1, column=1, sticky=(W))
        ## Spacing
        self._lbl_farnsworth_spacing.grid(row=1, column=2, sticky=(E), padx=(0, 2))
        for spacingRadioButton in range(len(self._FARNSWORTH_SPACING_OPTIONS)):
            self._spacingRadioButtons[spacingRadioButton].grid(
                row=1, column=(3 + spacingRadioButton), sticky=(W), padx=2
            )
        # Code Sender
        self._lbl_code_sender.grid(row=0, column=0, sticky=(E), padx=(0, 2))
        self._chkCodeSenderOn.grid(row=0, column=1, sticky=(W), padx=(0, 2))
        self._chkCodeSenderRepeat.grid(row=0, column=2, sticky=(W), padx=(0, 2))
        self._btnCodeSenderClear.grid(
            row=0, column=3, columnspan=3, sticky=(E), padx=(0, 2)
        )


class MKOBWindow:
    def __init__(self, root, mkob_version_text, cfg: Config) -> None:

        self._app_started: bool = False  # Flag that will be set True when MKOB triggers on_app_started
        self._root = root
        self._app_name_version = mkob_version_text
        # Hide the window from view until its content can be fully initialized
        self._root.withdraw()
        self._root.protocol("WM_DELETE_WINDOW", self._on_app_distroy)  # Handle user clicking [X]
        self.window = ttk.Frame(root)

        # Operational values (from config)
        self._cfg = cfg
        self._code_type = cfg.code_type
        self._cwpm = cfg.min_char_speed
        self._twpm = cfg.text_speed
        self._spacing = cfg.spacing
        self._ignore_morse_setting_change = False

        # Pointers for other modules
        self._krdr = MKOBReader(self)
        self._ksl = MKOBStationList(self)
        self._ka = MKOBActions(self, self._ksl, self._krdr, self._cfg)
        self._kkb = MKOBKeyboard(self._ka, self)
        self._shortcuts_win = None

        # validators
        self._digits_only_validator = root.register(self._validate_number_entry)

        # delay IDs
        self._after_csc = None
        self._after_hmc = None
        self._after_hwc = None
        self._after_tsc = None

        # Needed to avoid F4 inserting clipboard
        self._root.bind_class(
            "<Key-F4>", ignore_event
        )
        # Keyboard bindings
        self._root.bind_all("<Key-Escape>", self._ka.handle_toggle_closer)
        self._root.bind_all("<Key-Pause>", self._ka.handle_toggle_code_sender)
        self._root.bind_all("<Key-F1>", self._ka.handle_toggle_code_sender)
        self._root.bind_all("<Key-F2>", self._ka.doConnect)
        ## Reserve F3 to avoid conflict with MorseKOB2
        self._root.bind_all("<Key-F4>", self._ka.handle_decrease_wpm)
        self._root.bind_all("<Key-F5>", self._ka.handle_increase_wpm)
        self._root.bind_all("<Key-F11>", self._ka.handle_clear_reader_window)
        self._root.bind_all("<Key-F12>", self._ka.handle_clear_sender_window)
        self._root.bind_all("<Key-Next>", self._ka.handle_decrease_wpm)
        self._root.bind_all("<Key-Prior>", self._ka.handle_increase_wpm)
        #
        # Record Player Controls
        self._root.bind_all(
            "<Control-KeyPress-s>", self._ka.handle_playback_stop
        )
        self._root.bind_all(
            "<Control-KeyPress-p>", self._ka.handle_playback_pauseresume
        )
        self._root.bind_all(
            "<Control-KeyPress-h>", self._ka.handle_playback_move_back15
        )
        self._root.bind_all(
            "<Control-KeyPress-l>", self._ka.handle_playback_move_forward15
        )
        self._root.bind_all(
            "<Control-KeyPress-j>", self._ka.handle_playback_move_sender_start
        )
        self._root.bind_all(
            "<Control-KeyPress-k>", self._ka.handle_playback_move_sender_end
        )

        # Menu Bar
        self._root.option_add("*tearOff", False)  # Don't create tear-off style menus
        self._menu = tk.Menu()
        self._root.config(menu=self._menu)

        # File menu
        self._fileMenu = tk.Menu(self._menu)
        self._menu.add_cascade(label="File", menu=self._fileMenu)
        self._fileMenu.add_command(label="New", command=self._ka.doFileNew)
        self._fileMenu.add_command(label="Open...", command=self._ka.doFileOpen)
        self._fileMenu.add_separator()
        self._fileMenu.add_command(label="Record", command=self._ka.doFileRecord)
        self._fileMenu.add_command(label="End Recording", command=self._ka.doFileRecordEnd)
        self._fileMenu.add_command(label="Play...", command=self._ka.doFilePlay)
        self._fileMenu.add_separator()
        self._fileMenu.add_command(
            label="Preferences...", command=self._ka.doFilePreferences
        )
        self._fileMenu.add_command(
            label="Load...", command=self._ka.doFilePrefsLoad
        )
        self._fileMenu.add_command(
            label="Save", command=self._ka.doFilePrefsSave
        )
        self._fileMenu.add_command(
            label="Save As...", command=self._ka.doFilePrefsSaveAs
        )
        self._fileMenu.add_command(
            label="Load Global", command=self._ka.doFilePrefsLoadGlobal
        )
        self._fileMenu.add_command(
            label="Save Global", command=self._ka.doFilePrefsSaveGlobal
        )
        self._fileMenu.add_separator()
        self._fileMenu.add_command(label="Exit", command=self._ka.doFileExit)

        # Tools menu
        self._toolsMenu = tk.Menu(self._menu)
        self._menu.add_cascade(label="Tools", menu=self._toolsMenu)
        self._showPacketsBV = tk.BooleanVar()
        self._toolsMenu.add_checkbutton(
            label="Show Packets",
            variable=self._showPacketsBV,
            command=self._ka.doShowPacketsChanged,
        )
        self._toolsMenu.add_command(
            label="Key Timing Graph...", command=self._ka.doKeyGraphShow
        )

        # Help menu
        self._helpMenu = tk.Menu(self._menu)
        self._menu.add_cascade(label="Help", menu=self._helpMenu)
        self._helpMenu.add_command(label="Keyboard Shortcuts", command=self._ka.doHelpShortcuts)
        self._helpMenu.add_separator()
        self._helpMenu.add_command(label="About", command=self._ka.doHelpAbout)

        # Paned/Splitter windows
        ## left (the Reader|Sender paned window) / right: Stations Connected & Controls)
        self._pw_left_right = tk.PanedWindow(
            self.window, orient=tk.HORIZONTAL, sashrelief="raised"
        )
        # top: Reader / bottom: Sender
        self._pw_topbottom_lf = tk.PanedWindow(
            self._pw_left_right, orient=tk.VERTICAL, sashrelief="raised"
        )

        # Reader (top left)
        style_reader = ttk.Style()
        style_reader.configure("Reader.TFrame")
        fm_reader = ttk.Frame(self._pw_topbottom_lf, style="Reader.TFrame", padding=2)
        self._txtReader = tkst.ScrolledText(
            fm_reader,
            width=40,
            height=20,
            highlightthickness=0,
            font="TkTextFont",
            wrap="word",
            takefocus=False,
        )
        # Code Sender w/controls (bottom left)
        ## Sender  w/controls
        style_sender = ttk.Style()
        style_sender.configure("Sender.TFrame")
        fm_sender_pad = ttk.Frame(self._pw_topbottom_lf, style="Sender.TFrame", padding=4)
        fm_sender = ttk.Frame(fm_sender_pad, borderwidth=2, relief="groove")
        self._txtKeyboard = tkst.ScrolledText(
            fm_sender,
            width=60,
            height=10,
            highlightthickness=0,
            font="TkFixedFont",
            wrap="word",
        )
        self._txtKeyboard.bind("<Key-F4>", self._ka.handle_decrease_wpm)
        self._txtKeyboard.focus_set()
        ### code sender checkboxes, clear, and Farnsworth
        self._fm_sndr_controls = SenderControls(
            fm_sender,
            self._kkb,
            self._spacing,
            self._twpm,
            self._digits_only_validator,
            self._handle_text_speed_change,
            self._handle_morse_change,
        )

        # Stations Connected | Office | Closer & Speed | Wire/Connect
        #  (right)
        self._fm_right = ttk.Frame(self._pw_left_right)
        style_spinbox = (
            ttk.Style()
        )  # Add padding around the spinbox entry fields to move the text away from the arrows
        style_spinbox.configure(
            "MK.TSpinbox", padding=(1, 1, 6, 1)
        )  # padding='W N E S'
        ## Station list
        self._txtStnList = tkst.ScrolledText(
            self._fm_right,
            width=26,
            height=25,
            highlightthickness=0,
            font="TkTextFont",
            wrap="none",
            takefocus=False,
        )
        ## Office ID (station)
        self._lbl_office = ttk.Label(self._fm_right, text="Office:")
        self._varOfficeID = tk.StringVar()
        self._varOfficeID.set(cfg.station)
        entOfficeID = ttk.Entry(self._fm_right, textvariable=self._varOfficeID)
        entOfficeID.bind("<Key-Return>", self._ka.doOfficeID)
        entOfficeID.bind("<FocusOut>", self._ka.doOfficeID)
        # Closer & Speed
        fm_closer_speed = ttk.Frame(self._fm_right, borderwidth=3, relief="groove")
        ## circuit closer
        self._varCircuitCloser = tk.IntVar()
        chkCCircuitCloser = ttk.Checkbutton(
            fm_closer_speed,
            text="Key Closed",
            variable=self._varCircuitCloser,
            command=self._ka.doCircuitCloser,
        )
        ## Character speed
        self._lbl_cwpm = ttk.Label(fm_closer_speed, text="Speed:")
        self._varCWPM = tk.StringVar()
        self._varCWPM.set(cfg.min_char_speed)
        self._varCWPM.trace_add("write", self._handle_char_speed_change)
        spnCWPM = ttk.Spinbox(
            fm_closer_speed,
            style="MK.TSpinbox",
            from_=5,
            to=40,
            width=4,
            format="%1.0f",
            justify=tk.RIGHT,
            validate="key",
            validatecommand=(self._digits_only_validator, "%P"),
            textvariable=self._varCWPM,
        )
        # Wire & Connect
        fm_wire_connect = ttk.Frame(self._fm_right, borderwidth=3, relief="groove")
        ## Wire
        self._lbl_wire = ttk.Label(fm_wire_connect, text="Wire:")
        self._varWireNo = tk.StringVar()
        self._varWireNo.set(str(cfg.wire))
        self._varWireNo.trace_add("write", self._handle_wire_change)
        self._spnWireNo = ttk.Spinbox(
            fm_wire_connect,
            style="MK.TSpinbox",
            from_=1,
            to=32000,
            width=7,
            format="%1.0f",
            justify=tk.RIGHT,
            validate="key",
            validatecommand=(self._digits_only_validator, "%P"),
            textvariable=self._varWireNo,
        )
        ## Connect
        self._connect_indicator = ConnectIndicator(fm_wire_connect)
        self._btnConnect = ttk.Button(
            fm_wire_connect, text=" Connect  ", width=10, command=self._ka.doConnect
        )

        ###########################################################################################
        # Layout...
        #  Make this the whole content of the application.
        #  We will subdivide below to hold the different widgets
        self.window.grid(column=0, row=0, sticky=(N, S, E, W))
        self.window.rowconfigure(0, weight=1)
        self.window.columnconfigure(0, weight=1)
        self.window.columnconfigure(1, weight=0)
        ## Reader (top)
        fm_reader.rowconfigure(0, weight=1, minsize=20, pad=2)
        fm_reader.columnconfigure(0, weight=1, minsize=100)
        ## Sender (bottom)
        fm_sender_pad.rowconfigure(0, weight=1, minsize=1)
        fm_sender_pad.columnconfigure(0, weight=1)
        fm_sender.grid(
            row=0, column=0, sticky=(N, S, W, E), padx=2, pady=2, ipadx=2, ipady=2
        )
        fm_sender.rowconfigure(0, weight=1, minsize=50, pad=2)
        fm_sender.rowconfigure(1, weight=0, minsize=20, pad=2)
        fm_sender.columnconfigure(0, weight=1, minsize=80)
        ## Right:
        self._fm_right.rowconfigure(0, weight=1)
        self._fm_right.rowconfigure(1, weight=0)
        self._fm_right.columnconfigure(0, weight=0)
        self._fm_right.columnconfigure(1, weight=1)
        ## Major Frames
        ### Reader
        self._txtReader.grid(row=0, column=0, sticky=(N, S, W, E), padx=2, pady=2)
        ### Sender
        self._txtKeyboard.grid(row=0, column=0, sticky=(N, S, W, E), padx=2, pady=2)
        #### Sender Controls
        self._fm_sndr_controls.window.grid(row=1, column=0, sticky=(N, S, W, E))
        self._fm_sndr_controls.layout()
        ### Stations
        self._txtStnList.grid(
            row=0, column=0, columnspan=2, sticky=(N, S, W, E), padx=(2, 6), pady=(6, 2)
        )
        ### Office
        self._lbl_office.grid(row=1, column=0, sticky=(N, S, W), padx=2)
        entOfficeID.grid(row=1, column=1, sticky=(W, E), padx=(0, 5))
        ### Closer & Speed
        fm_closer_speed.grid(
            row=2, column=0, columnspan=2, sticky=(N, S, W, E), padx=(0, 6), pady=(0, 6)
        )
        fm_closer_speed.rowconfigure(0, weight=0)
        fm_closer_speed.columnconfigure(0, weight=0)
        fm_closer_speed.columnconfigure(1, weight=1)
        chkCCircuitCloser.grid(row=0, column=0, sticky=(W))
        self._lbl_cwpm.grid(row=0, column=1, sticky=(N, S, E), padx=2)
        spnCWPM.grid(row=0, column=2, sticky=(E))
        ### Wire & Connect
        fm_wire_connect.grid(
            row=3, column=0, columnspan=2, sticky=(N, S, W, E), padx=(0, 6), pady=(0, 8)
        )
        fm_wire_connect.columnconfigure(0, weight=1)
        fm_wire_connect.columnconfigure(1, weight=0)
        fm_wire_connect.columnconfigure(2, weight=0)
        fm_wire_connect.columnconfigure(3, weight=0)
        self._lbl_wire.grid(row=0, column=0, sticky=(E))
        self._spnWireNo.grid(row=0, column=1, sticky=(W))
        self._connect_indicator.window.grid(row=0, column=2, sticky=(E), padx=2, pady=2)
        self._btnConnect.grid(row=0, column=3, sticky=(E), padx=(0, 2), pady=(2, 3))
        ## Splitters (Paned Windows (Panels))
        ### Left: Top | Bottom
        self._pw_topbottom_lf.grid(row=0, column=0, sticky=(N, S, W, E))
        self._pw_topbottom_lf.add(
            fm_reader,
            minsize=100,
            padx=4,
            pady=2,
            sticky=(N, S, W, E),
            stretch="always",
        )
        self._pw_topbottom_lf.add(
            fm_sender_pad,
            minsize=98,
            padx=0,
            pady=0,
            sticky=(N, S, W, E),
            stretch="always",
        )
        ### Left | Right (paned window left | Stations & Controls)
        self._pw_left_right.grid(row=0, column=0, sticky=(N, S, W, E))
        self._pw_left_right.add(
            self._pw_topbottom_lf,
            minsize=200,
            padx=1,
            pady=1,
            sticky=(N, S, W, E),
            stretch="always",
        )
        self._pw_left_right.add(
            self._fm_right, minsize=98, padx=2, pady=1, sticky=(N, S, W, E), stretch="always"
        )

        ###########################################################################################
        # Register virtual events and bind handlers.
        ## For events that need the 'data' element,
        ## direct tcl/tk commands must be used, because tkinter
        ## doesn't provide wrapper methods that include data.
        ##
        ## For these cases, a commented line is included that shows what the
        ## wrapper method call would be if data wasn't needed.

        #### Circuit Open/Close
        self._root.bind(mkobevents.EVENT_CIRCUIT_CLOSE, self._ka.handle_circuit_close)
        self._root.bind(mkobevents.EVENT_CIRCUIT_OPEN, self._ka.handle_circuit_open)

        #### Emit code sequence (from KEY)
        ### self._root.bind(mkobevents.EVENT_EMIT_KEY_CODE, self._ka.handle_emit_key_code)
        cmd = self._root.register(self._ka.handle_emit_key_code)
        self._root.tk.call("bind", root, mkobevents.EVENT_EMIT_KEY_CODE, cmd + " %d")
        #### Emit code sequence (from KB (keyboard))
        ### self._root.bind(mkobevents.EVENT_EMIT_KB_CODE, self._ka.handle_emit_kb_code)
        cmd = self._root.register(self._ka.handle_emit_kb_code)
        self._root.tk.call("bind", root, mkobevents.EVENT_EMIT_KB_CODE, cmd + " %d")
        #### Current Sender and Station List
        self._root.bind(mkobevents.EVENT_STATIONS_CLEAR, self._ka.handle_clear_stations)
        ### self._root.bind(mkobevents.EVENT_CURRENT_SENDER, self._ka.handle_sender_update)
        cmd = self._root.register(self._ka.handle_sender_update)
        self._root.tk.call("bind", root, mkobevents.EVENT_CURRENT_SENDER, cmd + " %d")
        ### self._root.bind(mkobevents.EVENT_STATION_ACTIVE, ksl.handle_update_station_active)
        cmd = self._root.register(self._ksl.handle_update_station_active)
        self._root.tk.call("bind", root, mkobevents.EVENT_STATION_ACTIVE, cmd + " %d")

        #### Reader
        self._root.bind(mkobevents.EVENT_READER_CLEAR, self._ka.handle_reader_clear)
        ### self._root.bind(mkobevents.EVENT_APPEND_TEXT, krdr.handle_append_text)
        cmd = self._root.register(self._ka.handle_reader_append_text)
        self._root.tk.call(
            "bind", root, mkobevents.EVENT_READER_APPEND_TEXT, cmd + " %d"
        )

        # set option values
        self._varCircuitCloser.set(True)
        self._fm_sndr_controls.code_sender_enabled = True
        self._fm_sndr_controls.code_sender_repeat = False

        # Make sure window size reflects all widgets
        self.set_app_title()
        self._root.update()
        self._cfg.register_listener(
            self._config_changed_listener, config2.ChangeType.ANY
        )

        #### Keyboard event for the code send window (this must go after the 'root.update')
        self._root.bind(
            mkobevents.EVENT_KB_PROCESS_SEND, self._kkb.handle_keyboard_send
        )
        return

    def _config_changed_listener(self, ct: int):
        """
        Called by the Config instance when a change is made.
        """
        self.set_app_title()

    def _validate_number_entry(self, P):
        """
        Assure that 'P' is a number or blank.
        """
        p_is_ok = P.isdigit() or P == ""
        return p_is_ok

    def _handle_char_speed_change_delayed(self, *args):
        self._after_csc = None
        cwpmstr = self._varCWPM.get().strip()
        new_cwpm = self._cwpm
        if not cwpmstr == "":
            new_cwpm = int(cwpmstr)
        if not new_cwpm == self._cwpm:
            log.debug("_handle_char_speed_change")
            if new_cwpm < self._twpm:
                self._fm_sndr_controls.text_speed = new_cwpm
            self._handle_morse_change()

    def _handle_char_speed_change(self, *args):
        if self._after_csc:
            self._root.after_cancel(self._after_csc)
        self._after_csc = self._root.after(800, self._handle_char_speed_change_delayed)

    def _handle_morse_change_delayed(self, *args):
        self._after_hmc = None
        fspacing = self._fm_sndr_controls.farnsworth_spacing
        cwpmstr = self._varCWPM.get().strip()
        new_cwpm = self._cwpm
        if not cwpmstr == "":
            new_cwpm = int(cwpmstr)
        twpmstr = self._fm_sndr_controls.text_speed
        new_twpm = self._twpm
        if not twpmstr == "":
            new_twpm = int(twpmstr)
        changed = False
        if not new_cwpm == self._cwpm:
            self._cwpm = new_cwpm
            changed = True
        if not new_twpm == self._twpm:
            self._twpm = new_twpm
            changed = True
        if not fspacing == self._spacing:
            self._spacing = fspacing
            changed = True
        if changed:
            log.debug("_handle_morse_change")
            self._ka.doMorseChange()

    def _handle_morse_change(self, *args):
        if self._after_hmc:
            self._root.after_cancel(self._after_hmc)
        self._after_hmc = self._root.after(1200, self._handle_morse_change_delayed)

    def _handle_wire_change_delayed(self, *args):
        self._after_hwc = None
        log.debug("_handle_wire_change")
        wstr = self._varWireNo.get().strip()
        if not wstr == "":
            new_wire = int(wstr)
            if new_wire < 0:
                new_wire = 0
            elif new_wire > 32000:
                new_wire = 32000
            if not str(new_wire) == wstr:
                self._varWireNo.set(str(new_wire))
            self._ka.doWireNo()

    def _handle_wire_change(self, *args):
        if self._after_hwc:
            self._root.after_cancel(self._after_hwc)
        self._after_hwc = self._root.after(1200, self._handle_wire_change_delayed)

    def _handle_text_speed_change_delayed(self, *args):
        self._after_tsc = None
        twpmstr = self._fm_sndr_controls.text_speed
        new_twpm = self._twpm
        if not twpmstr == "":
            new_twpm = int(twpmstr)
        if not new_twpm == self._twpm:
            log.debug("_handle_text_speed_change")
            if new_twpm > self._cwpm:
                self.cwpm = new_twpm
            self._handle_morse_change()

    def _handle_text_speed_change(self, *args):
        if self._after_tsc:
            self._root.after_cancel(self._after_tsc)
        self._after_tsc = self._root.after(800, self._handle_text_speed_change_delayed)

    def _on_app_distroy(self) -> None:
        """
        Called when TK generates the WM_DELETE_WINDOW event due to user clicking 'X' on main window.
        """
        log.debug("MKOBWindow._on_app_distroy triggered.")
        self.exit()
        return

    def on_app_started(self) -> None:
        """
        Called by MKOB via a tk.after when the main loop has been started.
        """
        self._app_started = True
        # Now that the windows and controls are initialized, create our MKOBMain.
        self._km = MKOBMain(self._root, self._app_name_version, self._ka, self, self._cfg)
        self._ka.start(self._km, self._kkb)
        self._kkb.start(self._km)
        self._km.start()
        # Set to disconnected state
        self.connected(False)
        # Finish up...
        self._ka.doMorseChange()
        return

    @property
    def code_sender_enabled(self):
        """
        The state of the code sender checkbox.
        """
        return self._fm_sndr_controls.code_sender_enabled

    @code_sender_enabled.setter
    def code_sender_enabled(self, enabled: bool):
        """
        Set the state of the code sender checkbox ON|OFF
        """
        self._fm_sndr_controls.code_sender_enabled = enabled

    @property
    def circuit_closer(self):
        return self._varCircuitCloser.get()

    @circuit_closer.setter
    def circuit_closer(self, v):
        self._varCircuitCloser.set(v)

    @property
    def app_name_version(self):
        return self._app_name_version

    @property
    def show_packets(self):
        """
        Boolean indicating if the 'show packets' option is set.
        """
        return self._showPacketsBV.get()

    @property
    def keyboard_win(self):
        return self._txtKeyboard

    @property
    def reader_win(self):
        return self._txtReader

    @property
    def root_win(self):
        return self._root

    @property
    def keyboard_sender(self):
        return self._kkb

    @property
    def station_list_win(self):
        return self._txtStnList

    @property
    def cwpm(self) -> int:
        """
        Current code/char speed in words per minute.
        """
        return self._cwpm

    @cwpm.setter
    def cwpm(self, speed: int):
        self._cwpm = speed
        self._ignore_morse_setting_change = True
        self._varCWPM.set(speed)
        self._ignore_morse_setting_change = False

    @property
    def spacing(self) -> config.Spacing:
        return self._fm_sndr_controls.farnsworth_spacing

    @spacing.setter
    def spacing(self, sp: config.Spacing):
        self._ignore_morse_setting_change = True
        self._spacing = sp
        self._fm_sndr_controls.farnsworth_spacing = sp
        self._ignore_morse_setting_change = False

    @property
    def twpm(self) -> int:
        """
        Current text (Farnsworth) speed in words per minute.
        """
        return self._twpm

    @twpm.setter
    def twpm(self, speed: int):
        self._ignore_morse_setting_change = True
        self._twpm = speed
        self._fm_sndr_controls.text_speed = speed
        self._ignore_morse_setting_change = False

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
    def wire_number(self, v:int):
        w = self._varWireNo.get()
        if not str(v) == w:
            self._varWireNo.set(str(v))

    def connected(self, connected):
        """
        Fill the connected indicator and change the button label based on state.
        """
        self._connect_indicator.connected = connected
        self._btnConnect["text"] = "Disconnect" if connected else "Connect"

    def event_generate(self, event, when="tail", data=None):
        """
        Generate a main message loop event.
        """
        log.debug("=>Event generate: {}".format(event), 4)
        return self._root.event_generate(event, when=when, data=data)

    def exit(self, distroy_app:bool = True):
        """
        Exit the program by distroying the main window and quiting
        the message loop.
        """
        if self._km:
            self._km.exit()
            self._km = None
        if distroy_app:
            self._root.destroy()
        self._root.quit()
        return

    def give_keyboard_focus(self):
        """
        Make the keyboard window the active (focused) window.
        """
        self._txtKeyboard.focus_set()

    def set_app_title(self):
        cfg_modified_attrib = "*" if self._cfg.is_dirty() else ""
        # If our config has a filename, display it as part of our title
        name = self._cfg.get_name()
        if not self._cfg.using_global():
            n = " - " + name
        else:
            n = " - Global"
        self._root.title(self._app_name_version + n + cfg_modified_attrib)

    def set_minimum_sizes(self):
        """
        Set the minimum resizable pane sizes.

        This should be called after the window has had a chance to initialize and display.
        It will then set the paned windows minimum sizes to keep the user from sliding them
        to the point that they hide controls.
        """
        w = self._pw_topbottom_lf.winfo_width()
        self._pw_left_right.paneconfigure(
            self._pw_topbottom_lf, minsize=w
        )
        w = self._fm_right.winfo_width()
        self._pw_left_right.paneconfigure(
            self._fm_right, minsize=w
        )
        self._root.minsize(self._root.winfo_width(), int(self._root.winfo_height() * 0.666))

    def show_help_about(self):
        """
        Display help about the app and environment.
        """
        title = "About MKOB"
        copy_license = "Copyright (c) 2020-24 PyKOB - MorseKOB in Python\nMIT License"
        msg = "{}\n{}\n\npykob: {}\nPython: {}\npyaudio: {}\npyserial: {}\nTcl/Tk: {}/{}".format(
            self.app_name_version,
            copy_license,
            PKVERSION,
            sys.version,
            config.pyaudio_version,
            config.pyserial_version,
            tk.TclVersion,
            tk.TkVersion,
        )
        tk.messagebox.showinfo(title=title, message=msg)

    def show_shortcuts(self):
        """
        Display the Keyboard Shortcuts window.
        """
        if not (self._shortcuts_win and MKOBHelpKeys.active):
            self._shortcuts_win = MKOBHelpKeys()
        self._shortcuts_win.focus()
