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

"""config module  

Reads configuration information for `per-machine` and `per-user` values.  

An example of a `per-machine` value is the KOB serial/com port (PORT).  
An example of a `per-user` value is the code speed (WPM).

Configuration/preference values are read/written to:
 Windows:
  User: [user]\AppData\Roaming\pykob\config-[user].ini
  Machine: \ProgramData\pykob\config_app.ini
 Mac:
  User: 
  Machine: 
 Linux:
  User: ~/.pykob/config-[user].ini
  Machine: ~/.pykob/config_app.ini

The files are INI format with the values in a section named "PYKOB".

"""
import argparse
import configparser
import distutils
import getpass
import os
import platform
import socket
import sys
from distutils.util import strtobool
from enum import Enum, unique
from pykob import log

@unique
class Spacing(Enum):
    char = "CHARSPACING"
    word = "WORDSPACING"

# Application name
__APP_NAME = "pykob"
# INI Section
__CONFIG_SECTION = "PYKOB"
# System/Machine INI file Parameters/Keys
__SERIAL_PORT_KEY = "PORT"
# User INI file Parameters/Keys
__CWPM_SPEED_KEY = "CWPM_SPEED"
__WPM_SPEED_KEY = "WPM_SPEED"
__SOUND_KEY = "SOUND"
__SOUNDER_KEY = "SOUNDER"
__SPACING_KEY = "SPACING"
__STATION_KEY = "STATION"
__WIRE_KEY = "WIRE"


# Paths and Configurations
app_config_dir = None
app_config_file_path = None
app_config = None
user_config_dir = None
user_config_file_path = None
user_config = None

# System information
hostname = None
os_name = None
platform_name= None
system_name = None
system_version = None
user_home = None
user_name = None

# Machine/System Settings
serial_port = None

# User Settings
sound = True
sounder = False
spacing = Spacing.char
station = None
wire = None
char_speed = 18
word_speed = 18

def onOffFromBool(b):
    """Return 'ON' if `b` is `True` and 'OFF' if `b` is `False`

    Parameters
    ----------
    b : boolean
        The value to evaluate
    Return
    ------
        'ON' for `True`, 'OFF' for `False`
    """
    #print(b)
    r = "ON" if b else "OFF"
    return r

def noneOrValueFromStr(s):
    """Return `None` if `s` is '' and the string value otherwise

    Parameters
    ----------
    s : str
        The string value to evaluate
    Return
    ------
        `None` or the string value
"""
    r = None if not s or not s.strip() else s
    return r

def create_config_files_if_needed():
    global app_config_dir
    global app_config_file_path
    global user_config_dir
    global user_config_file_path

    # Create the files if they don't exist
    if not os.path.isfile(user_config_file_path):
        # need to create
        user_config_dir = os.path.split(user_config_file_path)[0]
        if not os.path.isdir(user_config_dir):
            os.makedirs(user_config_dir)
        f = open(user_config_file_path, 'w')
        f.close()
    if not os.path.isfile(app_config_file_path):
        # need to create
        app_config_dir = os.path.split(app_config_file_path)[0]
        if not os.path.isdir(app_config_dir):
            os.makedirs(app_config_dir)
        f = open(app_config_file_path, 'w')
        f.close()

def set_cwpm_speed(s):
    """Sets the Character words per minute speed

    A difference between character words per minute speed and words per 
    minute speed is used to calulate a Farnsworth timing value.

    Parameters
    ----------
    s : str
        The speed in words-per-minute as an interger string value
    """

    global char_speed
    try:
        _speed = int(s)
        char_speed = _speed
        user_config.set(__CONFIG_SECTION, __CWPM_SPEED_KEY, str(char_speed))
    except ValueError as ex:
        log.err("CHARS value '{}' is not a valid integer value. Not setting CWPM value.".format(ex.args[0]))

def set_serial_port(p):
    """Sets the name/path of the serial/tty port to use for a 
    key+sounder/loop interface

    Parameters
    ----------
    p : str
        The 'COM' port for Windows, the 'tty' device path for Mac and Linux
    """

    global serial_port
    serial_port = noneOrValueFromStr(p)
    app_config.set(__CONFIG_SECTION, __SERIAL_PORT_KEY, serial_port)

def set_sound(s):
    """Sets the Sound/Audio enable state

    When set to `True` via a value of "TRUE"/"ON"/"YES" the computer audio 
    will be used to produce sounder output.

    Parameters
    ----------
    s : str
        The enable/disable state to set as a string. Values of `YES`|`ON`|`TRUE` 
        will enable sound. Values of `NO`|`OFF`|`FALSE` will disable sound.
    """

    global sound
    try:
        _sb = strtobool(str(s))
        sound = onOffFromBool(_sb)
        user_config.set(__CONFIG_SECTION, __SOUND_KEY, sound)
    except ValueError as ex:
        log.err("SOUND value '{}' is not a valid boolean value. Not setting value.".format(ex.args[0]))

