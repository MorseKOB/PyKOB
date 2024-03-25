# ============================================
# Imports
# ============================================
from pykob.util import strtobool
import re  # RegEx
from typing import Any, Callable, Optional

from pykob import config, log
from pykob.internet import HOST_DEFAULT, PORT_DEFAULT
from pykob.config2 import Config

GUI = True                              # Hope for the best...
try:
    import tkinter as tk
    from tkinter import ttk
except ModuleNotFoundError:
    GUI = False

SERIAL = True                           # Hope for the best...
try:
    import serial
    import serial.tools.list_ports
except ModuleNotFoundError:
    SERIAL = False

global preferencesDialog
preferencesDialog = None                # Force creation of a new dialog when first invoked

class PreferencesWindow:
    """
    Preferences window for setting the configuration in a GUI.

    callback: Invoked when the window is dismissed
    quitWhenDismissed: Forces an exit from the running Tkinter mainloop on exit
    cfg: Configuration to use. If 'None', the global configuration will be used.

    """
    def __init__(self, cfg:Config, callback=None, quitWhenDismissed:bool=False, allowApply:bool=False, saveIfRequested:bool=True):
        if not GUI:
            return  # Tkinter isn't available, so we can't run.
        self._callback = callback
        self._quitOnExit = quitWhenDismissed
        self._cfg = cfg

        self._allowApply = allowApply  # If True, provide an 'Apply' button and change 'OK' to 'Save'
        self._saveIfRequested = saveIfRequested
        self._apply_pressed = False
        self._save_pressed = False
        self._cancelled = False

        self.AUDIO_TYPES = ["Sounder", "Tone"]
        self.AUDIO_TYPE_SETTINGS = [config.AudioType.SOUNDER, config.AudioType.TONE]
        self.HW_INTERFACE_TYPES = ["None", "Serial Port", "GPIO (Raspberry Pi)"]
        self.HW_INTERFACE_CONFIG_SETTINGS = ['None', 'SERIAL', 'GPIO']
        self.NONE_HW_INTERFACE = 0      # index of 'None' in list above
        self.SERIAL_HW_INTERFACE = 1    # index of 'SERIAL'
        self.GPIO_HW_INTERFACE = 2      # index of 'GPIO'

        self.EQUIPMENT_TYPES = ['Local loop (key and sounder in series)',
                                'Separate key and sounder',
                                'Separate dot/dash paddle and sounder']
        self.EQUIPMENT_TYPE_SETTINGS = ["LOOP", "KEY_SOUNDER", "KEYER"]
        self.DEFAULT_EQUIPMENT_TYPE = 1

        self.CHARACTER_SPACING_OPTIONS = ["None", "Between characters", "Between words"]
        self.CHARACTER_SPACING_SETTINGS = ['NONE', 'CHAR', 'WORD']
        self.CHARACTER_SPACING_NONE = 0
        self.CHARACTER_SPACING_CHARACTER = 1
        self.CHARACTER_SPACING_WORD = 2
        self.DEFAULT_CHARACTER_SPACING = 2

        self.CODE_TYPES = ["American", "International"]
        self.CODE_TYPE_SETTINGS = ['AMERICAN', 'INTERNATIONAL']
        self.DEFAULT_CODE_TYPE = 0

        self.root = tk.Toplevel()
        self.root.withdraw()  # Hide until built
        self.root.resizable(False, False)
        cfgname = "Global" if cfg.using_global() else cfg.get_name()
        if not cfgname:
            cfgname = ""
        self.root.title("Preferences - {}".format(cfgname))

        # validators
        self._digits_only_validator = self.root.register(self._validate_number_entry)

        #######################################################################
        #
        #   Create three-tabbed interface: Basic/Morse/Advanced
        #
        #######################################################################

        prefs_nb = ttk.Notebook(self.root)
        prefs_nb.pack(fill=tk.BOTH)
        basic_prefs = ttk.Frame(prefs_nb)
        prefs_nb.add(basic_prefs, text="Base")
        code_prefs = ttk.Frame(prefs_nb)
        prefs_nb.add(code_prefs, text="Morse Code")
        advanced_prefs = ttk.Frame(prefs_nb)
        prefs_nb.add(advanced_prefs, text="Advanced")

        #######################################################################
        #
        #   Local Interface section
        #
        #######################################################################

        # Create a container frame to hold all local interface-related widgets
        basiclocalInterface = ttk.LabelFrame(basic_prefs, text=" Local Interface")
        ttk.Label(basiclocalInterface, text="Key and sounder interface:").grid(row=0, column=0, rowspan=6, sticky=tk.NW)
        advancedlocalInterface = ttk.LabelFrame(advanced_prefs, text=" Local Interface")
        ttk.Label(advancedlocalInterface, text="Key and sounder interface:").grid(row=0, column=0, rowspan=6, padx=[12,0], sticky=tk.NW)

        # Create three Radiobuttons using one IntVar for the interface type
        self._interfaceType = tk.IntVar()
        for interfaceRadioButton in range(len(self.HW_INTERFACE_TYPES)):
            ttk.Radiobutton(basiclocalInterface, text=self.HW_INTERFACE_TYPES[interfaceRadioButton],
                            variable=self._interfaceType,
                            state='enabled',
                            value=interfaceRadioButton + 1).grid(
                                row=2 + interfaceRadioButton,
                                column=1,
                                sticky=tk.W)
        # Initialize the interface type to its default value of 'None':
        self._interfaceType.set(self.NONE_HW_INTERFACE + 1)
        # GPIO takes precidence over serial
        if self._cfg.gpio:
            self._interfaceType.set(self.GPIO_HW_INTERFACE + 1)
        elif self._cfg.serial_port:
            self._interfaceType.set(self.SERIAL_HW_INTERFACE + 1)

        # Add a pop-up menu with the list of available serial connections:
        self._serialPort = tk.StringVar()
        if SERIAL:
            systemSerialPorts = serial.tools.list_ports.comports()
            serialPortValues = [systemSerialPorts[p].device for p in range(len(systemSerialPorts))]
        else:
            serialPortValues = []
        serialPortMenu = ttk.Combobox(basiclocalInterface,
                                      width=30,
                                      textvariable=self._serialPort,
                                      state='readonly' if SERIAL else 'disabled',
                                      values=serialPortValues).grid(row=3,
                                                                    column=2, columnspan=4,
                                                                    sticky=tk.W)
        for serial_device in serialPortValues:
            # If port device  matches this radio button, update the selected value
            if self._cfg.serial_port == serial_device:
                self._serialPort.set(serial_device)

        # Label the equipment type:
        ttk.Label(basiclocalInterface, text="Equipment type:").grid(row=7, rowspan=3, column=0, sticky=tk.NE)

        # Create three Radiobuttons using one IntVar for the equipment type
        self._equipmentType = tk.IntVar()

        # Initialize the equipment type to its default value of 'Separate key and sounder':
        self._equipmentType.set(self.DEFAULT_EQUIPMENT_TYPE)

        _row = 8
        for equipmentRadioButton in range(len(self.EQUIPMENT_TYPES)):
            _row += equipmentRadioButton
            ttk.Radiobutton(basiclocalInterface, text=self.EQUIPMENT_TYPES[equipmentRadioButton],
                            variable=self._equipmentType,
                            state='enabled',
                            value=equipmentRadioButton + 1).grid(row=_row, column=1, columnspan=2, sticky=tk.W)
            # If current config matches this radio button, update the selected value
            if self._cfg.interface_type.name.upper() == self.EQUIPMENT_TYPE_SETTINGS[equipmentRadioButton]:
                self._equipmentType.set(equipmentRadioButton + 1)

        # Add a checkbox for the 'Use system sound' option
        self._useSystemSound = tk.IntVar(value=self._cfg.sound)
        _row += 1
        ttk.Checkbutton(basiclocalInterface,
                        text="Use system sound",
                        variable=self._useSystemSound).grid(row=_row, column=0, sticky=tk.W)
        # Drop-down list of Audio Types
        self._audioType = self._cfg.audio_type
        audioTypeLabel = ttk.Label(basiclocalInterface, text="Type").grid(row=_row, column=1, sticky=tk.W)
        self._audioTypeMenu = ttk.Combobox(basiclocalInterface, width=20, state='readonly')
        self._audioTypeMenu.grid(row=_row, column=2, columnspan=2, sticky=tk.W)
        self._audioTypeMenu["values"] = self.AUDIO_TYPES
        self._audioTypeMenu.current(self.AUDIO_TYPE_SETTINGS.index(self._audioType))
        self._audioTypeMenu.bind("<<ComboboxSelected>>", self._audioTypeSelected)

        # Add a checkbox for the 'Use local sounder' option
        self._useLocalSounder = tk.IntVar(value=self._cfg.sounder)
        _row += 1
        ttk.Checkbutton(basiclocalInterface,
                        text="Use local sounder",
                        variable=self._useLocalSounder).grid(row=_row, column=0, columnspan=6, sticky=tk.W)

        # Add a number field for the 'Sounder Power Save' time
        self._sounderPowerSave = tk.IntVar(value=self._cfg.sounder_power_save)
        ttk.Label(advancedlocalInterface, text="Sounder power save (seconds):").grid(row=6, column=0, columnspan=2, padx=(22,0), sticky=tk.W)
        ttk.Entry(advancedlocalInterface, width=12, textvariable=self._sounderPowerSave).grid(row=6, column=2, padx=1, sticky=tk.W)

        # Add a single checkbox for the sound local code option
        self._soundLocalCode = tk.IntVar(value=self._cfg.local)
        ttk.Checkbutton(
            advancedlocalInterface,
            text="Sound local code",
            variable=self._soundLocalCode,
        ).grid(row=7, column=0, padx=[22,0], sticky=tk.W)

        # Add a single checkbox for the key inversion next to the "Separate key/sounder" option
        self._invertKeyInput = tk.IntVar(value=self._cfg.invert_key_input)
        ttk.Checkbutton(advancedlocalInterface, text="Invert key input",
                        variable=self._invertKeyInput).grid(row=8, column=0, padx=[22, 0], sticky=tk.W)

        basiclocalInterface.pack(fill=tk.BOTH)
        advancedlocalInterface.pack(fill=tk.BOTH)

        #######################################################################
        #
        #   Internet connection section
        #
        #######################################################################

        # Create a container frame to hold all internet connection-related widgets
        internetConnection = ttk.LabelFrame(advanced_prefs, text=" Internet Connection")

        s = self._cfg.server_url
        s = s.strip() if s else ""
        server_url = HOST_DEFAULT
        server_port = PORT_DEFAULT
        if len(s) > 0:
            # Parse the URL into components
            ex = re.compile("^([^: ]*)((:?)([0-9]*))$")
            m = ex.match(s)
            h = m.group(1)
            cp = m.group(2)
            c = m.group(3)
            p = m.group(4)
            if h and len(h) > 0:
                server_url = h
            if p and len(p) > 0:
                server_port = p

        # Create a label to pad the left side
        p0 = ttk.Label(internetConnection, text="")
        # Create and label an entry for the server URL:
        self._serverUrl = tk.StringVar(value=server_url)
        lserver = ttk.Label(internetConnection, text="Server:")
        fserver = ttk.Entry(internetConnection, width=40, textvariable=self._serverUrl)
        # Create and label an entry for the server port number:
        self._portNumber = tk.StringVar(value=server_port)
        lport = ttk.Label(internetConnection, text="Port number:")
        fport = ttk.Entry(internetConnection, width=8, textvariable=self._portNumber)

        # Create a label to pad the left side
        p1 = ttk.Label(internetConnection, text="")
        # Add a checkbox for the 'Transmit to remote stations' option
        self._transmitToRemoteStations = tk.IntVar(value=self._cfg.remote)
        btrans = ttk.Checkbutton(
            internetConnection,
            text="Transmit to wire (to remote stations)",
            variable=self._transmitToRemoteStations,
        )

        # Create a label to pad the left side
        p2 = ttk.Label(internetConnection, text="")
        # Create and label an entry for the wire number:
        self._wireNumber = tk.StringVar(value=self._cfg.wire)
        lwire = ttk.Label(internetConnection, text="Wire number:")
        fwire = ttk.Entry(internetConnection, width=5, textvariable=self._wireNumber)

        # Create a label to pad the left side
        p3 = ttk.Label(internetConnection, text="")
        # Create and label an entry for the station ID:
        self._stationID = tk.StringVar(value=self._cfg.station)
        loffice = ttk.Label(internetConnection, text="Office/Station ID:")
        foffice= ttk.Entry(internetConnection, width=52, textvariable=self._stationID)

        # Create a label to pad the left side
        p4 = ttk.Label(internetConnection, text="")
        # Add a checkbox for the 'Automatically connect at startup' option
        self._autoConnectAtStartup = tk.IntVar(value=self._cfg.auto_connect)
        bconnect = ttk.Checkbutton(
            internetConnection,
            text="Automatically connect at startup",
            variable=self._autoConnectAtStartup,
        )

        # internetConnection.grid(row=1, column=0, columnspan=5, pady=6, sticky=tk.W)
        p0.grid(row=0, column=0, padx=[20, 0])
        lserver.grid(row=0, column=1, columnspan=1, padx=0, sticky=tk.W)
        fserver.grid(row=0, column=2, columnspan=7, padx=1, sticky=[tk.W, tk.E])
        lport.grid(row=0, column=10, columnspan=2, padx=1, sticky=tk.W)
        fport.grid(row=0, column=12, columnspan=1, padx=1, sticky=[tk.W])
        #
        p2.grid(row=1, column=0, padx=[20, 0])
        lwire.grid(row=1, column=1, columnspan=2, padx=0, sticky=tk.W)
        fwire.grid(row=1, column=3, columnspan=10, padx=1, sticky=tk.W)
        #
        p3.grid(row=2, column=0, padx=[20, 0])
        loffice.grid(row=2, column=1, columnspan=3, padx=0, sticky=tk.W)
        foffice.grid(row=2, column=4, columnspan=9, padx=1, sticky=[tk.W, tk.E])
        #
        p4.grid(row=3, column=0, padx=[20, 0])
        bconnect.grid(row=3, column=1, columnspan=12, padx=1, sticky=tk.W)
        #
        p1.grid(row=4, column=0, padx=[20, 0])
        btrans.grid(row=4, column=1, columnspan=12, padx=0, sticky=tk.W)
        #
        internetConnection.pack(fill=tk.BOTH)

        #######################################################################
        #
        #   Morse Code section
        #
        #######################################################################

        # Create a container frame to hold all code-related widgets
        codeOptions = ttk.LabelFrame(code_prefs, text=" Code Options")

        ttk.Label(codeOptions, text="Speed (WPM) and Farnsworth spacing:").grid(row=0, column=0, columnspan=2, sticky=tk.W)

        # Customize the TSpinbox style to add some padding between the entry and the arrows.
        style_spinbox = ttk.Style()
        style_spinbox.configure('MK.TSpinbox', padding=(1,1,6,1)) # padding='W N E S'

        ttk.Label(codeOptions, text="Character speed:").grid(row=1, column=1, sticky=tk.E)
        self._dotSpeed = tk.DoubleVar(value=self._cfg.min_char_speed)
        self._dotSpeedControl = tk.Spinbox(codeOptions, 
                # style='MK.TSpinbox', 
                from_=1, 
                to=99, 
                borderwidth=4,
                width=4, 
                format="%2.f", 
                justify=tk.RIGHT,
                repeatdelay=700,
                repeatinterval=300,
                command=self._dotSpeedChange,
                textvariable=self._dotSpeed)
        self._dotSpeedControl.grid(row=1, column=2, padx=(4,10), sticky=tk.W)

        ttk.Label(codeOptions, text="Text (word) speed:").grid(row=1, column=3, sticky=tk.E)
        self._textSpeed = tk.DoubleVar(value=self._cfg.text_speed)
        self._textSpeedControl = tk.Spinbox(codeOptions, 
                # style='MK.TSpinbox', 
                from_=5, 
                to=40,
                borderwidth=3,
                width=4, 
                format="%2.f", 
                justify=tk.RIGHT,
                repeatdelay=700,
                repeatinterval=300,
                command=self._codeSpeedChange,
                textvariable=self._textSpeed)
        self._textSpeedControl.grid(row=1, column=4, padx=(4,10), sticky=tk.W)

        # Create three Radiobuttons using one IntVar for the character spacing options
        ttk.Label(codeOptions, text="Farnsworth spacing:").grid(row=2, column=0, columnspan=4, sticky=tk.W)
        # Initialize the code spacing option to its default value of 'None':
        self._characterSpacing = tk.IntVar(value=self.DEFAULT_CHARACTER_SPACING)
        # Preserve the currently configured Farnsworth spacing option to restore
        # it if the dot speed is toggled to be the same as text speed or not
        self._original_configured_spacing = self._cfg.spacing + 1

        self._spacingRadioButtonWidgets = []
        for spacingRadioButton in range(len(self.CHARACTER_SPACING_OPTIONS)):
            self._spacingRadioButtonWidgets.append(
                ttk.Radiobutton(codeOptions, text=self.CHARACTER_SPACING_OPTIONS[spacingRadioButton],
                                command=self._spacingChange,
                                variable=self._characterSpacing,
                                value=spacingRadioButton + 1))
            self._spacingRadioButtonWidgets[spacingRadioButton].grid(column=1, sticky=tk.W)
            # If current config matches this radio button, update the selected value
            if self._cfg.spacing == spacingRadioButton:
                self._original_configured_spacing = spacingRadioButton + 1
                self._characterSpacing.set(spacingRadioButton + 1)

        # Create a pair of Radiobuttons using one IntVar for the code type options
        ttk.Label(codeOptions, text=" ").grid(row=6, column=0) # a row of padding
        ttk.Label(codeOptions, text="Morse code type:").grid(row=7, column=0, sticky=tk.W)
        self._codeType = tk.IntVar()
        # Initialize the code spacing option to its default value of 'None':
        self._codeType.set(self.DEFAULT_CODE_TYPE)
        for codeTypeRadioButton in range(len(self.CODE_TYPES)):
            ttk.Radiobutton(codeOptions, text=self.CODE_TYPES[codeTypeRadioButton],
                            variable=self._codeType,
                            value=codeTypeRadioButton + 1).grid(row=7, column=1 + codeTypeRadioButton, sticky=tk.W)
            # If current config matches this radio button, update the selected value
            if self._cfg.code_type.name.upper() == self.CODE_TYPE_SETTINGS[codeTypeRadioButton].upper():
                self._codeType.set(codeTypeRadioButton + 1)

        # codeOptions.grid(row=2, column=0, columnspan=4, pady=6, sticky=tk.W)
        codeOptions.pack(fill=tk.BOTH)

        #######################################################################
        #
        #   Logging Options
        #
        #######################################################################
        loggingOptions = ttk.LabelFrame(advanced_prefs, text=" Logging")
        ttk.Label(loggingOptions, text="Level:").grid(row=0, column=0, padx=[24, 0], sticky=tk.W)
        self._varLoggingLevel = tk.StringVar()
        lll = log.get_logging_level()
        cll = self._cfg.logging_level
        ll = max(lll, cll)
        if not lll == cll:
            self._cfg.logging_level = ll
        self._varLoggingLevel.set(ll)
        self._spnLogLevel = tk.Spinbox(
            loggingOptions,
            # style="MK.TSpinbox",
            from_=log.LOGGING_MIN_LEVEL,
            to=99999,
            borderwidth=4,
            width=7,
            format="%1.0f",
            justify=tk.RIGHT,
            repeatdelay=700,
            repeatinterval=300,
            validate="key",
            textvariable=self._varLoggingLevel,
        ).grid(row=0, column=1, padx=1)
        loggingOptions.pack(fill=tk.BOTH)

        #######################################################################
        #
        #   Overall "Apply" / "Save" / "Cancel" buttons
        #
        #######################################################################

        # Add a "Save", optionally an "Apply", and a "Cancel" button
        dialogButtons = ttk.LabelFrame(self.root, text='')
        dialogButtons.columnconfigure(0, weight=88)

        self._cancel_button = ttk.Button(dialogButtons, text="Cancel", command=self._clickCancel)
        # self._cancel_button.configure(state='disabled')
        self._cancel_button.grid(row=0, column=1, padx=6, pady=12, sticky=tk.E)
        dialogButtons.columnconfigure(1, weight=0)

        self._OK_button = ttk.Button(dialogButtons, text="Save", command=self._clickOK)
        if self._allowApply:
            self._apply_button = ttk.Button(dialogButtons, text="Apply", command=self._clickApply)
            # self._apply_button.configure(state='disabled')
            self._apply_button.grid(row=0, column=2, padx=6, pady=12, sticky=tk.E)
            dialogButtons.columnconfigure(2, weight=0)
            self._apply_button["default"] = "active"
            self._OK_button["default"] = "normal"
        else:
            self._OK_button["default"] = "active"

        # self._OK_button.configure(state='disabled')
        self._OK_button.grid(row=0, column=3, padx=6, pady=12, sticky=tk.E)
        dialogButtons.columnconfigure(3, weight=0)
        dialogButtons.pack(fill=tk.X)

        # Assign keyboard keys to Cancel and Apply/Save
        self.root.bind("<Key-Escape>", lambda e: self._clickCancel())
        self.root.bind(
            "<Key-Return>",
            lambda e: (self._clickApply() if self._allowApply else self._clickOK()),
        )

        prefs_nb.pack(expand=1, fill='both')

        # The call to update() is necessary to make the window update its dimensions to the
        # eventual displayed size.
        self.root.update()

        ## The following causes trouble on some Linux (RaspberryPi, Quadra). Just let the OS place it.
        # Center the preferences window on the screen, about 40% of the way from the top:
        # prefs_width = self. root.winfo_reqwidth()
        # prefs_height = self.root.winfo_reqheight()
        # win_width = self.root.winfo_screenwidth()
        # win_height = self.root.winfo_screenheight()
        # left_offset = int((win_width - prefs_width) / 2 - self.root.winfo_y())
        # top_offset = int((win_height - prefs_height) * 0.4- self.root.winfo_x())     # 40% of padding above, 60% below
        # self.root.geometry('+%d+%d' % (left_offset, top_offset))
        self.root.geometry("+36+36")
        self.root.state("normal")

    # #############################################################################################

    def _audioTypeSelected(self, *args):
        #
        # Audio type was selected.
        #
        selidx = self._audioTypeMenu.current()
        self._audioType = self.AUDIO_TYPE_SETTINGS[selidx]
        self._audioTypeMenu.selection_clear()

    def _codeSpeedChange(self):
        #
        # Text speed was changed - if it just went above "dot speed", adjust
        # dot speed to show characters will be sent faster to maintain the
        # newly selected text speed:
        #
        if str(self._dotSpeedControl.cget('state')) == tk.NORMAL:
            if self._textSpeed.get() > self._dotSpeed.get():
                self._dotSpeed.set(int(self._textSpeed.get()))

    def _dotSpeedChange(self):
        #
        # Dot speed was changed - if it just went below the overall "text speed",
        # adjust the text speed to match dot speed, since you can't send proper
        # code faster than the individual characters are sent
        #
        if self._dotSpeed.get() < self._textSpeed.get():
            self._textSpeed.set(int(self._dotSpeed.get()))

    def _spacingChange(self):
        if self._characterSpacing.get() == self.CHARACTER_SPACING_NONE + 1:
            # Farnsworth spacing has been turned off - make sure only the "Dot speed" control is enabled:
            if str(self._textSpeedControl.cget('state')) == tk.NORMAL:
                # Separate "text speed" control is still active - disable it now
                self._textSpeedControl.config(state = tk.DISABLED)
                # Set the speed to the dot speed if it was higher than the selected text speed:
                if self._textSpeed.get() <= self._dotSpeed.get():
                    self._textSpeed.set(int(self._dotSpeed.get()))
        else:
            # Farnsworth mode is on: enable the separate "text speed" control:
            if str(self._textSpeedControl.cget('state')) == tk.DISABLED:
                # Separate "text speed" control has been disabled - enable it now
                # lower the overall text speed to the selected dot speed if the latter is lower
                if self._dotSpeed.get() < self._textSpeed.get():
                    self._textSpeed.set(int(self._dotSpeed.get()))
                self._textSpeedControl.config(state = tk.NORMAL)

    def _validate_number_entry(self, P):
        """
        Assure that 'P' is a number or blank.
        """
        p_is_ok = P.isdigit() or P == ""
        return p_is_ok

    def _apply(self):
        with self._cfg.notification_pauser() as muted_cfg:
            ndl = self._varLoggingLevel.get()
            if ndl:
                lv = log.INFO_LEVEL
                try:
                    lv = int(ndl)
                except Exception:
                    pass
                muted_cfg.logging_level = lv
            log.debug("Interface type: {}  Equipment type: {}".format(self.HW_INTERFACE_TYPES[self._interfaceType.get() - 1],
                self.EQUIPMENT_TYPE_SETTINGS[self._equipmentType.get() - 1]))
            it = self._interfaceType.get() - 1
            if it == self.NONE_HW_INTERFACE:
                muted_cfg.gpio = False
                muted_cfg.serial_port = None
            elif it == self.GPIO_HW_INTERFACE:
                muted_cfg.gpio = True
            else:
                muted_cfg.gpio = False
                sp = self._serialPort.get()
                muted_cfg.serial_port = sp
            # Config 'interface_type' is the 'equipment type' here (Loop, Key&Sounder, keyer)
            muted_cfg.interface_type = config.interface_type_from_str(self.EQUIPMENT_TYPE_SETTINGS[self._equipmentType.get() - 1])
            muted_cfg.local = self._soundLocalCode.get()
            muted_cfg.invert_key_input = self._invertKeyInput.get()
            muted_cfg.sound = self._useSystemSound.get()
            muted_cfg.audio_type = self._audioType
            muted_cfg.sounder = self._useLocalSounder.get()
            muted_cfg.sounder_power_save = int(self._sounderPowerSave.get())
            host = self._serverUrl.get().strip()
            port = self._portNumber.get().strip()
            if len(port) > 0:
                port = ':' + port
            surl = host + port
            if len(surl) < 1:
                surl = None
            muted_cfg.server_url = surl
            muted_cfg.remote = self._transmitToRemoteStations.get()
            muted_cfg.station = self._stationID.get()
            muted_cfg.wire = int(self._wireNumber.get())
            muted_cfg.auto_connect = self._autoConnectAtStartup.get()
            muted_cfg.text_speed = int(self._textSpeed.get())
            muted_cfg.min_char_speed = int(self._dotSpeed.get())
            muted_cfg.spacing = config.spacing_from_str(self.CHARACTER_SPACING_SETTINGS[self._characterSpacing.get() - 1])
            muted_cfg.code_type = config.codeTypeFromString(self.CODE_TYPE_SETTINGS[self._codeType.get() - 1])

    def _clickCancel(self):
        self._cancelled = True
        self.dismiss()

    def _clickApply(self):
        self._apply_pressed = True
        self._apply()
        self.dismiss()

    def _clickOK(self):
        self._save_pressed = True
        self._apply()
        if self._saveIfRequested and self._cfg.is_dirty():
            if self._cfg.get_filepath():
                self._cfg.save_config()
            else:
                self._cfg.load_to_global()
                self._cfg.save_global()
                self._cfg.clear_dirty()
        self.dismiss()

    @property
    def apply_pressed(self) -> bool:
        return self._apply_pressed

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    @property
    def cfg(self) -> Config:
        return self._cfg

    @property
    def save_pressed(self) -> bool:
        return self._save_pressed

    def display(self):
        if GUI:
            self.root.mainloop()

    def dismiss(self):
        if GUI:
            if self._quitOnExit:
                self.root.quit()
            self.root.destroy()
        if self._callback:
            self._callback(self)
