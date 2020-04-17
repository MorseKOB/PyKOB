""" 
config module

Reads configuration information for `per-machine` and `per-user` values.  

An example of a `per-machine` value is the KOB serial/com port (PORT).  
An example of a 'per-user' value is the code speed (WPM).

Configuration/preference values are read/written to:
 Windows:
  User: [user]\AppData\Roaming\pykob\pyconfig-[user].ini
  Machine: \ProgramData\pykob\pyconfig-machine.ini
 Mac:
  User: 
  Machine: 
 Linux:
  User: ~/
  Machine: 

"""

import configparser
import getpass
import os
import platform
import socket
import sys
from pykob import log

log.log("config initializing")

# Get the system data
username = getpass.getuser()
userHome = os.path.expanduser('~')
osName = os.name
systemName = platform.system()
systemVersion = platform.release()
platform = sys.platform
hostname = socket.gethostname()

# Create the user and application configuration paths
userConfigFile = os.path.join(os.environ['LOCALAPPDATA'], os.path.normcase('pykob/config-' + username))
appConfigFile = os.path.join(os.environ['ProgramData'], os.path.normcase('pykob/config-app'))

# Create the files if they don't exist
if not os.path.isfile(userConfigFile):
    # need to create
    userConfigDir = os.path.split(userConfigFile)[0]
    if not os.path.isdir(userConfigDir):
        os.makedirs(userConfigDir)
    f = open(userConfigFile, 'w')
    f.close()
if not os.path.isfile(appConfigFile):
    # need to create
    appConfigDir = os.path.split(appConfigFile)[0]
    if not os.path.isdir(appConfigDir):
        os.makedirs(appConfigDir)
    f = open(appConfigFile, 'w')
    f.close()

__userConfigDefaults = {'SPEED':20, 'AUDIO':'True'}
__appConfigDefaults = {'PORT':''}

__userConfig = configparser.ConfigParser(defaults=__userConfigDefaults)
__appConfig = configparser.ConfigParser(defaults=__appConfigDefaults)

__userConfig.read(userConfigFile)
__appConfig.read(appConfigFile)

# Get the System (App) config values
__appConfigDefault = __appConfig['DEFAULT']
Port = __appConfigDefault['PORT']
# If there isn't a PORT value set PORT to None
if not Port:
    Port = None

# Get the User config values
__userConfigDefault = __userConfig['DEFAULT']
Audio = __userConfigDefault.getboolean('AUDIO')
Speed = __userConfigDefault.getint('SPEED')

def printInfo():
    print("User:", username)
    print("User home path", userHome)
    print("User configuration file:", userConfigFile)
    print("App configuration file", appConfigFile)
    print("OS:", osName)
    print("System:", systemName)
    print("Version:", systemVersion)
    print("Platform", platform)
    print("Host:", hostname)
    print("======================================")
    print("Port:", Port)
    print("--------------------------------------")
    print("Audio", Audio)
    print("Speed:", Speed)

