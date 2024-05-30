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
config module

Reads configuration information for the PyKOB modules and applications.

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
import getpass
import os
import platform
import pykob
import socket
import sys
from pykob.util import strtobool
from enum import IntEnum, unique
from pykob import log, util

@unique
class Spacing(IntEnum):
    none = 0
    char = 1
    word = 2

@unique
class AudioType(IntEnum):
    SOUNDER = 1
    TONE = 10

@unique
class CodeType(IntEnum):
    american = 1
    international = 2

@unique
class InterfaceType(IntEnum):
    key_sounder = 1     # Separate Key & Sounder
    loop = 2            # Key and Sounder in series
    keyer = 3           # Dit-Dah Paddle and separate (or no) Sounder

# Application name
_APP_NAME = "pykob"
# INI Section
_CONFIG_SECTION = "PYKOB"
# System/Machine INI file Parameters/Keys
_SERIAL_PORT_KEY = "PORT"
_GPIO_KEY = "GPIO"
# User INI file Parameters/Keys
_AUDIO_TYPE_KEY = "AUDIO_TYPE"
_AUTO_CONNECT_KEY = "AUTO_CONNECT"
_CODE_TYPE_KEY = "CODE_TYPE"
_DECODE_AT_DETECTED_KEY = "DECODE_AT_DETECTED"
_LOGGING_LEVEL_KEY = "LOGGING_LEVEL"
_INTERFACE_TYPE_KEY = "INTERFACE_TYPE"
_INVERT_KEY_INPUT_KEY = "KEY_INPUT_INVERT"
_LOCAL_KEY = "LOCAL"
_MIN_CHAR_SPEED_KEY = "CHAR_SPEED_MIN"
_NO_KEY_CLOSER_KEY = "NO_KEY_CLOSER"
_REMOTE_KEY = "REMOTE"
_SERVER_URL_KEY = "SERVER_URL"
_SOUND_KEY = "SOUND"
_SOUNDER_KEY = "SOUNDER"
_SOUNDER_POWER_SAVE_KEY = "SOUNDER_POWER_SAVE"
_SPACING_KEY = "SPACING"
_STATION_KEY = "STATION"
_TEXT_SPEED_KEY = "TEXT_SPEED"
_WIRE_KEY = "WIRE"


# Paths and Configurations
global app_config_dir, app_config_file_path, app_config
global user_config_dir, user_config_file_path, user_config
#
app_config_dir = None
app_config_file_path = None
app_config = None
user_config_dir = None
user_config_file_path = None
user_config = None

# System information
hostname = None
os_name = None
platform_name = None
pyaudio_version = None
pyserial_version = None
python_version = None
pykob_version = None
system_name = None
system_version = None
user_home = None
user_name = None

# Machine/System Settings
serial_port = None
gpio = False

# User Settings
audio_type = AudioType.SOUNDER
auto_connect = False
code_type = CodeType.american
decode_at_detected = False
logging_level = log.INFO_LEVEL
interface_type = InterfaceType.loop
invert_key_input = False
local = True
no_key_closer = False
remote = True
server_url = None
sound = True
sounder = False
sounder_power_save = 0
spacing = Spacing.none
station = None
wire = 0
min_char_speed = 18
text_speed = 18

def codeTypeFromString(s):
    """Return the CodeType for a string (A:AMERICAN|I:INTERNATIONAL). Raises a ValueError if not valid"""
    s = s.upper()
    if s=="A" or s=="AMERICAN":
        return CodeType.american
    elif s=="I" or s=="INTERNATIONAL":
        return CodeType.international
    raise ValueError(s)

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

def audio_type_from_str(s):
    """
    From a string of 'SOUNDER'|'S' or 'TONE'|'T' return the AudioType.

    Parameters
    ----------
    s : str
        'T|TONE' for AudioType.TONE
        'S|SOUNDER' for AudioType.SOUNDER

    Raise a value error if it isn't one of those values
    """
    s = s.upper()
    if s == 'S' or s == "SOUNDER":
        return AudioType.SOUNDER
    elif s == 'T' or s == "TONE":
        return AudioType.TONE
    else:
        msg = "TYPE value '{}' is not a valid `Audio Type` value of 'SOUNDER' or 'TONE'.".format(s)
        log.err(msg)
        raise ValueError(msg)