def set_sounder(s):
    """Sets the Sounder enable state

    When set to `True` via a value of "TRUE"/"ON"/"YES" the sounder will 
    be driven if the `port` value is configured.

    Parameters
    ----------
    s : str
        The enable/disable state to set as a string. Values of `YES`|`ON`|`TRUE` 
        will enable sounder output. Values of `NO`|`OFF`|`FALSE` will disable 
        sounder output.
    """

    global sounder
    try:
        _sb = strtobool(str(s))
        sounder = onOffFromBool(_sb)
        user_config.set(__CONFIG_SECTION, __SOUNDER_KEY, sounder)
    except ValueError as ex:
        log.err("SOUNDER value '{}' is not a valid boolean value. Not setting value.".format(ex.args[0]))

def set_spacing(s):
    """Sets the Spacing (for Farnsworth timing) to Character `Spacing.char` or 
    Word `Spacing.word`

    When set to `Spacing.char` Farnsworth spacing will be added between characters. 
    When set to `Spacing.word` Farnsworth spacing will be added between words.
    
    Parameters
    ----------
    s : str
        The value `C|CHAR` will set the spacing to `Spacing.char`. The value 
        `W|WORD` will set the spacing to `Spacing.word`.
    """

    global spacing
    s = s.upper()
    if s=="C" or s=="CHAR" or s=="CHARACTER":
        spacing = Spacing.char
    elif s=="W" or s=="WORD":
        spacing = Spacing.word
    else:
        log.err("SPACING value '{}' is not a valid `Spacing` value 'CHAR' or 'WORD'.".format(s))
        return
    user_config.set(__CONFIG_SECTION, __SPACING_KEY, "CHAR" if spacing == Spacing.char else "WORD")


def set_station(s):
    """Sets the station name to use when connecting to a wire

    Parameters
    ----------
    s : str
        The station name
    """

    global station
    station = noneOrValueFromStr(s)
    user_config.set(__CONFIG_SECTION, __STATION_KEY, station)

def set_wire(w):
    """Sets the wire to use when connecting

    Parameters
    ----------
    w : str
        The wire name
    """

    global wire
    wire = noneOrValueFromStr(w)
    user_config.set(__CONFIG_SECTION, __WIRE_KEY, wire)

def set_wpm_speed(s):
    """Sets the Words per minute speed

    Parameters
    ----------
    s : str
        The speed in words-per-minute as an interger string value
    """

    global word_speed
    try:
        _speed = int(s)
        word_speed = _speed
        user_config.set(__CONFIG_SECTION, __WPM_SPEED_KEY, str(word_speed))
    except ValueError as ex:
        log.err("WORDS value '{}' is not a valid integer value. Not setting WPM value.".format(ex.args[0]))

def print_info():
    """Print system and configuration information
    """

    print_system_info()
    print_config()

def print_system_info():
    """Print system information
    """

    print("User:", user_name)
    print("User Home Path:", user_home)
    print("User Configuration File:", user_config_file_path)
    print("App Configuration File", app_config_file_path)
    print("OS:", os_name)
    print("System:", system_name)
    print("Version:", system_version)
    print("Platform", platform_name)
    print("Host:", hostname)

def print_config():
    """Print the PyKOB configuration
    """

    print("======================================")
    print("Serial serial_port: '{}'".format(serial_port))
    print("--------------------------------------")
    print("Sound:", sound)
    print("Sounder:", sounder)
    print("Spacing:", spacing)
    print("Station:", noneOrValueFromStr(station))
    print("Wire:", noneOrValueFromStr(wire))
    print("Character speed", char_speed)
    print("Words per min speed:", word_speed)

def save_config():
    """Save (write) the configuration values out to the user and 
    system/machine config files.
    """

    create_config_files_if_needed()
    with open(user_config_file_path, 'w') as configfile:
        user_config.write(configfile, space_around_delimiters=False)
    with open(app_config_file_path, 'w') as configfile:
        app_config.write(configfile, space_around_delimiters=False)

