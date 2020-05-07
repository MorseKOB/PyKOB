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
config module

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
from pykob import log

# Application name
__APP_NAME = "pykob"
# INI Section
__CONFIG_SECTION = "PYKOB"
# System/Machine INI file Parameters/Keys
__SERIAL_PORT_KEY = "PORT"
# User INI file Parameters/Keys
__SOUND_KEY = "SOUND"
__WPM_SPEED_KEY = "WPM_SPEED"
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
station = None
wire = None
words_per_min_speed = 18

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

def set_wpm_speed(s):
    global words_per_min_speed
    try:
        _speed = int(s)
        words_per_min_speed = _speed
        user_config.set(__CONFIG_SECTION, __WPM_SPEED_KEY, str(words_per_min_speed))
    except ValueError as ex:
        log.err("SPEED value '{}' is not a valid integer value. Not setting value.".format(ex.args[0]))

def set_sound(s):
    global sound
    try:
        _sound = strtobool(str(s))
        if _sound:
            user_config.set(__CONFIG_SECTION, __SOUND_KEY, "ON")
        else:
            user_config.set(__CONFIG_SECTION, __SOUND_KEY, "OFF")
        sound = _sound
    except ValueError as ex:
        log.err("SOUND value '{}' is not a valid boolean value. Not setting value.".format(ex.args[0]))

def set_serial_port(p):
    global serial_port
    serial_port = p
    app_config.set(__CONFIG_SECTION, __SERIAL_PORT_KEY, serial_port)

def set_station(s):
    global station
    station = s
    user_config.set(__CONFIG_SECTION, __STATION_KEY, station)

def set_wire(w):
    global wire
    wire = w
    user_config.set(__CONFIG_SECTION, __WIRE_KEY, wire)

def print_info():
    print_system_info()
    print_config()

def print_system_info():
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
    print("======================================")
    print("Serial serial_port: '{}'".format(serial_port))
    print("--------------------------------------")
    soundPrint = "OFF"
    if sound:
        soundPrint = "ON"
    print("Sound:", soundPrint)
    print("Station:", station)
    print("Wire:", wire)
    print("Words per Min Speed:", words_per_min_speed)

'''
Save (write) the configuration values out to the user and machine config files.
'''
def save_config():
    create_config_files_if_needed()
    with open(user_config_file_path, 'w') as configfile:
        user_config.write(configfile, space_around_delimiters=False)
    with open(app_config_file_path, 'w') as configfile:
        app_config.write(configfile, space_around_delimiters=False)


def read_config():
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
    global sound
    global station
    global wire
    global words_per_min_speed
    #
    global serial_port_override
    global sound_override
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

    userConfigDefaults = {__WPM_SPEED_KEY:"18", __SOUND_KEY:"ON"}
    app_configDefaults = {"PORT":""}

    user_config = configparser.ConfigParser(defaults=userConfigDefaults, allow_no_value=True, default_section=__CONFIG_SECTION)
    app_config = configparser.ConfigParser(defaults=app_configDefaults, allow_no_value=True, default_section=__CONFIG_SECTION)

    user_config.read(user_config_file_path)
    app_config.read(app_config_file_path)

    try:
        # Get the System (App) config values
        serial_port = app_config.get(__CONFIG_SECTION, __SERIAL_PORT_KEY)
        # If there isn't a PORT value set PORT to None
        if not serial_port:
            serial_port = None

        # Get the User config values
        sound = user_config.getboolean(__CONFIG_SECTION, __SOUND_KEY)
        words_per_min_speed = user_config.getint(__CONFIG_SECTION, __WPM_SPEED_KEY)
    except KeyError as ex:
        log.err("Key '{}' not found in configuration file.".format(ex.args[0]))
    except ValueError as ex:
        log.err("SPEED value '{}' is not a valid integer value. Setting to 18.".format(ex.args[0]))
        words_per_min_speed = 18

# ### Mainline
read_config()

serial_port_override = argparse.ArgumentParser(add_help=False)
serial_port_override.add_argument("-p", "--port", default=serial_port, help="The  name of the serial port to use ", metavar="portname", dest="serial_port")

sound_override = argparse.ArgumentParser(add_help=False)
sound_override.add_argument("-a", "--sound", default="ON" if sound else "OFF", choices=["ON", "OFF"], help="'ON' or 'OFF' to indicate whether morse audio should be generated", metavar="sound", dest="sound")

wpm_override = argparse.ArgumentParser(add_help=False)
wpm_override.add_argument("-s", "--speed", default=words_per_min_speed, type=int, help="The  morse send speed in WPM", metavar="speed", dest="words_per_min_speed")

exit