def set_audio_type(s):
    """
    Sets the Audio Type (for SOUNDER or TONE)

    Parameters
    ----------
    s : str
        The value `S|SOUNDER` will set the audio type to 'SOUNDER'.
        The value `T|TONE` will set the audio type to 'TONE'.
    """
    global audio_type
    audio_type = audio_type_from_str(s)
    user_config.set(_CONFIG_SECTION, _AUDIO_TYPE_KEY, audio_type.name.upper())

def set_auto_connect(s):
    """Sets the Auto Connect to wire enable state

    When set to `True` via a value of "TRUE"/"ON"/"YES" the application should
    automatically connect to the configured wire.

    Note that this is a 'suggestion'. It isn't used by the base pykob
    modules. It should be used by applications (like MKOB) to initiate a connection
    to the configured wire.

    Parameters
    ----------
    s : str
        The enable/disable state to set as a string. Values of `YES`|`ON`|`TRUE`
        will enable auto-connect. Values of `NO`|`OFF`|`FALSE` will disable auto-connect.
    """

    global auto_connect
    try:
        auto_connect = strtobool(str(s))
        user_config.set(_CONFIG_SECTION, _AUTO_CONNECT_KEY, util.on_off_from_bool(auto_connect))
    except ValueError as ex:
        log.err("Auto Connect value '{}' is not a valid boolean value. Not setting value.".format(ex.args[0]))
        raise

def code_type_from_str(s):
    """
    CodeType object from the string representation (for American or International)

    Parameters
    ----------
    s : str
        The value `A|AMERICAN` will return code type 'American'.
        The value `I|INTERNATIONAL` will return code type 'International'.
    """
    s = s.upper()
    if s=="A" or s=="AMERICAN":
        return CodeType.american
    elif s=="I" or s=="INTERNATIONAL":
        return CodeType.international
    else:
        msg = "TYPE value '{}' is not a valid `Code Type` value of 'AMERICAN' or 'INTERNATIONAL'.".format(s)
        log.err(msg)
        raise ValueError(msg)

def set_code_type(s):
    """
    Sets the Code Type (for American or International)

    Parameters
    ----------
    s : str
        The value `A|AMERICAN` will set the code type to 'American'.
        The value `I|INTERNATIONAL` will set the code type to 'International'.
    """
    global code_type
    code_type = code_type_from_str(s)
    user_config.set(_CONFIG_SECTION, _CODE_TYPE_KEY, code_type.name.upper())

def set_logging_level(s: str):
    """Sets the debug level (0-...)

    Parameters
    ----------
    s : str
        The debug level
    """

    try:
        _l = int(s)
        set_logging_level_int(_l)
    except ValueError as ex:
        log.err(
            "Logging Level value '{}' is not a valid integer value.".format(ex.args[0])
        )
        raise


def set_logging_level_int(level: int):
    global logging_level
    logging_level = level if level >=log.LOGGING_MIN_LEVEL else log.LOGGING_MIN_LEVEL
    user_config.set(_CONFIG_SECTION, _LOGGING_LEVEL_KEY, str(logging_level))


def interface_type_from_str(s):
    """
    Interface Type object from the string representation.

        Parameters
        ----------
        s : str
            The value `KS|KEY_SOUNDER` will return 'InterfaceType.key_sounder'.
            The value `L|LOOP` will return 'InterfaceType.loop'.
            The value `K|KEYER` will return 'InterfaceType.keyer'.
    """
    s = s.upper()
    if s=="KS" or s=="KEY_SOUNDER":
        return(InterfaceType.key_sounder)
    elif s=="L" or s=="LOOP":
        return (InterfaceType.loop)
    elif s=="K" or s=="KEYER":
        return(InterfaceType.keyer)
    else:
        msg = "TYPE value '{}' is not a valid `Interface Type` value of 'KEY_SOUNDER', 'LOOP' or 'KEYER'.".format(s)
        log.err(msg)
        raise ValueError(msg)

def set_decode_at_detected(b):
    """
    Enable/disable decoding at the detected speed.

    When enabled, the detected incoming code speed is used for the Morse Reader (decoder).
    When disabled, the configured code character speed (keyboard sender speed) is used
    for the Morse Reader (this is how MorseKOB and older versions of PyKOB operate).

    Parameters
    ----------
    b : string 'true/false'
        The enable/disable state to set as a string. Values of `YES`|`ON`|`TRUE`
        will enable decoding at the detected speed. Values of `NO`|`OFF`|`FALSE` 
        will decode at the configured character speed.
    """
    global decode_at_detected
    try:
        decode_at_detected = strtobool(str(b))
        user_config.set(_CONFIG_SECTION, _DECODE_AT_DETECTED_KEY, util.on_off_from_bool(decode_at_detected))
    except ValueError as ex:
        log.err("DECODE AT DETECTED value '{}' is not a valid boolean value. Not setting value.".format(ex.args[0]))
        raise
    return

