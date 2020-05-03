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
An example of a 'per-user' value is the code speed (WPM).

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

The files are INI format with the values in a section named 'PYKOB'.

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
appName = 'pykob'
# INI Section
configSection = 'PYKOB'

# Paths and Configurations
appConfigDir = None
appConfigFilePath = None
appConfig = None
userConfigDir = None
userConfigFilePath = None
userConfig = None

# System information
hostname = None
osName = None
platformName= None
systemName = None
systemVersion = None
userHome = None
userName = None

# Settings
Speed = 20
Sound = True
Port = None

def createConfigFilesIfNeeded():
    global appConfigDir
    global appConfigFilePath
    global userConfigDir
    global userConfigFilePath

    # Create the files if they don't exist
    if not os.path.isfile(userConfigFilePath):
        # need to create
        userConfigDir = os.path.split(userConfigFilePath)[0]
        if not os.path.isdir(userConfigDir):
            os.makedirs(userConfigDir)
        f = open(userConfigFilePath, 'w')
        f.close()
    if not os.path.isfile(appConfigFilePath):
        # need to create
        appConfigDir = os.path.split(appConfigFilePath)[0]
        if not os.path.isdir(appConfigDir):
            os.makedirs(appConfigDir)
        f = open(appConfigFilePath, 'w')
        f.close()

def setSpeed(speed):
    global Speed
    try:
        _speed = int(speed)
        Speed = _speed
        userConfig.set(configSection, 'SPEED', str(Speed))
    except ValueError as ex:
        log.err("SPEED value '{}' is not a valid integer value. Not setting value.".format(ex.args[0]))

def setSound(sound):
    global Sound
    try:
        _sound = strtobool(str(sound))
        if _sound:
            userConfig.set(configSection, 'SOUND', 'ON')
        else:
            userConfig.set(configSection, 'SOUND', 'OFF')
        Sound = _sound
    except ValueError as ex:
        log.err("SOUND value '{}' is not a valid boolean value. Not setting value.".format(ex.args[0]))

def setPort(port):
    global Port
    Port = port
    appConfig.set(configSection, 'PORT', Port)

def printInfo():
    printSystemInfo()
    printConfig()

def printSystemInfo():
    print("User:", userName)
    print("User Home Path:", userHome)
    print("User Configuration File:", userConfigFilePath)
    print("App Configuration File", appConfigFilePath)
    print("OS:", osName)
    print("System:", systemName)
    print("Version:", systemVersion)
    print("Platform", platformName)
    print("Host:", hostname)

def printConfig():
    print("======================================")
    print("Port: '{}'".format(Port))
    print("--------------------------------------")
    soundPrint = 'OFF'
    if Sound:
        soundPrint = 'ON'
    print("Sound:", soundPrint)
    print("Speed:", Speed)

'''
Save (write) the configuration values out to the user and machine config files.
'''
def saveConfig():
    createConfigFilesIfNeeded()
    with open(userConfigFilePath, 'w') as configfile:
        userConfig.write(configfile, space_around_delimiters=False)
    with open(appConfigFilePath, 'w') as configfile:
        appConfig.write(configfile, space_around_delimiters=False)


def readConfig():
    global hostname
    global platformName
    global osName
    global systemName
    global systemVersion
    global appConfig
    global appConfigFilePath
    global userConfig
    global userConfigFilePath
    global userHome
    global userName
    #
    global Port
    global Sound
    global Speed
    global PortOverride
    global SoundtOverride
    global WPMOverride

    # Get the system data
    try:
        userName = getpass.getuser()
        userHome = os.path.expanduser('~')
        osName = os.name
        systemName = platform.system()
        systemVersion = platform.release()
        platformName = sys.platform
        hostname = socket.gethostname()

        # User configuration file name
        userConfigFileName = f'config-{userName}.ini'
        appConfigFileName = 'config_app.ini'

        # Create the user and application configuration paths
        if systemName == 'Windows':
            userConfigFilePath = os.path.join(os.environ['LOCALAPPDATA'], os.path.normcase(os.path.join(appName, userConfigFileName)))
            appConfigFilePath = os.path.join(os.environ['ProgramData'], os.path.normcase(os.path.join(appName, appConfigFileName)))
        elif systemName == 'Linux' or systemName == 'Darwin': # Linux or Mac
            userConfigFilePath = os.path.join(userHome, os.path.normcase(os.path.join(f'.{appName}', userConfigFileName)))
            appConfigFilePath = os.path.join(userHome, os.path.normcase(os.path.join(f'.{appName}', appConfigFileName)))
        else:
            log.err('Unknown System name')
            exit

    except KeyError as ex:
        log.err("Key '{}' not found in environment.".format(ex.args[0]))
        exit

    createConfigFilesIfNeeded()

    userConfigDefaults = {'SPEED':'18', 'SOUND':'ON'}
    appConfigDefaults = {'PORT':''}

    userConfig = configparser.ConfigParser(defaults=userConfigDefaults, allow_no_value=True, default_section='PYKOB')
    appConfig = configparser.ConfigParser(defaults=appConfigDefaults, allow_no_value=True, default_section='PYKOB')

    userConfig.read(userConfigFilePath)
    appConfig.read(appConfigFilePath)

    try:
        # Get the System (App) config values
        Port = appConfig.get(configSection, 'PORT')
        # If there isn't a PORT value set PORT to None
        if not Port:
            Port = None

        # Get the User config values
        Sound = userConfig.get(configSection, 'SOUND')
        Speed = userConfig.getint(configSection, 'SPEED')
    except KeyError as ex:
        log.err("Key '{}' not found in configuration file.".format(ex.args[0]))
    except ValueError as ex:
        log.err("SPEED value '{}' is not a valid integer value. Setting to 18.".format(ex.args[0]))
        Speed = 18

# ### Mainline
readConfig()

PortOverride = argparse.ArgumentParser(add_help=False)
PortOverride.add_argument("-p", "--port", default=Port, help="The  name of the serial port to use ", metavar="portname", dest="Port")

SoundtOverride = argparse.ArgumentParser(add_help=False)
SoundtOverride.add_argument("-a", "--sound", default=Sound, choices=['ON', 'OFF'], help="'ON' or 'OFF' to indicate whether morse audio should be generated", metavar="sound", dest="Sound")

WPMOverride = argparse.ArgumentParser(add_help=False)
WPMOverride.add_argument("-s", "--speed", default=Speed, type=int, help="The  morse send speed in WPM", metavar="speed", dest="Speed")

exit