def read_config():
    """Read the configuration values from the user and machine config files.
    """

    global hostname
    global platform_name
    global os_name
    global system_name
    global system_version
    global app_config
    global app_config_file_path
    global user_config
    global user_config_file_path
    global user_home
    global user_name
    #
    global serial_port
    #
    global char_speed
    global sound
    global sounder
    global spacing
    global station
    global wire
    global word_speed
    #
    global cwpm_override
    global serial_port_override
    global sound_override
    global spacing_override
    global station_override
    global wire_override
    global wpm_override

    # Get the system data
    try:
        user_name = getpass.getuser()
        user_home = os.path.expanduser('~')
        os_name = os.name
        system_name = platform.system()
        system_version = platform.release()
        platform_name = sys.platform
        hostname = socket.gethostname()

        # User configuration file name
        userConfigFileName = "config-{}.ini".format(user_name)
        app_configFileName = "config_app.ini"

        # Create the user and application configuration paths
        if system_name == "Windows":
            user_config_file_path = os.path.join(os.environ["LOCALAPPDATA"], os.path.normcase(os.path.join(__APP_NAME, userConfigFileName)))
            app_config_file_path = os.path.join(os.environ["ProgramData"], os.path.normcase(os.path.join(__APP_NAME, app_configFileName)))
        elif system_name == "Linux" or system_name == "Darwin": # Linux or Mac
            user_config_file_path = os.path.join(user_home, os.path.normcase(os.path.join(".{}".format(__APP_NAME), userConfigFileName)))
            app_config_file_path = os.path.join(user_home, os.path.normcase(os.path.join(".{}".format(__APP_NAME), app_configFileName)))
        else:
            log.err("Unknown System name")
            exit

    except KeyError as ex:
        log.err("Key '{}' not found in environment.".format(ex.args[0]))
        exit

    create_config_files_if_needed()

    user_config_defaults = {\
        __CWPM_SPEED_KEY:"20", \
        __SOUND_KEY:"ON", \
        __SOUNDER_KEY:"OFF", \
        __SPACING_KEY:"CHAR", \
        __STATION_KEY:"", \
        __WIRE_KEY:"", \
        __WPM_SPEED_KEY:"18"}
    app_config_defaults = {"PORT":""}

    user_config = configparser.ConfigParser(defaults=user_config_defaults, allow_no_value=True, default_section=__CONFIG_SECTION)
    app_config = configparser.ConfigParser(defaults=app_config_defaults, allow_no_value=True, default_section=__CONFIG_SECTION)

    user_config.read(user_config_file_path)
    app_config.read(app_config_file_path)

    try:
        # Get the System (App) config values
        serial_port = app_config.get(__CONFIG_SECTION, __SERIAL_PORT_KEY)
        # If there isn't a PORT value set PORT to None
        if not serial_port:
            serial_port = None

        # Get the User config values
        __option = "Character Speed"
        char_speed = user_config.getint(__CONFIG_SECTION, __CWPM_SPEED_KEY)
        __option = "Word Speed"
        word_speed = user_config.getint(__CONFIG_SECTION, __WPM_SPEED_KEY)
        __option = "Sound"
        sound = user_config.getboolean(__CONFIG_SECTION, __SOUND_KEY)
        __option = "Sounder"
        sounder = user_config.getboolean(__CONFIG_SECTION, __SOUNDER_KEY)
        __option = "Spacing"
        _spacing = (user_config.get(__CONFIG_SECTION, __SPACING_KEY)).upper()
        if _spacing == "CHAR":
            spacing = Spacing.char
        elif _spacing == "WORD":
            spacing = Spacing.word
        else:
            raise ValueError(_spacing)
        __option = "Station"
        _station = user_config.get(__CONFIG_SECTION, __STATION_KEY)
        if not _station or _station.upper() == "NONE":
            station = _station
        __option = "Wire"
        _wire = user_config.get(__CONFIG_SECTION, __WIRE_KEY)
        if not _wire or _wire.upper() == "NONE":
            wire = _wire
    except KeyError as ex:
        log.err("Key '{}' not found in configuration file.".format(ex.args[0]))
    except ValueError as ex:
        log.err("{} option value '{}' is not a valid value for the option.".format(__option, ex.args[0]))
        word_speed = 18

# ### Mainline
read_config()

serial_port_override = argparse.ArgumentParser(add_help=False)
serial_port_override.add_argument("-p", "--port", default=serial_port, \
help="The name of the serial port to use (or 'NONE').", metavar="portname", dest="serial_port")

cwpm_override = argparse.ArgumentParser(add_help=False)
cwpm_override.add_argument("-c", "--chars", default=char_speed, type=int, \
help="The character speed to use in Words per Minute. This is used in conjunction with \
`speed` to introduce Farnsworth timing.", metavar="charspeed", dest="char_")

sound_override = argparse.ArgumentParser(add_help=False)
sound_override.add_argument("-a", "--sound", default="ON" if sound else "OFF", 
choices=["ON", "OFF"], help="'ON' or 'OFF' to indicate whether morse audio \
should be generated.", metavar="sound", dest="sound")

sounder_override = argparse.ArgumentParser(add_help=False)
sounder_override.add_argument("-A", "--sounder", default="ON" if sounder else "OFF", 
choices=["ON", "OFF"], help="'ON' or 'OFF' to indicate whether to use \
sounder if `port` is configured.", metavar="sounder", dest="sounder")

spacing_override = argparse.ArgumentParser(add_help=False)
spacing_override.add_argument("-s", "--spacing", default=spacing, \
help="The spacing (CHAR|WORD) to use.", metavar="spacing", dest="spacing")

station_override = argparse.ArgumentParser(add_help=False)
station_override.add_argument("-5", "--station", default=station, \
help="The station to use (or 'NONE').", metavar="station", dest="station")

wire_override = argparse.ArgumentParser(add_help=False)
wire_override.add_argument("-W", "--wire", default=wire, \
help="The wire to use (or 'NONE').", metavar="wire", dest="wire")

wpm_override = argparse.ArgumentParser(add_help=False)
wpm_override.add_argument("-w", "--words", default=word_speed, type=int, \
help="The morse send speed in Words per Minute.", metavar="speed", dest="word_speed")

exit