def set_interface_type(s):
    """Sets the Interface Type (for Key-Sounder, Loop or Keyer)

    Parameters
    ----------
    s : str
        The value `KS|KEY_SOUNDER` will set the interface type to 'InterfaceType.key_sounder'.
        The value `L|LOOP` will set the interface type to 'InterfaceType.loop'.
        The value `K|KEYER` will set the interface type to 'InterfaceType.keyer'.
    """
    global interface_type
    interface_type = interface_type_from_str(s)
    user_config.set(_CONFIG_SECTION, _INTERFACE_TYPE_KEY, interface_type.name.upper())


def set_invert_key_input(b):
    """
    Enable/disable key input signal (DSR) invert.

    When key-invert is enabled, the key input (DSR on the serial interface)
    is inverted (because the RS-232 logic is inverted). This is primarily used
    when the input is from a modem (in dial-up connection).

    Parameters
    ----------
    b : string 'true/false'
        The enable/disable state to set as a string. Values of `YES`|`ON`|`TRUE`
        will enable key invert. Values of `NO`|`OFF`|`FALSE` will disable key invert.
    """
    global invert_key_input
    try:
        invert_key_input = strtobool(str(b))
        user_config.set(_CONFIG_SECTION, _INVERT_KEY_INPUT_KEY, util.on_off_from_bool(invert_key_input))
    except ValueError as ex:
        log.err("INVERT KEY INPUT value '{}' is not a valid boolean value. Not setting value.".format(ex.args[0]))
        raise

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
        user_config.set(_CONFIG_SECTION, _LOCAL_KEY, util.on_off_from_bool(local))
    except ValueError as ex:
        log.err("LOCAL value '{}' is not a valid boolean value. Not setting value.".format(ex.args[0]))
        raise

def set_min_char_speed(s: str):
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

    try:
        _speed = int(s)
        set_min_char_speed_int(_speed)
    except ValueError as ex:
        log.err("CHARS value '{}' is not a valid integer value. Not setting CWPM value.".format(ex.args[0]))
        raise

def set_min_char_speed_int(si: int):
    global min_char_speed
    min_char_speed = si
    user_config.set(_CONFIG_SECTION, _MIN_CHAR_SPEED_KEY, str(min_char_speed))

def set_no_key_closer(b):
    """Enable/disable whether the (physical) key has a closer.

    If the key doesn't have a physical closer, applications might adapt by
    implementing some type of virtual closer.

    Parameters
    ----------
    b : str
        The enable/disable state to set as a string. Values of `YES`|`ON`|`TRUE`
        will indicate the key has no closer. Values of `NO`|`OFF`|`FALSE` indicate a key with a closer.
    """
    global no_key_closer
    try:
        no_key_closer = strtobool(str(b))
        user_config.set(_CONFIG_SECTION, _NO_KEY_CLOSER_KEY, util.on_off_from_bool(no_key_closer))
    except ValueError as ex:
        log.err("No key closer value '{}' is not a valid boolean value. Not setting value.".format(ex.args[0]))
        raise
    return

def set_remote(r):
    """Enable/disable remote send

    When remote send is enabled, the content will be sent to the
    wire configured.

    Parameters
    ----------
    r : str
        The enable/disable state to set as a string. Values of `YES`|`ON`|`TRUE`
        will enable remote send. Values of `NO`|`OFF`|`FALSE` will disable remote send.
    """
    global remote
    try:
        remote = strtobool(str(r))
        user_config.set(_CONFIG_SECTION, _REMOTE_KEY, util.on_off_from_bool(remote))
    except ValueError as ex:
        log.err("REMOTE value '{}' is not a valid boolean value. Not setting value.".format(ex.args[0]))
        raise
    return

def set_serial_port(p):
    """Sets the name/path of the serial/tty port to use for a
    key+sounder/loop interface

    Parameters
    ----------
    p : str
        The 'COM' port for Windows, the 'tty' device path for Mac and Linux
    """

    global serial_port
    serial_port = util.str_none_or_value(p)
    app_config.set(_CONFIG_SECTION, _SERIAL_PORT_KEY, serial_port)

