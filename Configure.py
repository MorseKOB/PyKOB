#! python

"""

Configure.py

Configures system values and user preferences for the suite of PyKOB applications.

Command line parameters:
    -h              : Print help information for using the application
    -port <port>    : Set the system PORT (COM or tty) value to use for a sounder
    -speed <speed>  : Set the user Words-Per-Minute speed preference
    -sound <ON|OFF> : Set the user preference for using/not-using the computer sound

Examples:
    configure -port COM3
    configure -speed 22 -sound ON

"""
import sys
from pykob import config

# System configuration
port = None
# User preferences
sound = None
speed = None

# Check for command line parameters...
#  If none are supplied, print the current configuration
#  If arguments are given, process them against 'help' or the setting values.
nargs = len(sys.argv)
print(f'Argument count is {nargs}. They are:')
for i, arg in enumerate(sys.argv):
    print(f"Argument {i:>6}: {arg}")
config.printInfo()
exit
