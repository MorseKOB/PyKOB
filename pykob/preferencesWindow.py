# ============================================
# Imports
# ============================================
from distutils.util import strtobool
from typing import Any, Callable, Optional

from pykob import config, config2, log
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
        self._save_pressed = False

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

        HOST_DEFAULT = "mtc-kob.dyndns.org"
        PORT_DEFAULT = 7890

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
        self.root.title("Preferences")

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
        prefs_nb.add(basic_prefs, text="Basic")
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
        ttk.Label(advancedlocalInterface, text="Key and sounder interface:").grid(row=0, column=0, rowspan=6, sticky=tk.NW)

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

        for equipmentRadioButton in range(len(self.EQUIPMENT_TYPES)):
            ttk.Radiobutton(basiclocalInterface, text=self.EQUIPMENT_TYPES[equipmentRadioButton],
                            variable=self._equipmentType,
                            state='enabled',
                            value=equipmentRadioButton + 1).grid(row=8 + equipmentRadioButton,
                                                             column=1, columnspan=2,
                                                             sticky=tk.W)
            # If current config matches this radio button, update the selected value
            if self._cfg.interface_type.name.upper() == self.EQUIPMENT_TYPE_SETTINGS[equipmentRadioButton]:
                self._equipmentType.set(equipmentRadioButton + 1)

        # Add a checkbox for the 'Use system sound' option
        self._useSystemSound = tk.IntVar(value=self._cfg.sound)
        ttk.Checkbutton(basiclocalInterface,
                        text="Use system sound",
                        variable=self._useSystemSound).grid(column=0, columnspan=6, sticky=tk.W)

        # Add a checkbox for the 'Use local sounder' option
        self._useLocalSounder = tk.IntVar(value=self._cfg.sounder)
        ttk.Checkbutton(basiclocalInterface,
                        text="Use local sounder",
                        variable=self._useLocalSounder).grid(column=0, columnspan=6,
                                                            sticky=tk.W)

        # Add a number field for the 'Sounder Power Save' time
        self._sounderPowerSave = tk.IntVar(value=self._cfg.sounder_power_save)
        ttk.Label(advancedlocalInterface, text="Sounder power save (seconds):").grid(row=6, column=0, columnspan=2, padx=(20,4), sticky=tk.W)
        ttk.Entry(advancedlocalInterface, width=12, textvariable=self._sounderPowerSave).grid(row=6, column=2, sticky=tk.W)

        # Add a single checkbox for the key inversion next to the "Separate key/sounder" option
        self._invertKeyInput = tk.IntVar(value=self._cfg.invert_key_input)
        ttk.Checkbutton(advancedlocalInterface, text="Invert key input",
                        variable=self._invertKeyInput).grid(row=7, column=0, padx=20, sticky=tk.W)

        basiclocalInterface.pack(fill=tk.BOTH)
        advancedlocalInterface.pack(fill=tk.BOTH)

        #######################################################################
        #
        #   Internet connection section
        #
        #######################################################################

        # Create a container frame to hold all internet connection-related widgets
        internetConnection = ttk.LabelFrame(advanced_prefs, text=" Internet Connection")
        # ttk.Label(internetConnection, text="Host Name").grid(row=0, column=0, sticky=tk.W)

        server_url = self._cfg.server_url if self._cfg.server_url else HOST_DEFAULT
        server_port = PORT_DEFAULT
        # see if a port was included
        # ZZZ error checking - should have 0 or 1 ':' and if port is included it should be numeric
        hp = server_url.split(':',1)
        if len(hp) == 2:
            server_port = hp[1]
        server_url = hp[0]

        # Create and label an entry for the server URL:
        self._serverUrl = tk.StringVar(value=server_url)
        ttk.Label(internetConnection, text="Server:").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(internetConnection, width=30, textvariable=self._serverUrl).grid(row=0, column=1, sticky=tk.E)

        # Create and label an entry for the server port number:
        self._portNumber = tk.StringVar(value=server_port)
        ttk.Label(internetConnection, text="Port number:").grid(row=0, column=2, sticky=tk.E)
        ttk.Entry(internetConnection, width=12, textvariable=self._portNumber).grid(row=0, column=3, sticky=tk.E)

        # Add a checkbox for the 'Transmit to remote stations' option
        self._transmitToRemoteStations = tk.IntVar(value=self._cfg.remote)
        ttk.Checkbutton(internetConnection,
                        text="Transmit to remote stations",
                        variable=self._transmitToRemoteStations).grid(row=1, column=0, columnspan=4, sticky=tk.W)

        # Create and label an entry for the station ID:
        self._stationID = tk.StringVar(value=self._cfg.station)
        ttk.Label(internetConnection, text="Station ID:").grid(row=2, column=0, sticky=tk.E)
        ttk.Entry(internetConnection, width=55, textvariable=self._stationID).grid(row=2, column=1, columnspan=3, sticky=tk.W)

        # Create and label an entry for the wire number:
        self._wireNumber = tk.StringVar(value=self._cfg.wire)
        ttk.Label(internetConnection, text="Wire number:").grid(row=3, column=0, sticky=tk.E)
        ttk.Entry(internetConnection, width=5, textvariable=self._wireNumber).grid(row=3, column=1, sticky=tk.W)

        # Add a checkbox for the 'Automatically connect at startup' option
        self._autoConnectAtStartup = tk.IntVar(value=self._cfg.auto_connect)
        ttk.Checkbutton(internetConnection,
                        text="Automatically connect at startup",
                        variable=self._autoConnectAtStartup).grid(row=4, column=0, columnspan=2, padx=20, sticky=tk.W)

        # internetConnection.grid(row=1, column=0, columnspan=5, pady=6, sticky=tk.W)
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
        self._dotSpeedControl = \
            ttk.Spinbox(codeOptions, style='MK.TSpinbox', from_=1, to=99, width=4, format="%2.f", justify=tk.RIGHT,
                        command=self._dotSpeedChange,
                        textvariable=self._dotSpeed)
        self._dotSpeedControl.grid(row=1, column=2, padx=(4,10), sticky=tk.W)

        ttk.Label(codeOptions, text="Text (word) speed:").grid(row=1, column=3, sticky=tk.E)
        # print("Setting text speed to", self._cfg.text_speed)
        self._textSpeed = tk.DoubleVar(value=self._cfg.text_speed)
        self._textSpeedControl = \
            ttk.Spinbox(codeOptions, style='MK.TSpinbox', from_=5, to=40,
                        width=4, format="%2.f", justify=tk.RIGHT,
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
        #   Debug Options
        #
        #######################################################################
        advancedDebugOptions = ttk.LabelFrame(advanced_prefs, text=" Debug Options")
        ttk.Label(advancedDebugOptions, text="Level:").grid(row=0, column=0)
        self._varDBLevel = tk.StringVar()
        ldl = log.get_debug_level()
        cdl = self._cfg.debug_level
        dl = max(ldl, cdl)
        if not ldl == cdl:
            self._cfg.debug_level = dl
        self._varDBLevel.set(dl)
        self._spnDBLevel = ttk.Spinbox(
            advancedDebugOptions,
            style="MK.TSpinbox",
            from_=1,
            to=99999,
            width=7,
            format="%1.0f",
            justify=tk.RIGHT,
            validate="key",
            validatecommand=(self._digits_only_validator, "%P"),
            textvariable=self._varDBLevel,
        ).grid(row=0, column=1)
        advancedDebugOptions.pack(fill=tk.BOTH)

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
        self.root.state("normal")

    # #############################################################################################

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

    def _clickCancel(self):
        self.dismiss()

    def _clickApply(self, dismiss=True):
        with self._cfg.notification_pauser() as muted_cfg:
            ndl = self._varDBLevel.get()
            if ndl:
                dlv = int(ndl)
                muted_cfg.debug_level = dlv
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
            # print("Invert key input: ", self._invertKeyInput.get())
            muted_cfg.invert_key_input = self._invertKeyInput.get()
            # print("Use system sound: ", self._useSystemSound.get())
            muted_cfg.sound = self._useSystemSound.get()
            # print("Use local sounder: ", self._useLocalSounder.get())
            muted_cfg.sounder = self._useLocalSounder.get()
            # print("Sounder Power Save: ", self._sounderPowerSave.get())
            muted_cfg.sounder_power_save = int(self._sounderPowerSave.get())
            # print("Server URL: {}".format(self._serverUrl.get() + ":" + self._portNumber.get()))
            muted_cfg.server_url = self._serverUrl.get() + ":" + self._portNumber.get()
            # print("Transmit to remote stations: ", self._transmitToRemoteStations.get())
            muted_cfg.remote = self._transmitToRemoteStations.get()
            # print("Station ID:", self._stationID.get())
            muted_cfg.station = self._stationID.get()
            # print("Wire number:", self._wireNumber.get())
            muted_cfg.wire = int(self._wireNumber.get())
            # print("Auto-connect at startup:", self._autoConnectAtStartup.get())
            muted_cfg.auto_connect = self._autoConnectAtStartup.get()
            # print("Code speed:", self._codeSpeed.get())
            muted_cfg.text_speed = int(self._textSpeed.get())
            # print("Character rate:", self._dotSpeed.get())
            muted_cfg.min_char_speed = int(self._dotSpeed.get())
            # print("Character spacing:", self.CHARACTER_SPACING_OPTIONS[self._characterSpacing.get() - 1])
            muted_cfg.spacing = config.spacing_from_str(self.CHARACTER_SPACING_SETTINGS[self._characterSpacing.get() - 1])
            # print("Code type:", self.CODE_TYPES[self._codeType.get() - 1])
            muted_cfg.code_type = config.codeTypeFromString(self.CODE_TYPE_SETTINGS[self._codeType.get() - 1])
        if dismiss:
            self.dismiss()

    def _clickOK(self):
        self._save_pressed = True
        self._clickApply(dismiss=False)
        if self._saveIfRequested and self._cfg.is_dirty():
            if self._cfg.get_filepath():
                self._cfg.save_config()
            else:
                self._cfg.load_to_global()
                self._cfg.save_global()
                self._cfg.clear_dirty()
        self.dismiss()

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