def set_gpio(s):
    """Sets the key/sounder interface to Raspberry Pi GPIO

    When set to `True` via a value of "TRUE"/"ON"/"YES" the application should
    enable the GPIO interface to the key/sounder.

    Parameters
    ----------
    s : str
        The enable/disable state to set as a string. Values of `YES`|`ON`|`TRUE`
        will enable GPIO interface. Values of `NO`|`OFF`|`FALSE` will disable GPIO.
        Serial port will become active (if configured for sounder = ON)
    """

    global gpio
    try:
        gpio = strtobool(str(s))
        app_config.set(_CONFIG_SECTION, _GPIO_KEY, util.on_off_from_bool(gpio))
    except ValueError as ex:
        log.err("GPIO value '{}' is not a valid boolean value. Not setting value.".format(ex.args[0]))
        raise

def set_server_url(s):
    """Sets the KOB Server URL to connect to for wires

    Parameters
    ----------
    s : str
        The KOB Server URL or None. Also set to None if the value is 'DEFAULT'.
    """

    global server_url
    server_url = util.str_none_or_value(s)
    if server_url and server_url.upper() == 'DEFAULT':
        server_url = None
    user_config.set(_CONFIG_SECTION, _SERVER_URL_KEY, server_url)

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
        user_config.set(_CONFIG_SECTION, _SOUND_KEY, util.on_off_from_bool(sound))
    except ValueError as ex:
        log.err("SOUND value '{}' is not a valid boolean value. Not setting value.".format(ex.args[0]))
        raise

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
        user_config.set(_CONFIG_SECTION, _SOUNDER_KEY, util.on_off_from_bool(sounder))
    except ValueError as ex:
        log.err("SOUNDER value '{}' is not a valid boolean value. Not setting value.".format(ex.args[0]))
        raise

def set_sounder_power_save(s):
    """Sets the time (in seconds) to delay before de-energizing the sounder to save power

    To save power, reduce fire risk, etc. the sounder drive circuit will be de-energized after
    this many seconds of idle time. Setting this to zero (0) will disable the power save functionality.

    Parameters
    ----------
    s : str
        The number of idle seconds before power-save as an interger string value
    """

    global sounder_power_save
    try:
        _seconds = int(s)
        sounder_power_save = _seconds if _seconds >= 0 else 0
        user_config.set(_CONFIG_SECTION, _SOUNDER_POWER_SAVE_KEY, str(sounder_power_save))
    except ValueError as ex:
        log.err("Idle time '{}' is not a valid integer value. Not setting SounderPowerSave value.".format(ex.args[0]))
        raise

def spacing_from_str(s):
    """
    Spacing object (for Farnsworth timing) from the string representation of
    "None" (disabled) `Spacing.none`,
    "Character" `Spacing.char`
    "Word" `Spacing.word`

    Parameters
    ----------
    s : str
        The value `N|NONE` will return `Spacing.none` (disabled).
        The value `C|CHAR` will return `Spacing.char`.
        The value `W|WORD` will return `Spacing.word`.
    """
    s = s.upper()
    if s=="N" or s=="NONE":
        return Spacing.none
    elif s=="C" or s=="CHAR" or s=="CHARACTER":
        return Spacing.char
    elif s=="W" or s=="WORD":
        return Spacing.word
    else:
        msg = "SPACING value '{}' is not a valid `Spacing` value of 'NONE', 'CHAR' or 'WORD'.".format(s)
        log.err(msg)
        raise ValueError(msg)

