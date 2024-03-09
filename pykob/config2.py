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
from distutils.util import strtobool
from enum import Flag, IntEnum, unique
import json
from json import JSONDecodeError
import os.path
from pathlib import Path
import sys
from typing import Any, Callable, Optional

from pykob import config, log
from pykob.config import AudioType, CodeType, InterfaceType, Spacing

PYKOB_CFG_EXT = ".pkcfg"
VERSION = "2.0.0"
_PYKOB_CFG_VERSION_KEY = "PYKOB_CFG_VERSION"
_DEBUG_LEVEL_KEY = "DEBUG_LEVEL"

def add_ext_if_needed(s: str) -> str:
    if s and not s.endswith(PYKOB_CFG_EXT):
        return (s + PYKOB_CFG_EXT)
    return s

@unique
class ChangeType(IntEnum):
    NONE            = 0x00
    HARDWARE        = 0x01
    MORSE           = 0x02
    OPERATIONS      = 0x04
    SAVE            = 0x80
    ANY             = 0xFF

class ConfigLoadError(Exception):
    pass

class Config:
    def __enter__(self) -> 'Config':
        """
        Used by 'with' statement.
        """
        self._pause_notify = self._pause_notify + 1
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Used by 'with' statement.
        """
        x = self._pause_notify
        if x > 0:
            x = x - 1
            self._pause_notify = x
            if x == 0:
                self._notify_listeners()
        else:
            self._pause_notify = 0  # Fix erronious value
        return False  # Don't supress exceptions

    def __init__(self) -> None:
        self._version: str = VERSION
        self._version_loaded: Optional[str] = None
        # Hardware Settings
        self._audio_type: AudioType = AudioType.SOUNDER
        self._p_audio_type: AudioType = AudioType.SOUNDER
        self._gpio: bool = False
        self._p_gpio: bool = False
        self._serial_port: Optional[str] = None
        self._p_serial_port: Optional[str] = None
        self._interface_type: InterfaceType = InterfaceType.loop
        self._p_interface_type: InterfaceType = InterfaceType.loop
        self._invert_key_input: bool = False
        self._p_invert_key_input: bool = False
        self._sound: bool = True
        self._p_sound: bool = True
        self._sounder: bool = False
        self._p_sounder: bool = False
        self._sounder_power_save: int = 0
        self._p_sounder_power_save: int = 0
        # Morse Settings
        self._code_type: CodeType = CodeType.american
        self._p_code_type: CodeType = CodeType.american
        self._min_char_speed: int = 18
        self._p_min_char_speed: int = 18
        self._spacing: Spacing = Spacing.none
        self._p_spacing: Spacing = Spacing.none
        self._text_speed: int = 18
        self._p_text_speed: int = 18
        # Operational Settings
        self._auto_connect: bool = False
        self._p_auto_connect: bool = False
        self._debug_level: int = 0
        self._p_debug_level: int = 0
        self._local: bool = True
        self._p_local: bool = True
        self._remote: bool = True
        self._p_remote: bool = True
        self._server_url: Optional[str] = None
        self._p_server_url: Optional[str] = None
        self._station: str = ""
        self._p_station: str = ""
        self._wire: int = 0
        self._p_wire: int = 0
        #
        # Change tracking
        self._hw_chng: bool = False
        self._morse_chng: bool = False
        self._ops_chng: bool = False
        self._saved_chng: bool = False
        self._pause_notify: int = 0
        #
        # Our operational values
        self._dirty = False
        self._filepath: Optional[str] = None  # The path used to load or last saved to
        self._using_global: bool = False
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
            config._AUDIO_TYPE_KEY: self._set_audio_type,
            config._SOUNDER_KEY: self._set_sounder,
            config._STATION_KEY: self._set_station,
            config._WIRE_KEY: self._set_wire,
            config._CODE_TYPE_KEY: self._set_code_type,
            config._MIN_CHAR_SPEED_KEY: self._set_min_char_speed,
            config._SPACING_KEY: self._set_spacing,
            config._TEXT_SPEED_KEY: self._set_text_speed,
            _DEBUG_LEVEL_KEY: self._set_debug_level
        }
        #
        # Listeners is a dictionary of Callable(int) keys and int (ChangeType...) values.
        self._change_listeners: dict[Callable[[int],None],int] = {}  # Start out empty

    def _notify_listeners(self):
        """
        Notify interested parties of changes
        """
        if self._pause_notify > 0:
            return
        # Collect all of the change types
        ct = ChangeType.NONE
        if self._hw_chng:
            ct = ct | ChangeType.HARDWARE
        if self._morse_chng:
            ct = ct | ChangeType.MORSE
        if self._ops_chng:
            ct = ct | ChangeType.OPERATIONS
        if self._saved_chng:
            ct = ct | ChangeType.SAVE
        if not ct == ChangeType.NONE:
            for listener, change_types in self._change_listeners.items():
                if not ((ct & change_types) == 0):
                    # Call the listener with the change types
                    listener(ct)
        self.clear_pending_notifications()

    def _changed_hw(self):
        """
        Hardware settings changed.
        """
        self._hw_chng = True
        self._notify_listeners()

    def _changed_morse(self):
        """
        Morse settings changed.
        """
        self._morse_chng = True
        self._notify_listeners()

    def _changed_ops(self):
        """
        Operational settings changed.
        """
        self._ops_chng = True
        self._notify_listeners()

    # ########################################################################
    # Config (internal) Settings
    #

    @property
    def version(self) -> str:
        return self._version

    @property
    def version_loaded(self) -> Optional[str]:
        return self._version_loaded

    # ########################################################################
    # Hardware Settings
    #

    @property
    def audio_type(self) -> AudioType:
        return self._audio_type

    @audio_type.setter
    def audio_type(self, v: AudioType) -> None:
        x = self._audio_type
        self._audio_type = v
        if not v == x:
            self._changed_hw()

    def _set_audio_type(self, v: str) -> None:
        o = config.audio_type_from_str(v)
        self.audio_type = o

    @property
    def audio_type_p(self) -> AudioType:
        return self._p_audio_type

    @property
    def audio_type_changed(self) -> bool:
        return not self._audio_type == self._p_audio_type

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
    def gpio_p(self) -> bool:
        return self._p_gpio
    @property
    def gpio_changed(self) -> bool:
        return not self._gpio == self._p_gpio

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
    def interface_type_p(self) -> InterfaceType:
        return self._p_interface_type

    @property
    def interface_type_changed(self) -> bool:
        return not self._interface_type == self._p_interface_type

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
    def invert_key_input_p(self) -> bool:
        return self._p_invert_key_input

    @property
    def invert_key_input_changed(self) -> bool:
        return not self._invert_key_input == self._p_invert_key_input

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
    def serial_port_p(self) -> str:
        return self._p_serial_port

    @property
    def serial_port_changed(self) -> bool:
        return not self._serial_port == self._p_serial_port

    @property
    def sound(self) -> bool:
        return self._sound

    @sound.setter
    def sound(self, v: bool) -> None:
        x = self._sound
        self._sound = v
        if not v == x:
            self._changed_hw()

    def _set_sound(self, v: bool) -> None:
        self.sound = v

    @property
    def sound_p(self) -> bool:
        return self._p_sound

    @property
    def sound_changed(self) -> bool:
        return not self._sound == self._p_sound

    @property
    def sounder(self) -> bool:
        return self._sounder

    @sounder.setter
    def sounder(self, v: bool) -> None:
        x = self._sounder
        self._sounder = v
        if not v == x:
            self._changed_hw()

    def _set_sounder(self, v: bool) -> None:
        self.sounder = v

    @property
    def sounder_p(self) -> bool:
        return self._p_sounder

    @property
    def sounder_changed(self) -> bool:
        return not self._sounder == self._p_sounder

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

    @property
    def sounder_power_save_p(self) -> int:
        return self._p_sounder_power_save

    @property
    def sounder_power_save_changed(self) -> bool:
        return not self._sounder_power_save == self._p_sounder_power_save

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
    def code_type_p(self) -> CodeType:
        return self._p_code_type

    @property
    def code_type_changed(self) -> bool:
        return not self._code_type == self._p_code_type

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
    def min_char_speed_p(self) -> int:
        return self._p_min_char_speed

    @property
    def min_char_speed_changed(self) -> bool:
        return not self._min_char_speed == self._p_min_char_speed

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
    def spacing_p(self) -> Spacing:
        return self._p_spacing

    @property
    def spacing_changed(self) -> bool:
        return not self._spacing == self._p_spacing

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

    @property
    def text_speed_p(self) -> CodeType:
        return self._p_text_speed

    @property
    def text_speed_changed(self) -> bool:
        return not self._text_speed == self._p_text_speed

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
    def auto_connect_p(self) -> bool:
        return self._p_auto_connect

    @property
    def auto_connect_changed(self) -> bool:
        return not self._auto_connect == self._p_auto_connect

    @property
    def debug_level(self) -> int:
        return self._debug_level

    @debug_level.setter
    def debug_level(self, v: int) -> None:
        x = self._debug_level
        self._debug_level = v
        if not v == x:
            log.set_debug_level(v)
            self._changed_ops()

    def _set_debug_level(self, v: int) -> None:
        self.debug_level = v

    @property
    def debug_level_p(self) -> int:
        return self._p_debug_level

    @property
    def debug_level_changed(self) -> bool:
        return not self._debug_level == self._p_debug_level

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
    def local_p(self) -> bool:
        return self._p_local

    @property
    def local_changed(self) -> bool:
        return not self._local == self._p_local

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
    def remote_p(self) -> bool:
        return self._p_remote

    @property
    def remote_changed(self) -> bool:
        return not self._remote == self._p_remote

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
    def server_url_p(self) -> Optional[str]:
        return self._p_server_url

    @property
    def server_url_changed(self) -> bool:
        return not self._server_url == self._p_server_url

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
    def station_p(self) -> str:
        return self._p_station

    @property
    def station_changed(self) -> bool:
        return not self._station == self._p_station

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

    @property
    def wire_p(self) -> int:
        return self._p_wire

    @property
    def wire_changed(self) -> bool:
        return not self._wire == self._p_wire

    # ########################################################################

    def clear_pending_notifications(self):
        """
        Clear pending notification flags (as if the notifications had been sent)
        """
        self._hw_chng = False
        self._morse_chng = False
        self._ops_chng = False
        self._saved_chng = False

    def clear_dirty(self):
        """
        Clear the 'dirty' status.

        The dirty status is internally managed (set when values change and
        cleared when the configuration is saved), but this can be used
        to override the dirty status to indicate that the configuration is
        not dirty.
        """
        # Hardware Settings
        self._p_audio_type = self._audio_type
        self._p_gpio = self._gpio
        self._p_serial_port = self._serial_port
        self._p_interface_type = self._interface_type
        self._p_invert_key_input = self._invert_key_input
        self._p_sound = self._sound
        self._p_sounder = self._sounder
        self._p_sounder_power_save = self._sounder_power_save
        # Morse Settings
        self._p_code_type = self._code_type
        self._p_min_char_speed = self._min_char_speed
        self._p_spacing = self._spacing
        self._p_text_speed = self._text_speed
        # Operational Settings
        self._p_auto_connect = self._auto_connect
        self._p_debug_level = self._debug_level
        self._p_local = self._local
        self._p_remote = self._remote
        self._p_server_url = self._server_url
        self._p_station = self._station
        self._p_wire = self._wire
        # The override
        self._dirty = False

    def copy(self):
        cfg = Config()
        cfg.copy_from(self)
        return cfg

    def copy_from(self, cfg_src:'Config'):
        """
        Copy all values from a source config to this config.
        """
        with self.notification_pauser() as muted_cfg:
            # Use the 'properties' to set the values in order to properly flag changes
            # Hardware Settings
            muted_cfg.audio_type = cfg_src._audio_type
            muted_cfg.gpio = cfg_src._gpio
            muted_cfg.serial_port = cfg_src._serial_port
            muted_cfg.interface_type = cfg_src._interface_type
            muted_cfg.invert_key_input = cfg_src._invert_key_input
            muted_cfg.sound = cfg_src._sound
            muted_cfg.sounder = cfg_src._sounder
            muted_cfg.sounder_power_save = cfg_src._sounder_power_save
            # Morse Settings
            muted_cfg.code_type = cfg_src._code_type
            muted_cfg.min_char_speed = cfg_src._min_char_speed
            muted_cfg.spacing = cfg_src._spacing
            muted_cfg.text_speed = cfg_src._text_speed
            # App Operation Settings
            muted_cfg.auto_connect = cfg_src._auto_connect
            muted_cfg.debug_level = cfg_src._debug_level
            muted_cfg.local = cfg_src._local
            muted_cfg.remote = cfg_src._remote
            muted_cfg.server_url = cfg_src._server_url
            muted_cfg.station = cfg_src._station
            muted_cfg.wire = cfg_src._wire

    def get_changes_types(self) -> int:
        """
        Get the combined types of all changes.
        """
        ct = 0
        if self.gpio_changed:
            ct = ct | ChangeType.HARDWARE
        if self.serial_port_changed:
            ct = ct | ChangeType.HARDWARE
        if self.interface_type_changed:
            ct = ct | ChangeType.HARDWARE
        if self.invert_key_input_changed:
            ct = ct | ChangeType.HARDWARE
        if self.sound_changed:
            ct = ct | ChangeType.HARDWARE
        if self.sounder_changed:
            ct = ct | ChangeType.HARDWARE
        if self.sounder_power_save_changed:
            ct = ct | ChangeType.HARDWARE
        if self.code_type_changed:
            ct = ct | ChangeType.MORSE
        if self.min_char_speed_changed:
            ct = ct | ChangeType.MORSE
        if self.spacing_changed:
            ct = ct | ChangeType.MORSE
        if self.text_speed_changed:
            ct = ct | ChangeType.MORSE
        if self.auto_connect_changed:
            ct = ct | ChangeType.OPERATIONS
        if self.local_changed:
            ct = ct | ChangeType.OPERATIONS
        if self.remote_changed:
            ct = ct | ChangeType.OPERATIONS
        if self.server_url_changed:
            ct = ct | ChangeType.OPERATIONS
        if self.station_changed:
            ct = ct | ChangeType.OPERATIONS
        if self.wire_changed:
            ct = ct | ChangeType.OPERATIONS
        if self.debug_level_changed:
            ct = ct | ChangeType.OPERATIONS
        return ct

    def get_data(self) -> dict[str,Any]:
        """
        Get the complete config data as a Dictionary.
        """
        data = {
            _PYKOB_CFG_VERSION_KEY: self._version,
            config._AUDIO_TYPE_KEY: self._audio_type.name.upper(),
            config._GPIO_KEY: self._gpio,
            config._SERIAL_PORT_KEY: self._serial_port,
            config._INTERFACE_TYPE_KEY: self._interface_type.name.upper(),
            config._INVERT_KEY_INPUT_KEY: self._invert_key_input,
            config._SOUNDER_POWER_SAVE_KEY: self._sounder_power_save,
            config._AUTO_CONNECT_KEY: self._auto_connect,
            config._DEBUG_LEVEL_KEY: self._debug_level,
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

    def get_directory(self) -> Optional[str]:
        """
        Get the configuration file directory that the '.pkcfg' file
        was loaded from or last saved to.

        Returns: The name if a configuration was loaded or None if copied or from Global
        """
        dir = None
        if self._filepath:
            p = Path(self._filepath)
            p = p.resolve()
            dir = p.parent
        return dir

    def get_filepath(self) -> Optional[str]:
        """
        The file path used to load from and save to.

        Return: File path or None if the path hasn't been established.
        """
        return self._filepath

    def get_name(self, include_ext:bool=False) -> Optional[str]:
        """
        Get the configuration name. It is the (base) name of the '.pkcfg' file
        used to load the configuration or that it was last saved to.

        include_ext: Set to True to include the file extension
        """
        name = None
        if self._filepath:
            p = Path(self._filepath)
            n = p.name
            if not include_ext:
                n = n.removesuffix(PYKOB_CFG_EXT)
            name = n
        return name

    def is_dirty(self) -> bool:
        """
        True if any values have changed and the configuration has not been successfully saved.
        """
        # The override
        if self._dirty:
            return True
        # Hardware Settings
        if not self._p_audio_type == self._audio_type:
            return True
        if  not self._p_gpio == self._gpio:
            return True
        if  not self._p_serial_port == self._serial_port:
            return True
        if  not self._p_interface_type == self._interface_type:
            return True
        if  not self._p_invert_key_input == self._invert_key_input:
            return True
        if  not self._p_sound == self._sound:
            return True
        if  not self._p_sounder == self._sounder:
            return True
        if  not self._p_sounder_power_save == self._sounder_power_save:
            return True
        # Morse Settings
        if  not self._p_code_type == self._code_type:
            return True
        if  not self._p_min_char_speed == self._min_char_speed:
            return True
        if  not self._p_spacing == self._spacing:
            return True
        if  not self._p_text_speed == self._text_speed:
            return True
        # Operational Settings
        if  not self._p_auto_connect == self._auto_connect:
            return True
        if not self._p_debug_level == self._debug_level:
            return True
        if not self._p_local == self._local:
            return True
        if  not self._p_remote == self._remote:
            return True
        if  not self._p_server_url == self._server_url:
            return True
        if  not self._p_station == self._station:
            return True
        if  not self._p_wire == self._wire:
            return True
        return False

    def load_config(self, filepath:Optional[str]=None) -> None:
        """
        Load this config from a Configuration file (json).

        filepath: File path to use. If 'None', use the path last loaded from or saved to.
                If 'None' is supplied, and a path hasn't been established, raise a
                FileNotFoundError exception.

        Raises: FileNotFoundError if a path hasn't been established.
                System may throw other file related exceptions.
        """
        if not filepath and not self._filepath and not self._using_global:
            e = FileNotFoundError("File path not yet established")
            raise e
        elif not filepath:
            filepath = self._filepath

        if not filepath:
            self.load_from_global()
        else:
            try:
                data: dict[str:Any]
                with open(filepath, 'r', encoding="utf-8") as fp:
                    data = json.load(fp)
                if data:
                    # Disable change notifications until we are complete
                    with self.notification_pauser() as muted_cfg:
                        # Use the 'properties' to set the values in order to properly flag changes
                        muted_cfg._version_loaded = None
                        for key, value in data.items():
                            if _PYKOB_CFG_VERSION_KEY == key:
                                muted_cfg._version_loaded = value
                            else:
                                try:
                                    muted_cfg._key_prop_setters[key](value)
                                except KeyError as ke:
                                    log.debug("Property setter for entry not found: {}".format(ke))
                        #
                        muted_cfg._filepath = filepath
            except JSONDecodeError as jde:
                log.debug(jde)
                raise ConfigLoadError(jde)
            except Exception as ex:
                log.debug(ex)

    def load_from_global(self) -> None:
        """
        Load this config instance from the Global Config.
        """
        try:
            # Disable change notifications until we are complete
            with self.notification_pauser() as muted_cfg:
                # Use the 'properties' to set the values in order to properly flag changes
                # Hardware Settings
                muted_cfg.gpio = config.gpio
                muted_cfg.serial_port = config.serial_port
                muted_cfg.interface_type = config.interface_type
                muted_cfg.invert_key_input = config.invert_key_input
                muted_cfg.sound = config.sound
                muted_cfg.sounder = config.sounder
                muted_cfg.sounder_power_save = config.sounder_power_save
                # Morse Settings
                muted_cfg.code_type = config.code_type
                muted_cfg.min_char_speed = config.min_char_speed
                muted_cfg.spacing = config.spacing
                muted_cfg.text_speed = config.text_speed
                # App Operation Settings
                muted_cfg.auto_connect = config.auto_connect
                muted_cfg.debug_level = config.debug_level
                muted_cfg.local = config.local
                muted_cfg.remote = config.remote
                muted_cfg.server_url = config.server_url
                muted_cfg.station = config.station
                muted_cfg.wire = config.wire
        except Exception as ex:
            log.debug(ex)
            raise

    def load_to_global(self) -> None:
        """
        Load this config instance into the Global Config
        """
        try:
            # Hardware Settings
            config.set_audio_type(self._audio_type.name)
            config.set_gpio(self._gpio)
            config.set_serial_port(self._serial_port)
            config.set_interface_type(self._interface_type.name)
            config.set_invert_key_input(self._invert_key_input)
            config.set_sound(self._sound)
            config.set_sounder(self._sounder)
            config.set_sounder_power_save(str(self._sounder_power_save))
            # App Operation Settings
            config.set_auto_connect(self._auto_connect)
            config.set_debug_level_int(self._debug_level)
            config.set_local(self._local)
            config.set_remote(self._remote)
            config.set_server_url(self._server_url)
            config.set_station(self._station)
            config.set_wire_int(self._wire)
            # Morse Settings
            config.set_code_type(self._code_type.name)
            config.set_min_char_speed_int(self._min_char_speed)
            config.set_spacing(self._spacing.name)
            config.set_text_speed_int(self._text_speed)
        except Exception as ex:
            log.debug(ex)

    def notification_pauser(self) -> 'Config':
        """
        Return 'with' statement pause notify context manager.
        """
        return self

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
        print("Sound: {}".format(config.onOffFromBool(self._sound)), file=f)
        print("Audio Type: {}".format(self._audio_type.name.upper()), file=f)
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
        print("--------------------", file=f)
        print("Local copy: {}".format(config.onOffFromBool(self._local)), file=f)
        print("Remote send: {}".format(config.onOffFromBool(self._remote)), file=f)
        print("Debug level: {}".format(self._debug_level), file=f)

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

    def restore_config(self, clear_dirty:bool=True):
        # Hardware Settings
        self._audio_type = self._p_audio_type
        self._gpio = self._p_gpio
        self._serial_port = self._p_serial_port
        self._interface_type = self._p_interface_type
        self._invert_key_input = self._p_invert_key_input
        self._sound = self._p_sound
        self._sounder = self._p_sounder
        self._sounder_power_save = self._p_sounder_power_save
        # Morse Settings
        self._code_type = self._p_code_type
        self._min_char_speed = self._p_min_char_speed
        self._spacing = self._p_spacing
        self._text_speed = self._p_text_speed
        # Operational Settings
        self._auto_connect = self._p_auto_connect
        self._debug_level = self._p_debug_level
        self._local = self._p_local
        self._remote = self._p_remote
        self._server_url = self._p_server_url
        self._station = self._p_station
        self._wire = self._p_wire
        # The override
        if clear_dirty:
            self._dirty = False

    def save_config(self, filepath:Optional[str]=None):
        """
        Save this configuration.

        filepath: File path to use. If 'None', use the path loaded from or last saved to.
                If 'None' is supplied, and a path hasn't been established, and 'using_global'
                has not been set, raise a FileNotFoundError exception.

        Raises: FileNotFoundError if a path hasn't been established and not using global.
                System may throw other file related exceptions.
        """
        try:
            if not filepath:
                if self.using_global():
                    self.save_global()
                if self._filepath:
                    filepath = self._filepath
            if not filepath:
                e = FileNotFoundError("File path not yet established")
                raise e

            data = self.get_data()
            with open(filepath, 'w', encoding="utf-8") as fp:
                json.dump(data, fp)
                fp.write('\n')
            self.set_filepath(filepath)
            self._saved_chng = True
            self.clear_dirty()
            self._notify_listeners()
        except Exception as ex:
            log.debug(ex)

    def save_global(self) -> None:
        """
        Save our copy to the Global Config.
        """
        self.load_to_global()
        config.save_config()

    def set_dirty(self):
        """
        Set the 'dirty' status.

        The dirty status is internally managed (set when values change and
        cleared when the configuration is saved), but this can be used
        to override the dirty status to indicate that the configuration is
        not dirty.
        """
        self._dirty = True

    def set_filepath(self, filepath:str):
        self._filepath = filepath
        if filepath:
            self._using_global = False

    def set_using_global(self, global_):
        self._using_global = global_
        if self._using_global:
            self._filepath = None

    def using_global(self) -> bool:
        return self._using_global

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
config_file_override = argparse.ArgumentParser(add_help=False)
config_file_override.add_argument("--config", metavar="config-file", dest="pkcfg_filepath",
    help="Configuration file to use. If not specified, the global configuration is used.")

debug_level_override = argparse.ArgumentParser(add_help=False)
debug_level_override.add_argument("--debug-level", metavar="debug-level", dest="debug_level",
    type=int, default=0,
    help="Debug logging level. A value of '0' disables output, higher values enable more output.")

audio_type_override = argparse.ArgumentParser(add_help=False)
audio_type_override.add_argument(
    "-Z",
    "--audiotype",
    metavar="audio-type",
    dest="audio_type",
    help="The audio type (SOUNDER|TONE) to use.",
)

auto_connect_override = argparse.ArgumentParser(add_help=False)
auto_connect_override.add_argument("-C", "--autoconnect", metavar="auto-connect", dest="auto_connect",
    choices=["ON", "On", "on", "YES", "Yes", "yes", "OFF", "Off", "off", "NO", "No", "no"],
    help="'ON' or 'OFF' to indicate whether an application should automatically connect to a configured wire.")

code_type_override = argparse.ArgumentParser(add_help=False)
code_type_override.add_argument("-T", "--type", metavar="code-type", dest="code_type",
    help="The code type (AMERICAN|INTERNATIONAL) to use.")

interface_type_override = argparse.ArgumentParser(add_help=False)
interface_type_override.add_argument("-I", "--interface", metavar="interface-type", dest="interface_type",
    help="The interface type (KEY_SOUNDER|LOOP|KEYER) to use.")

invert_key_input_override = argparse.ArgumentParser(add_help=False)
invert_key_input_override.add_argument("-M", "--iki", metavar="invert-key-input", dest="invert_key_input",
    help="True/False to Enable/Disable inverting the key input signal (used for dial-up/modem connections).")

local_override = argparse.ArgumentParser(add_help=False)
local_override.add_argument("-L", "--local", metavar="local-copy", dest="local",
    help="'ON' or 'OFF' to Enable/Disable sounding of local code.")

min_char_speed_override = argparse.ArgumentParser(add_help=False)
min_char_speed_override.add_argument("-c", "--charspeed", metavar="wpm", dest="min_char_speed", type=int,
    help="The minimum character speed to use in words per minute.")

remote_override = argparse.ArgumentParser(add_help=False)
remote_override.add_argument(
    "-R",
    "--remote",
    metavar="remote-send",
    dest="remote",
    help="'ON' or 'OFF' to Enable/Disable sending code to the connected wire (internet).",
)

server_url_override = argparse.ArgumentParser(add_help=False)
server_url_override.add_argument("-U", "--url", metavar="url", dest="server_url",
    help="The KOB Server URL to use (or 'NONE' to use the default).")

serial_port_override = argparse.ArgumentParser(add_help=False)
serial_port_override.add_argument("-p", "--port", metavar="portname", dest="serial_port",
    help="The name of the serial port to use (or 'NONE').")

gpio_override = argparse.ArgumentParser(add_help=False)
gpio_override.add_argument("-g", "--gpio", metavar="gpio", dest="gpio",
    choices=["ON", "On", "on", "YES", "Yes", "yes", "OFF", "Off", "off", "NO", "No", "no"],
    help="'ON' or 'OFF' to indicate whether GPIO (Raspberry Pi) key/sounder interface should be used." +
        "GPIO takes priority over the serial interface if both are specified.")

sound_override = argparse.ArgumentParser(add_help=False)
sound_override.add_argument("-a", "--sound", metavar="sound", dest="sound",
    choices=["ON", "On", "on", "YES", "Yes", "yes", "OFF", "Off", "off", "NO", "No", "no"],
    help="'ON' or 'OFF' to indicate whether computer audio should be used to sound code.")

sounder_override = argparse.ArgumentParser(add_help=False)
sounder_override.add_argument(
    "-A",
    "--sounder",
    metavar="sounder",
    dest="sounder",
    choices=[
        "ON",
        "On",
        "on",
        "YES",
        "Yes",
        "yes",
        "OFF",
        "Off",
        "off",
        "NO",
        "No",
        "no",
    ],
    help="'ON' or 'OFF' to indicate whether to use sounder if 'gpio' or `port` is configured.",
)

sounder_pwrsv_override = argparse.ArgumentParser(add_help=False)
sounder_pwrsv_override.add_argument("-P", "--pwrsv", metavar="seconds", dest="sounder_power_save", type=int,
    help="The sounder power-save delay in seconds, or '0' to disable power-save.")

spacing_override = argparse.ArgumentParser(add_help=False)
spacing_override.add_argument("-s", "--spacing", metavar="spacing", dest="spacing",
    help="Where to add spacing for Farnsworth (NONE|CHAR|WORD).")

station_override = argparse.ArgumentParser(add_help=False)
station_override.add_argument("-S", "--station", metavar="station", dest="station",
    help="The Station ID to use (or 'NONE').")

text_speed_override = argparse.ArgumentParser(add_help=False)
text_speed_override.add_argument("-t", "--textspeed", metavar="wpm", dest="text_speed", type=int, \
    help="The morse text speed in words per minute. Used for Farnsworth timing. " +
    "Spacing must not be 'NONE' to enable Farnsworth.")

wire_override = argparse.ArgumentParser(add_help=False)
wire_override.add_argument("-W", "--wire", metavar="wire", dest="wire", type=int,
    help="The Wire to use (or 'NONE').")

# ########################################################################
# Process the results from argparse.ArgumentParser.parse_args.
# ########################################################################
#
def process_config_arg(args) -> Config:
    """
    Process the argparse.ArgumentParser.parse_args result for the --config option.

    Returns: A Config instance that has been loaded from a configuration
    file or from the global store.

    Raises: FileNotFoundError if a config file is specified and it
    doesn't exist.

    """
    cfg = Config()
    if hasattr(args, "pkcfg_filepath"):
        file_path = config.noneOrValueFromStr(args.pkcfg_filepath)
        if file_path:
            file_path = file_path.strip()
            file_path = add_ext_if_needed(file_path)
            if not os.path.isfile(file_path):
                raise FileNotFoundError("Configuration file '{}' does not exist.".format(file_path))
            cfg.load_config(file_path)
            cfg.set_using_global(False)
            return cfg
    #
    cfg.load_from_global()
    cfg.set_using_global(True)
    return cfg

def process_config_args(args, cfg:Config=None) -> Config:
    """
    Process the argparse.ArgumentParser.parse_args results for all of the
    configuration options.

    Return: A Config instance that has been loaded from a configuration file
    or the global store, and then has the specified values applied.

    Raises: Various Exceptions from processing the arguments.
    """
    if not cfg:
        # Get a Config instance to use as a base
        cfg = process_config_arg(args)
    # Set config values if they were specified
    if hasattr(args, "debug_level"):
        if args.debug_level:
            n = args.debug_level
            cfg.debug_level = n if n >= 0 else 0
    if hasattr(args, "audio_type"):
        if args.audio_type:
            cfg.audio_type = config.audio_type_from_str(args.audio_type)
    if hasattr(args, "auto_connect"):
        if args.auto_connect:
            cfg.auto_connect = strtobool(args.auto_connect)
    if hasattr(args, "code_type"):
        if args.code_type:
            cfg.code_type = config.codeTypeFromString(args.code_type)
    if hasattr(args, "interface_type"):
        if args.interface_type:
            cfg.interface_type = config.interface_type_from_str(args.interface_type)
    if hasattr(args, "invert_key_input"):
        if args.invert_key_input:
            cfg.invert_key_input = strtobool(args.invert_key_input)
    if hasattr(args, "min_char_speed"):
        if args.min_char_speed:
            n = args.min_char_speed
            if n < 5:
                n = 5
            elif n > 50:
                n = 50
            cfg.min_char_speed = n
    if hasattr(args, "local"):
        if args.local:
            cfg.local = strtobool(args.local)
    if hasattr(args, "remote"):
        if args.remote:
            cfg.remote = strtobool(args.remote)
    if hasattr(args, "serial_port"):
        if args.serial_port:
            s = config.noneOrValueFromStr(args.serial_port)
            if not s or s.strip().upper() == 'NONE':
                cfg.serial_port = None
            else:
                cfg.serial_port = s.strip()
    if hasattr(args, "gpio"):
        if args.gpio:
            cfg.gpio = strtobool(args.gpio)
    if hasattr(args, "server_url"):
        if args.server_url:
            s = config.noneOrValueFromStr(args.server_url)
            if not s or s.strip().upper() == 'DEFAULT' or s.strip().upper() == 'NONE':
                cfg.server_url = None
            else:
                cfg.server_url = s.strip()
    if hasattr(args, "sound"):
        if args.sound:
            cfg.sound = strtobool(args.sound)
    if hasattr(args, "sounder"):
        if args.sounder:
            cfg.sounder = strtobool(args.sounder)
    if hasattr(args, "sounder_power_save"):
        if args.sounder_power_save:
            n = args.sounder_power_save
            if n < 0:
                n = 0
            cfg.sounder_power_save = n
    if hasattr(args, "spacing"):
        if args.spacing:
            cfg.spacing = config.spacing_from_str(args.spacing)
    if hasattr(args, "station"):
        if args.station:
            s = args.station.strip()
            cfg.station = s
    if hasattr(args, "text_speed"):
        if args.text_speed:
            n = args.text_speed
            if n < 5:
                n = 5
            elif n > 50:
                n = 50
            cfg.text_speed = n
    if hasattr(args, "wire"):
        if args.wire:
            n = args.wire
            if n < 0:
                n = 0
            elif n > 32000:
                n = 32000
            cfg.wire = n
    return cfg


"""
Test code
"""
if __name__ == "__main__":
    # Self-test
    cfg = Config()
    cfg.load_from_global()
    cfg.print_config()
