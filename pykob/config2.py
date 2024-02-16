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
config class module

Class that holds current configuration values and can read and write to
configuration files. It can read and write the global configuration information
but is intended to be used for newer multiple-configuration operation. This is
to allow users to have multiple configuration files and select between them,
or to run multiple copies of the applications simultaniously with different
configurations for each (something that can't be done with the current 'global'
config module).

A mechanism for change notification is available.

"""
import argparse
from enum import IntEnum, unique
import json
import sys
from typing import Any, Callable, Optional

from pykob import config
from pykob.config import CodeType, InterfaceType, Spacing

PYKOB_CFG_EXT = ".pkcfg"

def add_ext_if_needed(s: str) -> str:
    if s and not s.endswith(".pkcfg"):
        return (s + PYKOB_CFG_EXT)
    return s

@unique
class ChangeType(IntEnum):
    hardware = 1
    morse = 2
    operations = 4

class Config:
    def __init__(self) -> None:
        # Hardware Settings
        self._gpio: bool = False
        self._serial_port: Optional[str] = None
        self._interface_type: InterfaceType = InterfaceType.loop
        self._invert_key_input: bool = False
        self._sounder_power_save: int = 0
        # Morse Settings
        self._code_type: CodeType = CodeType.american
        self._min_char_speed: int = 18
        self._spacing: Spacing = Spacing.none
        self._text_speed: int = 18
        # Operational Settings
        self._auto_connect: bool = False
        self._local: bool = True
        self._remote: bool = True
        self._server_url: Optional[str] = None
        self._sound: bool = True
        self._sounder: bool = False
        self._station: str = ""
        self._wire: int = 0
        #
        # Change tracking
        self._hw_chng: bool = False
        self._morse_chng: bool = False
        self._ops_chng: bool = False
        self._pause_notify: bool = False
        #
        # Our operational values
        self._filepath: Optional[str] = None  # The path used to load or last saved to
        #
        # Key to property setter dictionary
        self._key_prop_setters: dict[str,Any] = {
            config._GPIO_KEY: self._set_gpio,
            config._SERIAL_PORT_KEY: self._set_serial_port,
            config._INTERFACE_TYPE_KEY: self._set_interface_type,
            config._INVERT_KEY_INPUT_KEY: self._set_invert_key_input,
            config._SOUNDER_POWER_SAVE_KEY: self._set_sounder_power_save,
            config._AUTO_CONNECT_KEY: self._set_auto_connect,
            config._LOCAL_KEY: self._set_local,
            config._REMOTE_KEY: self._set_remote,
            config._SERVER_URL_KEY: self._set_server_url,
            config._SOUND_KEY: self._set_sound,
            config._SOUNDER_KEY: self._set_sounder,
            config._STATION_KEY: self._set_station,
            config._WIRE_KEY: self._set_wire,
            config._CODE_TYPE_KEY: self._set_code_type,
            config._MIN_CHAR_SPEED_KEY: self._set_min_char_speed,
            config._SPACING_KEY: self._set_spacing,
            config._TEXT_SPEED_KEY: self._set_text_speed
        }
        #
        # Listeners is a dictionary of Callable(int) keys and int (ChangeType...) values.
        self._change_listeners: dict[Callable[[int],None],int] = {}  # Start out empty
        self._dirty = False


    def _notify_listeners(self):
        """
        Notify interested parties of changes
        """
        if self._pause_notify:
            return
        # Collect all of the change types
        ct = 0
        if self._hw_chng:
            ct = ct | ChangeType.hardware
        if self._morse_chng:
            ct = ct | ChangeType.morse
        if self._ops_chng:
            ct = ct | ChangeType.operations
        for listener, change_types in self._change_listeners.items():
            if not ((ct & change_types) == 0):
                # Call the listener with the change types
                listener(ct)
        self._hw_chng = False
        self._morse_chng = False
        self._ops_chng = False

    def _changed_hw(self):
        """
        Hardware settings changed.
        """
        self._hw_chng = True
        self._dirty = True
        self._notify_listeners()

    def _changed_morse(self):
        """
        Morse settings changed.
        """
        self._morse_chng = True
        self._dirty = True
        self._notify_listeners()

    def _changed_ops(self):
        """
        Operational settings changed.
        """
        self._ops_chng = True
        self._dirty = True
        self._notify_listeners()


    # ########################################################################
    # Hardware Settings
    #

    @property
    def gpio(self) -> bool:
        return self._gpio
    @gpio.setter
    def gpio(self, v: bool) -> None:
        x = self._gpio
        self._gpio = v
        if not v == x:
            self._changed_hw()
    def _set_gpio(self, v: bool) -> None:
        self.gpio = v

    @property
    def serial_port(self) -> str:
        return self._serial_port
    @serial_port.setter
    def serial_port(self, v: str) -> None:
        x = self._serial_port
        self._serial_port = v
        if not v == x:
            self._changed_hw()
    def _set_serial_port(self, v: str) -> None:
        self.serial_port = v

    @property
    def interface_type(self) -> InterfaceType:
        return self._interface_type
    @interface_type.setter
    def interface_type(self, v: InterfaceType) -> None:
        x = self._interface_type
        self._interface_type = v
        if not v == x:
            self._changed_hw()
    def _set_interface_type(self, v: str) -> None:
        o = config.interface_type_from_str(v)
        self.interface_type = o

    @property
    def invert_key_input(self) -> bool:
        return self._invert_key_input
    @invert_key_input.setter
    def invert_key_input(self, v: bool) -> None:
        x = self._invert_key_input
        self._invert_key_input = v
        if not v == x:
            self._changed_hw()
    def _set_invert_key_input(self, v: bool) -> None:
        self.invert_key_input = v

    @property
    def sounder_power_save(self) -> int:
        return self._sounder_power_save
    @sounder_power_save.setter
    def sounder_power_save(self, v: int) -> None:
        x = self._sounder_power_save
        self._sounder_power_save = v
        if not v == x:
            self._changed_hw()
    def _set_sounder_power_save(self, v: int) -> None:
        self.sounder_power_save = v

    # ########################################################################
    # Morse Settings
    #

    @property
    def code_type(self) -> CodeType:
        return self._code_type
    @code_type.setter
    def code_type(self, v: CodeType) -> None:
        x = self._code_type
        self._code_type = v
        if not v == x:
            self._changed_morse()
    def _set_code_type(self, v: str) -> None:
        o = config.code_type_from_str(v)
        self.code_type = o

    @property
    def min_char_speed(self) -> int:
        return self._min_char_speed
    @min_char_speed.setter
    def min_char_speed(self, v: int) -> None:
        x = self._min_char_speed
        self._min_char_speed = v
        if not v == x:
            self._changed_morse()
    def _set_min_char_speed(self, v: int) -> None:
        self.min_char_speed = v

    @property
    def spacing(self) -> Spacing:
        return self._spacing
    @spacing.setter
    def spacing(self, v: Spacing) -> None:
        x = self._spacing
        self._spacing = v
        if not v == x:
            self._changed_morse()
    def _set_spacing(self, v: Spacing) -> None:
        o = config.spacing_from_str(v)
        self.spacing = o

    @property
    def text_speed(self) -> CodeType:
        return self._text_speed
    @text_speed.setter
    def text_speed(self, v: CodeType) -> None:
        x = self._text_speed
        self._text_speed = v
        if not v == x:
            self._changed_morse()
    def _set_text_speed(self, v: CodeType) -> None:
        self.text_speed = v

    # ########################################################################
    # Operational Settings
    #

    @property
    def auto_connect(self) -> bool:
        return self._auto_connect
    @auto_connect.setter
    def auto_connect(self, v: bool) -> None:
        x = self._auto_connect
        self._auto_connect = v
        if not v == x:
            self._changed_ops()
    def _set_auto_connect(self, v: bool) -> None:
        self.auto_connect = v

    @property
    def local(self) -> bool:
        return self._local
    @local.setter
    def local(self, v: bool) -> None:
        x = self._local
        self._local = v
        if not v == x:
            self._changed_ops()
    def _set_local(self, v: bool) -> None:
        self.local = v

    @property
    def remote(self) -> bool:
        return self._remote
    @remote.setter
    def remote(self, v: bool) -> None:
        x = self._remote
        self._remote = v
        if not v == x:
            self._changed_ops()
    def _set_remote(self, v: bool) -> None:
        self.remote = v

    @property
    def server_url(self) -> Optional[str]:
        return self._server_url
    @server_url.setter
    def server_url(self, v: Optional[str]) -> None:
        x = self._server_url
        self._server_url = v
        if not v == x:
            self._changed_ops()
    def _set_server_url(self, v: Optional[str]) -> None:
        self.server_url = v

    @property
    def sound(self) -> bool:
        return self._sound
    @sound.setter
    def sound(self, v: bool) -> None:
        x = self._sound
        self._sound = v
        if not v == x:
            self._changed_ops()
    def _set_sound(self, v: bool) -> None:
        self.sound = v

    @property
    def sounder(self) -> bool:
        return self._sounder
    @sounder.setter
    def sounder(self, v: bool) -> None:
        x = self._sounder
        self._sounder = v
        if not v == x:
            self._changed_ops()
    def _set_sounder(self, v: bool) -> None:
        self.sounder = v

    @property
    def station(self) -> str:
        return self._station
    @station.setter
    def station(self, v: str) -> None:
        x = self._station
        self._station = v
        if not v == x:
            self._changed_ops()
    def _set_station(self, v: str) -> None:
        self.station = v

    @property
    def wire(self) -> int:
        return self._wire
    @wire.setter
    def wire(self, v: int) -> None:
        x = self._wire
        self._wire = v
        if not v == x:
            self._changed_ops()
    def _set_wire(self, v: int) -> None:
        self.wire = v

    # ########################################################################

    def clear_dirty(self):
        """
        Clear the 'dirty' status.

        The dirty status is internally managed (set when values change and
        cleared when the configuration is saved), but this can be used
        to override the dirty status to indicate that the configuration is
        not dirty.
        """
        self._dirty = False

    def copy(self):
        cfg = Config()
        cfg.copy_from(self)
        return cfg

    def copy_from(self, cfg_src):
        """
        Copy all values from a source config to this config.
        """
        pause_notify = self._pause_notify  # Save current pause-notify state
        self._pause_notify = True  # Hold off notifications while we set everything
        # Use the 'properties' to set the values in order to properly flag changes
        # Hardware Settings
        self.gpio = cfg_src._gpio
        self.serial_port = cfg_src._serial_port
        self.interface_type = cfg_src._interface_type
        self.invert_key_input = cfg_src._invert_key_input
        self.sounder_power_save = cfg_src._sounder_power_save
        # App Operation Settings
        self.auto_connect = cfg_src._auto_connect
        self.local = cfg_src._local
        self.remote = cfg_src._remote
        self.server_url = cfg_src._server_url
        self.sound = cfg_src._sound
        self.sounder = cfg_src._sounder
        self.station = cfg_src._station
        self.wire = cfg_src._wire
        # Morse Settings
        self.code_type = cfg_src._code_type
        self.min_char_speed = cfg_src._min_char_speed
        self.spacing = cfg_src._spacing
        self.text_speed = cfg_src._text_speed
        self._pause_notify = pause_notify  # Put the state back and notify
        self._notify_listeners()

    def get_data(self) -> dict[str,Any]:
        """
        Get the complete config data as a Dictionary.
        """
        data = {
            config._GPIO_KEY: self._gpio,
            config._SERIAL_PORT_KEY: self._serial_port,
            config._INTERFACE_TYPE_KEY: self._interface_type.name.upper(),
            config._INVERT_KEY_INPUT_KEY: self._invert_key_input,
            config._SOUNDER_POWER_SAVE_KEY: self._sounder_power_save,
            config._AUTO_CONNECT_KEY: self._auto_connect,
            config._LOCAL_KEY: self._local,
            config._REMOTE_KEY: self._remote,
            config._SERVER_URL_KEY: self._server_url,
            config._SOUND_KEY: self._sound,
            config._SOUNDER_KEY: self._sounder,
            config._STATION_KEY: self._station,
            config._WIRE_KEY: self._wire,
            config._CODE_TYPE_KEY: self._code_type.name.upper(),
            config._MIN_CHAR_SPEED_KEY: self._min_char_speed,
            config._SPACING_KEY: self._spacing.name.upper(),
            config._TEXT_SPEED_KEY: self._text_speed
        }
        return data

    def get_filepath(self) -> Optional[str]:
        """
        The file path used to load from and save to.
        
        Return: File path or None if the path hasn't been established.
        """
        return self._filepath
    
    def is_dirty(self) -> bool:
        """
        True if any values have changed and the configuration has not been successfully saved.
        """
        return self._dirty

    def load_config(self, filepath:Optional[str]=None) -> None:
        """
        Load this config from a Configuration file (json).

        filepath: File path to use. If 'None', use the path last loaded from or saved to.
                If 'None' is supplied, and a path hasn't been established, raise a
                FileNotFoundError exception.

        Raises: FileNotFoundError if a path hasn't been established.
                System may throw other file related exceptions.
        """
        if not filepath and not self._filepath:
            e = FileNotFoundError("File path not yet established")
            raise e
        elif not filepath:
            filepath = self._filepath

        data: dict[str:Any]
        with open(filepath, 'r', encoding="utf-8") as fp:
            data = json.load(fp)
        if data:
            # Disable change notifications until we are complete
            pause_notify = self._pause_notify  # Save current pause-notify state
            self._pause_notify = True
            # Use the 'properties' to set the values in order to properly flag changes
            for key, value in data.items():
                self._key_prop_setters[key](value)
            #
            self._filepath = filepath
            self._pause_notify = pause_notify
            self._notify_listeners()

    def load_from_global(self) -> None:
        """
        Load this config instance from the Global Config.
        """
        # Disable change notifications until we are complete
        pause_notify = self._pause_notify  # Save current pause-notify state
        self._pause_notify = True
        # Use the 'properties' to set the values in order to properly flag changes
        # Hardware Settings
        self.gpio = config.gpio
        self.serial_port = config.serial_port
        self.interface_type = config.interface_type
        self.invert_key_input = config.invert_key_input
        self.sounder_power_save = config.sounder_power_save
        # App Operation Settings
        self.auto_connect = config.auto_connect
        self.local = config.local
        self.remote = config.remote
        self.server_url = config.server_url
        self.sound = config.sound
        self.sounder = config.sounder
        self.station = config.station
        self.wire = config.wire
        # Morse Settings
        self.code_type = config.code_type
        self.min_char_speed = config.min_char_speed
        self.spacing = config.spacing
        self.text_speed = config.text_speed
        #
        self._pause_notify = pause_notify  # Put the state back and notify
        self._notify_listeners()

    def load_to_global(self) -> None:
        """
        Load this config instance into the Global Config
        """
        # Hardware Settings
        config.set_gpio(self._gpio)
        config.set_serial_port(self._serial_port)
        config.set_interface_type(self._interface_type.name)
        config.set_invert_key_input(self._invert_key_input)
        config.set_sounder_power_save(str(self._sounder_power_save))
        # App Operation Settings
        config.set_auto_connect(self._auto_connect)
        config.set_local(self._local)
        config.set_remote(self._remote)
        config.set_server_url(self._server_url)
        config.set_sound(self._sound)
        config.set_sounder(self._sounder)
        config.set_station(self._station)
        config.set_wire_int(self._wire)
        # Morse Settings
        config.set_code_type(self._code_type.name)
        config.set_min_char_speed_int(self._min_char_speed)
        config.set_spacing(self._spacing.name)
        config.set_text_speed_int(self._text_speed)

    def print_config(self, file=sys.stdout) -> None:
        """
        Print this configuration
        """
        url = config.noneOrValueFromStr(self._server_url)
        url = url if url else ''
        f = file
        print("======================================", file=f)
        print("GPIO interface (Raspberry Pi): {}".format(config.onOffFromBool(self._gpio)), file=f)
        print("Serial serial_port: '{}'".format(self._serial_port), file=f)
        print("--------------------------------------", file=f)
        print("Interface type: {}".format(self._interface_type.name.upper()), file=f)
        print("Invert key input: {}".format(config.onOffFromBool(self._invert_key_input)), file=f)
        print("Local copy: {}".format(config.onOffFromBool(self._local)), file=f)
        print("Remote send: {}".format(config.onOffFromBool(self._remote)), file=f)
        print("Sound: {}".format(config.onOffFromBool(self._sound)), file=f)
        print("Sounder: {}".format(config.onOffFromBool(self._sounder)), file=f)
        print("Sounder Power Save (seconds): {}".format(self._sounder_power_save), file=f)
        print("--------------------", file=f)
        print("KOB Server URL: {}".format(url), file=f)
        print("Auto Connect to Wire: {}".format(config.onOffFromBool(self._auto_connect)), file=f)
        print("Wire: {}".format(self._wire), file=f)
        print("Station: '{}'".format(config.noneOrValueFromStr(self._station)), file=f)
        print("--------------------", file=f)
        print("Code type: {}".format(self._code_type.name.upper()), file=f)
        print("Character speed: {}".format(self._min_char_speed), file=f)
        print("Words per min speed: {}".format(self._text_speed), file=f)
        print("Spacing: {}".format(self._spacing.name.upper()), file=f)

    def register_listener(self, listener:Callable[[int],None], change_types: int) -> None:
        """
        Register a change listener to be notified of changes to settings of a given type.

        The change listener method signature is: method(change_types:int)
        It will be called when one or more setting values of the given types changes.
        The method will be called once for changes to any number of settings with the change_types
        parameter indicating all of the types that have changed.

        change_types : int value comprised of one or more ChangeType values (or'ed together)
        """
        # Get the change types for the listener if it is already registered.
        ct = 0
        if listener in self._change_listeners:
            ct = self._change_listeners[listener]
        ct = ct | change_types  # Merge in the requested types
        self._change_listeners[listener] = ct

    def remove_listener(self, listener:Callable[[int],None]) -> None:
        if listener in self._change_listeners:
            del self._change_listeners[listener]

    def save_config(self, filepath:Optional[str]=None):
        """
        Save this configuration.

        filepath: File path to use. If 'None', use the path loaded from or last saved to.
                If 'None' is supplied, and a path hasn't been established, raise a
                FileNotFoundError exception.

        Raises: FileNotFoundError if a path hasn't been established.
                System may throw other file related exceptions.
        """
        if not filepath and not self._filepath:
            e = FileNotFoundError("File path not yet established")
            raise e
        elif not filepath:
            filepath = self._filepath

        data = self.get_data()
        with open(filepath, 'w', encoding="utf-8") as fp:
            json.dump(data, fp)
            fp.write('\n')
        self._filepath = filepath
        self._dirty = False

    def save_global(self) -> None:
        """
        Save our copy of the Global Config.
        """
        config.save_config()

    def set_dirty(self):
        """
        Clear the 'dirty' status.

        The dirty status is internally managed (set when values change and
        cleared when the configuration is saved), but this can be used
        to override the dirty status to indicate that the configuration is
        not dirty.
        """
        self._dirty = True

    def set_filepath(self, filepath:str):
        self._filepath = filepath


# ########################################################################
# Arg Parse parsers for each of the configuration values.
#
# These can be used by applications/utilities to provide standardized
# command-line options processing.
#
# See 'Configure.py' for an example of all of them in use.
#
# ########################################################################
#
auto_connect_override = argparse.ArgumentParser(add_help=False)
auto_connect_override.add_argument("-C", "--autoconnect",
choices=["ON", "On", "on", "YES", "Yes", "yes", "OFF", "Off", "off", "NO", "No", "no"], \
help="'ON' or 'OFF' to indicate whether an application should automatically connect to a configured wire.", \
metavar="auto-connect", dest="auto_connect")

code_type_override = argparse.ArgumentParser(add_help=False)
code_type_override.add_argument("-T", "--type", \
help="The code type (AMERICAN|INTERNATIONAL) to use.", metavar="code-type", dest="code_type")

interface_type_override = argparse.ArgumentParser(add_help=False)
interface_type_override.add_argument("-I", "--interface", \
help="The interface type (KEY_SOUNDER|LOOP|KEYER) to use.", metavar="interface-type", dest="interface_type")

invert_key_input_override = argparse.ArgumentParser(add_help=False)
invert_key_input_override.add_argument("-M", "--iki", \
help="True/False to Enable/Disable inverting the key input signal (used for dial-up/modem connections).", metavar="invert-key-input", dest="invert_key_input")

local_override = argparse.ArgumentParser(add_help=False)
local_override.add_argument("-L", "--local", \
help="True/False to Enable/Disable local copy of transmitted code.", metavar="local-copy", dest="local")

min_char_speed_override = argparse.ArgumentParser(add_help=False)
min_char_speed_override.add_argument("-c", "--charspeed", type=int, \
help="The minimum character speed to use in words per minute.", \
metavar="wpm", dest="min_char_speed")

remote_override = argparse.ArgumentParser(add_help=False)
remote_override.add_argument("-R", "--remote", \
help="True/False to Enable/Disable transmission over the internet on the specified wire.", \
metavar="remote-send", dest="remote")

server_url_override = argparse.ArgumentParser(add_help=False)
server_url_override.add_argument("-U", "--url", \
help="The KOB Server URL to use (or 'NONE' to use the default).", metavar="url", dest="server_url")

serial_port_override = argparse.ArgumentParser(add_help=False)
serial_port_override.add_argument("-p", "--port", \
help="The name of the serial port to use (or 'NONE').", metavar="portname", dest="serial_port")

gpio_override = argparse.ArgumentParser(add_help=False)
gpio_override.add_argument("-g", "--gpio",
choices=["ON", "On", "on", "YES", "Yes", "yes", "OFF", "Off", "off", "NO", "No", "no"], \
help="'ON' or 'OFF' to indicate whether GPIO (Raspberry Pi) key/sounder interface should be used.\
 GPIO takes priority over the serial interface.", \
metavar="gpio", dest="gpio")

sound_override = argparse.ArgumentParser(add_help=False)
sound_override.add_argument("-a", "--sound",
choices=["ON", "On", "on", "YES", "Yes", "yes", "OFF", "Off", "off", "NO", "No", "no"], \
help="'ON' or 'OFF' to indicate whether computer audio should be used to simulate a sounder.", \
metavar="sound", dest="sound")

sounder_override = argparse.ArgumentParser(add_help=False)
sounder_override.add_argument("-A", "--sounder",
choices=["ON", "On", "on", "YES", "Yes", "yes", "OFF", "Off", "off", "NO", "No", "no"], \
help="'ON' or 'OFF' to indicate whether to use sounder if `port` is configured.", \
metavar="sounder", dest="sounder")

sounder_pwrsv_override = argparse.ArgumentParser(add_help=False)
sounder_pwrsv_override.add_argument("-P", "--pwrsv", type=int, \
help="The sounder power-save delay in seconds, or '0' to disable.", \
metavar="seconds", dest="sounder_power_save")

spacing_override = argparse.ArgumentParser(add_help=False)
spacing_override.add_argument("-s", "--spacing", \
help="Where to add spacing for Farnsworth (NONE|CHAR|WORD).", metavar="spacing", dest="spacing")

station_override = argparse.ArgumentParser(add_help=False)
station_override.add_argument("-S", "--station", \
help="The Station ID to use (or 'NONE').", metavar="station", dest="station")

text_speed_override = argparse.ArgumentParser(add_help=False)
text_speed_override.add_argument("-t", "--textspeed", type=int, \
help="The morse text speed in words per minute. Used for Farnsworth timing. Spacing (-s) must not be 'NONE' to enable Farnsworth.", metavar="wpm", dest="text_speed")

wire_override = argparse.ArgumentParser(add_help=False)
wire_override.add_argument("-W", "--wire", type=int, \
help="The Wire to use (or 'NONE').", metavar="wire", dest="wire")


"""
Test code
"""
if __name__ == "__main__":
    # Self-test
    cfg = Config()
    cfg.load_from_global()
    cfg.print_config()
