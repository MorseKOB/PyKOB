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

import configparser
import distutils
import getpass
import os
import platform
import socket
import sys
from distutils.util import strtobool
from pykob import log

log.log("config initializing")

Speed = 20
Sound = True
Port = None

def createConfigFilesIfNeeded():
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
        __userConfig.set(configSection, 'SPEED', str(Speed))
        Speed = _speed
    except ValueError as ex:
        log.err(f"SPEED value '{ex.args[0]}' is not a valid integer value. Not setting value.")

def setSound(sound):
    global Sound
    try:
        _sound = strtobool(str(sound))
        if _sound:
            __userConfig.set(configSection, 'SOUND', 'ON')
        else:
            __userConfig.set(configSection, 'SOUND', 'OFF')
        Sound = _sound
    except ValueError as ex:
        log.err(f"SOUND value '{ex.args[0]}' is not a valid boolean value. Not setting value.")

def setPort(port):
    global Port
    Port = port
    __appConfig.set(configSection, 'PORT', Port)

def printInfo():
    print("User:", username)
    print("User home path", userHome)
    print("User configuration file:", userConfigFilePath)
    print("App configuration file", appConfigFilePath)
    print("OS:", osName)
    print("System:", systemName)
    print("Version:", systemVersion)
    print("Platform", platform)
    print("Host:", hostname)
    print("======================================")
    print("Port:", Port)
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
    with open(userConfigFilePath, 'w') as __configfile:
        __userConfig.write(__configfile, space_around_delimiters=False)
    with open(appConfigFilePath, 'w') as __configfile:
        __appConfig.write(__configfile, space_around_delimiters=False)


# ### Mainline

# Get the system data
try:
    username = getpass.getuser()
    userHome = os.path.expanduser('~')
    osName = os.name
    systemName = platform.system()
    systemVersion = platform.release()
    platform = sys.platform
    hostname = socket.gethostname()
    log.log(f'systemName={systemName}')

    # Application name
    appName = 'pykob'
    # INI Section
    configSection = 'PYKOB'

    # User configuration file name
    userConfigFileName = f'config-{username}.ini'
    appConfigFileName = 'config_app.ini'

    # Create the user and application configuration paths
    if systemName == 'Windows':
        userConfigFilePath = os.path.join(os.environ['LOCALAPPDATA'], os.path.normcase(os.path.join(appName, userConfigFileName)))
        appConfigFilePath = os.path.join(os.environ['ProgramData'], os.path.normcase(os.path.join(appName, appConfigFileName)))
    elif systemName == 'Linux':
        userConfigFilePath = os.path.join(userHome, os.path.normcase(os.path.join(f'.{appName}', userConfigFileName)))
        appConfigFilePath = os.path.join(userHome, os.path.normcase(os.path.join(f'.{appName}', appConfigFileName)))
    else:
        log.err('Unknown System name')
        exit

except KeyError as ex:
    log.err(f"Key '{ex.args[0]}' not found in environment.")
    exit

createConfigFilesIfNeeded()

__userConfigDefaults = {'SPEED':'20', 'SOUND':'ON'}
__appConfigDefaults = {'PORT':''}

__userConfig = configparser.ConfigParser(defaults=__userConfigDefaults, allow_no_value=True, default_section='PYKOB')
__appConfig = configparser.ConfigParser(defaults=__appConfigDefaults, allow_no_value=True, default_section='PYKOB')

__userConfig.read(userConfigFilePath)
__appConfig.read(appConfigFilePath)

try:
    # Get the System (App) config values
    Port = __appConfig.get(configSection, 'PORT')
    # If there isn't a PORT value set PORT to None
    if not Port:
        Port = None

    # Get the User config values
    Sound = __userConfig.getboolean(configSection, 'SOUND')
    Speed = __userConfig.getint(configSection, 'SPEED')
except KeyError as ex:
    log.err(f"Key '{ex.args[0]}' not found in configuration file.")
except ValueError as ex:
    log.err(f"SPEED value '{ex.args[0]}' is not a valid integer value. Setting to 20.")
    Speed = 20
