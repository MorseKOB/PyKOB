#============================================
# Imports
#============================================

from pykob import config

import tkinter as tk
from tkinter import ttk
from tkinter import scrolledtext
from tkinter import Menu

import serial
import serial.tools.list_ports

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
      # print("Configured serial port  =", config.serial_port)
      # print("Configured code speed  =", config.text_speed)
       
        interface = 'SERIAL'      # Placeholder until HW interface type is configured
        
        self.HW_INTERFACE_TYPES = ["None", "GPIO interface (Raspberry Pi)", "Serial Port"]
        self.SERIAL_HW_INTERFACE = 2        # index of 'Serial Port' in list above
        self.HW_INTERFACE_CONFIG_SETTINGS = ['None', 'GPIO', 'SERIAL']
        
        self.SERIAL_CONNECTION_TYPES = ['Local loop (key and sounder in series)',
                                       'Separate key and sounder',
                                       'Separate dot/dash paddle and sounder']
        self.SERIAL_CONNECTION_SETTINGS = ["LOOP", "KEY_SOUNDER", "KEYER"]
        self.DEFAULT_SERIAL_CONNECTION_TYPE = 2
        
        HOST_DEFAULT = "mtc-kob.dyndns.org"
        PORT_DEFAULT = 7890
        
        self.CHARACTER_SPACING_OPTIONS = ["None", "Between characters", "Between words"]
        self.CHARACTER_SPACING_SETTINGS = ['NONE', 'CHARACTER', 'WORD']
        self.DEFAULT_CHARACTER_SPACING = 2
        
        self.CODE_TYPES = ["American", "International"]
        self.CODE_TYPE_SETTINGS = ['AMERICAN', 'INTERNATIONAL']
        self.DEFAULT_CODE_TYPE = 1
    
        self.root = tk.Toplevel()
        self.root.resizable(False, False)

        self.root.title("Preferences")

        
        #######################################################################
        #
        #   Create two-tabbed interface: Basic/Advanced
        #
        #######################################################################
        
        prefs_nb = ttk.NoteBook(self.root)
        basic_prefs = ttk.Frame(prefs_nb)
        prefs_nb.add(basic_prefs, text="Basic")
        advanced_prefs = ttk.Frame(prefs_nb)
        prefs_nb.add(advanced_prefs, text="Advanced")

        #######################################################################
        #
        #   Local Interface section
        #
        #######################################################################

        # Create a container frame to hold all local interface-related widgets
        localInterface = ttk.LabelFrame(basic_prefs, text=" Local Interface")
        ttk.Label(localInterface, text="Key and sounder interface:").grid(row=0, column=0, rowspan=6, sticky=tk.NW)

        # Add a pop-up menu with the list of available serial connections:
        self.serialPort = tk.StringVar()
        systemSerialPorts = serial.tools.list_ports.comports()
        serialPortValues = [systemSerialPorts[p].device for p in range(len(systemSerialPorts))]
        serialPortMenu = ttk.Combobox(localInterface,
                                      width=30,
                                      textvariable=self.serialPort,
                                      state='readonly',
                                      values=serialPortValues).grid(row=1,
                                                                    column=0, columnspan=4,
                                                                    sticky=tk.W)
        for serial_device in serialPortValues:
            # If port device  matches this radio button, update the selected value
            if config.serial_port == serial_device:
                self.serialPort.set(serial_device)
        
        # Label the serial connection type:
        ttk.Label(localInterface, text="Serial connection:").grid(row=2, rowspan=3, column=0, sticky=tk.NE)

        # Create three Radiobuttons using one IntVar for the serial connection type
        self.serialConnectionType = tk.IntVar()

        # Initialize the serial connection type to its default value of 'Separate key and sounder':
        self.serialConnectionType.set(self.DEFAULT_SERIAL_CONNECTION_TYPE)
        
        for serialadioButton in range(len(self.SERIAL_CONNECTION_TYPES)):
            ttk.Radiobutton(localInterface, text=self.SERIAL_CONNECTION_TYPES[serialadioButton],
                            variable=self.serialConnectionType,
                            value=serialadioButton + 1).grid(row=serialadioButton + 2,
                                                             column=1, columnspan=2,
                                                             sticky=tk.W)
            # If current config matches this radio button, update the selected value
            if config.interface_type.to_string() == self.SERIAL_CONNECTION_SETTINGS[serialadioButton]:
                self.serialConnectionType.set(serialadioButton + 1)

        # Add a single checkbox for the key inversion next to the "Separate key/sounder" option
        self.invertKeyInput = tk.IntVar(value=config.invert_key_input)
        ttk.Checkbutton(localInterface, text="Invert key input",
                        variable=self.invertKeyInput).grid(row=4,
                                                           column=5,
                                                           padx=12, sticky=tk.W)
        
        # Add a checkbox for the 'Use system sound' option
        self.useSystemSound = tk.IntVar(value=config.sound)
        ttk.Checkbutton(localInterface,
                        text="Use system sound",
                        variable=self.useSystemSound).grid(column=0, columnspan=6,
                                                           sticky=tk.W)

        # Add a checkbox for the 'Use local sounder' option
        self.useLocalSounder = tk.IntVar(value=config.sounder)
        ttk.Checkbutton(localInterface,
                        text="Use local sounder",
                        variable=self.useLocalSounder).grid(column=0, columnspan=6,
                                                            sticky=tk.W)

        localInterface.pack(fill=tk.BOTH)

        #######################################################################
        #
        #   Internet connection section
        #
        #######################################################################

        # Create a container frame to hold all internet connection-related widgets
        internetConnection = ttk.LabelFrame(basic_prefs, text=" Internet Connection")
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
        self.serverUrl = tk.StringVar(value=server_url)
        ttk.Label(internetConnection, text="Server:").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(internetConnection, width=30, textvariable=self.serverUrl).grid(row=0, column=1, sticky=tk.W)
        
        # Create and label an entry for the server port number:
        self.portNumber = tk.StringVar(value=server_port)
        ttk.Label(internetConnection, text="Port number:").grid(row=0, column=2, sticky=tk.E)
        ttk.Entry(internetConnection, width=10, textvariable=self.portNumber).grid(row=0, column=3, sticky=tk.W)
        
        # Add a checkbox for the 'Transmit to remote stations' option
        self.transmitToRemoteStations = tk.IntVar(value=config.remote)
        ttk.Checkbutton(internetConnection,
                        text="Transmit to remote stations",
                        variable=self.transmitToRemoteStations).grid(row=1, column=0, columnspan=4, sticky=tk.W)

        # Create and label an entry for the initial station ID:
        self.initialStationID = tk.StringVar(value=config.station)
        ttk.Label(internetConnection, text="Initial station ID:").grid(row=2, column=0, sticky=tk.E)
        ttk.Entry(internetConnection, width=20, textvariable=self.initialStationID).grid(row=2, column=1, sticky=tk.W)

        # Create and label an entry for the initial wire number:
        self.initialWireNumber = tk.StringVar(value=config.wire)
        ttk.Label(internetConnection, text="Initial wire number:").grid(row=3, column=0, sticky=tk.E)
        ttk.Entry(internetConnection, width=5, textvariable=self.initialWireNumber).grid(row=3, column=1, sticky=tk.W)

        # Add a checkbox for the 'Automatically connect at startup' option
        self.autoConnectAtStartup = tk.IntVar(value=config.auto_connect)
        ttk.Checkbutton(internetConnection,
                        text="Automatically connect at startup",
                        variable=self.autoConnectAtStartup).grid(row=4, column=0, columnspan=2, padx=20, sticky=tk.W)

      # internetConnection.grid(row=1, column=0, columnspan=5, pady=6, sticky=tk.W)
        internetConnection.pack(fill=tk.BOTH)
        
        #######################################################################
        #
        #   Morse Code section
        #
        #######################################################################

        # Create a container frame to hold all code-related widgets
        codeOptions = ttk.LabelFrame(basic_prefs, text=" Code Options")
        
        ttk.Label(codeOptions, text="Code speed and Farnsworth spacing:").grid(row=0, column=0, columnspan=2, sticky=tk.W)
        
        ttk.Label(codeOptions, text="Intial Code Speed:").grid(row=1, column=1, padx=30, sticky=tk.E)
      # print("Setting code speed to", config.text_speed)
        self.codeSpeed = tk.DoubleVar(value=config.text_speed)
        ttk.Spinbox(codeOptions, from_=1, to=99,
                    width=4, format="%2.f", justify=tk.RIGHT,
                    textvariable=self.codeSpeed).grid(row=1,
                                                      column=2,
                                                      padx=10, sticky=tk.W)
        
        ttk.Label(codeOptions, text="Initial character rate:").grid(row=1, column=3, sticky=tk.E)
        self.characterRate = tk.DoubleVar(value=config.min_char_speed)
        ttk.Spinbox(codeOptions, from_=1, to=99, width=4, format="%2.f", justify=tk.RIGHT, textvariable=self.characterRate).grid(row=1, column=4, padx=10, sticky=tk.W)
        
        # Create three Radiobuttons using one IntVar for the character spacing options
        ttk.Label(codeOptions, text="Character spacing:").grid(row=2, column=0, columnspan=4, sticky=tk.W)
        # Initialize the code spacing option to its default value of 'None':
        self.characterSpacing = tk.IntVar(value=self.DEFAULT_CHARACTER_SPACING)
        for spacingRadioButton in range(len(self.CHARACTER_SPACING_OPTIONS)):
            ttk.Radiobutton(codeOptions, text=self.CHARACTER_SPACING_OPTIONS[spacingRadioButton],
                            variable=self.characterSpacing,
                            value=spacingRadioButton + 1).grid(column=1, sticky=tk.W)
            # If current config matches this radio button, update the selected value
            if config.spacing.to_string() == self.CHARACTER_SPACING_SETTINGS[spacingRadioButton]:
                self.characterSpacing.set(spacingRadioButton + 1)
    
        # Create a pair of Radiobuttons using one IntVar for the code type options
        ttk.Label(codeOptions, text="Morse code type:").grid(row=6, column=0, sticky=tk.W)
        self.codeType = tk.IntVar()
        # Initialize the code spacing option to its default value of 'None':
        self.codeType.set(self.DEFAULT_CODE_TYPE)
        for codeTypeRadioButton in range(len(self.CODE_TYPES)):
            ttk.Radiobutton(codeOptions, text=self.CODE_TYPES[codeTypeRadioButton],
                            variable=self.codeType,
                            value=codeTypeRadioButton + 1).grid(row=6, column=1 + codeTypeRadioButton, sticky=tk.W)
            # If current config matches this radio button, update the selected value
            if config.code_type.to_string() == self.CODE_TYPE_SETTINGS[codeTypeRadioButton]:
                self.codeType.set(codeTypeRadioButton + 1)
    
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

        self.cancel_button = ttk.Button(dialogButtons, text="Cancel", command=self._ClickCancel)
      # self.cancel_button.configure(state='disabled')
        self.cancel_button.grid(row=0, column=1, padx=6, pady=12, sticky=tk.E)
        dialogButtons.columnconfigure(1, weight=6)
        
        self.OK_button = ttk.Button(dialogButtons, text="Save", command=self._ClickOK)
      # self.OK_button.configure(state='disabled')
        self.OK_button.grid(row=0, column=2, padx=6, pady=12, sticky=tk.E)
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

    def _ClickCancel(self):
        self.dismiss()
    
    def _ClickOK(self):
        if self.serialPort.get() != "":
            # print("Serial port: ", self.serialPort.get())
            config.set_serial_port(self.serialPort.get())
      # print("Serial connection type: {} ({})".format(self.SERIAL_CONNECTION_TYPES[self.serialConnectionType.get() - 1], \
      #                                                self.SERIAL_CONNECTION_SETTINGS[self.serialConnectionType.get() - 1]))
        config.set_interface_type(self.SERIAL_CONNECTION_SETTINGS[self.serialConnectionType.get() - 1])
      # print("Invert key input: ", self.invertKeyInput.get())
        config.set_invert_key_input(self.invertKeyInput.get())
      # print("Use system sound: ", self.useSystemSound.get())
        config.set_sound(self.useSystemSound.get())
      # print("Use local sounder: ", self.useLocalSounder.get())
        config.set_sounder(self.useLocalSounder.get())
      # print("Server URL: {}".format(self.serverUrl.get() + ":" + self.portNumber.get()))
        config.set_server_url(self.serverUrl.get() + ":" + self.portNumber.get())
      # print("Transmit to remote stations: ", self.transmitToRemoteStations.get())
        config.set_remote(self.transmitToRemoteStations.get())
      # print("Initial station ID:", self.initialStationID.get())
        config.set_station(self.initialStationID.get())
      # print("Initial wire number:", self.initialWireNumber.get())
        config.set_wire(self.initialWireNumber.get())
      # print("Auto-connect at startup:", self.autoConnectAtStartup.get())
        config.set_auto_connect(self.autoConnectAtStartup.get())
      # print("Initial code speed:", self.codeSpeed.get())
        config.set_text_speed(self.codeSpeed.get())
      # print("Initial character rate:", self.characterRate.get())
        config.set_min_char_speed(self.characterRate.get())
      # print("Character spacing:", self.CHARACTER_SPACING_OPTIONS[self.characterSpacing.get() - 1])
        config.set_spacing(self.CHARACTER_SPACING_SETTINGS[self.characterSpacing.get() - 1])
      # print("Code type:", self.CODE_TYPES[self.codeType.get() - 1])
        config.set_code_type(self.CODE_TYPE_SETTINGS[self.codeType.get() - 1])
        
        config.save_config()
        
        self.dismiss()
    
    def display(self):
        self.root.mainloop()

    def dismiss(self):
        if self._quitOnExit:
            self.root.quit()
        self.root.destroy()
        if self._callback:
            self._callback(self)  