def set_spacing(s):
    """
    Sets the Spacing (for Farnsworth timing) to None (disabled) `Spacing.none`,
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
    spacing = spacing_from_str(s)
    user_config.set(_CONFIG_SECTION, _SPACING_KEY, spacing.name.upper())


def set_station(s):
    """Sets the Station ID to use when connecting to a wire

    Parameters
    ----------
    s : str
        The Station ID
    """

    global station
    station = util.str_none_or_value(s)
    user_config.set(_CONFIG_SECTION, _STATION_KEY, station)

def set_wire(w: str):
    """Sets the wire to connect to

    Parameters
    ----------
    w : str
        The Wire number
    """

    try:
        _wire = int(w)
        set_wire_int(_wire)
    except ValueError as ex:
        log.err("Wire number value '{}' is not a valid integer value.".format(ex.args[0]))
        raise

def set_wire_int(w: int):
    global wire
    wire = w
    user_config.set(_CONFIG_SECTION, _WIRE_KEY, str(w))

def set_text_speed(s: str):
    """Sets the Text (code) speed in words per minute

    Parameters
    ----------
    s : str
        The text speed in words-per-minute as an interger string value
    """
    try:
        _speed = int(s)
        set_text_speed_int(_speed)
    except ValueError as ex:
        log.err("Text speed value '{}' is not a valid integer value.".format(ex.args[0]))
        raise

def set_text_speed_int(s: int):
    global text_speed
    text_speed = s
    user_config.set(_CONFIG_SECTION, _TEXT_SPEED_KEY, str(text_speed))

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
    print("Platform:", platform_name)
    print("PyKOB:", pykob_version)
    print("Python:", python_version)
    print("PyAudio:", pyaudio_version)
    print("PySerial:", pyserial_version)
    print("Host:", hostname)

def print_config():
    """Print the PyKOB configuration
    """
    url = util.str_none_or_value(server_url)
    url = url if url else ''
    print("======================================")
    print("Serial serial_port: '{}'".format(serial_port))
    print("GPIO interface (Raspberry Pi):", util.on_off_from_bool(gpio))
    print("--------------------------------------")
    print("Audio type:", audio_type.name.upper())
    print("Auto Connect to Wire:", util.on_off_from_bool(auto_connect))
    print("Code type:", code_type.name.upper())
    print("Decode using detected speed:", util.on_off_from_bool(decode_at_detected))
    print("Interface type:", interface_type.name.upper())
    print("Invert key input:", util.on_off_from_bool(invert_key_input))
    print("Local copy:", util.on_off_from_bool(local))
    print("No key closer:", util.true_false_from_bool(no_key_closer))
    print("Remote send:", util.on_off_from_bool(remote))
    print("KOB Server URL:", url)
    print("Sound:", util.on_off_from_bool(sound))
    print("Sounder:", util.on_off_from_bool(sounder))
    print("Sounder Power Save (seconds):", sounder_power_save)
    print("Spacing:", spacing.name.upper())
    print("Station: '{}'".format(util.str_none_or_value(station)))
    print("Wire:", wire)
    print("Character speed", min_char_speed)
    print("Words per min speed:", text_speed)
    print()
    print("Logging level:", logging_level)

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
    global pykob_version
    global python_version
    global pyaudio_version
    global pyserial_version
    global system_name
    global system_version
    global app_config
    global app_config_dir
    global app_config_file_path
    global user_config
    global user_config_dir
    global user_config_file_path
    global user_home
    global user_name
    #
    global serial_port
    global gpio
    #
    global audio_type
    global auto_connect
    global code_type
    global decode_at_detected
    global logging_level
    global interface_type
    global invert_key_input
    global local
    global min_char_speed
    global no_key_closer
    global remote
    global server_url
    global sound
    global sounder
    global sounder_power_save
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
        pykob_version = pykob.VERSION
        python_version = "{}.{}.{}".format(sys.version_info.major, sys.version_info.minor, sys.version_info.micro)
        try:
            import pyaudio
            pyaudio_version = pyaudio.__version__ # NOTE: Using '__" property - not recommended, but only way to get version
        except:
            pyaudio_version = "PyAudio is not installed or the version information is not available (check installation)"
        try:
            import serial
            pyserial_version = serial.VERSION
        except:
            pyserial_version = "PySerial is not installed or the version information is not available (check installation)"
        hostname = socket.gethostname()

        # User configuration file name
        userConfigFileName = "config2-{}.ini".format(user_name)
        app_configFileName = "config2_app.ini"

        # Create the user and application configuration paths
        if system_name == "Windows":
            user_config_file_path = os.path.join(os.environ["LOCALAPPDATA"], os.path.normcase(os.path.join(_APP_NAME, userConfigFileName)))
            app_config_file_path = os.path.join(os.environ["ProgramData"], os.path.normcase(os.path.join(_APP_NAME, app_configFileName)))
        elif system_name == "Linux" or system_name == "Darwin": # Linux or Mac
            user_config_file_path = os.path.join(user_home, os.path.normcase(os.path.join(".{}".format(_APP_NAME), userConfigFileName)))
            app_config_file_path = os.path.join(user_home, os.path.normcase(os.path.join(".{}".format(_APP_NAME), app_configFileName)))
        else:
            log.err("Unknown System name")
            exit
        if user_config_dir is None:
            user_config_dir = os.path.dirname(user_config_file_path)
        if app_config_dir is None:
            app_config_dir = os.path.dirname(app_config_file_path)
    except KeyError as ex:
        log.err("Key '{}' not found in environment.".format(ex.args[0]))
        exit

    create_config_files_if_needed()

    user_config_defaults = {
        _AUDIO_TYPE_KEY:"SOUNDER",
        _AUTO_CONNECT_KEY:"OFF",
        _CODE_TYPE_KEY:"AMERICAN",
        _DECODE_AT_DETECTED_KEY:"OFF",
        _INTERFACE_TYPE_KEY:"LOOP",
        _INVERT_KEY_INPUT_KEY:"OFF",
        _LOCAL_KEY:"ON",
        _LOGGING_LEVEL_KEY:"0",
        _MIN_CHAR_SPEED_KEY:"18",
        _NO_KEY_CLOSER_KEY:"OFF",
        _REMOTE_KEY:"ON",
        _SERVER_URL_KEY:"NONE",
        _SOUND_KEY:"ON",
        _SOUNDER_KEY:"OFF",
        _SOUNDER_POWER_SAVE_KEY:"60",
        _SPACING_KEY:"NONE",
        _STATION_KEY:"Configure your office/station ID",
        _WIRE_KEY:"101",
        _TEXT_SPEED_KEY:"18"
    }
    app_config_defaults = {"PORT":"", "GPIO":"OFF"}

    user_config = configparser.ConfigParser(defaults=user_config_defaults, allow_no_value=True, default_section=_CONFIG_SECTION)
    app_config = configparser.ConfigParser(defaults=app_config_defaults, allow_no_value=True, default_section=_CONFIG_SECTION)

    user_config.read(user_config_file_path)
    app_config.read(app_config_file_path)

    try:
        ###
        # Get the System (App) config values
        ###
        serial_port = app_config.get(_CONFIG_SECTION, _SERIAL_PORT_KEY)
        # If there isn't a PORT value set PORT to None
        if not serial_port:
            serial_port = None

        # GPIO (Raspberry Pi)
        __option = "GPIO interface"
        __key = _GPIO_KEY
        gpio = app_config.getboolean(_CONFIG_SECTION, __key)

        ###
        # Get the User config values
        ###
        __option = "Audio type"
        __key = _AUDIO_TYPE_KEY
        _audio_type = (user_config.get(_CONFIG_SECTION, __key)).upper()
        if _audio_type == "SOUNDER":
            audio_type = AudioType.SOUNDER
        elif _audio_type == "TONE":
            audio_type = AudioType.TONE
        else:
            raise ValueError(_audio_type)
        __option = "Auto Connect to Wire"
        __key = _AUTO_CONNECT_KEY
        auto_connect = user_config.getboolean(_CONFIG_SECTION, __key)
        __option = "Code type"
        __key = _CODE_TYPE_KEY
        _code_type = (user_config.get(_CONFIG_SECTION, __key)).upper()
        if  _code_type == "AMERICAN":
            code_type = CodeType.american
        elif _code_type == "INTERNATIONAL":
            code_type = CodeType.international
        else:
            raise ValueError(_code_type)
        __option = "Decode at detected speed"
        __key = _DECODE_AT_DETECTED_KEY
        decode_at_detected = user_config.getboolean(_CONFIG_SECTION, __key)
        __option = "Interface type"
        __key = _INTERFACE_TYPE_KEY
        _interface_type = (user_config.get(_CONFIG_SECTION, __key)).upper()
        if _interface_type == "KEY_SOUNDER":
            interface_type = InterfaceType.key_sounder
        elif _interface_type == "LOOP":
            interface_type = InterfaceType.loop
        elif _interface_type == "KEYER":
            interface_type = InterfaceType.keyer
        else:
            raise ValueError(_interface_type)
        __option = "Invert key input"
        __key = _INVERT_KEY_INPUT_KEY
        invert_key_input = user_config.getboolean(_CONFIG_SECTION, __key)
        __option = "Local copy"
        __key = _LOCAL_KEY
        local = user_config.getboolean(_CONFIG_SECTION, __key)
        __option = "Logging Level"
        __key = _LOGGING_LEVEL_KEY
        logging_level = user_config.getint(_CONFIG_SECTION, __key)
        __option = "Minimum character speed"
        __key = _MIN_CHAR_SPEED_KEY
        min_char_speed = user_config.getint(_CONFIG_SECTION, __key)
        __option = "No key closer"
        __key = _NO_KEY_CLOSER_KEY
        no_key_closer = user_config.getboolean(_CONFIG_SECTION, __key)
        __option = "Remote send"
        __key = _REMOTE_KEY
        remote = user_config.getboolean(_CONFIG_SECTION, __key)
        __option = "Text speed"
        __key = _TEXT_SPEED_KEY
        text_speed = user_config.getint(_CONFIG_SECTION, __key)
        __option = "Server URL"
        __key = _SERVER_URL_KEY
        _server_url = user_config.get(_CONFIG_SECTION, __key)
        if (not _server_url) or (_server_url.upper() != "NONE"):
            server_url = _server_url
        __option = "Sound"
        __key = _SOUND_KEY
        sound = user_config.getboolean(_CONFIG_SECTION, __key)
        __option = "Sounder"
        __key = _SOUNDER_KEY
        sounder = user_config.getboolean(_CONFIG_SECTION, __key)
        __option = "Sounder power save (seconds)"
        __key = _SOUNDER_POWER_SAVE_KEY
        sounder_power_save = user_config.getint(_CONFIG_SECTION, __key)
        __option = "Spacing"
        __key = _SPACING_KEY
        _spacing = (user_config.get(_CONFIG_SECTION, __key)).upper()
        if _spacing == "NONE":
            spacing = Spacing.none
        elif _spacing == "CHAR":
            spacing = Spacing.char
        elif _spacing == "WORD":
            spacing = Spacing.word
        else:
            raise ValueError(_spacing)
        __option = "Station"
        __key = _STATION_KEY
        _station = user_config.get(_CONFIG_SECTION, __key)
        if (not _station) or (_station.upper() != "NONE"):
            station = _station
        __option = "Wire"
        __key = _WIRE_KEY
        _wire = user_config.get(_CONFIG_SECTION, __key)
        if (_wire) or (_wire.upper() != "NONE"):
            try:
                wire = int(_wire)
            except ValueError as ex:
                # log.err("Wire number value '{}' is not a valid integer value.".format(_wire))
                wire = 1
    except KeyError as ex:
        log.err("Key '{}' not found in configuration file.".format(ex.args[0]))
        raise
    except ValueError as ex:
        log.err("{} option value '{}' is not a valid value. INI file key: {}.".format(__option, ex.args[0], __key))
        raise

# ### Mainline
read_config()

audio_type_override = argparse.ArgumentParser(add_help=False)
audio_type_override.add_argument(
    "-Z",
    "--audiotype",
    default=audio_type.name.upper(),
    help="The audio type (SOUNDER|TONE) to use.",
    metavar="audio-type",
    dest="audio_type",
)

auto_connect_override = argparse.ArgumentParser(add_help=False)
auto_connect_override.add_argument("-C", "--autoconnect", default="ON" if auto_connect else "OFF",
choices=["ON", "On", "on", "YES", "Yes", "yes", "OFF", "Off", "off", "NO", "No", "no"],
help="'ON' or 'OFF' to indicate whether an application should automatically connect to a configured wire.",
metavar="auto-connect", dest="auto_connect")

code_type_override = argparse.ArgumentParser(add_help=False)
code_type_override.add_argument("-T", "--type", default=code_type.name.upper(),
help="The code type (AMERICAN|INTERNATIONAL) to use.", metavar="code-type", dest="code_type")

decode_at_detected_override = argparse.ArgumentParser(add_help=False)
decode_at_detected_override.add_argument("-D", "--decode-at-detected", default=decode_at_detected,
help="True/False to Enable/Disable decoding Morse at the detected speed.", metavar="use-detected-speed", dest="decode_at_detected")

interface_type_override = argparse.ArgumentParser(add_help=False)
interface_type_override.add_argument("-I", "--interface", default=interface_type.name.upper(),
help="The interface type (KEY_SOUNDER|LOOP|KEYER) to use.", metavar="interface-type", dest="interface_type")

invert_key_input_override = argparse.ArgumentParser(add_help=False)
invert_key_input_override.add_argument("-M", "--iki", default=invert_key_input,
help="True/False to Enable/Disable inverting the key input signal (used for dial-up/modem connections).", metavar="invert-key-input", dest="invert_key_input")

local_override = argparse.ArgumentParser(add_help=False)
local_override.add_argument(
    "-L",
    "--local",
    default=local,
    help="'ON' or 'OFF' to Enable/Disable sounding of local code.",
    metavar="local-copy",
    dest="local",
)

logging_level_override = argparse.ArgumentParser(add_help=False)
logging_level_override.add_argument(
    "--logging-level",
    metavar="logging-level",
    dest="logging_level",
    type=int,
    help="Logging level. A value of '0' disables DEBUG output, '-1' disables INFO, '-2' disables WARN, '-3' disables ERROR. Higher values above '0' enable more DEBUG output."
)

min_char_speed_override = argparse.ArgumentParser(add_help=False)
min_char_speed_override.add_argument("-c", "--charspeed", default=min_char_speed, type=int,
help="The minimum character speed to use in words per minute (used for Farnsworth timing).",
metavar="wpm", dest="min_char_speed")

no_key_closer_override = argparse.ArgumentParser(add_help=False)
no_key_closer_override.add_argument(
    "-X",
    "--no-key-closer",
    default=no_key_closer,
    help="'TRUE' or 'FALSE' to indicate if the physical key does not have a closer.",
    metavar="no-closer",
    dest="no_key_closer",
)

remote_override = argparse.ArgumentParser(add_help=False)
remote_override.add_argument(
    "-R",
    "--remote",
    default=remote,
    help="'ON' or 'OFF' to Enable/Disable sending code to the connected wire (internet).",
    metavar="remote-send",
    dest="remote",
)

server_url_override = argparse.ArgumentParser(add_help=False)
server_url_override.add_argument("-U", "--url", default=server_url,
help="The KOB Server URL to use (or 'NONE' to use the default).", metavar="url", dest="server_url")

serial_port_override = argparse.ArgumentParser(add_help=False)
serial_port_override.add_argument("-p", "--port", default=serial_port,
help="The name of the serial port to use (or 'NONE').", metavar="portname", dest="serial_port")

gpio_override = argparse.ArgumentParser(add_help=False)
gpio_override.add_argument(
    "-g",
    "--gpio",
    default="ON" if gpio else "OFF",
    choices=["ON","On","on","YES","Yes","yes","OFF","Off","off","NO","No","no"],
    help="'ON' or 'OFF' to indicate whether GPIO (Raspberry Pi) key/sounder interface should be used.\
 GPIO takes priority over the serial interface if both are specified.",
    metavar="gpio",
    dest="gpio",
)

sound_override = argparse.ArgumentParser(add_help=False)
sound_override.add_argument("-a", "--sound", default="ON" if sound else "OFF",
choices=["ON", "On", "on", "YES", "Yes", "yes", "OFF", "Off", "off", "NO", "No", "no"],
help="'ON' or 'OFF' to indicate whether computer audio should be used to sound code.",
metavar="sound", dest="sound")

sounder_override = argparse.ArgumentParser(add_help=False)
sounder_override.add_argument("-A", "--sounder", default="ON" if sounder else "OFF",
choices=["ON", "On", "on", "YES", "Yes", "yes", "OFF", "Off", "off", "NO", "No", "no"],
help="'ON' or 'OFF' to indicate whether to use sounder if 'gpio' or `port` is configured.",
metavar="sounder", dest="sounder")

sounder_pwrsv_override = argparse.ArgumentParser(add_help=False)
sounder_pwrsv_override.add_argument("-P", "--pwrsv", default=sounder_power_save, type=int,
help="The sounder power-save delay in seconds, or '0' to disable power-save.",
metavar="seconds", dest="sounder_power_save")

spacing_override = argparse.ArgumentParser(add_help=False)
spacing_override.add_argument(
    "-s",
    "--spacing",
    default=spacing.name.upper(),
    help="Where to add spacing for Farnsworth (NONE|CHAR|WORD).",
    metavar="spacing",
    dest="spacing",
)

station_override = argparse.ArgumentParser(add_help=False)
station_override.add_argument("-S", "--station", default=station,
help="The Station ID to use (or 'NONE').", metavar="station", dest="station")

text_speed_override = argparse.ArgumentParser(add_help=False)
text_speed_override.add_argument(
    "-t",
    "--textspeed",
    default=text_speed,
    type=int,
    help="The morse text speed in words per minute. Used for Farnsworth timing. "
    + "Spacing must not be 'NONE' to enable Farnsworth.",
    metavar="wpm",
    dest="text_speed",
)

wire_override = argparse.ArgumentParser(add_help=False)
wire_override.add_argument("-W", "--wire", default=wire,
help="The Wire to use (or 'NONE').", metavar="wire", dest="wire")
