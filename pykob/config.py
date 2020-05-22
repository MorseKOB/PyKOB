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
  User: ~/.pykob/config-[user].ini
  Machine: ~/.pykob/config_app.ini
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
    none = "NONE"
    char = "CHAR"
    word = "WORD"

@unique
class CodeType(Enum):
    international = "INTERNATIONAL"
    american = "AMERICAN"

# Application name
__APP_NAME = "pykob"
# INI Section
__CONFIG_SECTION = "PYKOB"
# System/Machine INI file Parameters/Keys
__SERIAL_PORT_KEY = "PORT"
# User INI file Parameters/Keys
__CODE_TYPE_KEY = "CODE_TYPE"
__LOCAL_KEY = "LOCAL"
__MIN_CHAR_SPEED_KEY = "CHAR_SPEED_MIN"
__REMOTE_KEY = "REMOTE"
__SOUND_KEY = "SOUND"
__SOUNDER_KEY = "SOUNDER"
__SPACING_KEY = "SPACING"
__STATION_KEY = "STATION"
__TEXT_SPEED_KEY = "TEXT_SPEED"
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
code_type = CodeType.american
local = False
remote = False
sound = True
sounder = False
spacing = Spacing.none
station = None
wire = None
min_char_speed = 18
text_speed = 18

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

def set_code_type(s):
    """Sets the Code Type (for American or International)

    Parameters
    ----------
    s : str
        The value `A|AMERICAN` will set the code type to 'American'.  
        The value `I|INTERNATIONAL` will set the code type to 'International'.  
    """

    global code_type
    s = s.upper()
    if s=="A" or s=="AMERICAN":
        code_type = CodeType.american
    elif s=="I" or s=="INTERNATIONAL":
        code_type = CodeType.international
    else:
        log.err("TYPE value '{}' is not a valid `Code Type` value of 'AMERICAN' or 'INTERNATIONAL'.".format(s))
        return
    user_config.set(__CONFIG_SECTION, __CODE_TYPE_KEY, code_type)


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

def set_local(l):
    """Enable/disable local copy

    When local copy is enabled, the local sound/sounder configuration is  
    used to locally sound the content being sent to the wire.
    
    Parameters
    ----------
    l : str
        The enable/disable state to set as a string. Values of `YES`|`ON`|`TRUE` 
        will enable local copy. Values of `NO`|`OFF`|`FALSE` will disable local copy.
    """

    global local
    try:
        local = strtobool(str(l))
        user_config.set(__CONFIG_SECTION, __LOCAL_KEY, onOffFromBool(local))
    except ValueError as ex:
        log.err("LOCAL value '{}' is not a valid boolean value. Not setting value.".format(ex.args[0]))

def set_remote(r):
    """Enable/disable remote send

    When remote send is enabled, the content will be sent to the  
    station+wire configured.  
    
    Parameters
    ----------
    r : str
        The enable/disable state to set as a string. Values of `YES`|`ON`|`TRUE` 
        will enable local copy. Values of `NO`|`OFF`|`FALSE` will disable local copy.
    """

    global remote
    try:
        remote = strtobool(str(r))
        user_config.set(__CONFIG_SECTION, __REMOTE_KEY, onOffFromBool(remote))
    except ValueError as ex:
        log.err("REMOTE value '{}' is not a valid boolean value. Not setting value.".format(ex.args[0]))

def set_min_char_speed(s):
    """Sets the minimum character speed in words per minute

    A difference between character speed (in WPM) and text speed  
    (in WPM) is used to calulate a Farnsworth timing value.  

    This is the minimum character speed. If the text speed is 
    higher, then the character speed will be bumped up to  
    the text speed.

    Parameters
    ----------
    s : str
        The speed in words-per-minute as an interger string value
    """

    global min_char_speed
    try:
        _speed = int(s)
        min_char_speed = _speed
        user_config.set(__CONFIG_SECTION, __MIN_CHAR_SPEED_KEY, str(min_char_speed))
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
        sound = strtobool(str(s))
        user_config.set(__CONFIG_SECTION, __SOUND_KEY, onOffFromBool(sound))
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
        sounder = strtobool(str(s))
        user_config.set(__CONFIG_SECTION, __SOUNDER_KEY, onOffFromBool(sounder))
    except ValueError as ex:
        log.err("SOUNDER value '{}' is not a valid boolean value. Not setting value.".format(ex.args[0]))

def set_spacing(s):
    """Sets the Spacing (for Farnsworth timing) to None (disabled) `Spacing.none`,  
    Character `Spacing.char` or Word `Spacing.word`

    When set to `Spacing.none` Farnsworth spacing will not be added.  
    When set to `Spacing.char` Farnsworth spacing will be added between characters.  
    When set to `Spacing.word` Farnsworth spacing will be added between words.  
    
    Parameters
    ----------
    s : str
        The value `N|NONE` will set the spacing to `Spacing.none` (disabled).  
        The value `C|CHAR` will set the spacing to `Spacing.char`.  
        The value `W|WORD` will set the spacing to `Spacing.word`.
    """

    global spacing
    s = s.upper()
    config_spacing = None
    if s=="N" or s=="NONE":
        spacing = Spacing.none
        config_spacing = "NONE"
    elif s=="C" or s=="CHAR" or s=="CHARACTER":
        spacing = Spacing.char
        config_spacing = "CHAR"
    elif s=="W" or s=="WORD":
        spacing = Spacing.word
        config_spacing = "WORD"
    else:
        log.err("SPACING value '{}' is not a valid `Spacing` value of 'NONE', 'CHAR' or 'WORD'.".format(s))
        return
    if config_spacing:
        user_config.set(__CONFIG_SECTION, __SPACING_KEY, config_spacing)


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

