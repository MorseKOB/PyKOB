#============================================
# Imports
#============================================

from pykob import config

GUI = True                              # Hope for the best...
try:
    import tkinter as tk
    from tkinter import ttk
    from tkinter import scrolledtext
    from tkinter import Menu
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

#
# 'callback' is invoked when the window is dismissed
# 'quitWhenDismissed' forces an exit from the running Tkinter mainloop on exit
#
class PreferencesWindow:
    def __init__(self, callback=None, quitWhenDismissed=False):
        self._callback = callback
        self._quitOnExit = quitWhenDismissed
        config.read_config()
        if not GUI:
            return
        
      # print("Configured serial port  =", config.serial_port)
      # print("Configured code speed  =", config.text_speed)
       
        interface = 'SERIAL'      # Placeholder until HW interface type is configured
        
        self.HW_INTERFACE_TYPES = ["None", "Serial Port", "GPIO (Raspberry Pi)"]
        self.NONE_HW_INTERFACE = 0        # index of 'None' in list above
        self.HW_INTERFACE_CONFIG_SETTINGS = ['None', 'SERIAL', 'GPIO']
        
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
        self.root.resizable(False, False)

        self.root.title("Preferences")

        
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

        # Initialize the interface type to its default value of 'None':
        self._interfaceType.set(self.NONE_HW_INTERFACE)
        
        for interfaceRadioButton in range(len(self.HW_INTERFACE_TYPES)):
            ttk.Radiobutton(basiclocalInterface, text=self.HW_INTERFACE_TYPES[interfaceRadioButton],
                            variable=self._interfaceType,
                            state='enabled',
                            value=interfaceRadioButton + 1).grid(row=2 + interfaceRadioButton,
                                                             column=1, columnspan=1,
                                                             sticky=tk.W)
            # GPIO takes precidence
            if config.gpio:
              if "GPIO" == self.HW_INTERFACE_CONFIG_SETTINGS[interfaceRadioButton]:
                self._interfaceType.set(interfaceRadioButton + 1)
            elif config.serial_port and ("SERIAL" == self.HW_INTERFACE_CONFIG_SETTINGS[interfaceRadioButton]):
              self._interfaceType.set(interfaceRadioButton + 1)

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
            if config.serial_port == serial_device:
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
                            state='enabled' if SERIAL or GPIO else 'disabled',
                            value=equipmentRadioButton + 1).grid(row=8 + equipmentRadioButton,
                                                             column=1, columnspan=2,
                                                             sticky=tk.W)
            # If current config matches this radio button, update the selected value
            if config.interface_type.name.upper() == self.EQUIPMENT_TYPE_SETTINGS[equipmentRadioButton]:
                self._equipmentType.set(equipmentRadioButton + 1)

        # Add a checkbox for the 'Use system sound' option
        self._useSystemSound = tk.IntVar(value=config.sound)
        ttk.Checkbutton(basiclocalInterface,
                        text="Use system sound",
                        variable=self._useSystemSound).grid(column=0, columnspan=6,
                                                           sticky=tk.W)

        # Add a checkbox for the 'Use local sounder' option
        self._useLocalSounder = tk.IntVar(value=config.sounder)
        ttk.Checkbutton(basiclocalInterface,
                        text="Use local sounder",
                        variable=self._useLocalSounder).grid(column=0, columnspan=6,
                                                            sticky=tk.W)

        # Add a number field for the 'Sounder Power Save' time
        self._sounderPowerSave = tk.IntVar(value=config.sounder_power_save)
        ttk.Label(advancedlocalInterface, text="Sounder power save (seconds):").grid(row=6, column=0, columnspan=2, padx=20, sticky=tk.W)
        ttk.Entry(advancedlocalInterface, width=12, textvariable=self._sounderPowerSave).grid(row=6, column=2, sticky=tk.W)

        # Add a single checkbox for the key inversion next to the "Separate key/sounder" option
        self._invertKeyInput = tk.IntVar(value=config.invert_key_input)
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

        server_url = config.server_url if config.server_url else HOST_DEFAULT
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
        self._transmitToRemoteStations = tk.IntVar(value=config.remote)
        ttk.Checkbutton(internetConnection,
                        text="Transmit to remote stations",
                        variable=self._transmitToRemoteStations).grid(row=1, column=0, columnspan=4, sticky=tk.W)

        # Create and label an entry for the station ID:
        self._stationID = tk.StringVar(value=config.station)
        ttk.Label(internetConnection, text="Station ID:").grid(row=2, column=0, sticky=tk.E)
        ttk.Entry(internetConnection, width=55, textvariable=self._stationID).grid(row=2, column=1, columnspan=3, sticky=tk.W)

        # Create and label an entry for the wire number:
        self._wireNumber = tk.StringVar(value=config.wire)
        ttk.Label(internetConnection, text="Wire number:").grid(row=3, column=0, sticky=tk.E)
        ttk.Entry(internetConnection, width=5, textvariable=self._wireNumber).grid(row=3, column=1, sticky=tk.W)

        # Add a checkbox for the 'Automatically connect at startup' option
        self._autoConnectAtStartup = tk.IntVar(value=config.auto_connect)
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
        
        ttk.Label(codeOptions, text="Code speed and Farnsworth spacing:").grid(row=0, column=0, columnspan=2, sticky=tk.W)
        
        ttk.Label(codeOptions, text="Code speed:").grid(row=1, column=1, padx=30, sticky=tk.E)
      # print("Setting code speed to", config.text_speed)
        self._codeSpeed = tk.DoubleVar(value=config.text_speed)
        self._codeSpeedControl = \
            ttk.Spinbox(codeOptions, from_=1, to=99,
                        width=4, format="%2.f", justify=tk.RIGHT,
                        command=self._codeSpeedChange,
                        textvariable=self._codeSpeed)
        self._codeSpeedControl.grid(row=1, column=2, padx=10, sticky=tk.W)
        
        ttk.Label(codeOptions, text="Dot speed:").grid(row=1, column=3, sticky=tk.E)
        self._dotSpeed = tk.DoubleVar(value=config.min_char_speed)
        self._dotSpeedControl = \
            ttk.Spinbox(codeOptions, from_=1, to=99, width=4, format="%2.f", justify=tk.RIGHT,
                        command=self._dotSpeedChange,
                        textvariable=self._dotSpeed)
        self._dotSpeedControl.grid(row=1, column=4, padx=10, sticky=tk.W)
        
        # Create three Radiobuttons using one IntVar for the character spacing options
        ttk.Label(codeOptions, text="Character spacing:").grid(row=2, column=0, columnspan=4, sticky=tk.W)
        # Initialize the code spacing option to its default value of 'None':
        self._characterSpacing = tk.IntVar(value=self.DEFAULT_CHARACTER_SPACING)
        # Preserve the currently configured Farnsworth spacing option to restore
        # it if the dot speed is toggled to be the same as code speed or not
        self._original_configured_spacing = self.CHARACTER_SPACING_CHARACTER + 1

        self._spacingRadioButtonWidgets = []
        for spacingRadioButton in range(len(self.CHARACTER_SPACING_OPTIONS)):
            self._spacingRadioButtonWidgets.append(
                ttk.Radiobutton(codeOptions, text=self.CHARACTER_SPACING_OPTIONS[spacingRadioButton],
                                command=self._spacingChange,
                                variable=self._characterSpacing,
                                value=spacingRadioButton + 1))
            self._spacingRadioButtonWidgets[spacingRadioButton].grid(column=1, sticky=tk.W)
            # If current config matches this radio button, update the selected value
            if config.spacing.name.upper() == self.CHARACTER_SPACING_SETTINGS[spacingRadioButton]:
                self._original_configured_spacing = spacingRadioButton + 1
                self._characterSpacing.set(spacingRadioButton + 1)
    
        # Create a pair of Radiobuttons using one IntVar for the code type options
        ttk.Label(codeOptions, text="Morse code type:").grid(row=6, column=0, sticky=tk.W)
        self._codeType = tk.IntVar()
        # Initialize the code spacing option to its default value of 'None':
        self._codeType.set(self.DEFAULT_CODE_TYPE)
        for codeTypeRadioButton in range(len(self.CODE_TYPES)):
            ttk.Radiobutton(codeOptions, text=self.CODE_TYPES[codeTypeRadioButton],
                            variable=self._codeType,
                            value=codeTypeRadioButton + 1).grid(row=6, column=1 + codeTypeRadioButton, sticky=tk.W)
            # If current config matches this radio button, update the selected value
            if config.code_type.name.upper() == self.CODE_TYPE_SETTINGS[codeTypeRadioButton].upper():
                self._codeType.set(codeTypeRadioButton + 1)


      # codeOptions.grid(row=2, column=0, columnspan=4, pady=6, sticky=tk.W)
        codeOptions.pack(fill=tk.BOTH)
        
        #######################################################################
        #
        #   Overall "Save" / "Cancel" buttons
        #
        #######################################################################

        # Add a "Save" and a "Cancel" button
        dialogButtons = ttk.LabelFrame(self.root, text='')
        dialogButtons.columnconfigure(0, weight=88)

        self._cancel_button = ttk.Button(dialogButtons, text="Cancel", command=self._clickCancel)
      # self._cancel_button.configure(state='disabled')
        self._cancel_button.grid(row=0, column=1, padx=6, pady=12, sticky=tk.E)
        dialogButtons.columnconfigure(1, weight=6)
        
        self._OK_button = ttk.Button(dialogButtons, text="Save", command=self._clickOK)
      # self._OK_button.configure(state='disabled')
        self._OK_button.grid(row=0, column=2, padx=6, pady=12, sticky=tk.E)
        dialogButtons.columnconfigure(2, weight=6)
      
        dialogButtons.pack(fill=tk.X)

        prefs_nb.pack(expand=1, fill='both')

        # The call to update() is necessary to make the window update its dimensions to the
        # eventual displayed size.
        self.root.update()

        # Center the preferences window on the screen, about 40% of the way from the top:
        prefs_width = self. root.winfo_reqwidth()
        prefs_height = self.root.winfo_reqheight()
        win_width = self.root.winfo_screenwidth()
        win_height = self.root.winfo_screenheight()
        left_offset = int((win_width - prefs_width) / 2 - self.root.winfo_y())
        top_offset = int((win_height - prefs_height) * 0.4- self.root.winfo_x())     # 40% of padding above, 60% below
        self.root.geometry('+%d+%d' % (left_offset, top_offset))

    def _codeSpeedChange(self):
        #
        # Code speed was changed - if it just went above "dot speed", adjust
        # dot speed to show characters will be sent faster to maintain the
        # newly selected code speed:
        #
        if str(self._dotSpeedControl.cget('state')) == tk.NORMAL:
          if self._codeSpeed.get() > self._dotSpeed.get():
              self._dotSpeed.set(int(self._codeSpeed.get()))

    def _dotSpeedChange(self):
        #
        # Dot speed was changed - if it just went below the overall "code speed",
        # adjust the code speed to match dot speed, since you can't send proper
        # code faster than the individual characters are sent
        #
        if self._dotSpeed.get() < self._codeSpeed.get():
            self._codeSpeed.set(int(self._dotSpeed.get()))

    def _spacingChange(self):
        if self._characterSpacing.get() == self.CHARACTER_SPACING_NONE + 1:
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

    def _clickCancel(self):
        self.dismiss()
    
    def _clickOK(self):
        if self._serialPort.get() != "":
            # print("Serial port: ", self._serialPort.get())
            config.set_serial_port(self._serialPort.get())
      # print("Serial connection type: {} ({})".format(self.EQUIPMENT_TYPES[self._equipmentType.get() - 1], \
      #                                                self.EQUIPMENT_TYPE_SETTINGS[self._equipmentType.get() - 1]))
        config.set_interface_type(self.EQUIPMENT_TYPE_SETTINGS[self._equipmentType.get() - 1])
      # print("Invert key input: ", self._invertKeyInput.get())
        config.set_invert_key_input(self._invertKeyInput.get())
      # print("Use system sound: ", self._useSystemSound.get())
        config.set_sound(self._useSystemSound.get())
      # print("Use local sounder: ", self._useLocalSounder.get())
        config.set_sounder(self._useLocalSounder.get())
      # print("Sounder Power Save: ", self._sounderPowerSave.get())
        config.set_sounder_power_save(self._sounderPowerSave.get())
      # print("Server URL: {}".format(self._serverUrl.get() + ":" + self._portNumber.get()))
        config.set_server_url(self._serverUrl.get() + ":" + self._portNumber.get())
      # print("Transmit to remote stations: ", self._transmitToRemoteStations.get())
        config.set_remote(self._transmitToRemoteStations.get())
      # print("Station ID:", self._stationID.get())
        config.set_station(self._stationID.get())
      # print("Wire number:", self._wireNumber.get())
        config.set_wire(self._wireNumber.get())
      # print("Auto-connect at startup:", self._autoConnectAtStartup.get())
        config.set_auto_connect(self._autoConnectAtStartup.get())
      # print("Code speed:", self._codeSpeed.get())
        config.set_text_speed(self._codeSpeed.get())
      # print("Character rate:", self._dotSpeed.get())
        config.set_min_char_speed(self._dotSpeed.get())
      # print("Character spacing:", self.CHARACTER_SPACING_OPTIONS[self._characterSpacing.get() - 1])
        config.set_spacing(self.CHARACTER_SPACING_SETTINGS[self._characterSpacing.get() - 1])
      # print("Code type:", self.CODE_TYPES[self._codeType.get() - 1])
        config.set_code_type(self.CODE_TYPE_SETTINGS[self._codeType.get() - 1])
        
        config.save_config()
        
        self.dismiss()
    
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