def set_text_speed(s):
    """Sets the Text (code) speed in words per minute

    Parameters
    ----------
    s : str
        The text speed in words-per-minute as an interger string value
    """

    global text_speed
    try:
        _speed = int(s)
        text_speed = _speed
        user_config.set(__CONFIG_SECTION, __TEXT_SPEED_KEY, str(text_speed))
    except ValueError as ex:
        log.err("Text speed value '{}' is not a valid integer value.".format(ex.args[0]))

def print_info():
    """Print system and PyKOB configuration information
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
    print("Code type:", code_type)
    print("Local copy:", onOffFromBool(local))
    print("Remote send:", onOffFromBool(remote))
    print("Sound:", onOffFromBool(sound))
    print("Sounder:", onOffFromBool(sounder))
    print("Spacing:", spacing)
    print("Station:", noneOrValueFromStr(station))
    print("Wire:", noneOrValueFromStr(wire))
    print("Character speed", min_char_speed)
    print("Words per min speed:", text_speed)

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
    global code_type
    global local
    global min_char_speed
    global remote
    global sound
    global sounder
    global spacing
    global station
    global wire
    global text_speed

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
        __CODE_TYPE_KEY:"AMERICAN", \
        __LOCAL_KEY:"OFF", \
        __MIN_CHAR_SPEED_KEY:"18", \
        __REMOTE_KEY:"OFF", \
        __SOUND_KEY:"ON", \
        __SOUNDER_KEY:"OFF", \
        __SPACING_KEY:"NONE", \
        __STATION_KEY:"", \
        __WIRE_KEY:"", \
        __TEXT_SPEED_KEY:"18"}
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
        __option = "Code type"
        __key = __CODE_TYPE_KEY
        _code_type = (user_config.get(__CONFIG_SECTION, __key)).upper()
        if _code_type == "AMERICAN":
            code_type = CodeType.american
        elif _code_type == "INTERNATIONAL":
            code_type = CodeType.international
        else:
            raise ValueError(_code_type)
        __option = "Local copy"
        __key = __LOCAL_KEY
        local = user_config.getboolean(__CONFIG_SECTION, __key)
        __option = "Minimum character speed"
        __key = __MIN_CHAR_SPEED_KEY
        min_char_speed = user_config.getint(__CONFIG_SECTION, __key)
        __option = "Remote send"
        __key = __REMOTE_KEY
        remote = user_config.getboolean(__CONFIG_SECTION, __key)
        __option = "Text speed"
        __key = __TEXT_SPEED_KEY
        text_speed = user_config.getint(__CONFIG_SECTION, __key)
        __option = "Sound"
        __key = __SOUND_KEY
        sound = user_config.getboolean(__CONFIG_SECTION, __key)
        __option = "Sounder"
        __key = __SOUNDER_KEY
        sounder = user_config.getboolean(__CONFIG_SECTION, __key)
        __option = "Spacing"
        __key = __SPACING_KEY
        _spacing = (user_config.get(__CONFIG_SECTION, __key)).upper()
        if _spacing == "NONE":
            spacing = Spacing.none
        elif _spacing == "CHAR":
            spacing = Spacing.char
        elif _spacing == "WORD":
            spacing = Spacing.word
        else:
            raise ValueError(_spacing)
        __option = "Station"
        __key = __STATION_KEY
        _station = user_config.get(__CONFIG_SECTION, __key)
        if not _station or _station.upper() == "NONE":
            station = _station
        __option = "Wire"
        __key = __WIRE_KEY
        _wire = user_config.get(__CONFIG_SECTION, __key)
        if not _wire or _wire.upper() == "NONE":
            wire = _wire
    except KeyError as ex:
        log.err("Key '{}' not found in configuration file.".format(ex.args[0]))
    except ValueError as ex:
        log.err("{} option value '{}' is not a valid value. INI file key: {}.".format(__option, ex.args[0], __key))

# ### Mainline
read_config()

code_type_override = argparse.ArgumentParser(add_help=False)
code_type_override.add_argument("-T", "--type", default=code_type, \
help="The code type (AMERICAN|INTERNATIONAL) to use.", metavar="type", dest="code_type")

local_override = argparse.ArgumentParser(add_help=False)
local_override.add_argument("-L", "--local", default=local, \
help="Enable/disable local copy of transmitted code.", metavar="local", dest="local")

remote_override = argparse.ArgumentParser(add_help=False)
remote_override.add_argument("-R", "--remote", default=remote, \
help="Enable/disable remote transmission of generated code.", metavar="remote", dest="remote")

serial_port_override = argparse.ArgumentParser(add_help=False)
serial_port_override.add_argument("-p", "--port", default=serial_port, \
help="The name of the serial port to use (or 'NONE').", metavar="portname", dest="serial_port")

min_char_speed_override = argparse.ArgumentParser(add_help=False)
min_char_speed_override.add_argument("-c", "--chars", default=min_char_speed, type=int, \
help="The minimum character speed to use in words per minute. This is used in conjunction with \
text speed to introduce Farnsworth timing.", metavar="charspeed", dest="char_speed_min")

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
help="The spacing (NONE|CHAR|WORD) to use.", metavar="spacing", dest="spacing")

station_override = argparse.ArgumentParser(add_help=False)
station_override.add_argument("-S", "--station", default=station, \
help="The station to use (or 'NONE').", metavar="station", dest="station")

wire_override = argparse.ArgumentParser(add_help=False)
wire_override.add_argument("-W", "--wire", default=wire, \
help="The wire to use (or 'NONE').", metavar="wire", dest="wire")

text_speed_override = argparse.ArgumentParser(add_help=False)
text_speed_override.add_argument("-t", "--texts", default=text_speed, type=int, \
help="The morse text speed in words per minute.", metavar="textspeed", dest="text_speed")

exit
